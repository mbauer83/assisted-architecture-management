"""RefreshSecuritySignals — the ONE application command owning the security
refresh lifecycle: typed bundle validation, idempotent-replay decision, staging
run creation, population, completion, atomic activation, and failure recording
with safe diagnostics. Adapters (v1: the CLI/script surface only) submit a
bundle; nothing else may drive the low-level transitions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Mapping

from src.application.security_refresh.ports import RefreshRunStore
from src.domain.security_refresh_run import (
    CreateNewRun,
    IdempotencyConflict,
    ReplayInProgress,
    ReplayStoredFailure,
    ReplayStoredSuccess,
    StoredRunKey,
    canonical_bundle_digest,
    replay_decision,
)


@dataclass(frozen=True)
class RefreshBundle:
    """The complete, normalized input of one refresh execution. Semantic fields
    only — run ids and timestamps are generated downstream and excluded from
    the idempotency digest by construction."""

    anchor_entity_id: str
    request_id: str
    components: tuple[Mapping[str, object], ...]
    findings: tuple[Mapping[str, object], ...]
    diagnostics: Mapping[str, object] = field(default_factory=dict)
    generator_metadata: Mapping[str, object] = field(default_factory=dict)
    source_metadata: Mapping[str, object] = field(default_factory=dict)
    bom_digest: str = ""
    bom_serial: str = ""
    bom_version: str = ""

    def payload_digest(self) -> str:
        return canonical_bundle_digest({
            "anchor_entity_id": self.anchor_entity_id,
            "components": [dict(c) for c in self.components],
            "findings": [dict(f) for f in self.findings],
            "diagnostics": dict(self.diagnostics),
            "generator_metadata": dict(self.generator_metadata),
            "source_metadata": dict(self.source_metadata),
            "bom_digest": self.bom_digest,
            "bom_serial": self.bom_serial,
            "bom_version": self.bom_version,
        })


@dataclass(frozen=True)
class RefreshValidationError:
    field: str
    message: str


def validate_bundle(bundle: RefreshBundle) -> list[RefreshValidationError]:
    errors: list[RefreshValidationError] = []
    if not bundle.anchor_entity_id.strip():
        errors.append(RefreshValidationError("anchor_entity_id", "anchor is required"))
    if not bundle.request_id.strip():
        errors.append(RefreshValidationError("request_id", "request_id is required"))
    for index, component in enumerate(bundle.components):
        if not str(component.get("component_id") or ""):
            errors.append(RefreshValidationError(
                "components", f"component[{index}] missing component_id"))
        if not str(component.get("name") or ""):
            errors.append(RefreshValidationError(
                "components", f"component[{index}] missing name"))
    known = {str(c.get("component_id")) for c in bundle.components}
    for index, finding in enumerate(bundle.findings):
        if str(finding.get("component_id") or "") not in known:
            errors.append(RefreshValidationError(
                "findings", f"finding[{index}] references unknown component_id"))
        raw_ids = finding.get("external_ids")
        if not (isinstance(raw_ids, (list, tuple)) and raw_ids):
            errors.append(RefreshValidationError(
                "findings", f"finding[{index}] needs at least one external id"))
    return errors


# ── Typed outcomes ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class RefreshActivated:
    run_id: str
    superseded_run_id: str | None
    component_count: int
    finding_count: int


@dataclass(frozen=True)
class RefreshInvalid:
    errors: tuple[RefreshValidationError, ...]


@dataclass(frozen=True)
class RefreshReplayed:
    """Same key + digest replay: the stored outcome, verbatim; nothing mutated."""

    run_id: str
    stored_outcome: str  # "in_progress" | "success" | "failed"
    message: str


@dataclass(frozen=True)
class RefreshConflict:
    """Same key, different payload digest — typed idempotency conflict."""

    run_id: str
    message: str


@dataclass(frozen=True)
class RefreshFailed:
    """The execution failed mid-flight; the run is recorded as failed."""

    run_id: str
    reason: str


RefreshResult = RefreshActivated | RefreshInvalid | RefreshReplayed | RefreshConflict | RefreshFailed


def refresh_security_signals(
    bundle: RefreshBundle,
    *,
    store: RefreshRunStore,
    new_run_id: Callable[[], str],
) -> RefreshResult:
    """Execute one refresh: validate → replay decision → staging → populate →
    complete → activate. Any populate/complete/activate error records the run
    as failed with a safe reason (failed is terminal — a retry needs a new
    request_id)."""
    errors = validate_bundle(bundle)
    if errors:
        return RefreshInvalid(errors=tuple(errors))

    digest = bundle.payload_digest()
    existing = store.find_run_by_request(bundle.anchor_entity_id, bundle.request_id)
    stored = None if existing is None else StoredRunKey(
        run_id=str(existing["run_id"]),
        status=str(existing["status"]),
        request_payload_digest=str(existing["request_payload_digest"]),
    )
    decision = replay_decision(stored, digest)
    if isinstance(decision, ReplayInProgress):
        return RefreshReplayed(run_id=decision.run_id, stored_outcome="in_progress",
                               message="A run for this request is in progress; retry later.")
    if isinstance(decision, ReplayStoredSuccess):
        return RefreshReplayed(run_id=decision.run_id, stored_outcome="success",
                               message="This request already succeeded; returning the original run.")
    if isinstance(decision, ReplayStoredFailure):
        return RefreshReplayed(run_id=decision.run_id, stored_outcome="failed",
                               message="This request previously failed; submit with a new request_id.")
    if isinstance(decision, IdempotencyConflict):
        return RefreshConflict(
            run_id=decision.run_id,
            message="request_id was already used with a different payload; nothing was written.",
        )
    assert isinstance(decision, CreateNewRun)

    run_id = new_run_id()
    store.create_staging_run(
        run_id=run_id,
        anchor_entity_id=bundle.anchor_entity_id,
        request_id=bundle.request_id,
        request_payload_digest=digest,
        bom_digest=bundle.bom_digest,
        bom_serial=bundle.bom_serial,
        bom_version=bundle.bom_version,
        generator_metadata=bundle.generator_metadata,
        source_metadata=bundle.source_metadata,
        diagnostics=bundle.diagnostics,
    )
    try:
        store.populate_run(run_id, components=bundle.components, findings=bundle.findings)
        store.complete_run(run_id)
        activation = store.activate_run(run_id)
    except Exception as exc:  # noqa: BLE001 — recorded as a failed run, safe reason only
        reason = f"{type(exc).__name__} during refresh execution"
        store.fail_run(run_id, reason=reason)
        return RefreshFailed(run_id=run_id, reason=reason)
    superseded = activation.get("superseded_run_id")
    return RefreshActivated(
        run_id=run_id,
        superseded_run_id=str(superseded) if superseded else None,
        component_count=len(bundle.components),
        finding_count=len(bundle.findings),
    )
