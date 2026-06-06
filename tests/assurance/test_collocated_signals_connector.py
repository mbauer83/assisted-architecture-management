"""Tests for CollocatedSQLCipherSignalsConnector (SC-2).

Covers:
  - TLP default is TLP:AMBER on all tables
  - All CRUD operations (BOM ingest, vuln ingest, anchors, stats)
  - Locked store raises RuntimeError (conn_factory returns None)
  - Round-trip: write → read with TLP preserved
"""

from __future__ import annotations

import sqlite3
from typing import Any

import pytest

from src.infrastructure.assurance._collocated_signals_connector import (
    CollocatedSQLCipherSignalsConnector,
)


def _make_connector(locked: bool = False) -> CollocatedSQLCipherSignalsConnector:
    """Build a connector backed by a plain in-memory SQLite connection."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = lambda cursor, row: dict(zip([c[0] for c in cursor.description], row))

    def factory() -> Any:
        return None if locked else conn

    return CollocatedSQLCipherSignalsConnector(factory)


def _cdx_bom(components: list[dict]) -> dict:
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.4",
        "serialNumber": "urn:uuid:test-collocated",
        "version": 1,
        "components": components,
    }


def _comp(name: str, purl: str = "") -> dict:
    return {"name": name, "purl": purl, "version": "1.0", "type": "library"}


# ── Lock gating ───────────────────────────────────────────────────────────────


class TestLockGating:
    def test_locked_raises_on_list_components(self) -> None:
        c = _make_connector(locked=True)
        with pytest.raises(RuntimeError, match="locked"):
            c.list_bom_components()

    def test_locked_raises_on_import_bom(self) -> None:
        c = _make_connector(locked=True)
        with pytest.raises(RuntimeError, match="locked"):
            c.import_bom({}, anchor_entity_id="ACP@x")

    def test_locked_raises_on_import_vulns(self) -> None:
        c = _make_connector(locked=True)
        with pytest.raises(RuntimeError, match="locked"):
            c.import_vulnerabilities([])

    def test_locked_raises_on_stats(self) -> None:
        c = _make_connector(locked=True)
        with pytest.raises(RuntimeError, match="locked"):
            c.get_stats()


# ── TLP defaults ──────────────────────────────────────────────────────────────


class TestTLPDefaults:
    def test_bom_ingest_default_tlp_amber(self) -> None:
        c = _make_connector()
        c.import_bom(
            _cdx_bom([_comp("requests", "pkg:pypi/requests@2.31.0")]),
            anchor_entity_id="ACP@root",
        )
        comps = c.list_bom_components()
        assert len(comps) == 1
        assert comps[0]["tlp"] == "TLP:AMBER"

    def test_explicit_tlp_preserved(self) -> None:
        c = _make_connector()
        c.import_bom(
            _cdx_bom([_comp("lib", "pkg:pypi/lib@1.0")]),
            anchor_entity_id="ACP@root",
            tlp="TLP:RED",
        )
        comps = c.list_bom_components()
        assert comps[0]["tlp"] == "TLP:RED"

    def test_vuln_default_tlp_amber(self) -> None:
        c = _make_connector()
        c.import_vulnerabilities([{"id": "CVE-2026-0001", "purl": "pkg:pypi/x@1"}])
        vulns = c.list_vulnerabilities()
        assert len(vulns) == 1
        assert vulns[0]["tlp"] == "TLP:AMBER"

    def test_anchor_default_tlp_amber(self) -> None:
        c = _make_connector()
        c.set_anchor("pkg:pypi/requests@2.31.0", "ACP@123")
        anchors = c.list_anchors()
        assert len(anchors) == 1
        assert anchors[0]["tlp"] == "TLP:AMBER"


# ── CRUD correctness (mirrors SQLiteSecurityConnector test coverage) ──────────


class TestBomIngest:
    def test_basic_ingest(self) -> None:
        c = _make_connector()
        result = c.import_bom(
            _cdx_bom([_comp("requests", "pkg:pypi/requests@2.31.0")]),
            anchor_entity_id="ACP@abc",
        )
        assert result["component_count"] == 1
        assert "ingest_id" in result
        assert result["anchor_entity_id"] == "ACP@abc"

    def test_anchor_matched_on_ingest(self) -> None:
        c = _make_connector()
        c.set_anchor("pkg:pypi/requests@2.31.0", "ACP@matched")
        result = c.import_bom(
            _cdx_bom([_comp("requests", "pkg:pypi/requests@2.31.0")]),
            anchor_entity_id="ACP@root",
        )
        assert result["anchor_matched"] == 1
        comps = c.list_bom_components(purl="pkg:pypi/requests@2.31.0")
        assert comps[0]["arch_entity_id"] == "ACP@matched"
        assert comps[0]["match_type"] == "anchor"

    def test_filter_by_anchor(self) -> None:
        c = _make_connector()
        c.import_bom(
            _cdx_bom([_comp("lib-a", "pkg:npm/a@1")]),
            anchor_entity_id="ENT@1",
        )
        c.import_bom(
            _cdx_bom([_comp("lib-b", "pkg:npm/b@1")]),
            anchor_entity_id="ENT@2",
        )
        result = c.list_bom_components(anchor_entity_id="ENT@1")
        assert len(result) == 1
        assert result[0]["name"] == "lib-a"


class TestVulnIngest:
    def test_basic_vuln_ingest(self) -> None:
        c = _make_connector()
        result = c.import_vulnerabilities(
            [{"id": "CVE-2026-0001", "purl": "pkg:pypi/req@2.31", "severity": "HIGH"}],
            source="osv",
        )
        assert result["inserted"] == 1

    def test_filter_by_severity(self) -> None:
        c = _make_connector()
        c.import_vulnerabilities([
            {"id": "CVE-2026-0001", "severity": "HIGH"},
            {"id": "CVE-2026-0002", "severity": "CRITICAL"},
        ])
        result = c.list_vulnerabilities(severity="CRITICAL")
        assert len(result) == 1

    def test_skip_records_without_id(self) -> None:
        c = _make_connector()
        result = c.import_vulnerabilities([{"severity": "HIGH"}])
        assert result["inserted"] == 0


class TestStats:
    def test_stats_counts(self) -> None:
        c = _make_connector()
        c.import_bom(_cdx_bom([_comp("lib")]), anchor_entity_id="ACP@x")
        c.import_vulnerabilities([{"id": "CVE-1", "purl": "pkg:x@1"}])
        c.set_anchor("pkg:x@1", "ACP@x")
        stats = c.get_stats()
        assert stats["bom_ingests"] == 1
        assert stats["bom_components"] == 1
        assert stats["vulnerabilities"] == 1
        assert stats["anchor_mappings"] == 1
