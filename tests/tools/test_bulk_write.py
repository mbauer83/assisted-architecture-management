"""Tests for artifact_bulk_write.

Covers: happy-path creates and connections, $ref substitution, auto-ordering
(connections submitted before entities still resolve), edit operations, error
isolation (one failure does not abort remaining items), content suppression,
dependency conflicts (duplicate connections, failed-ref propagation), and
dry-run coherence.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.infrastructure.mcp.artifact_mcp.bulk_tools import artifact_bulk_delete, artifact_bulk_write
from src.infrastructure.mcp import mcp_artifact_server as mcp
from src.application.verification.artifact_verifier import ArtifactRegistry, ArtifactVerifier
from src.infrastructure.artifact_index import shared_artifact_index


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------

@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "engagements" / "ENG-T" / "architecture-repository"
    (root / "model").mkdir(parents=True)
    (root / "diagram-catalog" / "diagrams").mkdir(parents=True)
    return root


def _make(repo: Path, artifact_type: str, name: str) -> str:
    r = mcp.artifact_create_entity(artifact_type=artifact_type, name=name,
                                   dry_run=False, repo_root=str(repo))
    assert r["wrote"], r
    return str(r["artifact_id"])


def _connect(repo: Path, src: str, tgt: str, conn_type: str) -> None:
    mcp.artifact_add_connection(source_entity=src, connection_type=conn_type,
                                target_entity=tgt, dry_run=False, repo_root=str(repo))


def _bulk(repo: Path, items, *, dry_run: bool = False):
    return artifact_bulk_write(items=items, dry_run=dry_run, repo_root=str(repo))


def _bulk_delete(repo: Path, items, *, dry_run: bool = False):
    return artifact_bulk_delete(items=items, dry_run=dry_run, repo_root=str(repo))


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Happy path — entity creates
# ---------------------------------------------------------------------------

class TestBulkCreate:
    def test_single_entity_live(self, repo: Path) -> None:
        results = _bulk(repo, [
            {"op": "create_entity", "artifact_type": "requirement", "name": "R1"},
        ])
        assert len(results) == 1
        assert results[0]["wrote"] is True
        assert results[0]["op"] == "create_entity"
        assert Path(str(results[0]["path"])).exists()

    def test_multiple_entities_live(self, repo: Path) -> None:
        results = _bulk(repo, [
            {"op": "create_entity", "artifact_type": "requirement", "name": "Ra"},
            {"op": "create_entity", "artifact_type": "outcome", "name": "Ob"},
            {"op": "create_entity", "artifact_type": "goal", "name": "Gc"},
        ])
        assert all(r["wrote"] is True for r in results)
        assert all(Path(str(r["path"])).exists() for r in results)

    def test_dry_run_does_not_write_files(self, repo: Path) -> None:
        results = _bulk(repo, [
            {"op": "create_entity", "artifact_type": "requirement", "name": "DryR"},
        ], dry_run=True)
        assert results[0]["wrote"] is False
        assert not Path(str(results[0]["path"])).exists()

    def test_dry_run_still_assigns_artifact_id(self, repo: Path) -> None:
        results = _bulk(repo, [
            {"op": "create_entity", "artifact_type": "outcome", "name": "DryId"},
        ], dry_run=True)
        assert results[0]["artifact_id"]


# ---------------------------------------------------------------------------
# $ref substitution
# ---------------------------------------------------------------------------

class TestRefSubstitution:
    def test_ref_creates_connection_between_batch_entities(self, repo: Path) -> None:
        results = _bulk(repo, [
            {"op": "create_entity", "artifact_type": "goal", "name": "G", "_ref": "g"},
            {"op": "create_entity", "artifact_type": "requirement", "name": "R", "_ref": "r"},
            {"op": "add_connection", "source_entity": "$ref:g",
             "connection_type": "archimate-influence", "target_entity": "$ref:r"},
        ])
        assert all("error" not in res for res in results), results
        assert all(res["wrote"] is True for res in results)

    def test_connection_path_contains_source_entity_id(self, repo: Path) -> None:
        results = _bulk(repo, [
            {"op": "create_entity", "artifact_type": "goal", "name": "Src", "_ref": "src"},
            {"op": "create_entity", "artifact_type": "outcome", "name": "Tgt", "_ref": "tgt"},
            {"op": "add_connection", "source_entity": "$ref:src",
             "connection_type": "archimate-realization", "target_entity": "$ref:tgt"},
        ])
        src_id = str(results[0]["artifact_id"])
        conn_path = str(results[2]["path"])
        assert src_id in conn_path

    def test_dry_run_ref_is_substituted_even_if_connection_fails_validation(
        self, repo: Path
    ) -> None:
        """In dry_run, entity creates don't write to disk, so connection validation
        will reject the source as 'not found'. The ref IS substituted though — the error
        mentions the artifact_id, not the literal '$ref:' string."""
        results = _bulk(repo, [
            {"op": "create_entity", "artifact_type": "driver", "name": "D", "_ref": "d"},
            {"op": "add_connection", "source_entity": "$ref:d",
             "connection_type": "archimate-association", "target_entity": "$ref:d"},
        ], dry_run=True)
        assert results[0]["wrote"] is False  # entity dry_run, not written
        # Connection may fail because entity isn't in the model, but ref was resolved
        if "error" in results[1]:
            assert "$ref:" not in results[1]["error"], "ref was not substituted"

    def test_unresolved_ref_returns_error_not_exception(self, repo: Path) -> None:
        results = _bulk(repo, [
            {"op": "add_connection", "source_entity": "$ref:missing",
             "connection_type": "archimate-serving", "target_entity": "$ref:also_missing"},
        ])
        assert "error" in results[0]
        assert "missing" in results[0]["error"]


# ---------------------------------------------------------------------------
# Auto-ordering (connections before entities in input)
# ---------------------------------------------------------------------------

class TestAutoOrdering:
    def test_connection_listed_first_still_resolves(self, repo: Path) -> None:
        results = _bulk(repo, [
            {"op": "add_connection", "source_entity": "$ref:comp",
             "connection_type": "archimate-serving", "target_entity": "$ref:svc"},
            {"op": "create_entity", "artifact_type": "application-component",
             "name": "Comp", "_ref": "comp"},
            {"op": "create_entity", "artifact_type": "service",
             "name": "Svc", "_ref": "svc"},
        ])
        assert all("error" not in res for res in results), results
        assert all(res["wrote"] is True for res in results)

    def test_results_maintain_input_order(self, repo: Path) -> None:
        results = _bulk(repo, [
            {"op": "add_connection", "source_entity": "$ref:g",
             "connection_type": "archimate-association", "target_entity": "$ref:g"},
            {"op": "create_entity", "artifact_type": "goal", "name": "G", "_ref": "g"},
            {"op": "create_entity", "artifact_type": "assessment", "name": "A"},
        ])
        assert results[0]["op"] == "add_connection"
        assert results[1]["op"] == "create_entity"
        assert results[2]["op"] == "create_entity"

    def test_edits_run_after_creates(self, repo: Path) -> None:
        """Edits on pre-existing entities should succeed even when mixed with creates."""
        existing = _make(repo, "requirement", "Pre-existing")
        results = _bulk(repo, [
            {"op": "edit_entity", "artifact_id": existing, "summary": "Batch edit"},
            {"op": "create_entity", "artifact_type": "outcome", "name": "New"},
        ])
        assert results[0]["op"] == "edit_entity"
        assert results[0]["wrote"] is True
        assert results[1]["op"] == "create_entity"
        assert results[1]["wrote"] is True


# ---------------------------------------------------------------------------
# Content suppression
# ---------------------------------------------------------------------------

class TestContentSuppression:
    def test_no_content_in_dry_run_results(self, repo: Path) -> None:
        results = _bulk(repo, [
            {"op": "create_entity", "artifact_type": "requirement", "name": "NC"},
        ], dry_run=True)
        assert "content" not in results[0]

    def test_no_content_in_live_write_results(self, repo: Path) -> None:
        results = _bulk(repo, [
            {"op": "create_entity", "artifact_type": "outcome", "name": "NCL"},
        ])
        assert "content" not in results[0]


# ---------------------------------------------------------------------------
# Error handling and isolation
# ---------------------------------------------------------------------------

class TestErrorHandling:
    def test_unknown_op_returns_error_result(self, repo: Path) -> None:
        results = _bulk(repo, [{"op": "do_magic"}])
        assert "error" in results[0]
        assert results[0]["wrote"] is False

    def test_partial_failure_does_not_abort_later_items(self, repo: Path) -> None:
        results = _bulk(repo, [
            {"op": "create_entity", "artifact_type": "not-a-real-type", "name": "Bad"},
            {"op": "create_entity", "artifact_type": "requirement", "name": "Good"},
        ])
        assert "error" in results[0] or results[0]["wrote"] is False
        assert results[1]["wrote"] is True

    def test_missing_required_name_field_returns_error(self, repo: Path) -> None:
        results = _bulk(repo, [
            {"op": "create_entity", "artifact_type": "requirement"},  # missing name
        ])
        assert "error" in results[0]

    def test_connection_to_nonexistent_entity_fails_gracefully(self, repo: Path) -> None:
        results = _bulk(repo, [
            {"op": "add_connection",
             "source_entity": "REQ@0000000000.XXXXXX.ghost",
             "connection_type": "archimate-realization",
             "target_entity": "OUT@0000000000.YYYYYY.ghost"},
        ])
        assert "error" in results[0] or results[0]["wrote"] is False

    def test_failed_create_ref_causes_connection_error(self, repo: Path) -> None:
        """$ref: from a failed create has no ID to resolve — connection must error."""
        results = _bulk(repo, [
            {"op": "create_entity", "artifact_type": "bad-type", "name": "Bad", "_ref": "bad"},
            {"op": "add_connection", "source_entity": "$ref:bad",
             "connection_type": "archimate-serving", "target_entity": "$ref:bad"},
        ])
        assert "error" in results[0] or results[0]["wrote"] is False
        assert "error" in results[1]

    def test_edit_nonexistent_entity_returns_error(self, repo: Path) -> None:
        results = _bulk(repo, [
            {"op": "edit_entity", "artifact_id": "REQ@9999999999.NoExist.ghost",
             "summary": "Should fail"},
        ])
        assert "error" in results[0]


# ---------------------------------------------------------------------------
# Edit operations
# ---------------------------------------------------------------------------

class TestBulkEdits:
    def test_edit_entity_summary(self, repo: Path) -> None:
        eid = _make(repo, "requirement", "Before Edit")
        results = _bulk(repo, [
            {"op": "edit_entity", "artifact_id": eid, "summary": "Updated via bulk"},
        ])
        assert results[0]["wrote"] is True
        assert "Updated via bulk" in Path(str(results[0]["path"])).read_text()

    def test_remove_connection(self, repo: Path) -> None:
        src = _make(repo, "goal", "RemSrc")
        tgt = _make(repo, "requirement", "RemTgt")
        _connect(repo, src, tgt, "archimate-influence")
        results = _bulk(repo, [
            {"op": "edit_connection", "source_entity": src, "target_entity": tgt,
             "connection_type": "archimate-influence", "operation": "remove"},
        ])
        assert results[0]["wrote"] is True

    def test_dry_run_edit_does_not_write(self, repo: Path) -> None:
        eid = _make(repo, "outcome", "Dry Edit")
        results = _bulk(repo, [
            {"op": "edit_entity", "artifact_id": eid, "summary": "Not written"},
        ], dry_run=True)
        assert results[0]["wrote"] is False
        assert "Not written" not in Path(str(results[0]["path"])).read_text()


# ---------------------------------------------------------------------------
# Conflict and dependency scenarios
# ---------------------------------------------------------------------------

class TestConflictsAndDependencies:
    def test_duplicate_connection_second_is_idempotent_or_errors(self, repo: Path) -> None:
        src = _make(repo, "requirement", "DupSrc")
        tgt = _make(repo, "outcome", "DupTgt")
        results = _bulk(repo, [
            {"op": "add_connection", "source_entity": src,
             "connection_type": "archimate-realization", "target_entity": tgt},
            {"op": "add_connection", "source_entity": src,
             "connection_type": "archimate-realization", "target_entity": tgt},
        ])
        assert len(results) == 2
        assert results[0]["wrote"] is True
        # Second must not raise; outcome is idempotent success or graceful error
        assert "wrote" in results[1] or "error" in results[1]

    def test_same_ref_used_in_multiple_connections(self, repo: Path) -> None:
        """One entity can be both source and target of multiple connections via the same ref."""
        results = _bulk(repo, [
            {"op": "create_entity", "artifact_type": "driver", "name": "Hub", "_ref": "hub"},
            {"op": "create_entity", "artifact_type": "assessment", "name": "A1", "_ref": "a1"},
            {"op": "create_entity", "artifact_type": "assessment", "name": "A2", "_ref": "a2"},
            {"op": "add_connection", "source_entity": "$ref:hub",
             "connection_type": "archimate-association", "target_entity": "$ref:a1"},
            {"op": "add_connection", "source_entity": "$ref:hub",
             "connection_type": "archimate-association", "target_entity": "$ref:a2"},
        ])
        assert all("error" not in res for res in results), results
        assert all(res["wrote"] is True for res in results)

    def test_large_batch_all_succeed(self, repo: Path) -> None:
        """Batches larger than the old 8-item parallel limit should complete correctly."""
        items = [
            {"op": "create_entity", "artifact_type": "requirement",
             "name": f"Req{i}", "_ref": f"r{i}"}
            for i in range(12)
        ]
        items += [
            {"op": "add_connection", "source_entity": f"$ref:r{i}",
             "connection_type": "archimate-association",
             "target_entity": f"$ref:r{(i + 1) % 12}"}
            for i in range(12)
        ]
        results = _bulk(repo, items)
        assert len(results) == 24
        errors = [r for r in results if "error" in r]
        assert not errors, errors


# ---------------------------------------------------------------------------
# Bulk delete
# ---------------------------------------------------------------------------

class TestBulkDelete:
    def test_delete_connection_document_diagram_and_entity_batch(self, repo: Path) -> None:
        src = _make(repo, "requirement", "DeleteSrc")
        tgt = _make(repo, "outcome", "DeleteTgt")
        _connect(repo, src, tgt, "archimate-realization")

        doc_id = "ADR@1000000001.AbcDef.to-delete"
        _write(
            repo / "docs" / "adr" / f"{doc_id}.md",
            """\
---
artifact-id: ADR@1000000001.AbcDef.to-delete
artifact-type: document
doc-type: adr
title: "Delete Me"
status: draft
version: 0.1.0
last-updated: '2026-04-27'
---

## Context

Delete me.
""",
        )

        diag_id = "bulk-delete-diagram"
        diag_path = repo / "diagram-catalog" / "diagrams" / f"{diag_id}.puml"
        _write(
            diag_path,
            f"""\
---
artifact-id: {diag_id}
artifact-type: diagram
diagram-type: archimate-application
name: "Bulk Delete Diagram"
entity-ids-used:
  - {src}
connection-ids-used:
  - {src} archimate-realization → {tgt}
version: 0.1.0
status: active
last-updated: '2026-04-27'
---
@startuml
Alice -> Bob
@enduml
""",
        )
        _write(repo / "diagram-catalog" / "rendered" / f"{diag_id}.png", "png")

        payload = _bulk_delete(
            repo,
            [
                {
                    "op": "delete_connection",
                    "source_entity": src,
                    "connection_type": "archimate-realization",
                    "target_entity": tgt,
                },
                {"op": "delete_document", "artifact_id": doc_id},
                {"op": "delete_diagram", "artifact_id": diag_id},
                {"op": "delete_entity", "artifact_id": src},
                {"op": "delete_entity", "artifact_id": tgt},
            ],
        )

        results = payload["results"]
        assert all("error" not in item for item in results), payload
        assert all(item["wrote"] is True for item in results)
        assert payload["batch_verification"]["valid"] is True

        verifier = ArtifactVerifier(ArtifactRegistry(shared_artifact_index(repo)))
        assert all(r.valid for r in verifier.verify_all(repo)), "repo should verify after batch delete"

    def test_delete_entity_requires_diagram_delete_in_same_batch(self, repo: Path) -> None:
        eid = _make(repo, "requirement", "DiagramBlocked")
        diag_id = "diagram-blocker"
        _write(
            repo / "diagram-catalog" / "diagrams" / f"{diag_id}.puml",
            f"""\
---
artifact-id: {diag_id}
artifact-type: diagram
diagram-type: archimate-application
name: "Diagram Blocker"
entity-ids-used:
  - {eid}
version: 0.1.0
status: active
last-updated: '2026-04-27'
---
@startuml
Alice -> Bob
@enduml
""",
        )

        payload = _bulk_delete(repo, [{"op": "delete_entity", "artifact_id": eid}], dry_run=True)
        assert payload["batch_verification"]["valid"] is False
        assert "diagram must also be deleted" in payload["results"][0]["error"]

    def test_delete_entities_with_internal_cycle_succeeds_via_implicit_connection_cleanup(
        self, repo: Path
    ) -> None:
        left = _make(repo, "goal", "Left")
        right = _make(repo, "requirement", "Right")
        _connect(repo, left, right, "archimate-influence")
        _connect(repo, right, left, "archimate-association")

        payload = _bulk_delete(
            repo,
            [
                {"op": "delete_entity", "artifact_id": left},
                {"op": "delete_entity", "artifact_id": right},
            ],
        )

        assert all("error" not in item for item in payload["results"]), payload
        implicit = payload["batch_verification"]["implicit_connection_deletes"]
        assert len(implicit) == 2
        assert payload["batch_verification"]["valid"] is True

    def test_delete_entity_blocked_by_external_incoming_connection(self, repo: Path) -> None:
        src = _make(repo, "goal", "ExternalSrc")
        tgt = _make(repo, "requirement", "BlockedTgt")
        _connect(repo, src, tgt, "archimate-influence")

        payload = _bulk_delete(
            repo,
            [{"op": "delete_entity", "artifact_id": tgt}],
            dry_run=True,
        )

        assert payload["batch_verification"]["valid"] is False
        assert "incoming connection must also be deleted" in payload["results"][0]["error"]
