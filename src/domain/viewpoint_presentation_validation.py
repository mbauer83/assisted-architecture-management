"""Registry-aware validation of a ``PresentationSpec``: capability
agreement per representation, style-rule mode shape (match vs. range), range-band overlap,
matrix axis-mode exclusivity, and column/group_by attribute resolution.
"""

from __future__ import annotations

from src.domain.viewpoint_condition_validation import CriteriaContext, RegistrySnapshot, issue, resolve_attribute_path
from src.domain.viewpoint_criteria import NUMERIC_ATTRIBUTE_TYPES, ConnectionCriteriaGroup, EntityCriteriaGroup
from src.domain.viewpoint_criteria_validation import (
    validate_connection_criteria,
    validate_depth_cap,
    validate_entity_criteria,
)
from src.domain.viewpoint_style_values import is_valid_style_value, style_value_error
from src.domain.viewpoint_validation_issue import ViewpointValidationIssue
from src.domain.viewpoints import (
    GROUP_BY_DIMENSIONS,
    REPRESENTATION_CAPABILITIES,
    PresentationSpec,
    Representation,
    StyleRule,
)

LABEL_ATTRIBUTE_OPTION = "label_attribute"
_LABEL_ATTRIBUTE_REPRESENTATIONS: frozenset[Representation] = frozenset({"exploration", "diagram"})

LAYOUT_OPTION = "layout"
_LAYOUT_REPRESENTATIONS: frozenset[Representation] = frozenset({"exploration"})
VALID_EXPLORATION_LAYOUTS: frozenset[str] = frozenset({"clusters", "radial", "force"})


def _style_value_issues(capability: str, values: tuple[tuple[str, str], ...]) -> list[ViewpointValidationIssue]:
    """One ``unknown-style-value`` error per ``(path, value)`` outside *capability*'s
    value domain (color capabilities: token or ``#rrggbb``; notation capabilities:
    semantic tokens; anything else is free-form and never flagged)."""
    return [
        issue("error", "unknown-style-value", path, style_value_error(capability, value))
        for path, value in values
        if not is_valid_style_value(capability, value)
    ]


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
    elif rule.mode == "range":
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
    else:
        issues.extend(_validate_scale_rule(rule, path=path, registries=registries))
    issues.extend(_validate_mode_fields(rule, path=path))
    issues.extend(_style_value_issues(rule.capability, _rule_style_values(rule, path=path)))
    return issues


def _rule_style_values(rule: StyleRule, *, path: str) -> tuple[tuple[str, str], ...]:
    values: list[tuple[str, str]] = []
    if rule.value is not None:
        values.append((f"{path}/value", rule.value))
    values.extend((f"{path}/range_bands/{index}/value", band.value) for index, band in enumerate(rule.range_bands))
    values.extend((f"{path}/scale_tokens/{index}", token) for index, token in enumerate(rule.scale_tokens))
    return tuple(values)


def _validate_scale_rule(
    rule: StyleRule, *, path: str, registries: RegistrySnapshot
) -> list[ViewpointValidationIssue]:
    if rule.scale_attribute is None:
        return [
            issue(
                "error",
                "missing-scale-attribute",
                f"{path}/scale_attribute",
                "mode='scale' requires scale_attribute",
            )
        ]
    context: CriteriaContext = "connection" if rule.capability.startswith("edge_") else "entity"
    declared = resolve_attribute_path(rule.scale_attribute, context=context, registries=registries)
    if declared is None and not rule.scale_attribute.startswith("derived."):
        return [issue("error", "unknown-attribute", f"{path}/scale_attribute", "unknown scale attribute")]
    if declared not in (None, "reserved") and declared not in NUMERIC_ATTRIBUTE_TYPES:
        return [
            issue(
                "error",
                "operator-type-mismatch",
                f"{path}/scale_attribute",
                "scale attributes must be numeric or date values",
            )
        ]
    if len(rule.scale_tokens) != 2:
        return [issue("error", "scale-token-count", f"{path}/scale_tokens", "scale mode requires exactly two tokens")]
    return []


def _validate_mode_fields(rule: StyleRule, *, path: str) -> list[ViewpointValidationIssue]:
    if rule.mode == "match":
        mismatched = rule.range_attribute is not None or bool(rule.range_bands) or any(
            value is not None for value in (rule.scale_attribute, rule.scale_min, rule.scale_max)
        ) or bool(rule.scale_tokens)
    elif rule.mode == "range":
        mismatched = rule.match_criteria is not None or rule.value is not None or any(
            value is not None for value in (rule.scale_attribute, rule.scale_min, rule.scale_max)
        ) or bool(rule.scale_tokens)
    else:
        mismatched = (
            rule.match_criteria is not None
            or rule.value is not None
            or rule.range_attribute is not None
            or bool(rule.range_bands)
        )
    if not mismatched:
        return []
    return [
        issue(
            "error",
            "style-mode-field-mismatch",
            path,
            f"style fields do not match mode {rule.mode!r}",
        )
    ]


def _validate_layout_option(presentation: PresentationSpec, *, path: str) -> list[ViewpointValidationIssue]:
    if LAYOUT_OPTION not in presentation.display_options:
        return []
    option_path = f"{path}/display_options/{LAYOUT_OPTION}"
    if presentation.representation not in _LAYOUT_REPRESENTATIONS:
        representation = presentation.representation
        message = f"display option {LAYOUT_OPTION!r} is unsupported by representation {representation!r}"
        return [issue("error", "unsupported-display-option", option_path, message)]
    value = presentation.display_options[LAYOUT_OPTION]
    if not isinstance(value, str) or value not in VALID_EXPLORATION_LAYOUTS:
        layouts = ", ".join(sorted(VALID_EXPLORATION_LAYOUTS))
        return [issue("error", "unknown-layout", option_path, f"layout must be one of: {layouts}")]
    return []


def _validate_label_attribute(
    presentation: PresentationSpec, *, path: str, registries: RegistrySnapshot
) -> list[ViewpointValidationIssue]:
    if LABEL_ATTRIBUTE_OPTION not in presentation.display_options:
        return []
    option_path = f"{path}/display_options/{LABEL_ATTRIBUTE_OPTION}"
    if presentation.representation not in _LABEL_ATTRIBUTE_REPRESENTATIONS:
        representation = presentation.representation
        message = f"display option {LABEL_ATTRIBUTE_OPTION!r} is unsupported by representation {representation!r}"
        return [issue("error", "unsupported-display-option", option_path, message)]
    value = presentation.display_options[LABEL_ATTRIBUTE_OPTION]
    if not isinstance(value, str) or not value:
        return [issue("error", "unknown-attribute", option_path, "label_attribute must be an attribute path")]
    declared = resolve_attribute_path(value, context="entity", registries=registries)
    if declared is None and not value.startswith("derived."):
        return [issue("error", "unknown-attribute", option_path, f"unknown label attribute {value!r}")]
    return []


def validate_presentation(
    presentation: PresentationSpec, *, path: str, registries: RegistrySnapshot, check_ergonomics: bool
) -> list[ViewpointValidationIssue]:
    issues: list[ViewpointValidationIssue] = []
    capabilities = REPRESENTATION_CAPABILITIES[presentation.representation]
    for option in presentation.display_options:
        if option in (LABEL_ATTRIBUTE_OPTION, LAYOUT_OPTION):
            continue
        if option not in capabilities:
            issues.append(
                issue(
                    "error",
                    "unsupported-display-option",
                    f"{path}/display_options/{option}",
                    f"display option {option!r} is unsupported by representation {presentation.representation!r}",
                )
            )
    issues.extend(_validate_label_attribute(presentation, path=path, registries=registries))
    issues.extend(_validate_layout_option(presentation, path=path))
    for key, token in presentation.default_style.items():
        if key not in capabilities:
            issues.append(
                issue(
                    "error",
                    "unsupported-capability",
                    f"{path}/default_style/{key}",
                    f"capability {key!r} is unsupported by representation {presentation.representation!r}",
                )
            )
        issues.extend(_style_value_issues(key, ((f"{path}/default_style/{key}", token),)))
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
