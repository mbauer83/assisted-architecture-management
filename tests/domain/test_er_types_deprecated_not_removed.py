"""Guard test: er-* connection types must remain loadable until WU-A2 migration.

These types are deprecated but still used by ENG-001; removing them prematurely
would break verification of existing connection files.
"""

from __future__ import annotations

from src.ontologies.archimate_4 import module as archimate_module


def test_er_types_still_present() -> None:
    ct = archimate_module.connection_types
    assert "er-one-to-many" in ct, "er-one-to-many removed prematurely"
    assert "er-many-to-many" in ct, "er-many-to-many removed prematurely"
    assert "er-one-to-one" in ct, "er-one-to-one removed prematurely"


def test_er_types_have_diagram_conn_lang() -> None:
    ct = archimate_module.connection_types
    for name in ("er-one-to-many", "er-many-to-many", "er-one-to-one"):
        assert ct[name].conn_lang == "er", f"{name} has unexpected conn_lang"
