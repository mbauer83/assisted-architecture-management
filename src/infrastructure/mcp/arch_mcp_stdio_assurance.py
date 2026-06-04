"""STDIO bridge for the assurance MCP servers.

Wraps arch-assurance-read and arch-assurance-write as STDIO transports
(for use with Claude Desktop / claude.ai MCP config).
"""

from __future__ import annotations


def main_read() -> None:
    from src.infrastructure.mcp.mcp_assurance_server import mcp_assurance_read  # noqa: PLC0415

    mcp_assurance_read.run(transport="stdio")


def main_write() -> None:
    from src.infrastructure.mcp.mcp_assurance_server import mcp_assurance_write  # noqa: PLC0415

    mcp_assurance_write.run(transport="stdio")


if __name__ == "__main__":
    main_read()
