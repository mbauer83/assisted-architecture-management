"""Spec-fidelity gate: every shipped Appendix-C definition's purpose/stakeholders/concerns/
scope element list matches its transcribed spec table exactly — an executable comparison,
not a review claim. "Core element" viewpoints (domain-union scope, no fixed element list
in the spec table) are asserted separately, without an element-list comparison."""

from __future__ import annotations

from src.domain.viewpoint_criteria import AttributeCondition
from src.infrastructure.app_bootstrap import build_runtime_catalogs, get_module_registry
from src.infrastructure.viewpoint_declarations import load_module_viewpoint_catalog
from src.ontologies.archimate_4._loader import _PACKAGE_DIR as _ARCH_PACKAGE_DIR
from tests.fixtures.viewpoints.standard_viewpoint_tables import STANDARD_VIEWPOINT_TABLES

_CATALOGS = build_runtime_catalogs(get_module_registry())
_DEFINITIONS_BY_SLUG = {d.slug: d for d in _CATALOGS.viewpoints.entries}

_CORE_ELEMENT_SLUGS = frozenset({"layered", "requirements-realization", "outcome-realization"})
# Custom, non-spec impact-analysis definitions shipped alongside the standard library —
# they have no ArchiMate spec table to compare against, so they're excluded here.
_CUSTOM_SLUGS = frozenset({"element-dependents", "element-dependencies", "process-technology-support"})


def test_every_table_has_a_shipped_definition() -> None:
    # Pure module-shipped catalog — `_DEFINITIONS_BY_SLUG` (built from the merged two-tier
    # catalog) is right for the per-slug lookups below, but an exact-membership assertion
    # must not be sensitive to whatever real engagement/enterprise content this
    # environment's configured workspace happens to have alongside the shipped library.
    shipped_only = load_module_viewpoint_catalog(_ARCH_PACKAGE_DIR)
    shipped = {d.slug for d in shipped_only.entries} - _CUSTOM_SLUGS
    tables = {table.slug for table in STANDARD_VIEWPOINT_TABLES}
    assert shipped == tables


def test_purpose_matches_the_spec_table_verbatim() -> None:
    for table in STANDARD_VIEWPOINT_TABLES:
        definition = _DEFINITIONS_BY_SLUG[table.slug]
        assert tuple(definition.purpose) == table.purpose, table.slug


def test_stakeholders_match_the_spec_table_verbatim() -> None:
    for table in STANDARD_VIEWPOINT_TABLES:
        definition = _DEFINITIONS_BY_SLUG[table.slug]
        assert tuple(definition.stakeholders) == table.stakeholders, table.slug


def test_concerns_match_the_spec_table_verbatim() -> None:
    for table in STANDARD_VIEWPOINT_TABLES:
        definition = _DEFINITIONS_BY_SLUG[table.slug]
        assert tuple(definition.concerns) == table.concerns, table.slug


def test_scope_element_list_matches_the_spec_table() -> None:
    for table in STANDARD_VIEWPOINT_TABLES:
        if table.slug in _CORE_ELEMENT_SLUGS:
            continue
        definition = _DEFINITIONS_BY_SLUG[table.slug]
        scope_types = {str(t) for t in (definition.scope.entity_types or ())} - {
            "grouping", "and-junction", "or-junction",
        }
        assert scope_types == set(table.entity_types), table.slug


def test_core_element_viewpoints_have_no_fixed_scope_and_use_domain_union() -> None:
    for slug in _CORE_ELEMENT_SLUGS:
        definition = _DEFINITIONS_BY_SLUG[slug]
        assert definition.scope.entity_types is None
        assert definition.query is not None
        condition = definition.query.entity_criteria.children[0]
        assert isinstance(condition, AttributeCondition)
        assert condition.attribute == "domain"
        assert condition.comparator == "in"
