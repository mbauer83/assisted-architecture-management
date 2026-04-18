"""Global-entity-reference verifier rules."""
from __future__ import annotations
from typing import TYPE_CHECKING
from src.common.model_verifier_types import Issue, Severity, VerificationResult
if TYPE_CHECKING:
    from src.common.model_verifier_registry import ModelRegistry

# Global-entity-reference rules
# ---------------------------------------------------------------------------

_GRF_TYPE = "global-entity-reference"
_GRF_FRONTMATTER_KEY = "global-entity-id"


def check_global_entity_reference(
    fm: dict,
    registry: "ModelRegistry | None",
    result: VerificationResult,
    loc: str,
) -> None:
    """Validate a global-entity-reference entity.

    E140 (error): ``global-entity-id`` field is missing or empty.
    E141 (error, registry-dependent): the referenced enterprise entity does not exist.
    W141 (warning, no registry): cannot verify because enterprise repo is not loaded.
    """
    global_id = fm.get(_GRF_FRONTMATTER_KEY)
    if not global_id:
        result.issues.append(Issue(
            Severity.ERROR, "E140",
            f"global-entity-reference is missing required '{_GRF_FRONTMATTER_KEY}' field",
            loc,
        ))
        return

    if registry is None:
        result.issues.append(Issue(
            Severity.WARNING, "W141",
            f"Cannot verify global-entity-id '{global_id}': enterprise repo not loaded",
            loc,
        ))
        return

    enterprise_ids = registry.enterprise_entity_ids()
    if not enterprise_ids:
        result.issues.append(Issue(
            Severity.WARNING, "W141",
            f"Cannot verify global-entity-id '{global_id}': no enterprise entities found in registry",
            loc,
        ))
        return

    if global_id not in enterprise_ids:
        result.issues.append(Issue(
            Severity.ERROR, "E141",
            f"global-entity-id '{global_id}' does not exist in the global (enterprise) repository",
            loc,
        ))
