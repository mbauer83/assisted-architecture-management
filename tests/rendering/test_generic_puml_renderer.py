from __future__ import annotations

from pathlib import Path

from src.domain.artifact_types import ConnectionRecord, EntityRecord
from src.infrastructure.rendering.generic_puml_renderer import GenericPumlRenderer

_ARCHIMATE_CONFIG = {
    "includes": ["_archimate-stereotypes.puml", "_archimate-glyphs.puml"],
    "grouping": {"by_field": "domain_dir", "stereotype_pattern": "{domain_dir|capitalize}Grouping"},
    "layout": {
        "nesting_connection_classes": ["nesting"],
        "flow_connection_classes": ["flow"],
    },
}


def _entity(
    artifact_id: str,
    artifact_type: str,
    name: str,
    alias: str,
    *,
    domain: str = "motivation",
    subdomain: str = "goals",
    element_type: str | None = None,
) -> EntityRecord:
    display_blocks = {}
    if element_type is not None:
        display_blocks["archimate"] = (
            "```yaml\n"
            f"domain: {domain.title()}\n"
            f"element-type: {element_type}\n"
            f"label: \"{name}\"\n"
            f"alias: {alias}\n"
            "```"
        )
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
        display_blocks=display_blocks,
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


def test_render_body_uses_includes_and_single_domain_type_groupings(tmp_path: Path) -> None:
    renderer = GenericPumlRenderer(_ARCHIMATE_CONFIG)
    driver = _entity("DRV@1.a.driver-a", "driver", "Driver A", "DRV_A", subdomain="drivers")
    assessment = _entity("ASS@1.a.assessment-a", "assessment", "Assessment A", "ASS_A", subdomain="assessments")

    puml = renderer.render_body(
        "Drivers and Assessments",
        [driver, assessment],
        [_conn(driver.artifact_id, assessment.artifact_id, "archimate-influence")],
        "archimate-motivation",
        tmp_path,
    )

    assert "!include ../_archimate-stereotypes.puml" in puml
    assert "!include ../_archimate-glyphs.puml" in puml
    assert 'rectangle "Drivers" <<MotivationGrouping>> {' in puml
    assert 'rectangle "Assessments" <<MotivationGrouping>> {' in puml
    assert "top to bottom direction" in puml
    assert 'Rel_Influence_Down(DRV_A, ASS_A, "")' in puml


def test_render_body_renders_junction_inside_nested_parent(tmp_path: Path) -> None:
    renderer = GenericPumlRenderer(_ARCHIMATE_CONFIG)
    process = _entity("PRC@1.a.process-a", "process", "Process A", "PRC_A", domain="business", subdomain="processes")
    function_a = _entity(
        "FNC@1.a.function-a", "function", "Function A", "FNC_A",
        domain="business", subdomain="functions",
    )
    function_b = _entity(
        "FNC@1.b.function-b", "function", "Function B", "FNC_B",
        domain="business", subdomain="functions",
    )
    junction = _entity("JNA@1.a.and-a", "and-junction", "AND A", "JNA_A", domain="business", subdomain="junctions")

    puml = renderer.render_body(
        "Nested Junction",
        [process, function_a, function_b, junction],
        [
            _conn(process.artifact_id, function_a.artifact_id, "archimate-composition"),
            _conn(process.artifact_id, function_b.artifact_id, "archimate-composition"),
            _conn(function_a.artifact_id, junction.artifact_id, "archimate-flow"),
            _conn(junction.artifact_id, function_b.artifact_id, "archimate-flow"),
        ],
        "archimate-business",
        tmp_path,
    )

    assert 'rectangle "Process A" as PRC_A {' in puml
    assert 'circle " " as JNA_A' in puml
    process_start = puml.index('rectangle "Process A" as PRC_A {')
    process_end = puml.index("}", process_start)
    assert 'circle " " as JNA_A' in puml[process_start:process_end]


def test_render_body_supports_sprite_and_non_sprite_element_declarations(tmp_path: Path) -> None:
    renderer = GenericPumlRenderer(_ARCHIMATE_CONFIG)
    stakeholder = _entity(
        "STK@1.a.stakeholder-a",
        "stakeholder",
        "Stakeholder A",
        "STK_A",
        subdomain="stakeholders",
        element_type="Stakeholder",
    )
    value = _entity(
        "VAL@1.a.value-a",
        "value",
        "Value A",
        "VAL_A",
        subdomain="values",
        element_type="Value",
    )

    puml = renderer.render_body(
        "Declaration Patterns",
        [stakeholder, value],
        [],
        "archimate-motivation",
        tmp_path,
    )

    assert 'rectangle "<$archimate_Stakeholder{scale=1.5}> Stakeholder A" <<Stakeholder>> as STK_A' in puml
    assert 'rectangle "Value A" <<Value>> as VAL_A' in puml


def test_inject_includes_inlines_only_needed_stereotypes_and_sprites(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    catalog = repo_root / "diagram-catalog"
    catalog.mkdir(parents=True, exist_ok=True)
    (catalog / "_archimate-stereotypes.puml").write_text(
        """\
' Grouping containers.
!include <archimate/Archimate>
hide stereotype
skinparam rectangle<<Process>> {
  BackgroundColor #E0D8CC
  BorderColor #8C7E6A
}
""",
        encoding="utf-8",
    )
    (catalog / "_archimate-glyphs.puml").write_text(
        "sprite $archimate_Process <svg xmlns=\"http://www.w3.org/2000/svg\"></svg>\n",
        encoding="utf-8",
    )
    renderer = GenericPumlRenderer(_ARCHIMATE_CONFIG)

    result = renderer.inject_includes(
        """\
@startuml test
!include ../_archimate-stereotypes.puml
!include ../_archimate-glyphs.puml
rectangle "<$archimate_Process{scale=1.5}> Proc" <<Process>> as PROC_A
@enduml
""",
        repo_root,
    )

    assert "Grouping containers" not in result
    assert "hide stereotype" in result
    assert "skinparam rectangle<<Process>>" in result
    assert "sprite $archimate_Process" in result
    assert "!include ../_archimate-glyphs.puml" not in result
