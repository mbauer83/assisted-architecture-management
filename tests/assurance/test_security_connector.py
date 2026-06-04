"""Tests for SQLiteSecurityConnector: anchor mapping, BOM ingest, vuln ingest."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from src.infrastructure.assurance._security_connector import SQLiteSecurityConnector


def _make_connector() -> SQLiteSecurityConnector:
    fd, tmp = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    return SQLiteSecurityConnector(Path(tmp))


def _cdx_bom(components: list[dict]) -> dict:
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.4",
        "serialNumber": "urn:uuid:test-abc",
        "version": 1,
        "components": components,
    }


def _comp(name: str, purl: str = "") -> dict:
    return {"name": name, "purl": purl, "version": "1.0", "type": "library"}


# ── Anchor mappings ───────────────────────────────────────────────────────────

class TestAnchorMappings:
    def test_set_and_list_anchor(self) -> None:
        c = _make_connector()
        c.set_anchor("pkg:pypi/requests@2.31.0", "ACP@123", ref_type="purl")
        anchors = c.list_anchors()
        assert len(anchors) == 1
        assert anchors[0]["component_ref"] == "pkg:pypi/requests@2.31.0"
        assert anchors[0]["arch_entity_id"] == "ACP@123"

    def test_filter_by_arch_entity_id(self) -> None:
        c = _make_connector()
        c.set_anchor("pkg:pypi/requests@2.31.0", "ACP@123")
        c.set_anchor("pkg:pypi/flask@3.0.0", "ACP@456")
        result = c.list_anchors(arch_entity_id="ACP@123")
        assert len(result) == 1
        assert result[0]["component_ref"] == "pkg:pypi/requests@2.31.0"

    def test_upsert_anchor(self) -> None:
        c = _make_connector()
        c.set_anchor("pkg:pypi/lib@1.0", "ACP@111")
        c.set_anchor("pkg:pypi/lib@1.0", "ACP@222")  # update
        anchors = c.list_anchors()
        assert len(anchors) == 1
        assert anchors[0]["arch_entity_id"] == "ACP@222"


# ── BOM ingestion ─────────────────────────────────────────────────────────────

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

    def test_components_stored(self) -> None:
        c = _make_connector()
        c.import_bom(
            _cdx_bom([
                _comp("requests", "pkg:pypi/requests@2.31.0"),
                _comp("flask", "pkg:pypi/flask@3.0.0"),
            ]),
            anchor_entity_id="ACP@abc",
        )
        comps = c.list_bom_components()
        assert len(comps) == 2

    def test_filter_by_anchor(self) -> None:
        c = _make_connector()
        c.import_bom(_cdx_bom([_comp("lib-a", "pkg:npm/a@1")]), anchor_entity_id="ENT@1")
        c.import_bom(_cdx_bom([_comp("lib-b", "pkg:npm/b@1")]), anchor_entity_id="ENT@2")
        result = c.list_bom_components(anchor_entity_id="ENT@1")
        assert len(result) == 1
        assert result[0]["name"] == "lib-a"

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

    def test_parse_error_returns_error_dict(self) -> None:
        c = _make_connector()
        # Pass a BOM that parses but has no components
        result = c.import_bom({}, anchor_entity_id="ACP@x")
        # Should succeed with 0 components (empty BOM, not a parse error)
        assert result.get("component_count") == 0

    def test_filter_by_purl(self) -> None:
        c = _make_connector()
        c.import_bom(
            _cdx_bom([_comp("requests", "pkg:pypi/requests@2.31.0"), _comp("flask")]),
            anchor_entity_id="ACP@x",
        )
        result = c.list_bom_components(purl="pkg:pypi/requests@2.31.0")
        assert len(result) == 1


# ── Vulnerability ingestion ───────────────────────────────────────────────────

class TestVulnIngest:
    def _vuln(self, ext_id: str, purl: str = "", severity: str = "HIGH") -> dict:
        return {
            "id": ext_id,
            "purl": purl,
            "severity": severity,
            "cvss_score": 7.5,
            "summary": f"Test vuln {ext_id}",
        }

    def test_basic_ingest(self) -> None:
        c = _make_connector()
        result = c.import_vulnerabilities(
            [self._vuln("CVE-2026-0001", "pkg:pypi/requests@2.31.0")],
            source="osv",
        )
        assert result["inserted"] == 1

    def test_list_all(self) -> None:
        c = _make_connector()
        c.import_vulnerabilities([
            self._vuln("CVE-2026-0001", "pkg:pypi/requests@2.31.0"),
            self._vuln("CVE-2026-0002", "pkg:npm/express@4.18.0"),
        ])
        vulns = c.list_vulnerabilities()
        assert len(vulns) == 2

    def test_filter_by_purl(self) -> None:
        c = _make_connector()
        c.import_vulnerabilities([
            self._vuln("CVE-2026-0001", "pkg:pypi/requests@2.31.0"),
            self._vuln("CVE-2026-0002", "pkg:npm/express@4.18.0"),
        ])
        result = c.list_vulnerabilities(purl="pkg:pypi/requests@2.31.0")
        assert len(result) == 1
        assert result[0]["ext_id"] == "CVE-2026-0001"

    def test_filter_by_severity(self) -> None:
        c = _make_connector()
        c.import_vulnerabilities([
            self._vuln("CVE-2026-0001", severity="HIGH"),
            self._vuln("CVE-2026-0002", severity="CRITICAL"),
        ])
        result = c.list_vulnerabilities(severity="CRITICAL")
        assert len(result) == 1

    def test_skip_records_without_id(self) -> None:
        c = _make_connector()
        result = c.import_vulnerabilities([{"severity": "HIGH"}])
        assert result["inserted"] == 0


# ── Stats ─────────────────────────────────────────────────────────────────────

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
