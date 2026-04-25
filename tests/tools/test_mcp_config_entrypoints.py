from __future__ import annotations

import json
from pathlib import Path

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
