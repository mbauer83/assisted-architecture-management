"""Entity-specialization verifier rule: unknown slug (E170), or one declared for a
different concept-kind/parent-type than this entity's own artifact-type (E171).

The connection-side counterpart (E160/E161) lives in `_verifier_outgoing.py` next to the
rest of per-connection validation; the endpoint/relationship-restriction warnings (W128/
W129) live in `_verifier_rules_semantic.py` alongside the other semantic-triple checks they
share resolved source/target types with.
"""

from __future__ import annotations

from src.application.verification.artifact_verifier_types import Issue, Severity, VerificationResult
from src.domain.specializations import SpecializationCatalog


def check_entity_specialization(
    fm: dict,
    catalog: SpecializationCatalog,
    result: VerificationResult,
    loc: str,
) -> None:
    slug = fm.get("specialization")
    if not slug:
        return
    slug = str(slug)
    parent_type = str(fm.get("artifact-type", ""))
    if catalog.get("entity", parent_type, slug) is not None:
        return
    matches = [e for e in catalog.entries if e.slug == slug]
    if not matches:
        result.issues.append(Issue(Severity.ERROR, "E170", f"Unknown specialization slug '{slug}'", loc))
        return
    declared_for = ", ".join(sorted({f"{e.concept_kind}/{e.parent_type}" for e in matches}))
    result.issues.append(
        Issue(
            Severity.ERROR,
            "E171",
            f"Specialization '{slug}' is not declared for entity type '{parent_type}' "
            f"(declared for: {declared_for}).",
            loc,
        )
    )
