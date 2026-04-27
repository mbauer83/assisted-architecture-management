from __future__ import annotations

import json
from pathlib import Path

from src.infrastructure.mcp.mcp_artifact_server import mcp_read, mcp_write

ROOT = Path(__file__).resolve().parents[2]


def _load_json(relative_path: str) -> dict:
    return json.loads((ROOT / relative_path).read_text(encoding="utf-8"))


def test_checked_in_mcp_configs_use_supported_stdio_entrypoints() -> None:
    supported = {"arch-mcp-stdio-read", "arch-mcp-stdio-write"}

    claude_config = _load_json(".mcp.json")
    vscode_config = _load_json(".vscode/mcp.json")

    claude_args = {tuple(server["args"]) for server in claude_config["mcpServers"].values()}
    vscode_args = {tuple(server["args"]) for server in vscode_config["servers"].values()}

    assert claude_args == {("run", command) for command in supported}
    assert vscode_args == {("run", command) for command in supported}


def test_read_server_tools_are_marked_read_only() -> None:
    tools = {tool.name: tool for tool in mcp_read._tool_manager.list_tools()}  # type: ignore[attr-defined]

    for name, tool in tools.items():
        ann = tool.annotations
        assert ann is not None, name
        assert ann.readOnlyHint is True, name
        assert ann.destructiveHint is False, name
        assert ann.idempotentHint is True, name
        assert ann.openWorldHint is False, name


def test_write_server_catalog_and_guidance_are_read_only_yaml_tools() -> None:
    tools = {tool.name: tool for tool in mcp_write._tool_manager.list_tools()}  # type: ignore[attr-defined]

    for name in ("artifact_write_help", "artifact_write_modeling_guidance"):
        tool = tools[name]
        ann = tool.annotations
        assert ann is not None, name
        assert ann.readOnlyHint is True, name
        assert ann.destructiveHint is False, name
        assert ann.idempotentHint is True, name
        assert ann.openWorldHint is False, name
        assert tool.fn_metadata.output_schema is None, name


def test_write_server_mutation_tool_annotations_match_expected_intent() -> None:
    tools = {tool.name: tool for tool in mcp_write._tool_manager.list_tools()}  # type: ignore[attr-defined]

    expected = {
        "artifact_create_entity": (False, False, False, False),
        "artifact_add_connection": (False, False, False, False),
        "artifact_create_matrix": (False, False, False, False),
        "artifact_create_diagram": (False, False, False, False),
        "artifact_create_document": (False, False, False, False),
        "artifact_edit_document": (False, False, False, False),
        "artifact_edit_entity": (False, False, False, False),
        "artifact_edit_connection": (False, True, False, False),
        "artifact_edit_diagram": (False, False, False, False),
        "artifact_edit_connection_associations": (False, False, False, False),
        "artifact_bulk_write": (False, False, False, False),
        "artifact_bulk_delete": (False, True, False, False),
        "artifact_promote_to_enterprise": (False, True, False, False),
        "artifact_save_changes": (False, False, False, True),
        "artifact_submit_for_review": (False, False, False, True),
        "artifact_withdraw_changes": (False, True, False, False),
    }

    for name, (read_only, destructive, idempotent, open_world) in expected.items():
        tool = tools[name]
        ann = tool.annotations
        assert ann is not None, name
        assert ann.readOnlyHint is read_only, name
        assert ann.destructiveHint is destructive, name
        assert ann.idempotentHint is idempotent, name
        assert ann.openWorldHint is open_world, name
