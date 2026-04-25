import logging
from typing import Any

import yaml  # type: ignore[import-untyped]
from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]
from mcp.types import TextContent

logger = logging.getLogger(__name__)


def _dump_yaml_text(data: object) -> str:
    dumped = yaml.dump(
        data,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    )
    if not isinstance(dumped, str):
        raise TypeError("yaml.dump returned non-string output")
    return dumped.rstrip()


def normalize_incoming_tool_name(tool_name: str, *, known_tools: set[str]) -> str:
    """Normalize an incoming tool name from bridges that namespace tools."""

    if tool_name in known_tools:
        return tool_name

    for sep in ("-", ":", ".", "/"):
        if sep in tool_name:
            candidate = tool_name.rsplit(sep, 1)[-1]
            if candidate in known_tools:
                return candidate
    return tool_name


def install_call_tool_normalizer(mcp: FastMCP) -> None:
    """Override FastMCP CallTool handler to normalize tool names and emit YAML responses."""

    async def _call_tool_handler(name: str, arguments: dict[str, Any]) -> Any:
        tools = mcp._tool_manager.list_tools()  # type: ignore[attr-defined]
        known = {t.name for t in tools}
        normalized = normalize_incoming_tool_name(name, known_tools=known)
        if normalized != name:
            logger.info("Normalized incoming tool name %r -> %r", name, normalized)
        context = mcp.get_context()
        # Get raw Python result; convert dict/list to compact YAML for token efficiency
        result = await mcp._tool_manager.call_tool(  # type: ignore[attr-defined]
            normalized,
            arguments,
            context=context,
            convert_result=False,
        )
        if isinstance(result, (dict, list)):
            yaml_text = _dump_yaml_text(result)
            return [TextContent(type="text", text=yaml_text)]
        # Fall back to FastMCP normal conversion for strings, ContentBlocks, etc.
        tool = mcp._tool_manager.get_tool(normalized)  # type: ignore[attr-defined]
        if tool is None:
            return [TextContent(type="text", text=str(result))]
        return tool.fn_metadata.convert_result(result)

    mcp._mcp_server.call_tool(validate_input=False)(_call_tool_handler)  # type: ignore[attr-defined]
