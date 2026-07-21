"""SQLCipher/SQLite adapter for the security refresh-run aggregate.

Every mutating method is ONE explicit transaction that also lands its
hash-chained audit row (``append_audit_row``) — the audited-mutation
durability invariant: no accepted signal mutation exists without its audit
record committed in the same unit of work. Activation supersedes the previous
active run and activates the target in that same transaction; the partial
unique index on (anchor, status='active') backs it with a database constraint.

Serialization across callers is the transport adapter's job (the existing
write queue); this adapter owns atomicity, not scheduling.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Callable, Mapping, Sequence

from src.domain.clock import utc_now_iso as _now_iso
from src.domain.security_refresh_run import is_allowed_transition, transition_error
from src.domain.signals_schema import SIGNALS_PRAGMAS_SQL
from src.domain.vulnerability_identity import (
    CreateCanonical,
    MergeCanonical,
    UseExisting,
    normalize_external_id,
    resolve_aliases,
)
from src.infrastructure.assurance._archive import append_audit_row
from src.infrastructure.assurance._signals_migrations import apply_signals_migrations


class RefreshRunTransitionError(RuntimeError):
    """A lifecycle transition the domain table forbids."""


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]
    return f"{prefix}@{digest}"


class SQLCipherRefreshRunStore:
    """Works over any DB-API connection factory returning a row-dict connection
    (co-located SQLCipher in production; plain SQLite in the deprecated public
    backend's migration tests)."""

    def __init__(self, conn_factory: Callable[[], Any]) -> None:
        self._conn_factory = conn_factory

    def _conn(self) -> Any:
        conn = self._conn_factory()
        if conn is None:
            raise RuntimeError("Assurance store is locked — cannot access refresh runs.")
        conn.executescript(SIGNALS_PRAGMAS_SQL)
        apply_signals_migrations(conn)
        return conn

    def _begin(self, conn: Any) -> None:
        try:
            conn.execute("BEGIN IMMEDIATE")
        except Exception:  # noqa: BLE001 — an implicit transaction is already open
            pass

    # ── Reads ─────────────────────────────────────────────────────────────────

    def find_run_by_request(self, anchor_entity_id: str, request_id: str) -> dict[str, Any] | None:
        conn = self._conn()
        return conn.execute(
            "SELECT * FROM security_refresh_runs WHERE anchor_entity_id=? AND request_id=?",
            (anchor_entity_id, request_id),
        ).fetchone()

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        conn = self._conn()
        return conn.execute(
            "SELECT * FROM security_refresh_runs WHERE run_id=?", (run_id,)
        ).fetchone()

    def get_active_run(self, anchor_entity_id: str) -> dict[str, Any] | None:
        conn = self._conn()
        return conn.execute(
            "SELECT * FROM security_refresh_runs WHERE anchor_entity_id=? AND status='active'",
            (anchor_entity_id,),
        ).fetchone()

    def list_runs(self, *, anchor_entity_id: str | None = None) -> list[dict[str, Any]]:
        conn = self._conn()
        if anchor_entity_id:
            return conn.execute(
                "SELECT * FROM security_refresh_runs WHERE anchor_entity_id=? ORDER BY started_at DESC",
                (anchor_entity_id,),
            ).fetchall()
        return conn.execute(
            "SELECT * FROM security_refresh_runs ORDER BY started_at DESC"
        ).fetchall()

    def list_run_components(self, run_id: str) -> list[dict[str, Any]]:
        conn = self._conn()
        return conn.execute(
            "SELECT * FROM run_components WHERE run_id=? ORDER BY component_id", (run_id,)
        ).fetchall()

    def list_run_findings(self, run_id: str) -> list[dict[str, Any]]:
        conn = self._conn()
        return conn.execute(
            "SELECT * FROM run_vulnerability_findings WHERE run_id=? ORDER BY finding_id",
            (run_id,),
        ).fetchall()

    # ── Lifecycle mutations (each: one transaction incl. audit) ───────────────

    def create_staging_run(
        self,
        *,
        run_id: str,
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
                "INSERT INTO security_refresh_runs "
                "(run_id, anchor_entity_id, request_id, request_payload_digest, bom_digest, "
                "bom_serial, bom_version, generator_metadata, source_metadata, diagnostics, "
                "status, started_at) VALUES (?,?,?,?,?,?,?,?,?,?,'staging',?)",
                (run_id, anchor_entity_id, request_id, request_payload_digest, bom_digest,
                 bom_serial, bom_version, json.dumps(dict(generator_metadata or {})),
                 json.dumps(dict(source_metadata or {})), json.dumps(dict(diagnostics or {})),
                 _now_iso()),
            )
            append_audit_row(conn, "REFRESH_RUN_STARTED", payload={
                "run_id": run_id, "anchor_entity_id": anchor_entity_id,
                "request_id": request_id,
            })
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def populate_run(
        self,
        run_id: str,
        *,
        components: Sequence[Mapping[str, object]],
        findings: Sequence[Mapping[str, object]],
    ) -> dict[str, str]:
        """Insert components and findings under a staging run; vulnerability
        alias sets in the findings resolve to canonical ids (creating or
        merging groups) inside the SAME transaction. Returns the mapping from
        each finding's primary external id to its canonical id."""
        conn = self._conn()
        self._require_status(conn, run_id, {"staging"}, "populate")
        self._begin(conn)
        canonical_by_ext: dict[str, str] = {}
        try:
            for comp in components:
                # Row identity is RUN-SCOPED: two runs sharing a caller-side
                # component id must never overwrite each other's rows (the
                # superseded run's history would cascade away with them).
                source_component_id = str(comp["component_id"])
                row_id = _stable_id("RCM", run_id, source_component_id)
                conn.execute(
                    "INSERT OR REPLACE INTO run_components "
                    "(component_id, run_id, source_component_id, bom_ref, purl, cpe, name, "
                    "version, component_type, group_name, directness) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (row_id, run_id, source_component_id, str(comp.get("bom_ref") or ""),
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
                component_row_id = _stable_id("RCM", run_id, str(finding["component_id"]))
                finding_id = _stable_id("FND", run_id, component_row_id, canonical_id)
                conn.execute(
                    "INSERT OR REPLACE INTO run_vulnerability_findings "
                    "(finding_id, run_id, component_id, canonical_vulnerability_id, "
                    "severity_band, cvss_score, cvss_vector, severity_source, "
                    "applicability, provenance) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (finding_id, run_id, component_row_id, canonical_id,
                     finding.get("severity_band"), finding.get("cvss_score"),
                     finding.get("cvss_vector"), finding.get("severity_source"),
                     str(finding.get("applicability") or "applicable"),
                     json.dumps(finding.get("provenance") or {})),
                )
            append_audit_row(conn, "REFRESH_RUN_POPULATED", payload={
                "run_id": run_id, "component_count": len(components),
                "finding_count": len(findings),
            })
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        return canonical_by_ext

    def complete_run(self, run_id: str) -> None:
        self._transition(run_id, "complete", "REFRESH_RUN_COMPLETED", "completed_at")

    def fail_run(self, run_id: str, *, reason: str) -> None:
        conn = self._conn()
        self._require_status(conn, run_id, {"staging"}, "fail")
        self._begin(conn)
        try:
            conn.execute(
                "UPDATE security_refresh_runs SET status='failed', failed_at=?, failure_reason=? "
                "WHERE run_id=?",
                (_now_iso(), reason, run_id),
            )
            append_audit_row(conn, "REFRESH_RUN_FAILED", payload={"run_id": run_id, "reason": reason})
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def activate_run(self, run_id: str) -> dict[str, Any]:
        """Supersede the anchor's current active run and activate the target in
        ONE transaction. Re-activating an already-active run is a no-op success."""
        conn = self._conn()
        run = self.get_run(run_id)
        if run is None:
            raise RefreshRunTransitionError(f"unknown run {run_id!r}")
        if run["status"] == "active":
            return {"run_id": run_id, "activated": False, "already_active": True}
        if not is_allowed_transition(str(run["status"]), "active"):
            raise RefreshRunTransitionError(transition_error(str(run["status"]), "active"))
        now = _now_iso()
        self._begin(conn)
        try:
            previous = conn.execute(
                "SELECT run_id FROM security_refresh_runs WHERE anchor_entity_id=? AND status='active'",
                (run["anchor_entity_id"],),
            ).fetchone()
            if previous is not None:
                conn.execute(
                    "UPDATE security_refresh_runs SET status='superseded', superseded_at=? WHERE run_id=?",
                    (now, previous["run_id"]),
                )
            conn.execute(
                "UPDATE security_refresh_runs SET status='active', activated_at=? WHERE run_id=?",
                (now, run_id),
            )
            append_audit_row(conn, "REFRESH_RUN_ACTIVATED", payload={
                "run_id": run_id, "anchor_entity_id": run["anchor_entity_id"],
                "superseded_run_id": previous["run_id"] if previous else None,
            })
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        return {
            "run_id": run_id, "activated": True,
            "superseded_run_id": previous["run_id"] if previous else None,
        }

    def fail_stale_staging(self, *, started_before_iso: str) -> list[str]:
        """Mark staging runs older than the cutoff failed (stale recovery);
        never auto-activates anything."""
        conn = self._conn()
        stale = [
            row["run_id"] for row in conn.execute(
                "SELECT run_id FROM security_refresh_runs WHERE status='staging' AND started_at < ?",
                (started_before_iso,),
            ).fetchall()
        ]
        for run_id in stale:
            self.fail_run(run_id, reason=f"stale staging run (started before {started_before_iso})")
        return stale

    # ── Internals ─────────────────────────────────────────────────────────────

    def _transition(self, run_id: str, target: str, audit_op: str, timestamp_field: str) -> None:
        conn = self._conn()
        run = self.get_run(run_id)
        if run is None:
            raise RefreshRunTransitionError(f"unknown run {run_id!r}")
        if not is_allowed_transition(str(run["status"]), target):
            raise RefreshRunTransitionError(transition_error(str(run["status"]), target))
        self._begin(conn)
        try:
            conn.execute(
                f"UPDATE security_refresh_runs SET status=?, {timestamp_field}=? WHERE run_id=?",  # noqa: S608
                (target, _now_iso(), run_id),
            )
            append_audit_row(conn, audit_op, payload={"run_id": run_id})
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def _require_status(self, conn: Any, run_id: str, allowed: set[str], action: str) -> None:
        run = conn.execute(
            "SELECT status FROM security_refresh_runs WHERE run_id=?", (run_id,)
        ).fetchone()
        if run is None:
            raise RefreshRunTransitionError(f"unknown run {run_id!r}")
        if str(run["status"]) not in allowed:
            raise RefreshRunTransitionError(
                f"cannot {action} run in status {run['status']!r} (needs {sorted(allowed)})"
            )

    def _resolve_canonical(self, conn: Any, external_ids: list[str]) -> str:
        index = {
            row["alias"]: row["canonical_id"]
            for row in conn.execute("SELECT alias, canonical_id FROM vulnerability_aliases").fetchall()
        }
        resolution = resolve_aliases(external_ids, index)
        now = _now_iso()
        if isinstance(resolution, UseExisting):
            canonical_id = resolution.canonical_id
        elif isinstance(resolution, CreateCanonical):
            canonical_id = _stable_id(
                "VID", *sorted(normalize_external_id(e) for e in external_ids)
            )
            conn.execute(
                "INSERT OR IGNORE INTO canonical_vulnerabilities (canonical_id, created_at) VALUES (?,?)",
                (canonical_id, now),
            )
        else:
            assert isinstance(resolution, MergeCanonical)
            canonical_id = resolution.survivor_id
            for merged in resolution.merged_ids:
                conn.execute(
                    "UPDATE canonical_vulnerabilities SET merged_into=? WHERE canonical_id=?",
                    (canonical_id, merged),
                )
                for table, column in (
                    ("vulnerability_aliases", "canonical_id"),
                    ("run_vulnerability_findings", "canonical_vulnerability_id"),
                    ("vex_assessments", "canonical_vulnerability_id"),
                ):
                    conn.execute(
                        f"UPDATE {table} SET {column}=? WHERE {column}=?",  # noqa: S608
                        (canonical_id, merged),
                    )
        for external_id in external_ids:
            conn.execute(
                "INSERT OR IGNORE INTO vulnerability_aliases (alias, canonical_id, created_at) VALUES (?,?,?)",
                (normalize_external_id(external_id), canonical_id, now),
            )
        return canonical_id
