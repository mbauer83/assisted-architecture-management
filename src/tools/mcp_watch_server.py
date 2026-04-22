"""Standalone MCP server exposing model watcher lifecycle tools.

Add this server alongside arch-mcp-model in your MCP config when agents
need explicit watcher lifecycle control (start/stop/status) or manual
cache refresh.  The main model server auto-starts the watcher at startup;
this server is optional and can be omitted when lifecycle control is not needed.

.mcp.json example:
    "arch-watch": {
        "command": "uv",
        "args": ["run", "arch-mcp-watch", "--transport", "stdio"]
    }
"""

import argparse
import os

from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]

from src.tools.model_mcp import install_call_tool_normalizer, register_watch_tools


mcp = FastMCP(
    name="arch_model_watch",
    instructions=(
        "Watcher lifecycle tools for the architecture model MCP server. "
        "Use model_tools_watch(action=start|stop|status) to control the file watcher, "
        "and model_tools_refresh to manually re-index after file changes. "
        "The main model server (arch-mcp-model) starts the watcher automatically; "
        "register this server only when explicit lifecycle control is required."
    ),
    host=os.getenv("ARCH_MCP_HOST", "127.0.0.1"),
    port=int(os.getenv("ARCH_MCP_WATCH_PORT", "8001")),
    log_level=os.getenv("ARCH_MCP_LOG_LEVEL", "INFO"),  # type: ignore[arg-type]
)

install_call_tool_normalizer(mcp)
register_watch_tools(mcp)


def main() -> None:
    parser = argparse.ArgumentParser(prog="arch-mcp-watch")
    parser.add_argument(
        "--transport",
        choices=("stdio", "streamable-http"),
        default=os.getenv("ARCH_MCP_TRANSPORT", "stdio"),
    )
    args = parser.parse_args()
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
