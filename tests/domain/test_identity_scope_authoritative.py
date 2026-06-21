"""WU-0.1 guard: identity_scope and id_prefix are consistent across all catalog views.

The ontology is authoritative; UI config derives from it via _apply_ontology_fields.
Checks that both the diagram-entity EntityTypeInfo (from the ontology loader) and
DiagramOwnEntityTypeUiConfig (from the merged config) report identical values for classifier.
"""

from __future__ import annotations

import src.infrastructure.app_bootstrap as app_bootstrap
from src.diagram_types.datatype import module as datatype_module
from src.domain.module_types import EntityTypeName


def _registry():
    return app_bootstrap.build_module_registry(complete_vocabulary=True)


def _datatype():
    return datatype_module  # the singleton loaded at import time


def test_classifier_identity_scope_in_entity_type_info():
    """EntityTypeInfo (ontology loader view) reports workspace + CLF."""
    et_info = _datatype().diagram_entity_type_infos[EntityTypeName("classifier")]
    assert et_info.identity_scope == "workspace"
    assert et_info.id_prefix == "CLF"


def test_classifier_identity_scope_in_ui_config():
    """DiagramOwnEntityTypeUiConfig (merged config view) reports workspace + CLF."""
    ui_entries = {oe.entity_type: oe for oe in _datatype().ui_config.diagram_only_types}
    clf_ui = ui_entries["classifier"]
    assert clf_ui.identity_scope == "workspace"
    assert clf_ui.id_prefix == "CLF"


def test_views_agree():
    """Both catalog views report the same identity_scope and id_prefix for every diagram entity."""
    dt = _datatype()
    ui_map = {oe.entity_type: oe for oe in dt.ui_config.diagram_only_types}
    for etype_name, et_info in dt.diagram_entity_type_infos.items():
        ui = ui_map.get(str(etype_name))
        if ui is None:
            continue
        assert ui.identity_scope == et_info.identity_scope, (
            f"{etype_name}: identity_scope mismatch ({ui.identity_scope!r} vs {et_info.identity_scope!r})"
        )
        assert ui.id_prefix == et_info.id_prefix, (
            f"{etype_name}: id_prefix mismatch ({ui.id_prefix!r} vs {et_info.id_prefix!r})"
        )


def test_absent_identity_scope_defaults_to_diagram():
    """Entity types not declaring identity_scope default to 'diagram'."""
    dt = _datatype()
    ui_map = {oe.entity_type: oe for oe in dt.ui_config.diagram_only_types}
    for etype_name, et_info in dt.diagram_entity_type_infos.items():
        if str(etype_name) == "classifier":
            continue
        assert et_info.identity_scope == "diagram", (
            f"{etype_name} should default to 'diagram', got {et_info.identity_scope!r}"
        )
        ui = ui_map.get(str(etype_name))
        if ui is not None:
            assert ui.identity_scope == "diagram"
