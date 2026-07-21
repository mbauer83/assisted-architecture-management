# Final Go/No-Go Review — Navigation and Tier Transparency

## Decision: GO

The planning package is ready for implementation. The three remaining contracts from the
previous pass are now specified consistently in PLAN, TASKS, and PROMPT, are assigned to
concrete work units, and have objective tests that exercise the actual failure paths.
No acceptance goal is left without delivery work, and no remaining ambiguity requires an
implementer to redesign a load-bearing abstraction.

## Final-condition verification

### 1. Workflow authorization granularity — satisfied

The application policy now owns distinct `enterprise_save`, `enterprise_submit`, and
`enterprise_discard` identities, with local versus pending-remote discard represented in
the target shape (`PLAN-navigation-and-tier-transparency.md:217-227`;
`TASKS-navigation-and-tier-transparency.md:74-99`). The closed health-reason type is owned
inward by the application policy and only serialized by infrastructure.

The normative matrix now allows local Save and local discard during enterprise
fetch/upstream/divergence faults while denying promotion, Submit, and remote-touching
Discard (`PLAN-navigation-and-tier-transparency.md:128-135,370-387`). The previously
missed reachable combination—`accumulating + dirty + persisted fetch fault`—must prove
both UI availability and backend acceptance. This closes the recovery deadlock without
weakening engagement autonomy or read-only enforcement.

### 2. Authority freshness — satisfied

Authority is explicitly excluded from the status cache. Cached data is limited to
expensive git/lifecycle measurements; every response overlays a fresh projection from the
same snapshot provider used by mutation enforcement
(`PLAN-navigation-and-tier-transparency.md:122-128,278-287`;
`TASKS-navigation-and-tier-transparency.md:199-209`).

The acceptance test runs through the real `WorkspaceMutationGate.blocking_writes()` path
and observes status before, during, and after the block without waiting for cache expiry
(`PLAN-navigation-and-tier-transparency.md:390-400`). This covers the direct production
transitions in both sync implementations and removes the former compatibility-shim blind
spot.

### 3. Pending Discard convergence — satisfied

Pending Discard is now an idempotent desired-state transition:

1. remote ref absent;
2. checkout on `main`;
3. local branch absent;
4. aggregate cleared.

Already-satisfied postconditions count as success, and aggregate state remains pending
until the full transition completes
(`PLAN-navigation-and-tier-transparency.md:451-466`;
`TASKS-navigation-and-tier-transparency.md:209-219`). Fault injection after every step,
including state persistence, must demonstrate that a retry converges while unrelated
files remain untouched. This adequately handles the non-atomic boundary across remote
git, local git, and runtime-state persistence.

## Overall adequacy

The package now pins the important invariants:

- GAR records are absent from GUI, REST-backed, MCP, and CLI search while remaining
  available to raw promotion/reference internals.
- Entity type/domain filters and visibility apply identically across FTS, fallback, and
  semantic search, including refill behavior.
- Every architecture-repository mutation enters one structurally registered,
  intent-authorized, serialized, gated pipeline; Save is verified before commit.
- Standard writes target only the configured active engagement; promotion/finalization
  remain available outside admin mode; direct enterprise authoring remains admin-only;
  read-only blocks all architecture-repository writes.
- Lifecycle health, authority, and UI action state remain consistent across polls,
  reconnects, failures, and partial recovery.
- Tier facets, URL state, list summaries, redirects, badges, navigation placement, and
  Enterprise terminology have regional and global parity tests.
- The source-length ratchet, strict typing, prepared SQL, `uv` tooling, owner restart
  protocol, and no-provenance conventions are explicit and objectively gated.

The General Coding Guidelines, Hexagonal Architecture ADR, Unified Backend ADR, and
Two-Tier Repository ADR were re-queried for this pass. The final design respects their
dependency direction, expressive closed types, one verified write pipeline, and autonomous
engagement-repository principles.

## Non-blocking clarification

The health matrix is exhaustive for workflow actions but does not state explicitly whether
enterprise sync-health faults deny direct `enterprise_admin_authoring`. The safest default
is to deny it—maintenance is the explicit recovery intent—and add that row to the policy
matrix. This is a small policy clarification, not a blocker to beginning S1.

Implementation may proceed from S1 under the ledger's ordering and quality gates.

