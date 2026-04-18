"""Behavioural tests for entity and connection edit MCP tools.

Covers model_edit_entity, model_edit_connection (remove), and model_edit_diagram
via the MCP server interface, exercising dry-run and live writes.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.tools import mcp_model_server as mcp


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "engagements" / "ENG-T" / "architecture-repository"
    (root / "model").mkdir(parents=True)
    (root / "diagram-catalog" / "diagrams").mkdir(parents=True)
    return root


def _make_entity(repo: Path, artifact_type: str, name: str) -> str:
    result = mcp.model_create_entity(
        artifact_type=artifact_type, name=name,
        summary=f"Summary for {name}",
        dry_run=False, repo_root=str(repo),
    )
    assert result["wrote"], result
    return str(result["artifact_id"])


def _make_connection(repo: Path, src: str, tgt: str, conn_type: str) -> None:
    result = mcp.model_add_connection(
        source_entity=src, connection_type=conn_type,
        target_entity=tgt, dry_run=False, repo_root=str(repo),
    )
    assert result["wrote"], result


# ---------------------------------------------------------------------------
# model_edit_entity
# ---------------------------------------------------------------------------

class TestEditEntity:
    def test_dry_run_returns_preview_content(self, repo: Path) -> None:
        eid = _make_entity(repo, "requirement", "Original Name")
        result = mcp.model_edit_entity(
            artifact_id=eid, name="New Name", dry_run=True, repo_root=str(repo),
        )
        assert result["wrote"] is False
        assert "New Name" in str(result.get("content", ""))

    def test_live_edit_name_updates_file(self, repo: Path) -> None:
        eid = _make_entity(repo, "requirement", "First Name")
        result = mcp.model_edit_entity(
            artifact_id=eid, name="Updated Name", dry_run=False, repo_root=str(repo),
        )
        assert result["wrote"] is True
        path = Path(str(result["path"]))
        content = path.read_text()
        assert "Updated Name" in content
        assert "name: Updated Name" in content

    def test_edit_preserves_artifact_id(self, repo: Path) -> None:
        eid = _make_entity(repo, "requirement", "Preserve Me")
        result = mcp.model_edit_entity(
            artifact_id=eid, name="New", dry_run=False, repo_root=str(repo),
        )
        path = Path(str(result["path"]))
        assert eid in path.read_text()

    def test_edit_nonexistent_entity_raises(self, repo: Path) -> None:
        with pytest.raises(ValueError, match="not found"):
            mcp.model_edit_entity(
                artifact_id="REQ@9999999999.NoExist.ghost",
                name="X", dry_run=False, repo_root=str(repo),
            )

    def test_edit_status(self, repo: Path) -> None:
        eid = _make_entity(repo, "requirement", "Status Test")
        result = mcp.model_edit_entity(
            artifact_id=eid, status="active", dry_run=False, repo_root=str(repo),
        )
        assert result["wrote"] is True
        assert "active" in Path(str(result["path"])).read_text()

    def test_edit_keywords(self, repo: Path) -> None:
        eid = _make_entity(repo, "requirement", "KW Test")
        result = mcp.model_edit_entity(
            artifact_id=eid, keywords=["alpha", "beta"], dry_run=False, repo_root=str(repo),
        )
        assert result["wrote"] is True
        content = Path(str(result["path"])).read_text()
        assert "alpha" in content and "beta" in content

    def test_cannot_edit_global_entity_reference_directly(self, repo: Path) -> None:
        # GRF entities are auto-managed; direct creation is blocked at create_entity,
        # but we confirm the type guard is in place
        with pytest.raises(ValueError, match="global-entity-reference"):
            mcp.model_create_entity(
                artifact_type="global-entity-reference",
                name="Should Fail",
                dry_run=False, repo_root=str(repo),
            )


# ---------------------------------------------------------------------------
# model_remove_connection (via edit_tools)
# ---------------------------------------------------------------------------

class TestRemoveConnection:
    def test_dry_run_remove_returns_preview(self, repo: Path) -> None:
        src = _make_entity(repo, "application-component", "SrcApp")
        tgt = _make_entity(repo, "application-component", "TgtApp")
        _make_connection(repo, src, tgt, "archimate-serving")

        result = mcp.model_edit_connection(
            source_entity=src, connection_type="archimate-serving",
            target_entity=tgt, operation="remove", dry_run=True, repo_root=str(repo),
        )
        assert result["wrote"] is False

    def test_live_remove_deletes_connection_header(self, repo: Path) -> None:
        src = _make_entity(repo, "application-component", "SrcDel")
        tgt = _make_entity(repo, "application-component", "TgtDel")
        _make_connection(repo, src, tgt, "archimate-serving")

        result = mcp.model_edit_connection(
            source_entity=src, connection_type="archimate-serving",
            target_entity=tgt, operation="remove", dry_run=False, repo_root=str(repo),
        )
        assert result["wrote"] is True
        outgoing_path = Path(str(result["path"]))
        # File may be deleted entirely when last connection removed, or connection header absent
        if outgoing_path.exists():
            assert f"archimate-serving → {tgt}" not in outgoing_path.read_text()
        # Either way the connection is gone

    def test_remove_nonexistent_connection_raises(self, repo: Path) -> None:
        src = _make_entity(repo, "application-component", "SrcOnly")
        with pytest.raises((ValueError, Exception)):
            mcp.model_edit_connection(
                source_entity=src, connection_type="archimate-serving",
                target_entity="APP@9999999999.NoExist.ghost",
                operation="remove", dry_run=False, repo_root=str(repo),
            )


# ---------------------------------------------------------------------------
# model_edit_diagram
# ---------------------------------------------------------------------------

class TestEditDiagram:
    def _make_diagram(self, repo: Path, name: str) -> str:
        # Use activity diagram type — no archimate !include required
        puml = f"""\
@startuml test-diagram-{name.lower().replace(' ', '-')}

title {name}

:Step A;
:Step B;

@enduml
"""
        result = mcp.model_create_diagram(
            diagram_type="activity-bpmn",
            name=name, puml=puml,
            artifact_id=f"test-diagram-{name.lower().replace(' ', '-')}",
            dry_run=False, repo_root=str(repo),
        )
        assert result["wrote"], result
        return str(result["artifact_id"])

    def test_edit_diagram_name_updates_title(self, repo: Path) -> None:
        diag_id = self._make_diagram(repo, "Original Diagram")
        result = mcp.model_edit_diagram(
            artifact_id=diag_id, name="Updated Diagram",
            dry_run=False, repo_root=str(repo),
        )
        assert result["wrote"] is True
        content = Path(str(result["path"])).read_text()
        assert "Updated Diagram" in content

    def test_edit_diagram_dry_run_returns_preview(self, repo: Path) -> None:
        diag_id = self._make_diagram(repo, "Dry Run Diagram")
        result = mcp.model_edit_diagram(
            artifact_id=diag_id, name="New Title",
            dry_run=True, repo_root=str(repo),
        )
        assert result["wrote"] is False
        assert "New Title" in str(result.get("content", ""))
