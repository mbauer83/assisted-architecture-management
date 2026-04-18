"""write_tools.py — re-exports all MCP write tool functions and registers them.

Logic lives in src/tools/model_mcp/write/*.
"""

from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]

from src.tools.model_mcp.write._common import WriteRepoScope, DiagramConnectionInferenceMode
from src.tools.model_mcp.write.connection import model_add_connection
from src.tools.model_mcp.write.diagram import model_create_diagram, model_create_matrix
from src.tools.model_mcp.write.entity import model_create_entity, model_write_help
from src.tools.model_mcp.write.promote import model_promote_to_enterprise

__all__ = [
    "DiagramConnectionInferenceMode",
    "WriteRepoScope",
    "model_add_connection",
    "model_create_diagram",
    "model_create_entity",
    "model_create_matrix",
    "model_promote_to_enterprise",
    "model_write_help",
]


def register_write_tools(mcp: FastMCP) -> None:
    from src.tools.model_mcp.write import connection, diagram, entity, promote
    entity.register(mcp)
    connection.register(mcp)
    diagram.register(mcp)
    promote.register(mcp)
