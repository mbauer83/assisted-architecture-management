from __future__ import annotations

from pathlib import Path

import pytest
from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]

from src.infrastructure.artifact_index import shared_artifact_index
from src.infrastructure.mcp.artifact_mcp.admin_tools import (
    artifact_admin_reindex,
    register_admin_tools,
)
from src.infrastructure.workspace.mutation_gate import GateRejected, WorkspaceMutationGate

_SHORT_ID = "APP@1712870400.Abc123"


def _write_entity(path: Path, artifact_id: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n"
        f"artifact-id: {artifact_id}\n"
        "artifact-type: application-component\n"
        "name: Payments\n"
        "version: 0.1.0\n"
        "status: draft\n"
        "---\n",
        encoding="utf-8",
    )


def test_entity_reindex_heals_out_of_band_slug_rename(tmp_path: Path) -> None:
    old_path = tmp_path / "model" / "application" / "application-component" / f"{_SHORT_ID}.old.md"
    new_path = old_path.with_name(f"{_SHORT_ID}.current.md")
    _write_entity(old_path, f"{_SHORT_ID}.old")
    index = shared_artifact_index(tmp_path)
    index.refresh()

    old_path.rename(new_path)
    _write_entity(new_path, f"{_SHORT_ID}.current")
    result = artifact_admin_reindex(scope="entity", short_id=f"{_SHORT_ID}.stale", repo_root=str(tmp_path))

    assert result["short_id"] == _SHORT_ID
    assert index.find_file_by_id(f"{_SHORT_ID}.current") == new_path
    assert index.find_file_by_id(f"{_SHORT_ID}.old") is None


def test_full_reindex_delegates_to_disk_refresh(tmp_path: Path, monkeypatch) -> None:
    calls: list[Path] = []
    monkeypatch.setattr(
        "src.infrastructure.mcp.artifact_mcp.admin_tools.sync_refresh_for_roots",
        calls.append,
    )

    result = artifact_admin_reindex(scope="full", repo_root=str(tmp_path))

    assert result["status"] == "reindexed"
    assert calls == [tmp_path.resolve()]


def test_reindex_respects_mutation_gate(tmp_path: Path, monkeypatch) -> None:
    gate = WorkspaceMutationGate()
    monkeypatch.setattr(
        "src.infrastructure.mcp.artifact_mcp.admin_tools.get_workspace_gate",
        lambda: gate,
    )

    with gate.blocking_writes("sync_in_progress"):
        with pytest.raises(GateRejected) as exc:
            artifact_admin_reindex(scope="full", repo_root=str(tmp_path))

    assert exc.value.reason == "sync_in_progress"


def test_entity_scope_requires_short_id(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="short_id is required"):
        artifact_admin_reindex(scope="entity", repo_root=str(tmp_path))


def test_admin_reindex_tool_is_registered() -> None:
    server = FastMCP(name="reindex-test")
    register_admin_tools(server)

    names = {tool.name for tool in server._tool_manager.list_tools()}  # type: ignore[attr-defined]

    assert "artifact_admin_reindex" in names
