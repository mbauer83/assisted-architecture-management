"""Normalize diagram binding shorthand to canonical top-level Binding records.

Diagram entity items may carry a nested ``binding:`` shorthand for convenience.
This module reads that shorthand and merges it with any explicit top-level
``bindings`` into a single list of Binding objects that the write path persists.

Shorthand restrictions (per spec §1.2):
- Only for entity subjects (kind=entity).
- Only single-target forms: entity_id, connection_id, or diagram_local.
- connection_ids and connection_path are not expressible as shorthand — use
  explicit top-level bindings for those.
- Only correspondence kinds: represents, scoped-by, traces-to, refines.
  ``abstracts`` requires an explicit binding because it implies multi-target.
- Default correspondence_kind is "represents" when omitted.
"""

from __future__ import annotations

from src.domain.bindings import (
    CORE_CORRESPONDENCE_KINDS,
    Binding,
    BindingSubject,
    parse_binding,
    parse_target,
)

_SHORTHAND_ALLOWED_KINDS: frozenset[str] = frozenset(
    {"represents", "scoped-by", "traces-to", "refines"}
)


def normalize_bindings(
    diagram_entities: dict[str, object] | None,
    existing_bindings: list[dict[str, object]] | None,
) -> list[Binding]:
    """Merge explicit top-level bindings with shorthand extracted from diagram entities.

    Explicit top-level bindings take precedence: if an explicit binding has the same
    id as a shorthand-derived binding, the shorthand is silently dropped.

    Returns an empty list when both inputs are empty/None.
    """
    result: list[Binding] = []
    seen_ids: set[str] = set()

    for raw in existing_bindings or []:
        if not isinstance(raw, dict):
            continue
        b = parse_binding(raw)
        result.append(b)
        seen_ids.add(b.id)

    if not diagram_entities:
        return result

    for entity_type, items in diagram_entities.items():
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            shorthand = item.get("binding")
            if shorthand is None:
                continue
            if not isinstance(shorthand, dict):
                raise ValueError(
                    f"Diagram entity in '{entity_type}': 'binding' must be a dict, "
                    f"got {type(shorthand).__name__}"
                )
            element_id = str(item.get("id") or "").strip()
            if not element_id:
                raise ValueError(
                    f"Diagram entity in '{entity_type}' has a 'binding' shorthand "
                    "but no 'id' — cannot generate a stable binding id"
                )
            binding = _normalize_shorthand(entity_type, element_id, shorthand)
            if binding.id in seen_ids:
                continue
            result.append(binding)
            seen_ids.add(binding.id)

    return result


def _normalize_shorthand(entity_type: str, element_id: str, shorthand: dict[str, object]) -> Binding:
    corr_kind = str(shorthand.get("correspondence_kind") or "represents")
    if corr_kind not in CORE_CORRESPONDENCE_KINDS:
        raise ValueError(
            f"Shorthand binding for '{element_id}' (type '{entity_type}'): "
            f"'{corr_kind}' is not a core correspondence kind"
        )
    if corr_kind not in _SHORTHAND_ALLOWED_KINDS:
        raise ValueError(
            f"Shorthand binding for '{element_id}' (type '{entity_type}'): "
            f"'{corr_kind}' cannot be expressed as shorthand — "
            "use an explicit top-level binding"
        )

    target_raw = shorthand.get("target")
    if not isinstance(target_raw, dict):
        raise ValueError(
            f"Shorthand binding for '{element_id}' (type '{entity_type}'): "
            f"'target' must be a dict, got {type(target_raw).__name__}"
        )
    if target_raw.get("connection_ids") is not None:
        raise ValueError(
            f"Shorthand binding for '{element_id}': connection_ids is a multi-target "
            "form — use an explicit top-level binding"
        )
    if target_raw.get("connection_path") is not None:
        raise ValueError(
            f"Shorthand binding for '{element_id}': connection_path cannot be "
            "expressed as shorthand — use an explicit top-level binding"
        )

    target = parse_target(target_raw)
    return Binding(
        id=f"bind-{element_id}",
        subject=BindingSubject(kind="entity", id=element_id),
        correspondence_kind=corr_kind,
        target=target,
    )
