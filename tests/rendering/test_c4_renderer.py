from __future__ import annotations

from pathlib import Path

from src.diagram_types.c4_renderer import C4PumlRenderer


class _Repo:
    def __init__(self, entities: dict[str, object], connections: list[object]) -> None:
        self._entities = entities
        self._connections = connections

    def get_entity(self, entity_id: str):
        return self._entities.get(entity_id)

    def list_connections(self):
        return list(self._connections)


class _Entity:
    def __init__(
        self,
        entity_id: str,
        name: str,
        artifact_type: str = "application-component",
        display_alias: str = "",
    ) -> None:
        self.artifact_id = entity_id
        self.name = name
        self.artifact_type = artifact_type
        self.display_alias = display_alias


class _Connection:
    def __init__(self, artifact_id: str, source: str, target: str, conn_type: str, content_text: str) -> None:
        self.artifact_id = artifact_id
        self.source = source
        self.target = target
        self.conn_type = conn_type
        self.content_text = content_text


def _renderer(
    scope_entity_type: str,
    scope_render_mode: str,
    internal_entity_types: list[str],
    person_archimate_types: frozenset[str] = frozenset(),
) -> C4PumlRenderer:
    return C4PumlRenderer(
        {
            "c4": {
                "scope_entity_type": scope_entity_type,
                "scope_render_mode": scope_render_mode,
                "internal_entity_types": internal_entity_types,
            }
        },
        person_archimate_types=person_archimate_types,
    )


def test_system_context_renders_scope_and_model_relationship(monkeypatch) -> None:
    repo = _Repo(
        entities={
            "BUS@1.user": _Entity("BUS@1.user", "Customer", artifact_type="business-actor", display_alias="P_Cust01"),
            "APP@1.system": _Entity("APP@1.system", "Ordering System", display_alias="SS_Order1"),
            "APP@1.payments": _Entity("APP@1.payments", "Payments", display_alias="SS_Paymt"),
        },
        connections=[
            _Connection(
                "BUS@1.user---APP@1.system@@archimate-access",
                "BUS@1.user",
                "APP@1.system",
                "archimate-access",
                "Uses the ordering workflow",
            )
        ],
    )
    monkeypatch.setattr("src.diagram_types._c4_resolve._repo", lambda repo_root: repo)

    renderer = _renderer(
        "software-system", "node", [],
        person_archimate_types=frozenset({"business-actor"}),
    )
    puml = renderer.render_body(
        "Ordering Context",
        [],
        [],
        "c4-system-context",
        Path("/tmp"),
        diagram_entities={"_scope_entity_id": "APP@1.system"},
    )

    assert 'actor "Customer" as P_Cust01' in puml
    assert 'rectangle "Ordering System" <<C4System>> as SS_Order1' in puml
    assert "[[" not in puml
    assert "Uses the ordering workflow" in puml


def test_container_view_renders_scope_as_boundary_and_collects_references() -> None:
    renderer = _renderer("software-system", "boundary", ["container"])

    diagram_entities = {
        "software-system": [{"id": "ordering", "entity_id": "APP@1.system", "scope": True, "label": "Ordering System"}],
        "container": [
            {"id": "api", "entity_id": "APP@1.api", "label": "API", "technology": "FastAPI"},
            {"id": "db", "entity_id": "APP@1.db", "label": "Database", "technology": "PostgreSQL"},
        ],
    }
    diagram_connections = [{"source": "api", "target": "db", "label": "Reads and writes orders"}]

    puml = renderer.render_body(
        "Ordering Containers",
        [],
        [],
        "c4-container",
        Path("/tmp"),
        diagram_entities=diagram_entities,
        diagram_connections=diagram_connections,
    )
    refs = renderer.collect_references(
        "c4-container",
        Path("/tmp"),
        diagram_entities=diagram_entities,
        diagram_connections=diagram_connections,
    )

    assert 'rectangle "Ordering System" <<C4System>> as SS_ordering_0 {' in puml
    assert 'rectangle "API\\n[FastAPI]" <<C4Container>> as C_api_0' in puml
    assert 'rectangle "Database\\n[PostgreSQL]" <<C4Container>> as C_db_1' in puml
    assert "Reads and writes orders" in puml
    assert refs.entity_ids == ()  # standalone mode: no model entity tracking
    assert refs.connection_ids == ()
