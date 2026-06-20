"""Tests for WU-E6: C4 node labels show name only by default; show_node_descriptions flag re-enables."""
from __future__ import annotations

from pathlib import Path

from src.diagram_types.c4._resolve import _ResolvedItem
from src.diagram_types.c4.renderer import C4PumlRenderer, _render_item_body

# ── helpers ────────────────────────────────────────────────────────────────────

def _item(
    *,
    label: str,
    description: str = "",
    technology: str = "",
    item_type: str = "container",
    external: bool = False,
) -> _ResolvedItem:
    return _ResolvedItem(
        local_id="c1",
        item_type=item_type,
        alias="C_alias",
        label=label,
        description=description,
        technology=technology,
        external=external,
    )


def _renderer(show_node_descriptions: bool = False) -> C4PumlRenderer:
    # scope_render_mode "boundary" renders containers inside the system boundary,
    # which is the layout used by the real C4 container diagram.
    return C4PumlRenderer(
        {
            "c4": {
                "scope_entity_type": "software-system",
                "scope_render_mode": "boundary",
                "internal_entity_types": ["container"],
                "show_node_descriptions": show_node_descriptions,
            }
        }
    )


def _render(show_node_descriptions: bool = False) -> str:
    renderer = _renderer(show_node_descriptions)
    diagram_entities = {
        "software-system": [{"id": "sys1", "label": "My System", "scope": True}],
        "container": [
            {"id": "c1", "label": "API Server", "technology": "Python/FastAPI",
             "description": "Handles all REST requests from the GUI."}
        ],
    }
    return renderer.render_body(
        "Test Diagram", [], [], "c4-container", Path("/tmp"),
        diagram_entities=diagram_entities,
    )


# ── _render_item_body unit tests ───────────────────────────────────────────────

def test_item_body_default_omits_description() -> None:
    item = _item(label="API Server", description="Handles REST requests")
    body = _render_item_body(item)
    assert "API Server" in body
    assert "Handles REST requests" not in body


def test_item_body_with_show_descriptions_includes_description() -> None:
    item = _item(label="API Server", description="Handles REST requests")
    body = _render_item_body(item, show_descriptions=True)
    assert "API Server" in body
    assert "Handles REST requests" in body


def test_item_body_technology_not_in_body_but_in_macro_call() -> None:
    """Technology is a macro argument (not in the label body).
    The body helper omits technology; the full _render_item call includes it.
    """
    item = _item(label="DB", technology="PostgreSQL")
    body = _render_item_body(item)
    assert "DB" in body
    assert "[PostgreSQL]" not in body  # tech is a macro arg, not in the label body
    # Technology appears in the full macro call via the renderer
    renderer = C4PumlRenderer({"c4": {"scope_entity_type": "software-system",
                                      "scope_render_mode": "boundary",
                                      "internal_entity_types": ["container"]}})
    rendered = renderer._render_item(item)
    assert "PostgreSQL" in rendered


def test_item_body_empty_description_unchanged_by_flag() -> None:
    """An item with no description stays the same regardless of the flag."""
    item = _item(label="Worker", description="")
    assert _render_item_body(item) == _render_item_body(item, show_descriptions=True)


# ── _render_item method tests ──────────────────────────────────────────────────

def test_render_item_default_no_description() -> None:
    renderer = _renderer()
    item = _item(label="API Server", description="Handles all REST requests from the GUI.")
    rendered = renderer._render_item(item)
    assert "API Server" in rendered
    assert "Handles all REST requests from the GUI." not in rendered


def test_render_item_with_show_descriptions() -> None:
    renderer = _renderer()
    item = _item(label="API Server", description="Handles all REST requests from the GUI.")
    rendered = renderer._render_item(item, show_descriptions=True)
    assert "Handles all REST requests from the GUI." in rendered


# ── Full render_body integration tests ─────────────────────────────────────────

def test_render_body_default_omits_description() -> None:
    puml = _render(show_node_descriptions=False)
    assert "API Server" in puml
    assert "Handles all REST requests from the GUI." not in puml


def test_render_body_show_node_descriptions_true_includes_description() -> None:
    puml = _render(show_node_descriptions=True)
    assert "API Server" in puml
    assert "Handles all REST requests from the GUI." in puml


def test_render_body_technology_always_rendered() -> None:
    for flag in (False, True):
        puml = _render(show_node_descriptions=flag)
        assert "Python/FastAPI" in puml


def test_render_body_no_show_key_in_config_omits_description() -> None:
    """Missing show_node_descriptions key defaults to False (no description)."""
    renderer = C4PumlRenderer(
        {
            "c4": {
                "scope_entity_type": "software-system",
                "scope_render_mode": "boundary",
                "internal_entity_types": ["container"],
                # show_node_descriptions deliberately absent
            }
        }
    )
    diagram_entities = {
        "software-system": [{"id": "sys1", "label": "My System", "scope": True}],
        "container": [
            {"id": "c1", "label": "API Server", "description": "Should not appear by default."}
        ],
    }
    puml = renderer.render_body(
        "Test", [], [], "c4-container", Path("/tmp"), diagram_entities=diagram_entities,
    )
    assert "Should not appear by default." not in puml
