"""ERP model writer operations package.

This package is the tool/infrastructure side of deterministic writing.
The MCP server should depend on these modules, not embed the logic.
"""

from .types import WriteResult
from .help import write_help
from .entity import create_entity
from .entity_edit import edit_entity, promote_entity
from .entity_delete import delete_entity
from .connection import add_connection
from .connection_edit import edit_connection, remove_connection, edit_connection_associations
from .diagram import create_diagram
from .diagram_edit import edit_diagram
from .diagram_delete import delete_diagram
from .matrix import create_matrix
from .type_guidance import get_type_guidance

__all__ = [
    "WriteResult",
    "write_help",
    "create_entity",
    "edit_entity",
    "delete_entity",
    "promote_entity",
    "add_connection",
    "edit_connection",
    "edit_connection_associations",
    "remove_connection",
    "create_diagram",
    "edit_diagram",
    "delete_diagram",
    "create_matrix",
    "get_type_guidance",
]
