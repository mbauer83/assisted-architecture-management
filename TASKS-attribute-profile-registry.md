# TASKS — Named Attribute Profiles: Registry, Lifecycle, and Failure Semantics

Execution ledger for `PLAN-attribute-profile-registry.md`. The plan is
normative; this file tracks execution and records what was verified.

## Resume protocol

1. Read `PLAN-attribute-profile-registry.md` §3 (locked decisions) and §4
   (failure semantics) first — they are not re-litigated.
2. Find the first unticked WU whose dependencies are ticked.
3. Gates before every commit: `uv run python -m pytest -q -n auto` (one at a
   time, never concurrent), `uv run ruff check src/ tests/`, `uv run zuban
   check`; frontend from `tools/gui/`: `npm run lint && npm run typecheck &&
   npx vitest run` (full `npm run lint`, never `lint:fast`).
4. Backend changes are inert until the owner restarts `arch-backend`; MCP
   surface changes also need a Claude session restart. Queue live verification.

## Questions

- **Q1 — Relationship profiles in scope?** ArchiMate applies profiles to
  relationships too, and `connection-metadata.*` schemata already exist. This
  plan covers entities only. Extend now or defer? OPEN.

## Stream P — Registry and resolution

### WU-P1 — Registry format and loader
- [ ] Declaration format with `profile_schema: <int>` (format version) and per
      profile `version: <int>` (content version) — PLAN §3 P4.
- [ ] An unrecognised `profile_schema` is a typed error, never a best-effort
      parse (follow the `QUERY_SCHEMA_VERSION` precedent).
- [ ] Shipped registry in the ontology module; optional repo-level registry.
- [ ] Tests: valid load; unknown format version rejected; absent registry is a
      valid "no named profiles" state (regression guard for existing repos).

### WU-P2 — Binding declaration (needs P1)
- [ ] A specialization may bind named profiles by name, in declaration order.
- [ ] A binding to an undefined profile is Class A (structural) — see WU-Q1.
- [ ] Tests: single binding; multiple bindings; binding the same profile to
      several (type, specialization) pairs contributes to all of them.

### WU-P3 — Resolution order (needs P2)
- [ ] Extend `compute_effective_attribute_schema` to append bound-profile
      fragments between the base schema and the specialization's own profile
      (PLAN §3 P2). The merge itself is already N-ary — do not modify it.
- [ ] Tests: order holds (specialization overrides shared profile overrides
      base); parent-attribute inheritance still works (regression — this
      already works today via fragment 1 and must not break).

### WU-P4 — Conflict classification (needs P3)
- [ ] Classify each conflict as Class A (structural) or Class B (scoped) per
      PLAN §4.
- [ ] Identical redefinition composes silently; only incompatible `type`
      redefinition conflicts (PLAN §3 P3 — today's semantic, keep it).
- [ ] Tests: identical redefinition across two profiles is NOT a conflict;
      differing types IS; each class is assigned correctly.

## Stream Q — Failure semantics

### WU-Q1 — Class A startup validation (needs P4)
- [ ] Validate attached repos at startup, before the index build, under the
      privileged write gate — mirroring `_group_registry_startup.py`.
- [ ] Engagement (writable) repo: hard fail with the file, the reason, and the
      fix. Enterprise (attached, read-only): log and continue.
- [ ] **Only attached repos** (PLAN §3 P6) — never a filesystem scan.
- [ ] Tests: malformed registry in the engagement repo aborts startup; the same
      defect in the enterprise repo does not; an unattached repo with a broken
      registry is never read.

### WU-Q2 — Class B quarantine set (needs P4)
- [ ] Compute the quarantined (entity-type, specialization) pairs at load.
- [ ] The effective schema for a quarantined pair resolves to the unambiguous
      fragment set, flagged `quarantined` with reasons.
- [ ] Tests: quarantine is confined to the affected pair; sibling
      specializations of the same base type are unaffected; reads of existing
      entities in a quarantined pair still work.

### WU-Q3 — Write-boundary gate (needs Q2) — LOAD-BEARING
- [ ] Reject creates/edits for a quarantined pair with a typed error naming the
      colliding profiles, the field, and the conflicting types.
- [ ] **Close the verified gap**: the write path uses `load_attribute_schema`
      (base only) and never sees specialization profiles
      (`artifact_write_formatting.py:336`). The gate must sit where every
      transport passes through it.
- [ ] Tests: the write is rejected through REST, MCP, **and** CLI (PLAN §8
      acceptance 5 — per-transport, since a gate that only covers one is not a
      gate); a non-quarantined pair writes normally.

### WU-Q4 — Stream Q boundary
- [ ] Full backend gates green. No entity can be written against an ambiguous
      schema through any transport.

## Stream R — Reconciliation

### WU-R1 — Conflict and drift reporting (needs Q2)
- [ ] Upgrade step reporting each conflict (profiles, field, types, resulting
      quarantined pairs) and content-version drift (shipped profile advanced
      past a customisation — the capability P4's content version exists for).
- [ ] Non-destructive: never overwrite operator content
      (`DefaultSchemataEnsureStep`'s contract).
- [ ] Tests: conflicts reported; drift reported with the intervening changes;
      operator customisations preserved.

### WU-R2 — Proposed resolutions (needs R1)
- [ ] Propose rename / align-type / unbind as manual instructions.
- [ ] Auto-migrate only where unambiguous (operator file byte-identical to an
      older shipped version).
- [ ] Tests: ambiguous cases are never auto-migrated.

## Stream S — Surfaces

### WU-S1 — Quarantine on the schema endpoint (needs Q2)
- [ ] Extend the existing conflicts channel (`entities.py:221` already returns
      `conflicts`) with quarantine state — do not add a parallel channel.
- [ ] REST + MCP parity, parity-tested.

### WU-S2 — GUI surfacing (needs S1)
- [ ] Banner on affected entity types; submit disabled with the reconciliation
      message.
- [ ] Progressive enhancement only — correctness is already guaranteed by WU-Q3
      (PLAN §3 P8). Verify by testing that a GUI unaware of quarantine still
      cannot write ambiguous data.
- [ ] Vitest coverage, separate file per component.

## Stream T — Docs and self-model

### WU-T1 — Reference documentation
- [ ] Profile authoring, binding, versioning, resolution order, and the failure
      semantics — the quarantine behaviour especially, since an operator who
      meets one must be able to act on it.

### WU-T2 — Self-model sync
- [ ] Model the profile-registry capability in ENG-ARCH-REPO: guidance-first,
      descriptions over new entities.

## Stream U — AIBOM handoff

### WU-U1 — Unblock the AIBOM plan
- [ ] Confirm `PLAN-aibom-model-derived.md` D3 can be executed on named
      profiles: one shared `ai-provenance` profile bound to the AI
      specializations, plus small per-specialization profiles for what genuinely
      differs.
- [ ] Verify the AIBOM schemata no longer redeclare attributes inherited from
      their base types (inheritance already works — PLAN §2).

## Restart-gated live verification queue

- [ ] Startup Class A behaviour on the restarted backend (engagement hard fail,
      enterprise warn) — verify with a deliberately broken registry in a
      scratch repo, never the live one.
- [ ] Quarantine write rejection through MCP after a session restart.
