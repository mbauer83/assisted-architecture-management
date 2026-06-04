"""Unit tests for the §17(B) stpa-basic-complete coverage checker (Phase 2)."""

from __future__ import annotations

import pytest

pytest.importorskip("sqlcipher3", reason="sqlcipher3 not installed")


@pytest.fixture()
def store(tmp_path):  # type: ignore[no-untyped-def]
    from src.infrastructure.assurance._sqlcipher_store import SQLCipherAssuranceStore
    from src.infrastructure.assurance.lifecycle import init_store

    db_path = tmp_path / "store.db"
    init_store(db_path)
    s = SQLCipherAssuranceStore(db_path)
    s.unlock()
    yield s
    s.lock()


def test_empty_store_passes_all_checks(store) -> None:  # type: ignore[no-untyped-def]
    from src.application.verification.stpa_complete import run_stpa_complete

    result = run_stpa_complete(store)
    assert result["passed"] is True
    assert "All STPA coverage checks passed" in str(result["summary"])


def test_result_structure_shape(store) -> None:  # type: ignore[no-untyped-def]
    from src.application.verification.stpa_complete import run_stpa_complete

    result = run_stpa_complete(store)
    assert "passed" in result
    assert "checks" in result
    assert "summary" in result
    expected_keys = {
        "hazard_leads_to_loss",
        "uca_concerns_control_action",
        "uca_violates_hazard",
        "loss_scenario_explains_uca",
        "uca_derives_constraint",
        "loss_scenario_derives_constraint",
    }
    assert set(result["checks"].keys()) == expected_keys
    for _key, check in result["checks"].items():
        assert "passed" in check
        assert "gap_count" in check
        assert "gaps" in check


def test_hazard_without_loss_fails(store) -> None:  # type: ignore[no-untyped-def]
    from src.application.verification.stpa_complete import run_stpa_complete

    store.create_node("hazard", "HAZ-1", concern_class="safety")
    result = run_stpa_complete(store)
    assert result["passed"] is False
    check = result["checks"]["hazard_leads_to_loss"]
    assert check["passed"] is False
    assert check["gap_count"] == 1
    assert any(g["name"] == "HAZ-1" for g in check["gaps"])


def test_hazard_with_loss_passes(store) -> None:  # type: ignore[no-untyped-def]
    from src.application.verification.stpa_complete import run_stpa_complete

    loss_id = store.create_node("loss", "Loss-1", concern_class="safety")
    haz_id = store.create_node("hazard", "HAZ-1", concern_class="safety")
    store.add_edge(haz_id, loss_id, "leads-to")
    result = run_stpa_complete(store)
    assert result["checks"]["hazard_leads_to_loss"]["passed"] is True


def test_uca_without_control_action_fails(store) -> None:  # type: ignore[no-untyped-def]
    from src.application.verification.stpa_complete import run_stpa_complete

    store.create_node("unsafe-control-action", "UCA-1", uca_type="not-provided", concern_class="safety")
    result = run_stpa_complete(store)
    assert result["checks"]["uca_concerns_control_action"]["passed"] is False


def test_uca_without_violates_hazard_fails(store) -> None:  # type: ignore[no-untyped-def]
    from src.application.verification.stpa_complete import run_stpa_complete

    ca_id = store.create_node("control-action", "CA-1")
    uca_id = store.create_node("unsafe-control-action", "UCA-1", uca_type="not-provided", concern_class="safety")
    store.add_edge(uca_id, ca_id, "concerns")
    result = run_stpa_complete(store)
    assert result["checks"]["uca_violates_hazard"]["passed"] is False


def test_loss_scenario_without_uca_fails(store) -> None:  # type: ignore[no-untyped-def]
    from src.application.verification.stpa_complete import run_stpa_complete

    store.create_node("loss-scenario", "LS-orphan", concern_class="safety")
    result = run_stpa_complete(store)
    assert result["checks"]["loss_scenario_explains_uca"]["passed"] is False


def test_complete_stpa_chain_passes(store) -> None:  # type: ignore[no-untyped-def]
    from src.application.verification.stpa_complete import run_stpa_complete

    loss_id = store.create_node("loss", "L-1", concern_class="safety")
    haz_id = store.create_node("hazard", "H-1", concern_class="safety")
    store.add_edge(haz_id, loss_id, "leads-to")
    ca_id = store.create_node("control-action", "CA-1")
    uca_id = store.create_node("unsafe-control-action", "UCA-1", uca_type="not-provided", concern_class="safety")
    store.add_edge(uca_id, ca_id, "concerns")
    store.add_edge(uca_id, haz_id, "violates")
    ls_id = store.create_node("loss-scenario", "LS-1", concern_class="safety")
    store.add_edge(ls_id, uca_id, "explains")
    acn_id = store.create_node("assurance-constraint", "ACN-1", concern_class="safety")
    store.add_edge(uca_id, acn_id, "derives")
    store.add_edge(ls_id, acn_id, "derives")
    result = run_stpa_complete(store)
    assert result["passed"] is True
    assert "All STPA coverage checks passed" in str(result["summary"])


def test_summary_reports_gap_counts(store) -> None:  # type: ignore[no-untyped-def]
    from src.application.verification.stpa_complete import run_stpa_complete

    store.create_node("hazard", "H-1", concern_class="safety")
    store.create_node("hazard", "H-2", concern_class="safety")
    result = run_stpa_complete(store)
    assert "2" in str(result["summary"])
    assert result["passed"] is False
