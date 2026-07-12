"""Registry-aware validation of a ``PresentationSpec`` (companion plan §5): capability
agreement per representation, style-rule mode shape (match vs. range), range-band overlap,
matrix axis-mode exclusivity, and column/group_by attribute resolution.
"""

from __future__ import annotations

from src.domain.viewpoint_condition_validation import RegistrySnapshot, issue, resolve_attribute_path
from src.domain.viewpoint_criteria import ConnectionCriteriaGroup, EntityCriteriaGroup
from src.domain.viewpoint_criteria_validation import (
    validate_connection_criteria,
    validate_depth_cap,
    validate_entity_criteria,
)
from src.domain.viewpoint_validation_issue import ViewpointValidationIssue
from src.domain.viewpoints import GROUP_BY_DIMENSIONS, REPRESENTATION_CAPABILITIES, PresentationSpec, StyleRule


def _validate_group_by_field(
    value: str | None, *, path: str, registries: RegistrySnapshot
) -> list[ViewpointValidationIssue]:
    if value is None or value in GROUP_BY_DIMENSIONS:
        return []
    declared = resolve_attribute_path(value, context="entity", registries=registries)
    if declared is None:
        return [issue("error", "unknown-attribute", path, f"unknown group-by attribute {value!r}")]
    return []


def _validate_range_bands(rule: StyleRule, *, path: str) -> list[ViewpointValidationIssue]:
    issues: list[ViewpointValidationIssue] = []
    bands = sorted(
        rule.range_bands,
        key=lambda band: (band.minimum is not None, band.minimum if band.minimum is not None else float("-inf")),
    )
    for position in range(len(bands) - 1):
        current = bands[position]
        following = bands[position + 1]
        if current.maximum is None or following.minimum is None or current.maximum > following.minimum:
            issues.append(
                issue(
                    "error",
                    "range-band-overlap",
                    f"{path}/range_bands",
                    "range bands must be non-overlapping and half-open",
                )
            )
            break
    return issues


def _validate_style_rule(
    rule: StyleRule,
    *,
    path: str,
    representation_capabilities: frozenset[str],
    registries: RegistrySnapshot,
    check_ergonomics: bool,
) -> list[ViewpointValidationIssue]:
    issues: list[ViewpointValidationIssue] = []
    if rule.capability not in representation_capabilities:
        issues.append(
            issue(
                "error",
                "unsupported-capability",
                f"{path}/capability",
                f"capability {rule.capability!r} is unsupported by this representation",
            )
        )
    is_edge_capability = rule.capability.startswith("edge_")
    if rule.mode == "match":
        criteria = rule.match_criteria
        if criteria is None:
            issues.append(
                issue(
                    "error", "missing-match-criteria", f"{path}/match_criteria", "mode='match' requires match_criteria"
                )
            )
        elif is_edge_capability != isinstance(criteria, ConnectionCriteriaGroup):
            issues.append(
                issue(
                    "error",
                    "capability-criteria-kind-mismatch",
                    f"{path}/match_criteria",
                    f"capability {rule.capability!r} requires "
                    + ("connection" if is_edge_capability else "entity")
                    + " criteria",
                )
            )
        elif isinstance(criteria, ConnectionCriteriaGroup):
            issues.extend(
                validate_connection_criteria(
                    criteria,
                    path=f"{path}/match_criteria",
                    is_root=True,
                    registries=registries,
                    check_ergonomics=check_ergonomics,
                )
            )
            if check_ergonomics:
                issues.extend(validate_depth_cap(criteria, path=f"{path}/match_criteria", registries=registries))
        elif isinstance(criteria, EntityCriteriaGroup):
            issues.extend(
                validate_entity_criteria(
                    criteria,
                    path=f"{path}/match_criteria",
                    is_root=True,
                    registries=registries,
                    check_ergonomics=check_ergonomics,
                )
            )
            if check_ergonomics:
                issues.extend(validate_depth_cap(criteria, path=f"{path}/match_criteria", registries=registries))
    else:
        if rule.range_attribute is None:
            issues.append(
                issue(
                    "error",
                    "missing-range-attribute",
                    f"{path}/range_attribute",
                    "mode='range' requires range_attribute",
                )
            )
        if check_ergonomics:
            issues.extend(_validate_range_bands(rule, path=path))
    return issues


def validate_presentation(
    presentation: PresentationSpec, *, path: str, registries: RegistrySnapshot, check_ergonomics: bool
) -> list[ViewpointValidationIssue]:
    issues: list[ViewpointValidationIssue] = []
    capabilities = REPRESENTATION_CAPABILITIES[presentation.representation]
    for option in presentation.display_options:
        if option not in capabilities:
            issues.append(
                issue(
                    "error",
                    "unsupported-display-option",
                    f"{path}/display_options/{option}",
                    f"display option {option!r} is unsupported by representation {presentation.representation!r}",
                )
            )
    for key in presentation.default_style:
        if key not in capabilities:
            issues.append(
                issue(
                    "error",
                    "unsupported-capability",
                    f"{path}/default_style/{key}",
                    f"capability {key!r} is unsupported by representation {presentation.representation!r}",
                )
            )
    for index, rule in enumerate(presentation.styling_rules):
        issues.extend(
            _validate_style_rule(
                rule,
                path=f"{path}/styling_rules/{index}",
                representation_capabilities=capabilities,
                registries=registries,
                check_ergonomics=check_ergonomics,
            )
        )
    if presentation.columns is not None:
        for index, column in enumerate(presentation.columns):
            declared = resolve_attribute_path(column.source, context="entity", registries=registries)
            if declared is None:
                issues.append(
                    issue(
                        "error",
                        "unknown-attribute",
                        f"{path}/columns/{index}/source",
                        f"unknown column source {column.source!r}",
                    )
                )
    issues.extend(_validate_group_by_field(presentation.group_by, path=f"{path}/group_by", registries=registries))
    if check_ergonomics:
        issues.extend(_validate_matrix_axes(presentation, path=path, registries=registries))
    return issues


def _validate_matrix_axes(
    presentation: PresentationSpec, *, path: str, registries: RegistrySnapshot
) -> list[ViewpointValidationIssue]:
    issues: list[ViewpointValidationIssue] = []
    grouped = presentation.row_by is not None or presentation.column_by is not None
    criteria_axes = presentation.row_criteria is not None or presentation.column_criteria is not None
    if grouped and criteria_axes:
        issues.append(issue("error", "matrix-axis-mode-mixed", path, "matrix cannot mix grouped and criteria axes"))
        return issues
    if grouped and (presentation.row_by is None) != (presentation.column_by is None):
        issues.append(
            issue("error", "matrix-axis-incomplete", path, "grouped matrix axes require both row_by and column_by")
        )
    if criteria_axes and (presentation.row_criteria is None) != (presentation.column_criteria is None):
        issues.append(
            issue(
                "error",
                "matrix-axis-incomplete",
                path,
                "criteria matrix axes require both row_criteria and column_criteria",
            )
        )
    for field_name, tree in (("row_by", presentation.row_by), ("column_by", presentation.column_by)):
        issues.extend(_validate_group_by_field(tree, path=f"{path}/{field_name}", registries=registries))
    for field_name, group in (
        ("row_criteria", presentation.row_criteria),
        ("column_criteria", presentation.column_criteria),
    ):
        if group is not None:
            issues.extend(
                validate_entity_criteria(
                    group, path=f"{path}/{field_name}", is_root=True, registries=registries, check_ergonomics=True
                )
            )
            issues.extend(validate_depth_cap(group, path=f"{path}/{field_name}", registries=registries))
    return issues
