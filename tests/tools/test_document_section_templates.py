"""Tests for document-spec section_templates: per-section body injection and spec validation."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pytest

from src.application.verification.artifact_verifier import ArtifactRegistry, ArtifactVerifier
from src.infrastructure.artifact_index import shared_artifact_index
from src.infrastructure.write.artifact_write.document import (
    _build_placeholder_body,
    _validate_section_templates,
    create_document,
)


@lru_cache(maxsize=1)
def _catalogs():
    from src.infrastructure.app_bootstrap import build_module_registry, build_runtime_catalogs  # noqa: PLC0415

    return build_runtime_catalogs(build_module_registry())


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _adr_schema(repo: Path, section_templates: str = "") -> None:
    templates_field = f',\n  "section_templates": {section_templates}' if section_templates else ""
    base = (
        '{\n  "abbreviation": "ADR",\n'
        '  "required_sections": ["Context", "Decision", "Consequences"]'
    )
    _write(repo / ".arch-repo" / "documents" / "adr.json", f"{base}{templates_field}\n}}\n")


def _verifier(repo: Path) -> ArtifactVerifier:
    return ArtifactVerifier(ArtifactRegistry(shared_artifact_index(repo)), catalogs=_catalogs())


# ── pure unit: _build_placeholder_body ─────────────────────────────────────

class TestBuildPlaceholderBody:
    def test_no_templates_uses_comment_placeholder(self) -> None:
        result = _build_placeholder_body(["Context", "Decision"])
        assert "## Context" in result
        assert "<!-- Add content here -->" in result

    def test_section_with_template_uses_template_body(self) -> None:
        templates = {"Context": "Describe the problem here.\n", "Decision": "Describe the decision.\n"}
        result = _build_placeholder_body(["Context", "Decision"], templates)
        assert "## Context\n\nDescribe the problem here." in result
        assert "## Decision\n\nDescribe the decision." in result
        assert "<!-- Add content here -->" not in result

    def test_partial_template_mixes_template_and_placeholder(self) -> None:
        templates = {"Decision": "Describe the decision.\n"}
        result = _build_placeholder_body(["Context", "Decision", "Consequences"], templates)
        assert "## Context\n\n<!-- Add content here -->" in result
        assert "## Decision\n\nDescribe the decision." in result
        assert "## Consequences\n\n<!-- Add content here -->" in result

    def test_empty_templates_dict_uses_comment_placeholder(self) -> None:
        result = _build_placeholder_body(["Context"], {})
        assert "<!-- Add content here -->" in result

    def test_template_body_is_stripped_trailing_whitespace(self) -> None:
        templates = {"Context": "Some content.   \n   "}
        result = _build_placeholder_body(["Context"], templates)
        assert "Some content." in result
        assert result.count("Some content.") == 1


# ── pure unit: _validate_section_templates ─────────────────────────────────

class TestValidateSectionTemplates:
    def test_valid_templates_pass(self) -> None:
        _validate_section_templates(
            {"Context": "foo", "Decision": "bar"},
            ["Context", "Decision", "Consequences"],
            "adr",
        )

    def test_non_dict_raises(self) -> None:
        with pytest.raises(ValueError, match="must be an object"):
            _validate_section_templates(["Context"], ["Context"], "adr")

    def test_key_not_in_required_sections_raises(self) -> None:
        with pytest.raises(ValueError, match="not in required_sections"):
            _validate_section_templates(
                {"UnknownSection": "foo"},
                ["Context", "Decision"],
                "adr",
            )

    def test_non_string_value_raises(self) -> None:
        with pytest.raises(ValueError, match="must be a string"):
            _validate_section_templates({"Context": 42}, ["Context"], "adr")  # type: ignore[arg-type]

    def test_empty_dict_is_valid(self) -> None:
        _validate_section_templates({}, ["Context", "Decision"], "adr")


# ── integration: create_document uses section_templates ────────────────────

class TestCreateDocumentSectionTemplates:
    def test_creates_body_from_section_templates_when_body_omitted(self, tmp_path: Path) -> None:
        repo = tmp_path / "engagements" / "ENG-T" / "architecture-repository"
        _adr_schema(
            repo,
            section_templates=(
                '{"Context": "Describe the context.\\n",'
                ' "Decision": "State the decision.\\n",'
                ' "Consequences": "List the consequences.\\n"}'
            ),
        )
        result = create_document(
            repo_root=repo,
            verifier=_verifier(repo),
            clear_repo_caches=lambda _: None,
            doc_type="adr",
            title="Test ADR with Templates",
            body=None,
            keywords=None,
            extra_frontmatter=None,
            artifact_id="ADR@1000000001.Test.test-adr",
            version="0.1.0",
            status="draft",
            last_updated="2026-06-19",
            dry_run=False,
        )
        assert result.wrote
        path = result.path
        assert path is not None
        content = Path(path).read_text(encoding="utf-8")
        assert "## Context\n\nDescribe the context." in content
        assert "## Decision\n\nState the decision." in content
        assert "<!-- Add content here -->" not in content

    def test_explicit_body_overrides_section_templates(self, tmp_path: Path) -> None:
        repo = tmp_path / "engagements" / "ENG-T" / "architecture-repository"
        _adr_schema(
            repo,
            section_templates='{"Context": "Template context.\\n"}',
        )
        explicit_body = (
            "## Context\n\nCustom body.\n\n"
            "## Decision\n\nCustom decision.\n\n"
            "## Consequences\n\nCustom consequences.\n"
        )
        result = create_document(
            repo_root=repo,
            verifier=_verifier(repo),
            clear_repo_caches=lambda _: None,
            doc_type="adr",
            title="Test Explicit Body",
            body=explicit_body,
            keywords=None,
            extra_frontmatter=None,
            artifact_id="ADR@1000000002.Test.explicit-body",
            version="0.1.0",
            status="draft",
            last_updated="2026-06-19",
            dry_run=False,
        )
        assert result.wrote
        content = Path(result.path).read_text(encoding="utf-8")
        assert "Custom body." in content
        assert "Template context." not in content

    def test_malformed_section_templates_in_spec_raises(self, tmp_path: Path) -> None:
        repo = tmp_path / "engagements" / "ENG-T" / "architecture-repository"
        _adr_schema(repo, section_templates='{"UnknownSection": "foo"}')
        with pytest.raises(ValueError, match="not in required_sections"):
            create_document(
                repo_root=repo,
                verifier=_verifier(repo),
                clear_repo_caches=lambda _: None,
                doc_type="adr",
                title="Bad Spec ADR",
                body=None,
                keywords=None,
                extra_frontmatter=None,
                artifact_id="ADR@1000000003.Test.bad-spec",
                version="0.1.0",
                status="draft",
                last_updated="2026-06-19",
                dry_run=False,
            )

    def test_section_without_template_falls_back_to_comment(self, tmp_path: Path) -> None:
        repo = tmp_path / "engagements" / "ENG-T" / "architecture-repository"
        _adr_schema(
            repo,
            section_templates='{"Context": "Describe the context.\\n"}',
        )
        result = create_document(
            repo_root=repo,
            verifier=_verifier(repo),
            clear_repo_caches=lambda _: None,
            doc_type="adr",
            title="Partial Templates ADR",
            body=None,
            keywords=None,
            extra_frontmatter=None,
            artifact_id="ADR@1000000004.Test.partial-templates",
            version="0.1.0",
            status="draft",
            last_updated="2026-06-19",
            dry_run=False,
        )
        assert result.wrote
        content = Path(result.path).read_text(encoding="utf-8")
        assert "## Context\n\nDescribe the context." in content
        assert "## Decision\n\n<!-- Add content here -->" in content
        assert "## Consequences\n\n<!-- Add content here -->" in content
