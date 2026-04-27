"""write_tools.py — re-exports all MCP write tool functions and registers them.

Logic lives in src/tools/model_mcp/write/*.
"""

from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]

from src.infrastructure.mcp.artifact_mcp.bulk_tools import artifact_bulk_delete
from src.infrastructure.mcp.artifact_mcp.write._common import DiagramConnectionInferenceMode, WriteRepoScope
from src.infrastructure.mcp.artifact_mcp.write.connection import artifact_add_connection
from src.infrastructure.mcp.artifact_mcp.write.diagram import artifact_create_diagram, artifact_create_matrix
from src.infrastructure.mcp.artifact_mcp.write.document import (
    artifact_create_document,
    artifact_edit_document,
)
from src.infrastructure.mcp.artifact_mcp.write.entity import (
    artifact_create_entity,
    artifact_write_help,
    artifact_write_modeling_guidance,
)
from src.infrastructure.mcp.artifact_mcp.write.promote import artifact_promote_to_enterprise

__all__ = [
    "DiagramConnectionInferenceMode",
    "WriteRepoScope",
    "artifact_add_connection",
    "artifact_bulk_delete",
    "artifact_create_diagram",
    "artifact_create_document",
    "artifact_create_entity",
    "artifact_create_matrix",
    "artifact_edit_document",
    "artifact_promote_to_enterprise",
    "artifact_write_help",
    "artifact_write_modeling_guidance",
]


def register_write_tools(mcp: FastMCP) -> None:
    from src.infrastructure.mcp.artifact_mcp import bulk_tools
    from src.infrastructure.mcp.artifact_mcp.write import connection, diagram, document, entity, promote

    entity.register(mcp)
    connection.register(mcp)
    diagram.register(mcp)
    document.register(mcp)
    promote.register(mcp)
    bulk_tools.register(mcp)
