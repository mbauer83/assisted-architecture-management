"""CSV export of a viewpoint execution result.

The export is COMPLETE — the full result at the execution's generation, never the visible
page of a paginated view (a 242-row result exported from one page would silently look
complete). Provenance travels in comment lines at the top (slug/version, parameters,
executed_at, index generation, counts), so an exported file is citable evidence, not a
bare grid.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping

from src.application.viewpoints.execution_result import ViewpointExecutionResult
from src.domain.viewpoints import ColumnSpec

_FIXED_COLUMNS: tuple[tuple[str, str], ...] = (
    ("id", "id"),
    ("name", "name"),
    ("type", "type"),
    ("specialization", "specialization"),
    ("group", "group"),
    ("status", "status"),
    ("version", "version"),
)


def build_execution_csv(
    result: ViewpointExecutionResult,
    columns: tuple[ColumnSpec, ...] | None,
    parameters: Mapping[str, object] | None,
) -> str:
    """Provenance block + header + one row per result entity. Authored columns render
    their server-resolved ``column_values`` (missing values stay empty, never guessed)."""
    buffer = io.StringIO()
    identity = f"{result.slug} v{result.version}" if result.slug else "(ad-hoc query)"
    parameter_text = (
        ", ".join(f"{name}={value}" for name, value in sorted(parameters.items())) if parameters else "(none)"
    )
    for line in (
        f"viewpoint: {identity}",
        f"parameters: {parameter_text}",
        f"executed_at: {result.executed_at}",
        f"index_generation: {result.index_generation}",
        f"entities: {result.returned_entity_count}/{result.total_entity_count} · "
        f"connections: {result.returned_connection_count}/{result.total_connection_count}",
    ):
        buffer.write(f"# {line}\r\n")

    authored = [column for column in (columns or ()) if column.source not in {name for name, _ in _FIXED_COLUMNS}]
    writer = csv.writer(buffer)
    writer.writerow([label for label, _ in _FIXED_COLUMNS] + [column.label or column.source for column in authored])
    for entity in result.entities:
        fixed = [
            entity.id,
            entity.name,
            entity.type,
            ", ".join(entity.specialization_slugs),
            entity.group,
            entity.status,
            entity.version,
        ]
        values = entity.column_values or {}
        extra = ["" if (value := values.get(column.source)) is None else str(value) for column in authored]
        writer.writerow(fixed + extra)
    return buffer.getvalue()
