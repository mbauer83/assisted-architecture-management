"""Tests for the ``viewpoints.execution_*`` settings (companion plan §7.1 bounds)."""

from __future__ import annotations

import pytest

from src.config.settings import (
    viewpoints_execution_default_entity_limit_mcp,
    viewpoints_execution_max_entities,
    viewpoints_execution_timeout_seconds,
)


def test_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.config import settings

    monkeypatch.setattr(settings, "load_settings", lambda: {"viewpoints": {}})
    assert viewpoints_execution_max_entities() == 500
    assert viewpoints_execution_default_entity_limit_mcp() == 200
    assert viewpoints_execution_timeout_seconds() == 10.0


def test_reads_configured_values(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.config import settings

    monkeypatch.setattr(
        settings,
        "load_settings",
        lambda: {
            "viewpoints": {
                "execution_max_entities": 50,
                "execution_default_entity_limit_mcp": 10,
                "execution_timeout_seconds": 2.5,
            }
        },
    )
    assert viewpoints_execution_max_entities() == 50
    assert viewpoints_execution_default_entity_limit_mcp() == 10
    assert viewpoints_execution_timeout_seconds() == 2.5


def test_invalid_values_fall_back_to_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.config import settings

    monkeypatch.setattr(
        settings,
        "load_settings",
        lambda: {
            "viewpoints": {
                "execution_max_entities": "not-a-number",
                "execution_default_entity_limit_mcp": "not-a-number",
                "execution_timeout_seconds": "not-a-number",
            }
        },
    )
    assert viewpoints_execution_max_entities() == 500
    assert viewpoints_execution_default_entity_limit_mcp() == 200
    assert viewpoints_execution_timeout_seconds() == 10.0
