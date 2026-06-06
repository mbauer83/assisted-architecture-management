"""Helpers for GUI entity list payloads."""

from __future__ import annotations

from typing import Any

from src.domain.artifact_types import EntityRecord
from src.infrastructure.gui.routers import state as s


def build_entity_list_rows(entities: list[EntityRecord], repo) -> list[dict[str, Any]]:
    counts = s.build_conn_counts_for_entities(repo, [e.artifact_id for e in entities])
    return [s.entity_to_summary(e, counts) for e in entities]
