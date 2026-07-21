"""Configured SignalAttributeCapability: viewpoint attribute values from the
D9 metrics use case, snapshot-pinned per anchor.

Injected at composition time in assurance-enabled deployments (the null
capability serves the rest) — availability is evaluated per CALL, never at
wiring time, so lock-state changes at runtime behave correctly. Each batch
pins one snapshot token per anchor and revalidates every token after all
reads; any change makes the whole batch unavailable — values from different
snapshots are never mixed. An anchor with no active run contributes NO values
(absent ⇒ default styling), never a fabricated zero."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import asdict

from src.application.assurance_exposure import AssuranceExposurePolicy
from src.application.security_refresh.metrics import compute_security_metrics
from src.application.security_refresh.snapshot import (
    AvailabilityState,
    SignalSnapshotToken,
    snapshot_still_valid,
    take_snapshot,
)
from src.application.viewpoints.ports import (
    NullSignalAttributeCapability,
    SignalAttributeCapability,
    SignalBasisRun,
    SignalMetricsBatch,
)
from src.infrastructure.mcp.assurance_mcp.context import AssuranceContext, get_assurance_context


class AssuranceSignalAttributeCapability:
    def __init__(self, context_lookup: Callable[[], AssuranceContext] = get_assurance_context) -> None:
        self._context_lookup = context_lookup

    def fetch_metrics(
        self, entity_ids: Sequence[str], metric_names: Sequence[str],
    ) -> SignalMetricsBatch:
        ctx = self._context_lookup()
        policy = AssuranceExposurePolicy(ctx.max_classification, ctx.is_available())
        if policy.check_locked():
            return SignalMetricsBatch(available=False, note="assurance store locked")
        run_store = ctx.refresh_run_store
        vex_store = ctx.vex_store
        if run_store is None or vex_store is None:
            return SignalMetricsBatch(
                available=False,
                note="signal metrics require the SQLCipher store with co-located signals",
            )
        store = ctx.store
        if not isinstance(store, AvailabilityState):
            return SignalMetricsBatch(available=False, note="store exposes no availability state")

        tokens: dict[str, SignalSnapshotToken] = {}
        values: dict[tuple[str, str], object] = {}
        basis_runs: list[SignalBasisRun] = []
        classifications: list[str] = []
        for entity_id in entity_ids:
            token = take_snapshot(
                entity_id, availability=store, run_store=run_store,
                vex_store=vex_store, exposure_ceiling=ctx.max_classification,
            )
            tokens[entity_id] = token
            if token.active_run_id is None:
                continue  # no active run: absent values, never fabricated zeros
            metrics = compute_security_metrics(
                entity_id, run_store=run_store, vex_store=vex_store, policy=policy,
            )
            basis_runs.append(SignalBasisRun(
                anchor_entity_id=entity_id,
                run_id=token.active_run_id,
                activated_at=token.active_run_activated_at or "",
            ))
            if metrics.computed_classification:
                classifications.append(metrics.computed_classification)
            payload = asdict(metrics)
            for metric_name in metric_names:
                value = payload.get(metric_name)
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    values[(entity_id, metric_name)] = value
        for entity_id, token in tokens.items():
            if not snapshot_still_valid(
                token, availability=store, run_store=run_store,
                vex_store=vex_store, exposure_ceiling=ctx.max_classification,
            ):
                return SignalMetricsBatch(
                    available=False, note="signal snapshot changed mid-evaluation; retry",
                )
        order = ("TLP:WHITE", "TLP:GREEN", "TLP:AMBER", "TLP:RED")
        classification = max(
            (c for c in classifications if c in order), key=order.index, default=None,
        )
        return SignalMetricsBatch(
            available=True, values=values,
            classification=classification, basis_runs=tuple(basis_runs),
        )

def composed_signal_attribute_capability() -> "SignalAttributeCapability":
    """Composition-root selection: CONFIGURED capability when the assurance
    capability is present in this deployment, otherwise the null capability.
    The decision is configuration-shaped (store file + key reachable), never
    the current lock state — availability is evaluated per call instead."""
    from src.infrastructure.assurance.capability import make_capability  # noqa: PLC0415
    from src.infrastructure.mcp.assurance_mcp.context import default_db_path  # noqa: PLC0415

    if make_capability(default_db_path()).enabled:
        return AssuranceSignalAttributeCapability()
    return NullSignalAttributeCapability()
