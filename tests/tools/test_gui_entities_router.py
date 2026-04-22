"""Regression tests for GUI entity listing across engagement and enterprise repos."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.common.model_query import ModelRepository
from src.tools.gui_routers.entity_listing import build_entity_summary_rows
from src.tools.gui_routers import state as gui_state


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _entity_md(artifact_id: str, name: str) -> str:
    rand = artifact_id.split(".")[1] if "." in artifact_id else "TEST"
    return f"""\
---
artifact-id: {artifact_id}
artifact-type: requirement
name: "{name}"
version: 0.1.0
status: active
last-updated: '2026-04-20'
---

<!-- §content -->

## {name}

Test entity.

## Properties

| Attribute | Value |
|---|---|
| (none) | (none) |

<!-- §display -->

### archimate

```yaml
domain: Motivation
element-type: Requirement
label: "{name}"
alias: REQ_{rand}
```
"""


def _outgoing_md(source_entity: str, connections: list[tuple[str, str]]) -> str:
    sections = "\n".join(f"### {conn_type} → {target}\n" for conn_type, target in connections)
    return f"""\
---
source-entity: {source_entity}
version: 0.1.0
status: active
last-updated: '2026-04-20'
---

<!-- §connections -->

{sections}
"""


@pytest.fixture()
def engagement_root(tmp_path: Path) -> Path:
    root = tmp_path / "engagements" / "ENG-TEST" / "architecture-repository"
    (root / "model").mkdir(parents=True)
    return root


@pytest.fixture()
def enterprise_root(tmp_path: Path) -> Path:
    root = tmp_path / "enterprise-repository"
    (root / "model").mkdir(parents=True)
    return root


def test_global_scope_listing_survives_root_entities_without_specialization_parent(
    engagement_root: Path,
    enterprise_root: Path,
) -> None:
    global_req = "REQ@2000000000.GloAAA.global-req"
    engagement_req = "REQ@1000000000.EngAAA.eng-req"

    _write(
        enterprise_root / "model" / "motivation" / "requirements" / f"{global_req}.md",
        _entity_md(global_req, "Global Req"),
    )
    _write(
        engagement_root / "model" / "motivation" / "requirements" / f"{engagement_req}.md",
        _entity_md(engagement_req, "Engagement Req"),
    )

    gui_state.init_state(ModelRepository([engagement_root, enterprise_root]), engagement_root, enterprise_root)

    repo = ModelRepository([engagement_root, enterprise_root])
    gui_state.init_state(repo, engagement_root, enterprise_root)

    global_entities = [entity for entity in repo.list_entities() if gui_state.is_global(entity.path)]
    rows = build_entity_summary_rows(global_entities[:1], repo)

    assert len(global_entities) == 1
    assert len(rows) == 1
    row = rows[0]
    assert row["artifact_id"] == global_req
    assert row["is_global"] is True
    assert "parent_entity_id" not in row
    assert "hierarchy_relation_type" not in row
    assert row["hierarchy_depth"] == 0
    assert "parent_specialization_id" not in row
    assert row["specialization_depth"] == 0


def test_entity_rows_emit_hierarchy_metadata_for_specialization_composition_and_aggregation(
    engagement_root: Path,
    enterprise_root: Path,
) -> None:
    parent_id = "REQ@1000000000.ParAAA.parent-req"
    specialization_child_id = "REQ@1000000001.ChdAAA.specialized-child"
    composition_child_id = "REQ@1000000002.CmpAAA.composed-child"
    aggregation_child_id = "REQ@1000000003.AggAAA.aggregated-child"
    global_req = "REQ@2000000000.GloAAA.global-req"

    _write(
        engagement_root / "model" / "motivation" / "requirements" / f"{parent_id}.md",
        _entity_md(parent_id, "Parent Req"),
    )
    _write(
        engagement_root / "model" / "motivation" / "requirements" / f"{specialization_child_id}.md",
        _entity_md(specialization_child_id, "Specialized Child"),
    )
    _write(
        engagement_root / "model" / "motivation" / "requirements" / f"{composition_child_id}.md",
        _entity_md(composition_child_id, "Composed Child"),
    )
    _write(
        engagement_root / "model" / "motivation" / "requirements" / f"{aggregation_child_id}.md",
        _entity_md(aggregation_child_id, "Aggregated Child"),
    )
    _write(
        engagement_root / "model" / "motivation" / "requirements" / f"{specialization_child_id}.outgoing.md",
        _outgoing_md(specialization_child_id, [("archimate-specialization", parent_id)]),
    )
    _write(
        engagement_root / "model" / "motivation" / "requirements" / f"{parent_id}.outgoing.md",
        _outgoing_md(
            parent_id,
            [
                ("archimate-composition", composition_child_id),
                ("archimate-aggregation", aggregation_child_id),
            ],
        ),
    )
    _write(
        enterprise_root / "model" / "motivation" / "requirements" / f"{global_req}.md",
        _entity_md(global_req, "Global Req"),
    )

    repo = ModelRepository([engagement_root, enterprise_root])
    gui_state.init_state(repo, engagement_root, enterprise_root)

    engagement_entities = [entity for entity in repo.list_entities() if not gui_state.is_global(entity.path)]
    rows = {row["artifact_id"]: row for row in build_entity_summary_rows(engagement_entities, repo)}

    assert rows[parent_id]["specialization_depth"] == 0
    assert rows[parent_id]["hierarchy_depth"] == 0
    assert "parent_entity_id" not in rows[parent_id]
    assert "parent_specialization_id" not in rows[parent_id]

    assert rows[specialization_child_id]["hierarchy_depth"] == 1
    assert rows[specialization_child_id]["hierarchy_relation_type"] == "specialization"
    assert rows[specialization_child_id]["parent_entity_id"] == parent_id
    assert rows[specialization_child_id]["parent_specialization_id"] == parent_id

    assert rows[composition_child_id]["hierarchy_depth"] == 1
    assert rows[composition_child_id]["hierarchy_relation_type"] == "composition"
    assert rows[composition_child_id]["parent_entity_id"] == parent_id
    assert rows[composition_child_id]["specialization_depth"] == 1

    assert rows[aggregation_child_id]["hierarchy_depth"] == 1
    assert rows[aggregation_child_id]["hierarchy_relation_type"] == "aggregation"
    assert rows[aggregation_child_id]["parent_entity_id"] == parent_id
    assert rows[aggregation_child_id]["specialization_depth"] == 1

    assert all(
        ("parent_entity_id" not in row) or isinstance(row["parent_entity_id"], str)
        for row in rows.values()
    )


def test_connection_to_dict_resolves_live_endpoint_names(engagement_root: Path, enterprise_root: Path) -> None:
    src_id = "REQ@1000000000.SrcAAA.source-name"
    tgt_id = "REQ@1000000001.TgtAAA.target-name"
    _write(
        engagement_root / "model" / "motivation" / "requirements" / f"{src_id}.md",
        _entity_md(src_id, "Source Display Name"),
    )
    _write(
        engagement_root / "model" / "motivation" / "requirements" / f"{tgt_id}.md",
        _entity_md(tgt_id, "Target Display Name"),
    )
    _write(
        engagement_root / "model" / "motivation" / "requirements" / f"{src_id}.outgoing.md",
        _outgoing_md(src_id, [("archimate-association", tgt_id)]),
    )

    repo = ModelRepository([engagement_root, enterprise_root])
    gui_state.init_state(repo, engagement_root, enterprise_root)

    conn = repo.find_connections_for(src_id)[0]
    payload = gui_state.connection_to_dict(conn)

    assert payload["source_name"] == "Source Display Name"
    assert payload["target_name"] == "Target Display Name"


def test_entity_context_read_model_groups_connections_and_counts(
    engagement_root: Path,
    enterprise_root: Path,
) -> None:
    src_id = "REQ@1000000000.SrcAAA.source"
    tgt_id = "REQ@1000000001.TgtAAA.target"
    peer_id = "REQ@1000000002.PeerAA.peer"
    _write(engagement_root / "model" / "motivation" / "requirements" / f"{src_id}.md", _entity_md(src_id, "Source"))
    _write(engagement_root / "model" / "motivation" / "requirements" / f"{tgt_id}.md", _entity_md(tgt_id, "Target"))
    _write(engagement_root / "model" / "motivation" / "requirements" / f"{peer_id}.md", _entity_md(peer_id, "Peer"))
    _write(
        engagement_root / "model" / "motivation" / "requirements" / f"{src_id}.outgoing.md",
        _outgoing_md(src_id, [("archimate-association", tgt_id), ("archimate-flow", peer_id)]),
    )
    _write(
        engagement_root / "model" / "motivation" / "requirements" / f"{peer_id}.outgoing.md",
        _outgoing_md(peer_id, [("archimate-association", src_id)]),
    )

    repo = ModelRepository([engagement_root, enterprise_root])
    gui_state.init_state(repo, engagement_root, enterprise_root)

    payload = repo.read_entity_context(src_id)
    assert payload is not None

    assert payload["entity"]["artifact_id"] == src_id
    assert payload["counts"] == {"conn_in": 0, "conn_out": 1, "conn_sym": 2}
    assert [conn["artifact_id"] for conn in payload["connections"]["outbound"]] == [f"{src_id}---{peer_id}@@archimate-flow"]
    assert payload["connections"]["inbound"] == []
    assert {conn["artifact_id"] for conn in payload["connections"]["symmetric"]} == {
        f"{src_id}---{tgt_id}@@archimate-association",
        f"{peer_id}---{src_id}@@archimate-association",
    }
    assert payload["generation"] >= 1


def test_clear_caches_applies_incremental_outgoing_changes(
    engagement_root: Path,
    enterprise_root: Path,
) -> None:
    src_id = "REQ@1000000000.SrcAAA.source"
    tgt_a = "REQ@1000000001.TgtAAA.target-a"
    tgt_b = "REQ@1000000002.TgtBBB.target-b"
    for artifact_id, name in ((src_id, "Source"), (tgt_a, "Target A"), (tgt_b, "Target B")):
        _write(engagement_root / "model" / "motivation" / "requirements" / f"{artifact_id}.md", _entity_md(artifact_id, name))
    outgoing_path = engagement_root / "model" / "motivation" / "requirements" / f"{src_id}.outgoing.md"
    _write(outgoing_path, _outgoing_md(src_id, [("archimate-flow", tgt_a)]))

    repo = ModelRepository([engagement_root, enterprise_root])
    gui_state.init_state(repo, engagement_root, enterprise_root)

    before = repo.read_entity_context(src_id)
    assert before is not None
    assert before["counts"] == {"conn_in": 0, "conn_out": 1, "conn_sym": 2}

    _write(outgoing_path, _outgoing_md(src_id, [("archimate-flow", tgt_a), ("archimate-serving", tgt_b)]))
    gui_state.clear_caches(outgoing_path)

    after = repo.read_entity_context(src_id)
    assert after is not None
    assert after["counts"] == {"conn_in": 0, "conn_out": 2, "conn_sym": 2}
    assert after["generation"] > before["generation"]
    assert {conn["artifact_id"] for conn in after["connections"]["outbound"]} == {
        f"{src_id}---{tgt_a}@@archimate-flow",
        f"{src_id}---{tgt_b}@@archimate-serving",
    }


def test_entity_detail_view_uses_entity_context_request() -> None:
    view_path = Path("tools/gui/src/ui/views/EntityDetailView.vue")
    content = view_path.read_text(encoding="utf-8")

    assert "svc.getEntityContext(entityId.value)" in content
    assert "svc.getConnections(" not in content
