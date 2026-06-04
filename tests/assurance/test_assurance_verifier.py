"""Tests for the §17(A) assurance verifier rules."""

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


def test_empty_store_is_valid(store) -> None:  # type: ignore[no-untyped-def]
    from src.application.verification.assurance_verifier import verify_store

    result = verify_store(store)
    assert result.valid
    assert not result.errors


def test_e501_uca_without_control_action(store) -> None:  # type: ignore[no-untyped-def]
    """E501: UCA must reference exactly one control-action via 'concerns'."""
    from src.application.verification.assurance_verifier import verify_store

    store.create_node("unsafe-control-action", "UCA-1", uca_type="not-provided", concern_class="safety")
    result = verify_store(store)
    codes = [i.code for i in result.errors]
    assert "E501" in codes


def test_e501_uca_with_control_action_passes(store) -> None:  # type: ignore[no-untyped-def]
    """E501: satisfied when UCA has exactly one 'concerns' edge."""
    from src.application.verification.assurance_verifier import verify_store

    ca_id = store.create_node("control-action", "Throttle Command")
    uca_id = store.create_node("unsafe-control-action", "UCA-1", uca_type="not-provided", concern_class="safety")
    store.add_edge(uca_id, ca_id, "concerns")
    result = verify_store(store)
    codes = [i.code for i in result.errors]
    assert "E501" not in codes


def test_e502_constraint_without_owner(store) -> None:  # type: ignore[no-untyped-def]
    """E502: safety/security constraint must have accountable-to owner."""
    from src.application.verification.assurance_verifier import verify_store

    store.create_node("assurance-constraint", "ACN-1", concern_class="safety")
    result = verify_store(store)
    codes = [i.code for i in result.errors]
    assert "E502" in codes


def test_e502_non_safety_constraint_no_owner_passes(store) -> None:  # type: ignore[no-untyped-def]
    """E502: operational constraints do not require an owner."""
    from src.application.verification.assurance_verifier import verify_store

    store.create_node("assurance-constraint", "ACN-op", concern_class="operational")
    result = verify_store(store)
    codes = [i.code for i in result.errors]
    assert "E502" not in codes


def test_e503_accepted_safety_constraint(store) -> None:  # type: ignore[no-untyped-def]
    """E503: disposition='accepted' is rejected for safety constraints (safeguard §2.1)."""
    from src.application.verification.assurance_verifier import verify_store

    store.create_node("assurance-constraint", "ACN-bad", concern_class="safety", disposition="accepted")
    result = verify_store(store)
    codes = [i.code for i in result.errors]
    assert "E503" in codes


def test_e503_eliminated_safety_constraint_passes(store) -> None:  # type: ignore[no-untyped-def]
    """E503: other dispositions are allowed for safety constraints."""
    from src.application.verification.assurance_verifier import verify_store

    store.create_node("assurance-constraint", "ACN-ok", concern_class="safety", disposition="eliminated")
    result = verify_store(store)
    codes = [i.code for i in result.errors]
    assert "E503" not in codes


def test_w501_unbound_pending_csn(store) -> None:  # type: ignore[no-untyped-def]
    """W501: modeling-gap finding for unbound-pending control-structure-nodes."""
    from src.application.verification.assurance_verifier import verify_store

    store.create_node("control-structure-node", "CSN-Unbound", binding_status="unbound-pending")
    result = verify_store(store)
    w_codes = [i.code for i in result.warnings]
    assert "W501" in w_codes
    assert result.valid  # warnings don't block


def test_w503_hazard_without_loss(store) -> None:  # type: ignore[no-untyped-def]
    """W503: hazard with no leads-to connection should warn."""
    from src.application.verification.assurance_verifier import verify_store

    store.create_node("hazard", "HAZ-1", concern_class="safety")
    result = verify_store(store)
    w_codes = [i.code for i in result.warnings]
    assert "W503" in w_codes


def test_e504_risk_accept_sole_disposition_safety_hazard(store) -> None:  # type: ignore[no-untyped-def]
    """E504: risk.treatment=accept cannot be sole disposition of a safety hazard."""
    from src.application.verification.assurance_verifier import verify_store

    haz_id = store.create_node("hazard", "HAZ-safety", concern_class="safety")
    risk_id = store.create_node("risk", "RSK-1", attributes={"treatment": "accept"})
    store.update_node(risk_id, attributes={"treatment": "accept"})
    store.add_edge(risk_id, haz_id, "assesses")
    # No treated-by constraint — should trigger E504
    result = verify_store(store)
    codes = [i.code for i in result.errors]
    assert "E504" in codes


def test_w502_constraint_without_evidence(store) -> None:  # type: ignore[no-untyped-def]
    """W502: assurance-constraint with no evidenced-by connection."""
    from src.application.verification.assurance_verifier import verify_store

    store.create_node("assurance-constraint", "ACN-no-evidence", concern_class="safety")
    result = verify_store(store)
    w_codes = [i.code for i in result.warnings]
    assert "W502" in w_codes


def test_locked_store_returns_e500(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Locked store returns E500 error."""
    from src.infrastructure.assurance._sqlcipher_store import SQLCipherAssuranceStore  # noqa: PLC0415
    from src.application.verification.assurance_verifier import verify_store  # noqa: PLC0415

    s = SQLCipherAssuranceStore(tmp_path / "store.db")
    result = verify_store(s)
    codes = [i.code for i in result.issues]
    assert "E500" in codes


def test_format_result(store) -> None:  # type: ignore[no-untyped-def]
    from src.application.verification.assurance_verifier import format_result, verify_store

    result = verify_store(store)
    fmt = format_result(result)
    assert "valid" in fmt
    assert "error_count" in fmt
    assert "warning_count" in fmt
    assert "issues" in fmt
