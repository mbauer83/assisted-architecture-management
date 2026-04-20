"""MCP server exposing ERP v2.0 model tools (query + verification + write).

This module is intentionally small: it wires together tool-registration modules
under src/tools/model_mcp/.

Tool logic lives in:
- src/tools/model_mcp/*_tools.py (MCP tool wrappers)
- src/common/* (domain-ish logic)
- src/tools/model_write/* (writer I/O operations)
"""


import argparse
import logging
import os

from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]

from src.tools.model_mcp import (
    auto_start_default_watcher,
    install_call_tool_normalizer,
    normalize_incoming_tool_name,
    register_edit_tools,
    register_query_tools,
    register_verify_tools,
    register_write_tools,
)

# Re-export commonly used tool functions for direct calling in tests.
from src.tools.model_mcp.write_tools import (  # noqa: F401
    model_add_connection,
    model_create_diagram,
    model_create_entity,
    model_create_matrix,
    model_promote_to_enterprise,
    model_write_help,
)
from src.tools.model_mcp.edit_tools import (  # noqa: F401
    model_delete_diagram,
    model_delete_entity,
    model_edit_connection,
    model_edit_connection_associations,
    model_edit_diagram,
    model_edit_entity,
)
from src.tools.model_mcp.verify_tools import (  # noqa: F401
    model_verify,
    model_verify_all,
    model_verify_file,
)


logger = logging.getLogger(__name__)


_INSTRUCTIONS = (
    "Architecture repository model query + verifier + writer tools. "
    "Targets an ArchiMate NEXT architecture repository (model/, diagram-catalog/). "
    "By default mounts both engagement repo + enterprise-repository; use repo_scope to restrict."
)

_HOST = os.getenv("SDLC_MCP_HOST", "127.0.0.1")
_PORT = int(os.getenv("SDLC_MCP_PORT", "8000"))
_LOG_LEVEL = os.getenv("SDLC_MCP_LOG_LEVEL", "INFO")
_SERVER_NAME = os.getenv("SDLC_MCP_SERVER_NAME", "sdlc_model")
_MOUNT_PATH = os.getenv("SDLC_MCP_MOUNT_PATH", "/")
_SSE_PATH = os.getenv("SDLC_MCP_SSE_PATH", "/sse")
_MESSAGE_PATH = os.getenv("SDLC_MCP_MESSAGE_PATH", "/messages/")
_STREAMABLE_HTTP_PATH = os.getenv("SDLC_MCP_STREAMABLE_HTTP_PATH", "/mcp")
_JSON_RESPONSE = os.getenv("SDLC_MCP_JSON_RESPONSE", "1") in {"1", "true", "TRUE", "yes", "YES"}
_STATELESS_HTTP = os.getenv("SDLC_MCP_STATELESS_HTTP", "1") in {"1", "true", "TRUE", "yes", "YES"}
_WATCH_AUTO_START = os.getenv("SDLC_MCP_MODEL_WATCH_AUTO_START", "1") in {"1", "true", "TRUE", "yes", "YES"}
_WATCH_INTERVAL_S = float(os.getenv("SDLC_MCP_MODEL_WATCH_INTERVAL_S", "2.0"))
_WATCH_SCOPE = os.getenv("SDLC_MCP_MODEL_WATCH_SCOPE", "both")
_WATCH_PERIODIC_RAW = os.getenv("SDLC_MCP_MODEL_WATCH_PERIODIC_REFRESH_S", "300")
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


def _normalize_incoming_tool_name(tool_name: str, *, known_tools: set[str]) -> str:
    """Backward-compatible alias used by tests."""

    return normalize_incoming_tool_name(tool_name, known_tools=known_tools)


# Install CallTool name normalization handler.
install_call_tool_normalizer(mcp)

# Register tool groups.
register_query_tools(mcp)
register_verify_tools(mcp)
register_write_tools(mcp)
register_edit_tools(mcp)


def main() -> None:
    """Run the MCP server.

    Default transport is stdio. For containerized deployments where the MCP host
    cannot spawn a stdio subprocess, use SSE/HTTP transports.
    """

    parser = argparse.ArgumentParser(prog="sdlc-mcp-model")
    parser.add_argument(
        "--transport",
        choices=("stdio", "streamable-http"),
        default=os.getenv("SDLC_MCP_TRANSPORT", "stdio"),
        help="MCP transport (default: stdio)",
    )
    args = parser.parse_args()

    # Check init state — warn if missing but don't block (backward compat)
    from src.tools.workspace_init import load_init_state
    state = load_init_state()
    if state:
        logger.info("arch-init state loaded: engagement=%s enterprise=%s",
                     state.get("engagement_root"), state.get("enterprise_root"))
    else:
        repo_root_env = os.getenv("SDLC_MCP_MODEL_REPO_ROOT")
        if not repo_root_env:
            logger.warning(
                "No .arch/init-state.yaml found and SDLC_MCP_MODEL_REPO_ROOT not set. "
                "Run `arch-init` to configure workspace repos."
            )

    if _WATCH_AUTO_START:
        try:
            watch_result = auto_start_default_watcher(
                interval_s=_WATCH_INTERVAL_S,
                periodic_refresh_s=_WATCH_PERIODIC_S,
                repo_scope=_WATCH_SCOPE if _WATCH_SCOPE in {"engagement", "enterprise", "both"} else "both",
            )
            logger.info("model watcher auto-start result: %s", watch_result)
        except Exception:  # noqa: BLE001
            logger.exception("failed to auto-start model watcher")

    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
