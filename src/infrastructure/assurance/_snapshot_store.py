"""SQLCipher/SQLite adapter for the security signal-snapshot aggregate.

Snapshots are keyed by the STABLE (slug-free) anchor id: every anchor crossing
this boundary — read or write — goes through ``anchor_key``. Callers legitimately
hold either id form (the GUI navigates by the full slugged id, scripts use the
short one), and SQL matches anchors by exact equality, so without normalization a
snapshot written under one form would be invisible to a reader using the other.

Every mutating method is ONE explicit transaction that also lands its
hash-chained audit row (``append_audit_row``) — the audited-mutation
durability invariant: no accepted signal mutation exists without its audit
record committed in the same unit of work. Activation supersedes the previous
active snapshot and activates the target in that same transaction; the partial
unique index on (anchor, status='active') backs it with a database constraint.

Serialization across callers is the transport adapter's job (the existing
write queue); this adapter owns atomicity, not scheduling.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Callable, Mapping, Sequence

from src.domain.clock import utc_now_iso as _now_iso
from src.domain.security_signal_snapshot import (
    SnapshotPopulation,
    anchor_key,
    is_allowed_transition,
    transition_error,
)
from src.domain.signals_schema import SIGNALS_PRAGMAS_SQL
from src.domain.vulnerability_identity import (
    normalize_external_id,
)
from src.infrastructure.assurance._archive import append_audit_row
from src.infrastructure.assurance._signals_migrations import apply_signals_migrations
from src.infrastructure.assurance._snapshot_deletion_ops import (
    delete_all_for_anchor,
    delete_one_snapshot,
)
from src.infrastructure.assurance._vulnerability_impact_ops import (
    list_active_findings_for_vulnerability,
    list_aliases_for_canonical,
    resolve_canonical_id,
)
from src.infrastructure.assurance._vulnerability_resolution import (
    resolve_canonical_vulnerability,
)


class SnapshotTransitionError(RuntimeError):
    """A lifecycle transition the domain table forbids."""


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]
    return f"{prefix}@{digest}"


class SQLCipherSnapshotStore:
    """Works over any DB-API connection factory returning a row-dict connection
    (co-located SQLCipher in production; plain SQLite in the deprecated public
    backend's migration tests)."""

    def __init__(self, conn_factory: Callable[[], Any]) -> None:
        self._conn_factory = conn_factory

    def _conn(self) -> Any:
        conn = self._conn_factory()
        if conn is None:
            raise RuntimeError("Assurance store is locked — cannot access signal snapshots.")
        conn.executescript(SIGNALS_PRAGMAS_SQL)
        apply_signals_migrations(conn)
        return conn

    def _begin(self, conn: Any) -> None:
        try:
            conn.execute("BEGIN IMMEDIATE")
        except Exception:  # noqa: BLE001 — an implicit transaction is already open
            pass

    # ── Reads ─────────────────────────────────────────────────────────────────

    def find_snapshot_by_request(self, anchor_entity_id: str, request_id: str) -> dict[str, Any] | None:
        conn = self._conn()
        return conn.execute(
            "SELECT * FROM security_signal_snapshots WHERE anchor_entity_id=? AND request_id=?",
            (anchor_key(anchor_entity_id), request_id),
        ).fetchone()

    def get_snapshot(self, snapshot_id: str) -> dict[str, Any] | None:
        conn = self._conn()
        return conn.execute(
            "SELECT * FROM security_signal_snapshots WHERE snapshot_id=?", (snapshot_id,)
        ).fetchone()

    def get_active_snapshot(self, anchor_entity_id: str) -> dict[str, Any] | None:
        conn = self._conn()
        return conn.execute(
            "SELECT * FROM security_signal_snapshots WHERE anchor_entity_id=? AND status='active'",
            (anchor_key(anchor_entity_id),),
        ).fetchone()

    def list_snapshots(self, *, anchor_entity_id: str | None = None) -> list[dict[str, Any]]:
        conn = self._conn()
        if anchor_entity_id:
            return conn.execute(
                "SELECT * FROM security_signal_snapshots WHERE anchor_entity_id=? ORDER BY started_at DESC",
                (anchor_key(anchor_entity_id),),
            ).fetchall()
        return conn.execute(
            "SELECT * FROM security_signal_snapshots ORDER BY started_at DESC"
        ).fetchall()

    def list_snapshot_components(self, snapshot_id: str) -> list[dict[str, Any]]:
        conn = self._conn()
        return conn.execute(
            "SELECT * FROM snapshot_components WHERE snapshot_id=? ORDER BY component_id", (snapshot_id,)
        ).fetchall()

    def list_snapshot_findings(self, snapshot_id: str) -> list[dict[str, Any]]:
        conn = self._conn()
        return conn.execute(
            "SELECT * FROM snapshot_vulnerability_findings WHERE snapshot_id=? ORDER BY finding_id",
            (snapshot_id,),
        ).fetchall()

    # ── Lifecycle mutations (each: one transaction incl. audit) ───────────────

    def create_staging_snapshot(
        self,
        *,
        snapshot_id: str,
        anchor_entity_id: str,
        request_id: str,
        request_payload_digest: str,
        bom_digest: str = "",
        bom_serial: str = "",
        bom_version: str = "",
        generator_metadata: Mapping[str, object] | None = None,
        source_metadata: Mapping[str, object] | None = None,
        diagnostics: Mapping[str, object] | None = None,
    ) -> None:
        conn = self._conn()
        self._begin(conn)
        try:
            conn.execute(
                "INSERT INTO security_signal_snapshots "
                "(snapshot_id, anchor_entity_id, request_id, request_payload_digest, bom_digest, "
                "bom_serial, bom_version, generator_metadata, source_metadata, diagnostics, "
                "status, started_at) VALUES (?,?,?,?,?,?,?,?,?,?,'staging',?)",
                (snapshot_id, anchor_key(anchor_entity_id), request_id, request_payload_digest, bom_digest,
                 bom_serial, bom_version, json.dumps(dict(generator_metadata or {})),
                 json.dumps(dict(source_metadata or {})), json.dumps(dict(diagnostics or {})),
                 _now_iso()),
            )
            append_audit_row(conn, "SIGNAL_SNAPSHOT_STARTED", payload={
                "snapshot_id": snapshot_id, "anchor_entity_id": anchor_key(anchor_entity_id),
                "request_id": request_id,
            })
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def populate_snapshot(
        self,
        snapshot_id: str,
        *,
        components: Sequence[Mapping[str, object]],
        findings: Sequence[Mapping[str, object]],
    ) -> SnapshotPopulation:
        """Insert components and findings under a staging snapshot; vulnerability
        alias sets in the findings resolve to canonical ids (creating or merging
        groups) inside the SAME transaction.

        Returns the canonical-id mapping together with submitted-vs-persisted
        counts. The row-id sets below are the exact persisted counts — every write
        is ``INSERT OR REPLACE`` on a deterministic id, so the number of distinct
        ids written IS the number of rows the snapshot ends up holding. Counting
        them costs one set insert per row and saves a post-commit ``COUNT(*)``.
        """
        conn = self._conn()
        self._require_status(conn, snapshot_id, {"staging"}, "populate")
        self._begin(conn)
        canonical_by_ext: dict[str, str] = {}
        component_row_ids: set[str] = set()
        finding_row_ids: set[str] = set()
        try:
            for comp in components:
                # Row identity is SNAPSHOT-SCOPED: two snapshots sharing a
                # caller-side component id must never overwrite each other's rows
                # (the superseded snapshot's history would cascade away with them).
                source_component_id = str(comp["component_id"])
                row_id = _stable_id("SCM", snapshot_id, source_component_id)
                component_row_ids.add(row_id)
                conn.execute(
                    "INSERT OR REPLACE INTO snapshot_components "
                    "(component_id, snapshot_id, source_component_id, bom_ref, purl, cpe, name, "
                    "version, component_type, group_name, directness) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (row_id, snapshot_id, source_component_id, str(comp.get("bom_ref") or ""),
                     str(comp.get("purl") or ""), str(comp.get("cpe") or ""),
                     str(comp.get("name") or ""), str(comp.get("version") or ""),
                     str(comp.get("component_type") or "library"),
                     str(comp.get("group_name") or ""),
                     str(comp.get("directness") or "unknown")),
                )
            for finding in findings:
                raw_ids = finding.get("external_ids") or []
                external_ids = [str(x) for x in raw_ids] if isinstance(raw_ids, (list, tuple)) else []
                canonical_id = self._resolve_canonical(conn, external_ids)
                if external_ids:
                    canonical_by_ext[normalize_external_id(external_ids[0])] = canonical_id
                component_row_id = _stable_id("SCM", snapshot_id, str(finding["component_id"]))
                finding_id = _stable_id("FND", snapshot_id, component_row_id, canonical_id)
                finding_row_ids.add(finding_id)
                conn.execute(
                    "INSERT OR REPLACE INTO snapshot_vulnerability_findings "
                    "(finding_id, snapshot_id, component_id, canonical_vulnerability_id, "
                    "severity_band, cvss_score, cvss_vector, severity_source, "
                    "applicability, provenance) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (finding_id, snapshot_id, component_row_id, canonical_id,
                     finding.get("severity_band"), finding.get("cvss_score"),
                     finding.get("cvss_vector"), finding.get("severity_source"),
                     str(finding.get("applicability") or "applicable"),
                     json.dumps(finding.get("provenance") or {})),
                )
            # The audit row records BOTH counts: an auditor reading only the
            # submitted number could not tell an alias collapse from lost writes.
            append_audit_row(conn, "SIGNAL_SNAPSHOT_POPULATED", payload={
                "snapshot_id": snapshot_id,
                "submitted_component_count": len(components),
                "persisted_component_count": len(component_row_ids),
                "submitted_finding_count": len(findings),
                "persisted_finding_count": len(finding_row_ids),
            })
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        return SnapshotPopulation(
            canonical_by_external_id=canonical_by_ext,
            submitted_component_count=len(components),
            persisted_component_count=len(component_row_ids),
            submitted_finding_count=len(findings),
            persisted_finding_count=len(finding_row_ids),
        )

    def complete_snapshot(self, snapshot_id: str) -> None:
        self._transition(snapshot_id, "complete", "SIGNAL_SNAPSHOT_COMPLETED", "completed_at")

    def fail_snapshot(self, snapshot_id: str, *, reason: str) -> None:
        conn = self._conn()
        self._require_status(conn, snapshot_id, {"staging"}, "fail")
        self._begin(conn)
        try:
            conn.execute(
                "UPDATE security_signal_snapshots SET status='failed', failed_at=?, failure_reason=? "
                "WHERE snapshot_id=?",
                (_now_iso(), reason, snapshot_id),
            )
            append_audit_row(conn, "SIGNAL_SNAPSHOT_FAILED", payload={"snapshot_id": snapshot_id, "reason": reason})
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    # ── Reverse lookup: one vulnerability → the anchors it affects ────────────

    def resolve_canonical_id(self, identifier: str) -> str | None:
        return resolve_canonical_id(self, identifier)

    def list_active_findings_for_vulnerability(self, canonical_id: str) -> list[dict[str, Any]]:
        return list_active_findings_for_vulnerability(self, canonical_id)

    def list_aliases_for_canonical(self, canonical_id: str) -> list[str]:
        return list_aliases_for_canonical(self, canonical_id)

    def delete_snapshot(self, snapshot_id: str) -> dict[str, Any] | None:
        """Delete one snapshot and its owned rows; None if absent. Blast radius is
        documented and tested in ``_snapshot_deletion_ops``."""
        return delete_one_snapshot(self, snapshot_id)

    def delete_anchor_snapshots(self, anchor_entity_id: str) -> list[dict[str, Any]]:
        """Delete every snapshot for one anchor, each its own audited transaction."""
        return delete_all_for_anchor(self, anchor_entity_id)

    def activate_snapshot(self, snapshot_id: str) -> dict[str, Any]:
        """Supersede the anchor's current active snapshot and activate the target in
        ONE transaction. Re-activating an already-active snapshot is a no-op success."""
        conn = self._conn()
        snapshot = self.get_snapshot(snapshot_id)
        if snapshot is None:
            raise SnapshotTransitionError(f"unknown snapshot {snapshot_id!r}")
        if snapshot["status"] == "active":
            return {"snapshot_id": snapshot_id, "activated": False, "already_active": True}
        if not is_allowed_transition(str(snapshot["status"]), "active"):
            raise SnapshotTransitionError(transition_error(str(snapshot["status"]), "active"))
        now = _now_iso()
        self._begin(conn)
        try:
            previous = conn.execute(
                "SELECT snapshot_id FROM security_signal_snapshots WHERE anchor_entity_id=? AND status='active'",
                (snapshot["anchor_entity_id"],),
            ).fetchone()
            if previous is not None:
                conn.execute(
                    "UPDATE security_signal_snapshots SET status='superseded', superseded_at=? WHERE snapshot_id=?",
                    (now, previous["snapshot_id"]),
                )
            conn.execute(
                "UPDATE security_signal_snapshots SET status='active', activated_at=? WHERE snapshot_id=?",
                (now, snapshot_id),
            )
            append_audit_row(conn, "SIGNAL_SNAPSHOT_ACTIVATED", payload={
                "snapshot_id": snapshot_id, "anchor_entity_id": snapshot["anchor_entity_id"],
                "superseded_snapshot_id": previous["snapshot_id"] if previous else None,
            })
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        return {
            "snapshot_id": snapshot_id, "activated": True,
            "superseded_snapshot_id": previous["snapshot_id"] if previous else None,
        }

    def fail_stale_staging(self, *, started_before_iso: str) -> list[str]:
        """Mark staging snapshots older than the cutoff failed (stale recovery);
        never auto-activates anything."""
        conn = self._conn()
        stale = [
            row["snapshot_id"] for row in conn.execute(
                "SELECT snapshot_id FROM security_signal_snapshots WHERE status='staging' AND started_at < ?",
                (started_before_iso,),
            ).fetchall()
        ]
        for snapshot_id in stale:
            self.fail_snapshot(snapshot_id, reason=f"stale staging snapshot (started before {started_before_iso})")
        return stale

    # ── Internals ─────────────────────────────────────────────────────────────

    def _transition(self, snapshot_id: str, target: str, audit_op: str, timestamp_field: str) -> None:
        conn = self._conn()
        snapshot = self.get_snapshot(snapshot_id)
        if snapshot is None:
            raise SnapshotTransitionError(f"unknown snapshot {snapshot_id!r}")
        if not is_allowed_transition(str(snapshot["status"]), target):
            raise SnapshotTransitionError(transition_error(str(snapshot["status"]), target))
        self._begin(conn)
        try:
            conn.execute(
                f"UPDATE security_signal_snapshots SET status=?, {timestamp_field}=? WHERE snapshot_id=?",  # noqa: S608
                (target, _now_iso(), snapshot_id),
            )
            append_audit_row(conn, audit_op, payload={"snapshot_id": snapshot_id})
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def _require_status(self, conn: Any, snapshot_id: str, allowed: set[str], action: str) -> None:
        snapshot = conn.execute(
            "SELECT status FROM security_signal_snapshots WHERE snapshot_id=?", (snapshot_id,)
        ).fetchone()
        if snapshot is None:
            raise SnapshotTransitionError(f"unknown snapshot {snapshot_id!r}")
        if str(snapshot["status"]) not in allowed:
            raise SnapshotTransitionError(
                f"cannot {action} snapshot in status {snapshot['status']!r} (needs {sorted(allowed)})"
            )

    def _resolve_canonical(self, conn: Any, external_ids: list[str]) -> str:
        return resolve_canonical_vulnerability(conn, external_ids, stable_id=_stable_id)
