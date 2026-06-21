"""Co-located SQLCipher security-signals connector (SC-2 default).

Stores BOM ingest records, components, vulnerabilities, and anchor mappings
in the *same* SQLCipher database as the main assurance store. The connection
is shared — one trust zone, one encryption key, one unlock event.

This is the default signals backend (signals_backend: sqlcipher-colocated).
The plaintext SQLite connector is the explicit public-BOM opt-out path.

All tables carry a `tlp` column (default TLP:AMBER — confidential). Reads are
gated behind store-unlock; locked ⇒ connector methods raise RuntimeError.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any, Callable

from src.domain.clock import utc_now_iso as _now_iso
from src.infrastructure.assurance._sbom_parser import parse_bom
from src.infrastructure.assurance._schema import SECURITY_SIGNALS_SCHEMA_SQL

logger = logging.getLogger(__name__)


def _stable_id(prefix: str, *parts: str) -> str:
    slug = hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]
    return f"{prefix}@{slug}"


def _safe_float(v: object) -> float | None:
    if v is None:
        return None
    try:
        return float(v)  # type: ignore[arg-type]
    except (ValueError, TypeError):
        return None


class CollocatedSQLCipherSignalsConnector:
    """SecuritySignalConnector adapter that co-locates signals in the SQLCipher store.

    Accepts the store's private connection factory (same pattern as the archive).
    All data is encrypted at rest via the store's SQLCipher key.
    """

    def __init__(self, conn_factory: Callable[[], Any]) -> None:
        self._conn_factory = conn_factory

    def _conn(self) -> Any:
        c = self._conn_factory()
        if c is None:
            raise RuntimeError("Assurance store is locked — cannot access security signals.")
        # Always run schema DDL — IF NOT EXISTS makes it idempotent, and the SQLCipher
        # store may create a new connection object after a lock/unlock cycle.
        c.executescript(SECURITY_SIGNALS_SCHEMA_SQL)
        c.commit()
        return c

    def import_bom(
        self,
        bom_data: dict[str, object],
        *,
        anchor_entity_id: str,
        bom_format: str = "cyclonedx",
        source_file: str = "",
        tlp: str = "TLP:AMBER",
    ) -> dict[str, object]:
        conn = self._conn()
        try:
            meta, components = parse_bom(bom_data)
        except Exception as exc:  # noqa: BLE001
            return {"error": "parse_failed", "detail": str(exc)}

        bom_serial = str(meta.get("bom_serial") or "")
        bom_version = str(meta.get("bom_version") or "1")
        detected_format = str(meta.get("bom_format") or bom_format)
        ingest_id = _stable_id("BOM", anchor_entity_id, bom_serial, bom_version)
        now = _now_iso()

        anchors = {
            row["component_ref"]: row["arch_entity_id"]
            for row in conn.execute(
                "SELECT component_ref, arch_entity_id FROM anchor_mappings"
            ).fetchall()
        }

        component_rows: list[dict[str, object]] = []
        for comp in components:
            purl = str(comp.get("purl") or "")
            cid = _stable_id("CMP", ingest_id, purl or str(comp.get("name") or ""))
            arch_match = anchors.get(purl) if purl else None
            component_rows.append({
                "component_id": cid,
                "ingest_id": ingest_id,
                "purl": purl,
                "cpe": str(comp.get("cpe") or ""),
                "name": str(comp.get("name") or ""),
                "version": str(comp.get("version") or ""),
                "component_type": str(comp.get("component_type") or "library"),
                "group_name": str(comp.get("group_name") or ""),
                "arch_entity_id": arch_match,
                "match_type": "anchor" if arch_match else "none",
                "created_at": now,
                "tlp": tlp,
            })

        conn.execute(
            "INSERT OR REPLACE INTO bom_ingests "
            "(ingest_id, anchor_entity_id, bom_serial, bom_version, bom_format, "
            "component_count, ingested_at, source_file, tlp) VALUES (?,?,?,?,?,?,?,?,?)",
            (ingest_id, anchor_entity_id, bom_serial, bom_version, detected_format,
             len(component_rows), now, source_file, tlp),
        )
        conn.executemany(
            "INSERT OR REPLACE INTO bom_components "
            "(component_id, ingest_id, purl, cpe, name, version, component_type, "
            "group_name, arch_entity_id, match_type, created_at, tlp) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            [
                (r["component_id"], r["ingest_id"], r["purl"], r["cpe"], r["name"],
                 r["version"], r["component_type"], r["group_name"],
                 r["arch_entity_id"], r["match_type"], r["created_at"], r["tlp"])
                for r in component_rows
            ],
        )
        conn.commit()
        logger.info("BOM ingested (colocated): %s (%d components)", ingest_id, len(component_rows))
        return {
            "ingest_id": ingest_id,
            "anchor_entity_id": anchor_entity_id,
            "bom_format": detected_format,
            "component_count": len(component_rows),
            "anchor_matched": sum(1 for r in component_rows if r["match_type"] == "anchor"),
        }

    def list_bom_components(
        self,
        *,
        anchor_entity_id: str | None = None,
        purl: str | None = None,
    ) -> list[dict[str, object]]:
        conn = self._conn()
        clauses: list[str] = []
        params: list[str] = []
        if anchor_entity_id:
            clauses.append(
                "ingest_id IN (SELECT ingest_id FROM bom_ingests WHERE anchor_entity_id=?)"
            )
            params.append(anchor_entity_id)
        if purl:
            clauses.append("purl=?")
            params.append(purl)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        return conn.execute(  # type: ignore[return-value]
            f"SELECT * FROM bom_components {where} ORDER BY created_at DESC",
            params,
        ).fetchall()

    def import_vulnerabilities(
        self,
        vuln_records: list[dict[str, object]],
        *,
        source: str = "osv",
        tlp: str = "TLP:AMBER",
    ) -> dict[str, object]:
        conn = self._conn()
        now = _now_iso()
        inserted = 0
        for rec in vuln_records:
            ext_id = str(rec.get("id") or rec.get("ext_id") or "")
            if not ext_id:
                continue
            purl = str(rec.get("purl") or rec.get("affected_purl") or "")
            db_specific = rec.get("database_specific")
            fallback_sev = db_specific.get("severity", "") if isinstance(db_specific, dict) else ""
            severity = str(rec.get("severity") or fallback_sev)
            cvss = rec.get("cvss_score") or rec.get("score")
            vex_status = str(rec.get("vex_status") or "")
            vex_just = str(rec.get("vex_justification") or "")
            desc = str(rec.get("summary") or rec.get("details") or rec.get("description") or "")
            vuln_id = _stable_id("VUL", ext_id, purl, source)
            conn.execute(
                "INSERT OR REPLACE INTO vulnerabilities "
                "(vuln_id,purl,ext_id,source,severity,cvss_score,vex_status,"
                "vex_justification,description,ingested_at,tlp) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (vuln_id, purl, ext_id, source, severity, _safe_float(cvss),
                 vex_status, vex_just, desc, now, tlp),
            )
            inserted += 1
        conn.commit()
        return {"source": source, "inserted": inserted}

    def list_vulnerabilities(
        self,
        *,
        purl: str | None = None,
        severity: str | None = None,
    ) -> list[dict[str, object]]:
        conn = self._conn()
        clauses: list[str] = []
        params: list[str] = []
        if purl:
            clauses.append("purl=?")
            params.append(purl)
        if severity:
            clauses.append("severity=?")
            params.append(severity)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        return conn.execute(  # type: ignore[return-value]
            f"SELECT * FROM vulnerabilities {where} ORDER BY ingested_at DESC",
            params,
        ).fetchall()

    def set_anchor(
        self,
        component_ref: str,
        arch_entity_id: str,
        *,
        ref_type: str = "purl",
        tlp: str = "TLP:AMBER",
    ) -> None:
        conn = self._conn()
        conn.execute(
            "INSERT OR REPLACE INTO anchor_mappings "
            "(component_ref, arch_entity_id, ref_type, created_at, tlp) VALUES (?,?,?,?,?)",
            (component_ref, arch_entity_id, ref_type, _now_iso(), tlp),
        )
        conn.commit()

    def list_anchors(
        self,
        *,
        arch_entity_id: str | None = None,
    ) -> list[dict[str, object]]:
        conn = self._conn()
        if arch_entity_id:
            return conn.execute(  # type: ignore[return-value]
                "SELECT * FROM anchor_mappings WHERE arch_entity_id=?",
                (arch_entity_id,),
            ).fetchall()
        return conn.execute(  # type: ignore[return-value]
            "SELECT * FROM anchor_mappings ORDER BY created_at DESC"
        ).fetchall()

    def get_stats(self) -> dict[str, object]:
        conn = self._conn()
        ingests = conn.execute("SELECT COUNT(*) as n FROM bom_ingests").fetchone()["n"]  # type: ignore[index]
        components = conn.execute("SELECT COUNT(*) as n FROM bom_components").fetchone()["n"]  # type: ignore[index]
        vulns = conn.execute("SELECT COUNT(*) as n FROM vulnerabilities").fetchone()["n"]  # type: ignore[index]
        anchors = conn.execute("SELECT COUNT(*) as n FROM anchor_mappings").fetchone()["n"]  # type: ignore[index]
        return {
            "bom_ingests": ingests,
            "bom_components": components,
            "vulnerabilities": vulns,
            "anchor_mappings": anchors,
        }
