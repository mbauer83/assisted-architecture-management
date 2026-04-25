from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]

from .query_graph_tools import register_query_graph_tools
from .query_list_read_tools import register_query_list_read_tools
from .query_scaffold_tools import register_query_scaffold_tools
from .query_search_tools import register_query_search_tools
from .query_stats_tools import register_query_stats_tools


def register_query_tools(mcp: FastMCP) -> None:
    """Register all model query tools."""

    register_query_stats_tools(mcp)
    register_query_list_read_tools(mcp)
    register_query_search_tools(mcp)
    register_query_graph_tools(mcp)
    register_query_scaffold_tools(mcp)
