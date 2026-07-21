"""Security refresh-run lifecycle: state machine, idempotent-replay decisions,
and the canonical bundle digest.

A refresh run is the atomic unit of security-signal ingestion: one anchor, one
staged population of components/aliases/vulnerabilities/findings, one atomic
activation. Metrics only ever read the single active run per anchor.

Lifecycle: ``staging → complete → active → superseded`` plus the terminal
``staging → failed``. Status never doubles as a timestamp — activation and
supersession carry their own fields. ``failed`` is TERMINAL: replaying the same
request returns the stored failure and instructs the caller to use a new
``request_id``; it never resumes.

Idempotency: ``(anchor_entity_id, request_id)`` is the replay key (one bundle
has exactly one anchor); ``request_payload_digest`` is the SHA-256 of the
canonical accepted bundle — every semantic field after normalization,
deliberately NOT the BOM digest (the BOM is not the whole command).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Literal, Mapping, Sequence

RunStatus = Literal["staging", "complete", "active", "superseded", "failed"]

_ALLOWED_TRANSITIONS: frozenset[tuple[str, str]] = frozenset({
    ("staging", "complete"),
    ("staging", "failed"),
    ("complete", "active"),
    ("active", "superseded"),
})

TERMINAL_STATUSES: frozenset[str] = frozenset({"failed", "superseded"})


def is_allowed_transition(current: str, target: str) -> bool:
    return (current, target) in _ALLOWED_TRANSITIONS


def transition_error(current: str, target: str) -> str:
    return (
        f"Illegal refresh-run transition {current!r} → {target!r}; allowed: "
        + ", ".join(sorted(f"{a}→{b}" for a, b in _ALLOWED_TRANSITIONS))
    )


# ── Idempotent replay ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class StoredRunKey:
    """What the store knows about an existing run under the replay key."""

    run_id: str
    status: str
    request_payload_digest: str


@dataclass(frozen=True)
class CreateNewRun:
    """No run exists under the key — begin a new staging run."""


@dataclass(frozen=True)
class ReplayInProgress:
    """Same key + digest, run not yet terminal/active: retry later; no mutation."""

    run_id: str


@dataclass(frozen=True)
class ReplayStoredSuccess:
    """Same key + digest, run reached active (or was later superseded):
    return the original success; no mutation, no new audit."""

    run_id: str


@dataclass(frozen=True)
class ReplayStoredFailure:
    """Same key + digest, run failed (terminal): return the stored failure and
    instruct the caller to use a new request_id; no mutation, no new audit."""

    run_id: str


@dataclass(frozen=True)
class IdempotencyConflict:
    """Same key, DIFFERENT digest: typed conflict; no signal or audit write."""

    run_id: str
    stored_digest: str
    submitted_digest: str


ReplayDecision = (
    CreateNewRun | ReplayInProgress | ReplayStoredSuccess | ReplayStoredFailure | IdempotencyConflict
)


def replay_decision(existing: StoredRunKey | None, submitted_digest: str) -> ReplayDecision:
    """The normative replay table for one (anchor, request_id) key."""
    if existing is None:
        return CreateNewRun()
    if existing.request_payload_digest != submitted_digest:
        return IdempotencyConflict(
            run_id=existing.run_id,
            stored_digest=existing.request_payload_digest,
            submitted_digest=submitted_digest,
        )
    if existing.status in ("staging", "complete"):
        return ReplayInProgress(run_id=existing.run_id)
    if existing.status in ("active", "superseded"):
        return ReplayStoredSuccess(run_id=existing.run_id)
    return ReplayStoredFailure(run_id=existing.run_id)


# ── Canonical bundle digest ────────────────────────────────────────────────────


def _canonical(value: object) -> object:
    """Normalization for digesting: mappings key-sorted recursively; sequences
    of mappings sorted by their canonical JSON so input ordering never changes
    the digest; scalars unchanged."""
    if isinstance(value, Mapping):
        return {str(k): _canonical(value[k]) for k in sorted(value, key=str)}
    if isinstance(value, (list, tuple)):
        canon = [_canonical(item) for item in value]
        return sorted(canon, key=lambda item: json.dumps(item, sort_keys=True, ensure_ascii=True))
    return value


def canonical_bundle_digest(semantic_fields: Mapping[str, object]) -> str:
    """SHA-256 over the canonical form of every semantic bundle field
    (components, findings, aliases, applicability evaluations, diagnostics,
    generator/source metadata, anchor) — generated fields (run id, timestamps)
    must not be passed in."""
    canonical = _canonical(semantic_fields)
    encoded = json.dumps(canonical, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


# ── Directness classification (I-C9) ──────────────────────────────────────────


def classify_directness(
    root_ref: str,
    component_ref: str,
    dependency_edges: Sequence[tuple[str, str]],
) -> Literal["direct", "transitive", "unknown"]:
    """BFS depth from the BOM root over the dependency graph: the root itself is
    not a dependency; depth 1 = direct; reachable depth ≥ 2 = transitive;
    unreachable (or cycle-locked away from the root) = unknown. Cycles terminate
    via the visited set."""
    if component_ref == root_ref:
        return "unknown"
    children: dict[str, list[str]] = {}
    for parent, child in dependency_edges:
        children.setdefault(parent, []).append(child)
    visited: set[str] = {root_ref}
    frontier = [root_ref]
    depth = 0
    while frontier:
        depth += 1
        next_frontier: list[str] = []
        for node in frontier:
            for child in children.get(node, []):
                if child == component_ref:
                    return "direct" if depth == 1 else "transitive"
                if child not in visited:
                    visited.add(child)
                    next_frontier.append(child)
        frontier = next_frontier
    return "unknown"
