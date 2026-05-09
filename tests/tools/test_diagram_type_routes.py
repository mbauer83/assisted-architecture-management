from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from src.application.artifact_repository import ArtifactRepository
from src.application.modeling.artifact_write import generate_diagram_id
from src.application.verification.artifact_verifier import ArtifactRegistry, ArtifactVerifier
from src.domain.artifact_types import EntityRecord
from src.infrastructure.app_bootstrap import build_module_registry
from src.infrastructure.artifact_index import shared_artifact_index
from src.infrastructure.diagram_types import diagram_type_domain
from src.infrastructure.gui.routers import state as gui_state
from src.infrastructure.gui.routers._diagram_context import fuzzy_entity_hits
from src.infrastructure.gui.routers.diagram_types import (
    list_diagram_types,
    read_diagram_kind_ui_config,
)
from src.infrastructure.gui.routers.diagrams import (
    get_diagram_kind_connection_types,
    get_diagram_kind_entity_types,
    read_diagram,
)
from src.infrastructure.write.artifact_write.diagram import create_diagram
from src.infrastructure.write.artifact_write.diagram_edit import edit_diagram


@pytest.fixture()
def repo_root(tmp_path: Path) -> Path:
    root = tmp_path / "engagements" / "ENG-TEST" / "architecture-repository"
    (root / "model").mkdir(parents=True)
    (root / "diagram-catalog" / "diagrams").mkdir(parents=True)
    return root


def _verifier(repo_root: Path) -> ArtifactVerifier:
    return ArtifactVerifier(ArtifactRegistry(shared_artifact_index(repo_root)))


def _entity(artifact_id: str, artifact_type: str, name: str) -> EntityRecord:
    return EntityRecord(
        artifact_id=artifact_id,
        artifact_type=artifact_type,
        name=name,
        version="0.1.0",
        status="draft",
        domain="motivation",
        subdomain=artifact_type,
        path=Path(f"/tmp/{artifact_id}.md"),
        keywords=(),
        extra={},
        content_text=f"{name} {artifact_type}",
        display_blocks={},
        display_label=name,
        display_alias=artifact_id.split(".")[1],
    )


def test_default_registry_registers_matrix_diagram_kind() -> None:
    registry = build_module_registry()

    matrix = registry.find_diagram_type("matrix")

    assert matrix is not None
    assert "goal" in matrix.effective_entity_types()
    assert "archimate-flow" in matrix.effective_connection_types()


def test_default_registry_registers_activity_diagram_kind() -> None:
    registry = build_module_registry()

    activity = registry.find_diagram_type("activity")

    assert activity is not None
    assert activity.ui_config.label == "Activity Diagram"
    assert activity.effective_entity_types() == {}


def test_diagram_type_domain_is_registry_derived() -> None:
    assert diagram_type_domain("archimate-business") == "business"
    assert diagram_type_domain("archimate-layered") is None
    assert diagram_type_domain("matrix") is None


def test_diagram_kind_entity_types_endpoint_excludes_internal_types() -> None:
    items = get_diagram_kind_entity_types("archimate-business")

    assert items
    assert any(item["artifact_type"] == "business-actor" for item in items)
    assert all(item["artifact_type"] != "global-artifact-reference" for item in items)


def test_diagram_kind_connection_types_endpoint_exposes_effective_vocabulary() -> None:
    items = get_diagram_kind_connection_types("matrix")

    flow_item = next(item for item in items if item["connection_type"] == "archimate-flow")

    assert flow_item["conn_lang"] == "archimate"
    assert "flow" in flow_item["classifications"]


def test_diagram_kind_ui_config_endpoint_shape() -> None:
    kinds = list_diagram_types()
    activity = read_diagram_kind_ui_config("activity")

    assert any(kind["key"] == "activity" and kind["label"] == "Activity Diagram" for kind in kinds)
    assert activity["entity_search_filter"] is False
    assert activity["diagram_only_types"][0]["entity_type"] == "swimlane"
    assert activity["type_ui_slots"]["step_editor"] == "activity-steps"


def test_fuzzy_entity_hits_filters_to_accepted_entity_types() -> None:
    requirement = _entity("REQ@1.req.customer-signup", "requirement", "Customer Signup")
    component = _entity("APP@1.app.customer-service", "application-component", "Customer Service")
    repo = SimpleNamespace(list_entities=lambda: [requirement, component])

    hits = fuzzy_entity_hits(
        repo,
        "customer service application-component",
        10,
        set(),
        accepted_entity_types={"application-component"},
    )

    assert [hit["artifact_id"] for hit in hits] == [component.artifact_id]


def test_diagram_entities_round_trips_create_read_edit_read(repo_root: Path) -> None:
    diagram_id = generate_diagram_id("activity", "Signup Flow")
    puml = f"@startuml {diagram_id}\ntitle Signup Flow\n@enduml\n"
    created_diagram_entities = {
        "swimlanes": [{"id": "sw-1", "label": "Customer"}],
        "steps": [{"type": "action", "id": "act-1", "label": "Submit Request", "lane_id": "sw-1"}],
    }

    create_result = create_diagram(
        repo_root=repo_root,
        verifier=_verifier(repo_root),
        clear_repo_caches=lambda _path: None,
        diagram_type="activity",
        name="Signup Flow",
        puml=puml,
        artifact_id=diagram_id,
        keywords=None,
        diagram_entities=created_diagram_entities,
        version="0.1.0",
        status="draft",
        last_updated=None,
        dry_run=False,
    )
    assert create_result.wrote is True

    repo = ArtifactRepository(shared_artifact_index(repo_root))
    repo.refresh()
    gui_state.init_state(repo, repo_root, None)
    assert read_diagram(diagram_id)["diagram_entities"] == created_diagram_entities

    edited_diagram_entities = {
        "swimlanes": [{"id": "sw-2", "label": "System"}],
        "steps": [{"type": "action", "id": "act-2", "label": "Validate", "lane_id": "sw-2"}],
    }
    edit_result = edit_diagram(
        repo_root=repo_root,
        verifier=_verifier(repo_root),
        clear_repo_caches=lambda _path: None,
        artifact_id=diagram_id,
        puml=puml,
        diagram_entities=edited_diagram_entities,
        dry_run=False,
    )
    assert edit_result.wrote is True

    repo.refresh()
    assert read_diagram(diagram_id)["diagram_entities"] == edited_diagram_entities
