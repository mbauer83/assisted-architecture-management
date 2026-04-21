"""STDIO bridge that connects local MCP clients to the unified HTTP backend."""

from __future__ import annotations

import argparse
import logging
import os

import anyio
from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream

from mcp.client.streamable_http import streamablehttp_client
from mcp.server.stdio import stdio_server
from mcp.shared.message import SessionMessage

from src.tools.backend_runtime import backend_url, configured_backend_url, ensure_backend_running


logger = logging.getLogger(__name__)


async def _pump_reader_to_writer(
    read_stream: MemoryObjectReceiveStream[SessionMessage | Exception],
    write_stream: MemoryObjectSendStream[SessionMessage],
) -> None:
    async with read_stream, write_stream:
        async for message in read_stream:
            if isinstance(message, Exception):
                raise message
            await write_stream.send(message)


async def _run_bridge(url: str) -> None:
    async with stdio_server() as (local_read, local_write):
        async with streamablehttp_client(url) as (remote_read, remote_write, _get_session_id):
            async with anyio.create_task_group() as tg:
                tg.start_soon(_pump_reader_to_writer, local_read, remote_write)
                tg.start_soon(_pump_reader_to_writer, remote_read, local_write)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="arch-mcp-stdio")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-autostart", action="store_true", default=False)
    args = parser.parse_args(argv)

    port = ensure_backend_running(port=args.port, start_if_missing=not args.no_autostart)
    target_base = configured_backend_url() or backend_url(port)
    anyio.run(_run_bridge, f"{target_base}/mcp")


if __name__ == "__main__":
    main()
