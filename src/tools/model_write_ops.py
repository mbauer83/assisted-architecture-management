"""model_write_ops.py — Compatibility facade.

The implementation was split into smaller modules under src/tools/model_write/.
This module remains as a stable import path for MCP server code and tests.
"""


from typing import Literal

from src.common.model_write import DiagramConnectionInferenceMode

from src.tools.model_write import (
    WriteResult,
    add_connection,
    create_diagram,
    create_entity,
    delete_entity,
    create_matrix,
    edit_connection,
    edit_diagram,
    edit_entity,
    delete_diagram,
    get_type_guidance,  # filter: list[str] | None = None
    promote_entity,
    remove_connection,
    write_help,
)


WriteRepoScope = Literal["engagement"]

__all__ = [
    "DiagramConnectionInferenceMode",
    "WriteRepoScope",
    "WriteResult",
    "write_help",
    "get_type_guidance",
    "create_entity",
    "edit_entity",
    "delete_entity",
    "promote_entity",
    "add_connection",
    "edit_connection",
    "remove_connection",
    "create_diagram",
    "edit_diagram",
    "delete_diagram",
    "create_matrix",
]
