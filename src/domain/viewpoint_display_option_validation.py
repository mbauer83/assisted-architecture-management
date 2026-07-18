"""Display-option validation for viewpoint presentations: the exploration layout
choice and the label-attribute override — both representation-gated, both validated at
save time so an unsupported or unknown option never reaches a renderer."""

from __future__ import annotations

from src.domain.viewpoint_condition_validation import RegistrySnapshot, issue, resolve_attribute_path
from src.domain.viewpoint_validation_issue import ViewpointValidationIssue
from src.domain.viewpoints import PresentationSpec, Representation

LABEL_ATTRIBUTE_OPTION = "label_attribute"
_LABEL_ATTRIBUTE_REPRESENTATIONS: frozenset[Representation] = frozenset({"exploration", "diagram"})

LAYOUT_OPTION = "layout"
_LAYOUT_REPRESENTATIONS: frozenset[Representation] = frozenset({"exploration"})
VALID_EXPLORATION_LAYOUTS: frozenset[str] = frozenset({"clusters", "radial", "force"})

def validate_layout_option(presentation: PresentationSpec, *, path: str) -> list[ViewpointValidationIssue]:
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


def validate_label_attribute(
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


