# Phase 1 — Assurance Capability: Core Infrastructure (1a–1d)

> Implementation of PLAN-assurance-stpa-grc.md §24 Phase 1a/1b/1c/1d.
> Canonical progress tracker: this file + the §24 checklist in the plan.

## Status legend: ☐ pending · ◐ in progress · ☑ done

## Phase 1a — Confidential Store + Analysis-Collection Substrate

| # | Task | Status |
|---|---|---|
| 1a-1 | Explore existing codebase patterns (explorer agent) | ☑ done |
| 1a-2 | Design Phase 1 implementation blueprint (architect agent) | ☑ done |
| 1a-3 | `ConfidentialAssuranceStore` port (Protocol) in `src/application/assurance_ports.py` | ☑ done |
| 1a-4 | SQLCipher adapter (`src/infrastructure/assurance/_sqlcipher_store.py`) + OS keychain key management | ☑ done |
| 1a-5 | `analysis-collection` grouping axis (4th axis) in `src/domain/groups.py` + `GroupRegistry` | ☑ done |
| 1a-6 | `arch-assurance` CLI lifecycle commands (init/unlock/backup/export/rotate-key) | ☑ done |
| 1a-7 | Fail-closed gating: assurance tools absent unless store configured+unlocked | ☑ done |
| 1a-8 | One-way `assurance→architecture` ref resolver (tolerant of dangling refs) | ☑ done |
| 1a-9 | Tests for Phase 1a | ☑ done |

## Phase 1b — Assurance Graph MVP

| # | Task | Status |
|---|---|---|
| 1b-1 | `src/ontologies/assurance/entities.yaml` — core entity types (loss, hazard, csn, cta, uca, acn) | ☑ done |
| 1b-2 | `src/ontologies/assurance/connections.yaml` — typed connection definitions | ☑ done |
| 1b-3 | `src/ontologies/assurance/_loader.py` — module loader with attribute_profiles | ☑ done |
| 1b-4 | Register assurance module in `_ALL_ONTOLOGY_MODULES` in `app_bootstrap.py` | ☑ done |
| 1b-5 | `attribute_profiles`: `concern_class`, `disposition`, `uca_type`, TLP, `binding_status` | ☑ done |
| 1b-6 | Always-on layers: TLP classification, no-secrets constraint, promotion gate stubs | ☑ done |
| 1b-7 | `src/infrastructure/mcp/assurance_mcp/read_tools.py` — `arch-assurance-read` MCP server tools | ☑ done |
| 1b-8 | `src/infrastructure/mcp/assurance_mcp/write_tools.py` — `arch-assurance-write` MCP server tools | ☑ done |
| 1b-9 | Regenerate `types.generated.ts` | ☑ done |
| 1b-10 | Tests for Phase 1b (ontology types, MCP gating) | ☑ done |

## Phase 1c — Immutable Records + Verifier

| # | Task | Status |
|---|---|---|
| 1c-1 | `AssuranceArchive` port (Protocol) | ☑ done |
| 1c-2 | Append-only hash-chained audit log adapter (`src/infrastructure/assurance/_archive.py`) | ☑ done |
| 1c-3 | Retention config (≥6-mo default, 10-yr option; Art. 12/18/19/26 EU AI Act) | ☑ done |
| 1c-4 | Sealable signed baselines (analysis sign-off snapshots) | ☑ done |
| 1c-5 | Verifier §17(A): hard structural validity rules | ☑ done |
| 1c-6 | Verifier §17(A): safety-disposition guard (US3) — `accepted` blocked w/o justification+sign-off | ☑ done |
| 1c-7 | Modeling-gap findings (§7.1, US6) — `unbound-pending` → informational | ☑ done |
| 1c-8 | Reference-vocabulary loader (STRIDE/CWE/ATT&CK seeds) + ISO 26262/21434 profiles | ☑ done |
| 1c-9 | Tests for Phase 1c (verifier rules, archive integrity, ref vocab) | ☑ done |

## Phase 1d — Minimal UI Surfacing

| # | Task | Status |
|---|---|---|
| 1d-1 | Frontend: `module_class` plumbing — filter assurance types from model catalog/pickers | ☑ done |
| 1d-2 | Frontend: "Assurance" nav section (enabled-gated, separate from model nav) | ☑ done |
| 1d-3 | Frontend: locked/unlocked banner (store not configured or locked) | ☑ done |
| 1d-4 | Backend: assurance-family excluded from `/api/entities` stats/catalogs by default | ☑ done |

## Quality Gate

| # | Task | Status |
|---|---|---|
| QG-1 | Run ruff + zuban | ☑ done |
| QG-2 | Run pytest (all tests green, pre-existing failure ignored) | ☑ done |
| QG-3 | CodeRabbit review (uncommitted) — fix critical findings | ☑ done |
| QG-4 | feature-dev code-reviewer — convention compliance check | ☑ done |
| QG-5 | Update §24 checklist in PLAN-assurance-stpa-grc.md | ☑ done |
| QG-6 | Commit Phase 1 | ◐ in progress |

## Definition of Done (Phase 1)

From §24:
- [x] A store can be configured + unlocked, fail-closed gating works (locked ⇒ no assurance tools, **G-b**)
- [x] An empty analysis-collection group exists
- [x] Nothing leaks to model views (**G-a** — assurance excluded from model stats/catalogs)
- [x] Core STPA chain can be created/queried/verified through one `arch-assurance` read+write MCP path
- [x] Assurance excluded from model stats/catalogs (**G-a**)
- [x] Every assurance mutation lands in the append-only hash-chained log (**G-c**)
- [x] §17(A) hard validity + safety-disposition guard pass/fail correctly (**G-d**)
- [x] Types.generated.ts regenerated
- [x] Tests green
