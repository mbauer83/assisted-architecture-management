from __future__ import annotations

from pathlib import Path

from src.domain.archimate_relation_rendering import format_cardinality_label
from src.domain.artifact_types import ConnectionRecord, EntityRecord
from src.infrastructure.mcp.artifact_mcp.query_scaffold_tools import artifact_diagram_scaffold
from src.infrastructure.rendering.diagram_builder import generate_archimate_puml_body
from src.infrastructure.rendering.generate_macros import generate_macros


def _entity(
    artifact_id: str,
    artifact_type: str,
    name: str,
    alias: str,
    *,
    domain: str = "motivation",
    subdomain: str = "goals",
) -> EntityRecord:
    return EntityRecord(
        artifact_id=artifact_id,
        artifact_type=artifact_type,
        name=name,
        version="0.1.0",
        status="draft",
        domain=domain,
        subdomain=subdomain,
        path=Path(f"/tmp/{artifact_id}.md"),
        keywords=(),
        extra={},
        content_text="",
        display_blocks={},
        display_label=name,
        display_alias=alias,
    )


def _conn(
    source: str,
    target: str,
    conn_type: str = "archimate-realization",
    *,
    src_cardinality: str = "",
    tgt_cardinality: str = "",
) -> ConnectionRecord:
    return ConnectionRecord(
        artifact_id=f"{source}---{target}@@{conn_type}",
        source=source,
        target=target,
        conn_type=conn_type,
        version="0.1.0",
        status="draft",
        path=Path("/tmp/test.outgoing.md"),
        extra={},
        content_text="",
        src_cardinality=src_cardinality,
        tgt_cardinality=tgt_cardinality,
    )


def test_generate_archimate_puml_body_normalizes_aliases_in_entities_and_connections() -> None:
    goal = _entity(
        "GOL@1.B6G_-P.support-technology-design-for-ai",
        "goal",
        "Support Technology Design for AI",
        "GOL_B6G_-P",
    )
    outcome = _entity(
        "OUT@1.i-3Bi-.ai-agents-query-technology-architecture",
        "outcome",
        "AI Agents Query Technology Architecture to Identify Constraints",
        "OUT_i-3Bi-",
        subdomain="outcomes",
    )

    puml = generate_archimate_puml_body(
        "Alias Test",
        [goal, outcome],
        [_conn(outcome.artifact_id, goal.artifact_id)],
        diagram_type="archimate-motivation",
    )

    assert " as GOL_B6G__P" in puml
    assert " as OUT_i_3Bi_" in puml
    assert 'Rel_Realization_Up(OUT_i_3Bi_, GOL_B6G__P, "")' in puml
    assert "GOL_B6G_-P" not in puml
    assert "OUT_i-3Bi-" not in puml


def test_generate_archimate_puml_body_single_domain_uses_type_groupings() -> None:
    driver_a = _entity("DRV@1.a.driver-a", "driver", "Driver A", "DRV_A", subdomain="drivers")
    driver_b = _entity("DRV@1.b.driver-b", "driver", "Driver B", "DRV_B", subdomain="drivers")
    assessment = _entity(
        "ASS@1.a.assessment-a",
        "assessment",
        "Assessment A",
        "ASS_A",
        subdomain="assessments",
    )

    puml = generate_archimate_puml_body(
        "Drivers and Assessments",
        [driver_a, driver_b, assessment],
        [
            _conn(driver_a.artifact_id, assessment.artifact_id, "archimate-influence"),
            _conn(driver_b.artifact_id, driver_a.artifact_id, "archimate-association"),
        ],
        diagram_type="archimate-motivation",
    )

    assert 'rectangle "Motivation" <<MotivationGrouping>>' not in puml
    assert 'rectangle "Drivers" <<MotivationGrouping>> {' in puml
    assert 'rectangle "Assessments" <<MotivationGrouping>> {' in puml
    assert "top to bottom direction" in puml
    assert "DRV_A -[hidden]right- DRV_B" in puml
    assert "DRV_B -[hidden]down- ASS_A" in puml
    assert 'Rel_Influence_Down(DRV_A, ASS_A, "")' in puml


def test_generate_macros_normalizes_aliases(tmp_path: Path) -> None:
    repo_root = tmp_path / "engagements" / "ENG-T" / "architecture-repository"
    entity_path = repo_root / "model" / "motivation" / "outcomes" / "OUT@1.i-3Bi-.alias-test.md"
    entity_path.parent.mkdir(parents=True, exist_ok=True)
    entity_path.write_text(
        """\
---
artifact-id: OUT@1.i-3Bi-.alias-test
artifact-type: outcome
name: "Alias Test"
version: 0.1.0
status: draft
last-updated: '2026-04-20'
---

<!-- §content -->

## Alias Test

<!-- §display -->

### archimate

```yaml
domain: Motivation
element-type: Outcome
label: "Alias Test"
alias: OUT_i-3Bi-
```
""",
        encoding="utf-8",
    )

    out_path = generate_macros(repo_root)
    content = out_path.read_text(encoding="utf-8")

    assert "$DECL_OUT_i_3Bi_" in content
    assert " as OUT_i_3Bi_" in content
    assert "OUT_i-3Bi-" not in content


def test_model_diagram_scaffold_uses_canonical_aliases(tmp_path: Path) -> None:
    repo_root = tmp_path / "engagements" / "ENG-T" / "architecture-repository"
    goal_id = "GOL@1.B6G_-P.support-technology-design-for-ai"
    outcome_id = "OUT@1.i-3Bi-.ai-agents-query-technology-architecture"
    goal_path = repo_root / "model" / "motivation" / "goals" / f"{goal_id}.md"
    outcome_path = repo_root / "model" / "motivation" / "outcomes" / f"{outcome_id}.md"
    outgoing_path = repo_root / "model" / "motivation" / "outcomes" / f"{outcome_id}.outgoing.md"

    goal_path.parent.mkdir(parents=True, exist_ok=True)
    outcome_path.parent.mkdir(parents=True, exist_ok=True)
    goal_path.write_text(
        f"""\
---
artifact-id: {goal_id}
artifact-type: goal
name: "Support Technology Design for AI"
version: 0.1.0
status: draft
last-updated: '2026-04-20'
---

<!-- §content -->

## Support Technology Design for AI

<!-- §display -->

### archimate

```yaml
domain: Motivation
element-type: Goal
label: "Support Technology Design for AI"
alias: GOL_B6G_-P
```
""",
        encoding="utf-8",
    )
    outcome_path.write_text(
        f"""\
---
artifact-id: {outcome_id}
artifact-type: outcome
name: "AI Agents Query Technology Architecture to Identify Constraints"
version: 0.1.0
status: draft
last-updated: '2026-04-20'
---

<!-- §content -->

## AI Agents Query Technology Architecture to Identify Constraints

<!-- §display -->

### archimate

```yaml
domain: Motivation
element-type: Outcome
label: "AI Agents Query Technology Architecture to Identify Constraints"
alias: OUT_i-3Bi-
```
""",
        encoding="utf-8",
    )
    outgoing_path.write_text(
        f"""\
---
source-entity: {outcome_id}
version: 0.1.0
status: draft
last-updated: '2026-04-20'
---

<!-- §connections -->

### archimate-realization → {goal_id}
""",
        encoding="utf-8",
    )

    result = artifact_diagram_scaffold(
        entity_ids=[goal_id, outcome_id],
        diagram_name="Alias Scaffold",
        repo_root=str(repo_root),
        repo_scope="engagement",
    )
    puml = str(result["puml"])

    assert " as GOL_B6G__P" in puml
    assert " as OUT_i_3Bi_" in puml
    assert 'Rel_Realization_Up(OUT_i_3Bi_, GOL_B6G__P, "")' in puml
    assert "GOL_B6G_-P" not in puml
    assert "OUT_i-3Bi-" not in puml


def test_model_diagram_scaffold_single_domain_uses_type_groupings(tmp_path: Path) -> None:
    repo_root = tmp_path / "engagements" / "ENG-T" / "architecture-repository"
    driver_id = "DRV@1.a.driver-a"
    assessment_id = "ASS@1.a.assessment-a"
    driver_path = repo_root / "model" / "motivation" / "drivers" / f"{driver_id}.md"
    assessment_path = repo_root / "model" / "motivation" / "assessments" / f"{assessment_id}.md"
    outgoing_path = repo_root / "model" / "motivation" / "drivers" / f"{driver_id}.outgoing.md"

    driver_path.parent.mkdir(parents=True, exist_ok=True)
    assessment_path.parent.mkdir(parents=True, exist_ok=True)
    driver_path.write_text(
        f"""\
---
artifact-id: {driver_id}
artifact-type: driver
name: "Driver A"
version: 0.1.0
status: draft
last-updated: '2026-04-20'
---

<!-- §content -->

## Driver A

<!-- §display -->

### archimate

```yaml
domain: Motivation
element-type: Driver
label: "Driver A"
alias: DRV_A
```
""",
        encoding="utf-8",
    )
    assessment_path.write_text(
        f"""\
---
artifact-id: {assessment_id}
artifact-type: assessment
name: "Assessment A"
version: 0.1.0
status: draft
last-updated: '2026-04-20'
---

<!-- §content -->

## Assessment A

<!-- §display -->

### archimate

```yaml
domain: Motivation
element-type: Assessment
label: "Assessment A"
alias: ASS_A
```
""",
        encoding="utf-8",
    )
    outgoing_path.write_text(
        f"""\
---
source-entity: {driver_id}
version: 0.1.0
status: draft
last-updated: '2026-04-20'
---

<!-- §connections -->

### archimate-influence → {assessment_id}
""",
        encoding="utf-8",
    )

    result = artifact_diagram_scaffold(
        entity_ids=[driver_id, assessment_id],
        diagram_name="Drivers and Assessments",
        repo_root=str(repo_root),
        repo_scope="engagement",
    )
    puml = str(result["puml"])

    assert 'rectangle "Motivation" <<MotivationGrouping>>' not in puml
    assert 'rectangle "Drivers" <<MotivationGrouping>> {' in puml
    assert 'rectangle "Assessments" <<MotivationGrouping>> {' in puml
    assert "top to bottom direction" in puml
    assert "DRV_A -[hidden]down- ASS_A" in puml
    assert 'Rel_Influence_Down(DRV_A, ASS_A, "")' in puml


# ── format_cardinality_label unit tests ───────────────────────────────────────


def test_format_cardinality_label_both_ends() -> None:
    assert format_cardinality_label("1", "0..*") == "1 -> 0..*"


def test_format_cardinality_label_src_only() -> None:
    assert format_cardinality_label("1", "") == "1 ->"


def test_format_cardinality_label_tgt_only() -> None:
    assert format_cardinality_label("", "*") == "-> *"


def test_format_cardinality_label_neither() -> None:
    assert format_cardinality_label("", "") == ""


# ── generate_archimate_puml_body cardinality rendering ───────────────────────


def test_generate_archimate_puml_body_renders_cardinality_both_ends() -> None:
    goal = _entity("GOL@1.a.goal-a", "goal", "Goal A", "GOL_A")
    outcome = _entity("OUT@1.a.outcome-a", "outcome", "Outcome A", "OUT_A", subdomain="outcomes")
    conn = _conn(
        outcome.artifact_id,
        goal.artifact_id,
        "archimate-realization",
        src_cardinality="1",
        tgt_cardinality="0..*",
    )

    puml = generate_archimate_puml_body("Test", [goal, outcome], [conn])

    assert '1 -> 0..*' in puml
    assert 'Rel_Realization_Up(OUT_A, GOL_A, "1 -> 0..*")' in puml


def test_generate_archimate_puml_body_renders_cardinality_src_only() -> None:
    goal = _entity("GOL@1.a.goal-a", "goal", "Goal A", "GOL_A")
    outcome = _entity("OUT@1.a.outcome-a", "outcome", "Outcome A", "OUT_A", subdomain="outcomes")
    conn = _conn(
        outcome.artifact_id,
        goal.artifact_id,
        "archimate-realization",
        src_cardinality="1",
    )

    puml = generate_archimate_puml_body("Test", [goal, outcome], [conn])

    assert 'Rel_Realization_Up(OUT_A, GOL_A, "1 ->")' in puml


def test_generate_archimate_puml_body_no_cardinality_keeps_empty_label() -> None:
    goal = _entity("GOL@1.a.goal-a", "goal", "Goal A", "GOL_A")
    outcome = _entity("OUT@1.a.outcome-a", "outcome", "Outcome A", "OUT_A", subdomain="outcomes")
    conn = _conn(outcome.artifact_id, goal.artifact_id, "archimate-realization")

    puml = generate_archimate_puml_body("Test", [goal, outcome], [conn])

    assert 'Rel_Realization_Up(OUT_A, GOL_A, "")' in puml
