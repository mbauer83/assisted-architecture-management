"""Round-trip tests for the assurance export/import portability bundle.

The seed workflow (export on one machine → commit JSON → import in CI/another machine)
relies on three guarantees, asserted here:
  - ids are preserved verbatim, so edges and arch-refs keep resolving;
  - analyses, nodes, edges, and arch-refs all survive the round-trip;
  - `replace=True` is idempotent (re-seeding does not duplicate or accumulate).
"""

from __future__ import annotations

import pytest

pytest.importorskip("sqlcipher3", reason="sqlcipher3 not installed")


def _make_store(tmp_path, name):  # type: ignore[no-untyped-def]
    from src.infrastructure.assurance._sqlcipher_store import SQLCipherAssuranceStore
    from src.infrastructure.assurance.lifecycle import init_store

    db_path = tmp_path / name
    init_store(db_path)
    store = SQLCipherAssuranceStore(db_path)
    store.unlock()
    return store


@pytest.fixture()
def populated_store(tmp_path):  # type: ignore[no-untyped-def]
    store = _make_store(tmp_path, "source.db")
    loss = store.create_node("loss", "Disclosure of evidence", tlp="TLP:GREEN")
    hazard = store.create_node("hazard", "Store readable in plaintext", tlp="TLP:GREEN")
    store.add_edge(hazard, loss, "leads-to")
    store.register_arch_ref(loss, "REQ@1.example.confidential-storage", "refines")
    yield store, {"loss": loss, "hazard": hazard}
    store.lock()


def test_export_bundle_includes_all_record_kinds(populated_store) -> None:  # type: ignore[no-untyped-def]
    from src.infrastructure.assurance._portability import export_bundle

    store, _ids = populated_store
    bundle = export_bundle(store)
    assert set(bundle) == {"analyses", "nodes", "edges", "arch_refs"}
    assert len(bundle["nodes"]) == 2
    assert len(bundle["edges"]) == 1
    assert len(bundle["arch_refs"]) == 1


def test_round_trip_preserves_ids_and_graph(populated_store, tmp_path) -> None:  # type: ignore[no-untyped-def]
    from src.infrastructure.assurance._portability import export_bundle, import_bundle

    source, ids = populated_store
    bundle = export_bundle(source)

    target = _make_store(tmp_path, "target.db")
    try:
        counts = import_bundle(target, bundle)
        assert counts == {"analyses": 0, "nodes": 2, "edges": 1, "arch_refs": 1}

        # Ids are preserved verbatim, so the edge still resolves to its endpoints.
        assert {n["node_id"] for n in target.list_nodes()} == {ids["loss"], ids["hazard"]}
        edge = target.list_edges()[0]
        assert (edge["source_id"], edge["target_id"]) == (ids["hazard"], ids["loss"])
        assert target.list_arch_refs()[0]["assurance_node_id"] == ids["loss"]
    finally:
        target.lock()


def test_replace_is_idempotent(populated_store, tmp_path) -> None:  # type: ignore[no-untyped-def]
    from src.infrastructure.assurance._portability import export_bundle, import_bundle

    source, _ids = populated_store
    bundle = export_bundle(source)

    target = _make_store(tmp_path, "target.db")
    try:
        import_bundle(target, bundle, replace=True)
        import_bundle(target, bundle, replace=True)  # second seed must not accumulate
        assert len(target.list_nodes()) == 2
        assert len(target.list_edges()) == 1
        assert len(target.list_arch_refs()) == 1
    finally:
        target.lock()


def test_import_requires_unlocked_store(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from src.infrastructure.assurance._portability import import_bundle
    from src.infrastructure.assurance._sqlcipher_store import SQLCipherAssuranceStore
    from src.infrastructure.assurance.lifecycle import init_store

    db_path = tmp_path / "locked.db"
    init_store(db_path)
    locked = SQLCipherAssuranceStore(db_path)  # not unlocked
    with pytest.raises(RuntimeError, match="unlocked"):
        import_bundle(locked, {"nodes": []})
