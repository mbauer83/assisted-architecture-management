"""SQLite-backed SecuritySignalConnector adapter.

Stores BOM ingest records, individual components, vulnerability findings,
and anchor mappings (component_ref → arch entity ID) in a plain SQLite DB
at .arch-assurance/security-signals.db.

This DB is NOT encrypted — BOM component lists are generally not sensitive.
Vulnerability data with confidential context should be managed via TLP tags
on the assurance entities that reference these signals.
"""

from __future__ import annotations

import hashlib
import logging
import sqlite3
import time
from pathlib import Path
from typing import Any

from src.infrastructure.assurance._sbom_parser import parse_bom
from src.infrastructure.assurance._schema import SECURITY_SIGNALS_SCHEMA_SQL

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _stable_id(prefix: str, *parts: str) -> str:
    """Deterministic ID — same logical inputs always yield the same ID (enables idempotent upsert)."""
    slug = hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]
    return f"{prefix}@{slug}"


def _transient_id(prefix: str, *parts: str) -> str:
    """Non-deterministic ID with epoch — for records where uniqueness per-call is desired."""
    slug = hashlib.sha256("|".join(parts).encode()).hexdigest()[:12]
    return f"{prefix}@{int(time.time())}.{slug}"


def _safe_float(v: object) -> float | None:
    if v is None:
        return None
    try:
        return float(v)  # type: ignore[arg-type]
    except (ValueError, TypeError):
        return None


def _dict_row(cursor: Any, row: Any) -> dict[str, object]:
    cols = [col[0] for col in cursor.description]
    return dict(zip(cols, row))


class SQLiteSecurityConnector:
    """SQLite adapter implementing SecuritySignalConnector."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None

    def _open(self) -> sqlite3.Connection:
        if self._conn is None:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(self._db_path))
            conn.executescript(SECURITY_SIGNALS_SCHEMA_SQL)
            conn.commit()
            conn.row_factory = _dict_row  # type: ignore[assignment]
            self._conn = conn
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __del__(self) -> None:
        self.close()

    def import_bom(
        self,
        bom_data: dict[str, object],
        *,
        anchor_entity_id: str,
        bom_format: str = "cyclonedx",
        source_file: str = "",
    ) -> dict[str, object]:
        conn = self._open()
        try:
            meta, components = parse_bom(bom_data)
        except Exception as exc:  # noqa: BLE001
            return {"error": "parse_failed", "detail": str(exc)}

        bom_serial = str(meta.get("bom_serial") or "")
        bom_version = str(meta.get("bom_version") or "1")
        detected_format = str(meta.get("bom_format") or bom_format)

        # Deterministic ID: same anchor+serial+version always upserts the same row (idempotent).
        ingest_id = _stable_id("BOM", anchor_entity_id, bom_serial, bom_version)
        now = _now_iso()

        anchors = {row["component_ref"]: row["arch_entity_id"]
                   for row in conn.execute("SELECT component_ref, arch_entity_id FROM anchor_mappings").fetchall()}

        component_rows: list[dict[str, object]] = []
        for comp in components:
            purl = str(comp.get("purl") or "")
            cid = _stable_id("CMP", ingest_id, purl or str(comp.get("name") or ""))
            arch_entity_id_match = anchors.get(purl) if purl else None
            match_type = "anchor" if arch_entity_id_match else "none"
            component_rows.append({
                "component_id": cid,
                "ingest_id": ingest_id,
                "purl": purl,
                "cpe": str(comp.get("cpe") or ""),
                "name": str(comp.get("name") or ""),
                "version": str(comp.get("version") or ""),
                "component_type": str(comp.get("component_type") or "library"),
                "group_name": str(comp.get("group_name") or ""),
                "arch_entity_id": arch_entity_id_match,
                "match_type": match_type,
                "created_at": now,
            })

        conn.execute(
            "INSERT OR REPLACE INTO bom_ingests VALUES (?,?,?,?,?,?,?,?)",
            (ingest_id, anchor_entity_id, bom_serial, bom_version, detected_format,
             len(component_rows), now, source_file),
        )
        conn.executemany(
            "INSERT OR REPLACE INTO bom_components "
            "(component_id,ingest_id,purl,cpe,name,version,component_type,group_name,"
            "arch_entity_id,match_type,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            [
                (r["component_id"], r["ingest_id"], r["purl"], r["cpe"], r["name"],
                 r["version"], r["component_type"], r["group_name"],
                 r["arch_entity_id"], r["match_type"], r["created_at"])
                for r in component_rows
            ],
        )
        conn.commit()
        logger.info("BOM ingested: %s (%d components)", ingest_id, len(component_rows))
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
        conn = self._open()
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
    ) -> dict[str, object]:
        conn = self._open()
        now = _now_iso()
        inserted = 0
        for rec in vuln_records:
            ext_id = str(rec.get("id") or rec.get("ext_id") or "")
            if not ext_id:
                continue
            purl = str(rec.get("purl") or rec.get("affected_purl") or "")
            db_specific = rec.get("database_specific")
            fallback_severity = db_specific.get("severity", "") if isinstance(db_specific, dict) else ""
            severity = str(rec.get("severity") or fallback_severity)
            cvss = rec.get("cvss_score") or rec.get("score")
            vex_status = str(rec.get("vex_status") or "")
            vex_just = str(rec.get("vex_justification") or "")
            desc = str(rec.get("summary") or rec.get("details") or rec.get("description") or "")
            vuln_id = _stable_id("VUL", ext_id, purl, source)
            conn.execute(
                "INSERT OR REPLACE INTO vulnerabilities "
                "(vuln_id,purl,ext_id,source,severity,cvss_score,vex_status,"
                "vex_justification,description,ingested_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (vuln_id, purl, ext_id, source, severity,
                 _safe_float(cvss),
                 vex_status, vex_just, desc, now),
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
        conn = self._open()
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
    ) -> None:
        conn = self._open()
        now = _now_iso()
        conn.execute(
            "INSERT OR REPLACE INTO anchor_mappings "
            "(component_ref, arch_entity_id, ref_type, created_at) VALUES (?,?,?,?)",
            (component_ref, arch_entity_id, ref_type, now),
        )
        conn.commit()

    def list_anchors(
        self,
        *,
        arch_entity_id: str | None = None,
    ) -> list[dict[str, object]]:
        conn = self._open()
        if arch_entity_id:
            return conn.execute(  # type: ignore[return-value]
                "SELECT * FROM anchor_mappings WHERE arch_entity_id=?",
                (arch_entity_id,),
            ).fetchall()
        return conn.execute("SELECT * FROM anchor_mappings ORDER BY created_at DESC").fetchall()  # type: ignore[return-value]

    def get_stats(self) -> dict[str, object]:
        conn = self._open()
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

    def _export_data(self) -> dict[str, object]:
        """Dump all tables for export/backup purposes."""
        conn = self._open()
        return {
            "bom_ingests": conn.execute("SELECT * FROM bom_ingests").fetchall(),
            "bom_components": conn.execute("SELECT * FROM bom_components").fetchall(),
            "vulnerabilities": conn.execute("SELECT * FROM vulnerabilities").fetchall(),
            "anchor_mappings": conn.execute("SELECT * FROM anchor_mappings").fetchall(),
        }
