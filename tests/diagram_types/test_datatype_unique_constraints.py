from pathlib import Path

import pytest

from src.application.verification.artifact_verifier_types import Severity, VerificationResult
from src.diagram_types.datatype._contributions import UNIQUE_CONSTRAINT_CONTRIBUTION
from src.domain.diagram_verification import BaseDiagramVerificationContext


def _run(constraints: object) -> list:
    fm = {
        "diagram-type": "datatype",
        "diagram-entities": {
            "classifier": [{
                "id": "CLF@1.ab.order",
                "attributes": [{"name": "tenant"}, {"name": "number"}],
                "unique_constraints": constraints,
            }],
        },
    }
    ctx = BaseDiagramVerificationContext(
        fm=fm,
        loc="test.puml",
        scope="engagement",
        diagram_id="DT-A",
        allowed_connections=frozenset(),
        allowed_entities=frozenset(),
        catalogs=None,
    )
    result = VerificationResult(path=Path("test.puml"), file_type="diagram")
    UNIQUE_CONSTRAINT_CONTRIBUTION.run(None, ctx, result)
    return [issue for issue in result.issues if issue.code == "E337"]


def test_valid_composite_constraint_passes() -> None:
    assert _run([["tenant", "number"]]) == []


@pytest.mark.parametrize(
    ("constraint", "message"),
    [
        ([[]], "at least one"),
        ([["tenant", "tenant"]], "duplicate"),
        ([["tenant", "missing"]], "unknown attribute"),
        ([[""]], "empty attribute"),
    ],
)
def test_invalid_constraint_fails(constraint: object, message: str) -> None:
    issues = _run(constraint)
    assert len(issues) == 1
    assert issues[0].severity == Severity.ERROR
    assert message in issues[0].message


def test_unique_constraint_contribution_is_registered() -> None:
    from src.diagram_types.datatype import module

    codes = {
        code
        for contribution in module.diagram_verification_contributions()
        for code in contribution.diagnostic_codes
    }
    assert "E337" in codes
