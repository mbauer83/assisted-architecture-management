from __future__ import annotations

from pathlib import Path

from src.application.verification.artifact_verifier import ArtifactRegistry, ArtifactVerifier
from src.infrastructure.artifact_index import shared_artifact_index
from src.infrastructure.write.artifact_write.document import create_document, edit_document


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _schema(repo: Path, *, subdirectory: str | None = None) -> None:
    subdirectory_field = f',\n  "subdirectory": "{subdirectory}"' if subdirectory is not None else ""
    _write(
        repo / ".arch-repo" / "documents" / "adr.json",
        """\
{
  "abbreviation": "ADR",
  "name": "Architecture Decision Record"%s,
  "required_sections": ["Context", "Decision", "Consequences"]
}
""" % subdirectory_field,
    )


def _verifier(repo: Path) -> ArtifactVerifier:
    return ArtifactVerifier(ArtifactRegistry(shared_artifact_index(repo)))


def test_create_document_uses_schema_subdirectory(tmp_path: Path) -> None:
    repo = tmp_path / "engagements" / "ENG-T" / "architecture-repository"
    _schema(repo, subdirectory="decisions/adr")

    result = create_document(
        repo_root=repo,
        verifier=_verifier(repo),
        clear_repo_caches=lambda _path: None,
        doc_type="adr",
        title="Adopt Structured Document Paths",
        body=None,
        keywords=None,
        extra_frontmatter=None,
        artifact_id="ADR@1000000000.AbcDef.structured-paths",
        version="0.1.0",
        status="draft",
        last_updated="2026-04-22",
        dry_run=False,
    )

    assert result.path == repo / "docs" / "decisions" / "adr" / "ADR@1000000000.AbcDef.structured-paths.md"
    assert result.path.exists()


def test_create_document_defaults_subdirectory_to_doc_type(tmp_path: Path) -> None:
    repo = tmp_path / "engagements" / "ENG-T" / "architecture-repository"
    _schema(repo)

    result = create_document(
        repo_root=repo,
        verifier=_verifier(repo),
        clear_repo_caches=lambda _path: None,
        doc_type="adr",
        title="Fallback Directory",
        body=None,
        keywords=None,
        extra_frontmatter=None,
        artifact_id="ADR@1000000001.AbcDef.fallback-directory",
        version="0.1.0",
        status="draft",
        last_updated="2026-04-22",
        dry_run=False,
    )

    assert result.path == repo / "docs" / "adr" / "ADR@1000000001.AbcDef.fallback-directory.md"
    assert result.path.exists()


def test_create_document_refuses_missing_required_section(tmp_path: Path) -> None:
    repo = tmp_path / "engagements" / "ENG-T" / "architecture-repository"
    _schema(repo)

    result = create_document(
        repo_root=repo,
        verifier=_verifier(repo),
        clear_repo_caches=lambda _path: None,
        doc_type="adr",
        title="Missing Sections",
        body="## Context\n\nOnly context.\n",
        keywords=None,
        extra_frontmatter=None,
        artifact_id="ADR@1000000002.AbcDef.missing-sections",
        version="0.1.0",
        status="draft",
        last_updated="2026-04-22",
        dry_run=False,
    )

    assert result.wrote is False
    assert any(issue["code"] == "E154" for issue in result.verification["issues"])
    assert not result.path.exists()


def test_create_document_refuses_broken_internal_reference(tmp_path: Path) -> None:
    repo = tmp_path / "engagements" / "ENG-T" / "architecture-repository"
    _schema(repo)

    result = create_document(
        repo_root=repo,
        verifier=_verifier(repo),
        clear_repo_caches=lambda _path: None,
        doc_type="adr",
        title="Broken Reference",
        body=(
            "## Context\n\nSee [Missing](../spec/NOPE.md).\n\n"
            "## Decision\n\nDecision.\n\n"
            "## Consequences\n\nConsequences.\n"
        ),
        keywords=None,
        extra_frontmatter=None,
        artifact_id="ADR@1000000003.AbcDef.broken-reference",
        version="0.1.0",
        status="draft",
        last_updated="2026-04-22",
        dry_run=False,
    )

    assert result.wrote is False
    assert any(issue["code"] == "W155" for issue in result.verification["issues"])
    assert not result.path.exists()


def test_edit_document_refuses_invalid_update(tmp_path: Path) -> None:
    repo = tmp_path / "engagements" / "ENG-T" / "architecture-repository"
    _schema(repo)

    created = create_document(
        repo_root=repo,
        verifier=_verifier(repo),
        clear_repo_caches=lambda _path: None,
        doc_type="adr",
        title="Editable ADR",
        body=None,
        keywords=None,
        extra_frontmatter=None,
        artifact_id="ADR@1000000004.AbcDef.editable-adr",
        version="0.1.0",
        status="draft",
        last_updated="2026-04-22",
        dry_run=False,
    )
    assert created.wrote is True

    original = created.path.read_text(encoding="utf-8")
    result = edit_document(
        repo_root=repo,
        verifier=_verifier(repo),
        clear_repo_caches=lambda _path: None,
        artifact_id="ADR@1000000004.AbcDef.editable-adr",
        title=None,
        body="## Context\n\nInvalid update.\n",
        keywords=None,
        extra_frontmatter=None,
        status=None,
        version=None,
        last_updated="2026-04-23",
        dry_run=False,
    )

    assert result.wrote is False
    assert any(issue["code"] == "E154" for issue in result.verification["issues"])
    assert created.path.read_text(encoding="utf-8") == original
