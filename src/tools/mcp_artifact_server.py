"""MCP server exposing artifact tools (query + verification + write).

Tool logic lives in:
- src/tools/artifact_mcp/*_tools.py (MCP tool wrappers)
- src/common/* (domain logic)
- src/tools/artifact_write/* (writer I/O operations)
"""

import argparse
import logging
import os

from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]

from src.tools.artifact_mcp import (
    auto_start_default_watcher,
    register_edit_tools,
    register_query_tools,
    register_verify_tools,
    register_write_tools,
)

# Re-export tool functions for direct calling in tests.
from src.tools.artifact_mcp.write_tools import (  # noqa: F401
    artifact_add_connection,
    artifact_create_diagram,
    artifact_create_document,
    artifact_create_entity,
    artifact_create_matrix,
    artifact_delete_document,
    artifact_edit_document,
    artifact_promote_to_enterprise,
    artifact_write_help,
)
from src.tools.artifact_mcp.edit_tools import (  # noqa: F401
    artifact_delete_diagram,
    artifact_delete_entity,
    artifact_edit_connection,
    artifact_edit_connection_associations,
    artifact_edit_diagram,
    artifact_edit_entity,
)
from src.tools.artifact_mcp.verify_tools import (  # noqa: F401
    artifact_verify,
    artifact_verify_all,
    artifact_verify_file,
)


logger = logging.getLogger(__name__)

_INSTRUCTIONS = (
    "Architecture repository artifact query + verifier + writer tools. "
    "Targets an ArchiMate NEXT architecture repository (model/, diagram-catalog/, documents/). "
    "By default mounts both engagement repo + enterprise repo; use repo_scope to restrict."
)

_HOST = os.getenv("ARCH_MCP_HOST", "127.0.0.1")
_PORT = int(os.getenv("ARCH_MCP_PORT", "8000"))
_LOG_LEVEL = os.getenv("ARCH_MCP_LOG_LEVEL", "INFO")
_SERVER_NAME = os.getenv("ARCH_MCP_SERVER_NAME", "arch_artifacts")
_MOUNT_PATH = os.getenv("ARCH_MCP_MOUNT_PATH", "/")
_SSE_PATH = os.getenv("ARCH_MCP_SSE_PATH", "/sse")
_MESSAGE_PATH = os.getenv("ARCH_MCP_MESSAGE_PATH", "/messages/")
_STREAMABLE_HTTP_PATH = os.getenv("ARCH_MCP_STREAMABLE_HTTP_PATH", "/mcp")
_JSON_RESPONSE = os.getenv("ARCH_MCP_JSON_RESPONSE", "1") in {"1", "true", "TRUE", "yes", "YES"}
_STATELESS_HTTP = os.getenv("ARCH_MCP_STATELESS_HTTP", "1") in {"1", "true", "TRUE", "yes", "YES"}
_WATCH_AUTO_START = os.getenv("ARCH_MCP_WATCH_AUTO_START", "1") in {"1", "true", "TRUE", "yes", "YES"}
_WATCH_INTERVAL_S = float(os.getenv("ARCH_MCP_WATCH_INTERVAL_S", "2.0"))
_WATCH_SCOPE = os.getenv("ARCH_MCP_WATCH_SCOPE", "both")
_WATCH_PERIODIC_RAW = os.getenv("ARCH_MCP_WATCH_PERIODIC_REFRESH_S", "300")
_WATCH_PERIODIC_S: float | None = (
    None if _WATCH_PERIODIC_RAW.lower() in ("0", "off", "disabled")
    else float(_WATCH_PERIODIC_RAW)
)


mcp = FastMCP(
    name=_SERVER_NAME,
    instructions=_INSTRUCTIONS,
    host=_HOST,
    port=_PORT,
    mount_path=_MOUNT_PATH,
    sse_path=_SSE_PATH,
    message_path=_MESSAGE_PATH,
    streamable_http_path=_STREAMABLE_HTTP_PATH,
    json_response=_JSON_RESPONSE,
    stateless_http=_STATELESS_HTTP,
    log_level=_LOG_LEVEL,  # type: ignore[arg-type]
)

register_query_tools(mcp)
register_verify_tools(mcp)
register_write_tools(mcp)
register_edit_tools(mcp)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="arch-mcp-artifacts")
    parser.add_argument(
        "--transport",
        choices=("stdio", "streamable-http"),
        default=os.getenv("ARCH_MCP_TRANSPORT", "stdio"),
    )
    parser.add_argument(
        "--standalone-stdio",
        action="store_true",
        default=os.getenv("ARCH_MCP_STANDALONE_STDIO", "0") in {"1", "true", "TRUE", "yes", "YES"},
    )
    args = parser.parse_args(argv)

    if args.transport == "streamable-http":
        from src.tools.arch_backend import main as backend_main
        backend_main([])
        return

    if args.transport == "stdio" and not args.standalone_stdio:
        from src.tools.arch_mcp_stdio import main as bridge_main
        bridge_main(["--port", str(_PORT)])
        return

    from src.tools.workspace_init import load_init_state
    state = load_init_state()
    if state:
        logger.info("arch-init state: engagement=%s enterprise=%s",
                    state.get("engagement_root"), state.get("enterprise_root"))
    else:
        repo_root_env = os.getenv("ARCH_MCP_MODEL_REPO_ROOT")
        if not repo_root_env:
            logger.warning(
                "No .arch/init-state.yaml found and ARCH_MCP_MODEL_REPO_ROOT not set. "
                "Run `arch-init` to configure workspace repos."
            )

    if _WATCH_AUTO_START:
        try:
            watch_result = auto_start_default_watcher(
                interval_s=_WATCH_INTERVAL_S,
                periodic_refresh_s=_WATCH_PERIODIC_S,
                repo_scope=_WATCH_SCOPE if _WATCH_SCOPE in {"engagement", "enterprise", "both"} else "both",
            )
            logger.info("watcher auto-start: %s", watch_result)
        except Exception:  # noqa: BLE001
            logger.exception("failed to auto-start watcher")

    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
