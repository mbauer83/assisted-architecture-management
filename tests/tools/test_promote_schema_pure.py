"""Tests for pure functions in promote_schema_check.py and _promote_conflicts.py.

Covers: _schema_superset_errors, _compare_schema_pairs (promote_schema_check),
_document_schema_errors, check_promotion_schema_compatibility,
and build_handler (_promote_conflicts).
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from src.domain.artifact_types import DocumentRecord
from src.infrastructure.write.artifact_write._promote_conflicts import build_handler
from src.infrastructure.write.artifact_write.promote_schema_check import (
    _compare_schema_pairs,
    _document_schema_errors,
    _schema_superset_errors,
    check_promotion_schema_compatibility,
)
from src.infrastructure.write.artifact_write.promote_to_enterprise import ConflictResolution

# ---------------------------------------------------------------------------
# _schema_superset_errors
# ---------------------------------------------------------------------------


class TestSchemaSupersetErrors:
    def test_no_errors_when_eng_is_superset(self) -> None:
        eng = {"properties": {"a": {}, "b": {}}, "required": ["a", "b"]}
        ent = {"properties": {"a": {}}, "required": ["a"]}
        assert _schema_superset_errors(eng, ent, "test") == []

    def test_error_when_eng_missing_property(self) -> None:
        eng = {"properties": {"a": {}}}
        ent = {"properties": {"a": {}, "b": {}}}
        errors = _schema_superset_errors(eng, ent, "test")
        assert len(errors) == 1
        assert "b" in errors[0]

    def test_error_when_eng_missing_required(self) -> None:
        eng = {"properties": {"a": {}, "b": {}}, "required": ["a"]}
        ent = {"properties": {"a": {}, "b": {}}, "required": ["a", "b"]}
        errors = _schema_superset_errors(eng, ent, "test")
        assert len(errors) == 1
        assert "b" in errors[0]

    def test_two_errors_when_both_missing(self) -> None:
        eng: dict = {}
        ent = {"properties": {"x": {}}, "required": ["x"]}
        errors = _schema_superset_errors(eng, ent, "scope")
        assert len(errors) == 2

    def test_no_errors_when_both_empty(self) -> None:
        assert _schema_superset_errors({}, {}, "scope") == []

    def test_scope_appears_in_error(self) -> None:
        eng: dict = {}
        ent = {"properties": {"x": {}}}
        errors = _schema_superset_errors(eng, ent, "my-scope")
        assert any("my-scope" in e for e in errors)


# ---------------------------------------------------------------------------
# _compare_schema_pairs
# ---------------------------------------------------------------------------


class TestCompareSchemaP:
    def test_skips_key_when_ent_schema_is_none(self) -> None:
        errors = _compare_schema_pairs(
            ["k1"],
            load_ent=lambda k: None,
            load_eng=lambda k: {},
            missing_eng_msg=lambda k: f"missing {k}",
            scope_label=lambda k: k,
        )
        assert errors == []

    def test_adds_missing_eng_msg_when_eng_schema_is_none(self) -> None:
        errors = _compare_schema_pairs(
            ["k1"],
            load_ent=lambda k: {},
            load_eng=lambda k: None,
            missing_eng_msg=lambda k: f"missing-eng:{k}",
            scope_label=lambda k: k,
        )
        assert errors == ["missing-eng:k1"]

    def test_propagates_superset_errors(self) -> None:
        errors = _compare_schema_pairs(
            ["k1"],
            load_ent=lambda k: {"properties": {"x": {}}},
            load_eng=lambda k: {},
            missing_eng_msg=lambda k: f"missing {k}",
            scope_label=lambda k: f"scope:{k}",
        )
        assert any("scope:k1" in e for e in errors)

    def test_no_errors_when_schemas_match(self) -> None:
        errors = _compare_schema_pairs(
            ["k1"],
            load_ent=lambda k: {"properties": {"a": {}}},
            load_eng=lambda k: {"properties": {"a": {}, "b": {}}},
            missing_eng_msg=lambda k: "",
            scope_label=lambda k: k,
        )
        assert errors == []

    def test_handles_multiple_keys(self) -> None:
        errors = _compare_schema_pairs(
            ["k1", "k2"],
            load_ent=lambda k: {"properties": {k: {}}},
            load_eng=lambda k: None,
            missing_eng_msg=lambda k: f"missing:{k}",
            scope_label=lambda k: k,
        )
        assert "missing:k1" in errors
        assert "missing:k2" in errors


# ---------------------------------------------------------------------------
# build_handler (_promote_conflicts.py)
# ---------------------------------------------------------------------------


class TestBuildHandler:
    def test_accept_enterprise_returns_handler(self) -> None:
        res = ConflictResolution(engagement_id="E@1", strategy="accept_enterprise")
        handler = build_handler(res)
        assert handler is not None

    def test_accept_engagement_returns_handler(self) -> None:
        res = ConflictResolution(engagement_id="E@1", strategy="accept_engagement")
        handler = build_handler(res)
        assert handler is not None

    def test_merge_with_fields_returns_handler(self) -> None:
        res = ConflictResolution(
            engagement_id="E@1",
            strategy="merge",
            merged_fields={"name": "New Name"},
        )
        handler = build_handler(res)
        assert handler is not None

    def test_merge_without_fields_returns_none(self) -> None:
        res = ConflictResolution(engagement_id="E@1", strategy="merge", merged_fields=None)
        handler = build_handler(res)
        assert handler is None

    def test_unknown_strategy_returns_none(self) -> None:
        res = ConflictResolution(engagement_id="E@1", strategy="accept_enterprise")
        res.strategy = "unknown"  # type: ignore[assignment]
        handler = build_handler(res)
        assert handler is None


# ---------------------------------------------------------------------------
# _document_schema_errors
# ---------------------------------------------------------------------------


def _make_doc_record(artifact_id: str, doc_type: str) -> DocumentRecord:
    return DocumentRecord(
        artifact_id=artifact_id,
        doc_type=doc_type,
        title="Test Doc",
        status="draft",
        path=Path("/fake/path.md"),
        keywords=(),
        sections=(),
        content_text="",
        extra={},
    )


def _make_mock_repo(doc_id: str, doc_type: str) -> MagicMock:
    repo = MagicMock()
    repo.get_document = lambda did: _make_doc_record(did, doc_type) if did == doc_id else None
    return repo


class TestDocumentSchemaErrors:
    def test_empty_document_ids_returns_no_errors(self, tmp_path: Path) -> None:
        repo = MagicMock()
        errors = _document_schema_errors(tmp_path, tmp_path, [], repo)
        assert errors == []

    def test_ent_schema_missing_skips_type(self, tmp_path: Path) -> None:
        eng = tmp_path / "eng"
        ent = tmp_path / "ent"
        eng.mkdir()
        ent.mkdir()
        repo = _make_mock_repo("DOC@1.AA.test", "my-doc-type")
        errors = _document_schema_errors(eng, ent, ["DOC@1.AA.test"], repo)
        assert errors == []

    def test_eng_schema_missing_reports_error(self, tmp_path: Path) -> None:
        eng = tmp_path / "eng"
        ent = tmp_path / "ent"
        eng.mkdir()
        ent.mkdir()
        schema_dir = ent / ".arch-repo" / "documents"
        schema_dir.mkdir(parents=True)
        ent_schema = {"frontmatter_schema": {}, "required_sections": ["Overview"]}
        (schema_dir / "my-doc.json").write_text(json.dumps(ent_schema))
        repo = _make_mock_repo("DOC@1.BB.test", "my-doc")
        errors = _document_schema_errors(eng, ent, ["DOC@1.BB.test"], repo)
        assert any("my-doc" in e for e in errors)

    def test_missing_required_section_reported(self, tmp_path: Path) -> None:
        eng = tmp_path / "eng"
        ent = tmp_path / "ent"
        eng.mkdir()
        ent.mkdir()
        ent_schema_dir = ent / ".arch-repo" / "documents"
        ent_schema_dir.mkdir(parents=True)
        eng_schema_dir = eng / ".arch-repo" / "documents"
        eng_schema_dir.mkdir(parents=True)
        ent_schema = {"frontmatter_schema": {}, "required_sections": ["Overview", "Background"]}
        eng_schema = {"frontmatter_schema": {}, "required_sections": ["Overview"]}
        (ent_schema_dir / "my-doc2.json").write_text(json.dumps(ent_schema))
        (eng_schema_dir / "my-doc2.json").write_text(json.dumps(eng_schema))
        repo = _make_mock_repo("DOC@1.CC.test", "my-doc2")
        errors = _document_schema_errors(eng, ent, ["DOC@1.CC.test"], repo)
        assert any("Background" in e for e in errors)

    def test_doc_id_not_in_repo_skipped(self, tmp_path: Path) -> None:
        eng = tmp_path / "eng"
        ent = tmp_path / "ent"
        eng.mkdir()
        ent.mkdir()
        repo = MagicMock()
        repo.get_document = lambda did: None
        errors = _document_schema_errors(eng, ent, ["DOC@9.ZZZ.not-found"], repo)
        assert errors == []

    def test_missing_section_entity_type_connection_reported(self, tmp_path: Path) -> None:
        eng = tmp_path / "eng"
        ent = tmp_path / "ent"
        eng.mkdir()
        ent.mkdir()
        ent_schema_dir = ent / ".arch-repo" / "documents"
        ent_schema_dir.mkdir(parents=True)
        eng_schema_dir = eng / ".arch-repo" / "documents"
        eng_schema_dir.mkdir(parents=True)
        ent_schema = {
            "frontmatter_schema": {},
            "sections": [{"name": "Specification", "required_entity_type_connections": ["requirement"]}],
        }
        eng_schema = {"frontmatter_schema": {}, "sections": [{"name": "Specification"}]}
        (ent_schema_dir / "my-doc3.json").write_text(json.dumps(ent_schema))
        (eng_schema_dir / "my-doc3.json").write_text(json.dumps(eng_schema))
        repo = _make_mock_repo("DOC@1.DD.test", "my-doc3")
        errors = _document_schema_errors(eng, ent, ["DOC@1.DD.test"], repo)
        assert any("requirement" in e and "Specification" in e for e in errors)

    def test_engagement_section_superset_reports_no_error(self, tmp_path: Path) -> None:
        eng = tmp_path / "eng"
        ent = tmp_path / "ent"
        eng.mkdir()
        ent.mkdir()
        ent_schema_dir = ent / ".arch-repo" / "documents"
        ent_schema_dir.mkdir(parents=True)
        eng_schema_dir = eng / ".arch-repo" / "documents"
        eng_schema_dir.mkdir(parents=True)
        ent_schema = {
            "frontmatter_schema": {},
            "sections": [{"name": "Specification", "required_entity_type_connections": ["requirement"]}],
        }
        eng_schema = {
            "frontmatter_schema": {},
            "sections": [
                {"name": "Specification", "required_entity_type_connections": ["requirement", "capability"]}
            ],
        }
        (ent_schema_dir / "my-doc4.json").write_text(json.dumps(ent_schema))
        (eng_schema_dir / "my-doc4.json").write_text(json.dumps(eng_schema))
        repo = _make_mock_repo("DOC@1.EE.test", "my-doc4")
        errors = _document_schema_errors(eng, ent, ["DOC@1.EE.test"], repo)
        assert errors == []


# ---------------------------------------------------------------------------
# check_promotion_schema_compatibility — both roots present
# ---------------------------------------------------------------------------


class TestCheckPromotionSchemaCompatibility:
    def test_returns_empty_when_single_root(self, tmp_path: Path) -> None:
        eng = tmp_path / "engagements" / "ENG-SCHK" / "architecture-repository"
        eng.mkdir(parents=True)
        registry = MagicMock()
        registry.repo_roots = [eng]
        repo = MagicMock()
        repo.get_entity = lambda eid: None
        repo.get_document = lambda did: None
        errors = check_promotion_schema_compatibility(
            entity_ids=[],
            has_diagrams=False,
            document_ids=[],
            registry=registry,
            repo=repo,
        )
        assert errors == []

    def test_runs_with_both_roots(self, tmp_path: Path) -> None:
        eng = tmp_path / "engagements" / "ENG-SCHK2" / "architecture-repository"
        ent = tmp_path / "enterprise-repository"
        eng.mkdir(parents=True)
        ent.mkdir(parents=True)
        registry = MagicMock()
        registry.repo_roots = [eng, ent]
        repo = MagicMock()
        repo.get_entity = lambda eid: None
        repo.get_document = lambda did: None
        errors = check_promotion_schema_compatibility(
            entity_ids=[],
            has_diagrams=False,
            document_ids=[],
            registry=registry,
            repo=repo,
        )
        assert isinstance(errors, list)
