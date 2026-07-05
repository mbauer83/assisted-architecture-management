"""User-supplied + sentinel PlantUML link emission for activity steps.

Extracted from ``renderer.py`` to keep it under the project's LoC limit.
"""

from __future__ import annotations

from typing import Any


def _link_clause(url: str) -> str:
    return f"[[{url.replace(']', '%5D')}]]"


def sentinel_target(step: dict[str, Any]) -> str:
    """The bound entity id if this step maps to one, else the step's own local id."""
    entity_id = step.get("entity_id")
    return str(entity_id) if entity_id else str(step.get("id") or "")


def link_suffix(step: dict[str, Any]) -> str:
    """User's ``link`` (preserved, unchanged) plus a sentinel ``arch://`` link so the
    frontend viewer extension can resolve this rendered element back to its artifact —
    the bound entity if ``entity_id`` is set, else the diagram-local placeholder entity
    that ``extract_diagram_entities`` gives this step (``display_alias`` = its local id).
    Both render as their own separate small link text (PlantUML activity links never wrap
    the action/decision/partition shape itself) — an existing convention this only adds to,
    never changes.
    """
    clauses: list[str] = []
    link = step.get("link")
    if link:
        clauses.append(_link_clause(str(link)))
    sentinel = sentinel_target(step)
    if sentinel:
        clauses.append(_link_clause(f"arch://{sentinel}"))
    return f" {' '.join(clauses)}" if clauses else ""
