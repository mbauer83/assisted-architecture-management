# Phase 2 — Assurance Capability: STPA (Control-Structure, Matrices, Skill)

> Implementation of PLAN-assurance-stpa-grc.md §24 Phase 2.
> Canonical progress tracker: this file + the §24 checklist in the plan.

## Status legend: ☐ pending · ◐ in progress · ☑ done

## Phase 2a — Control-Structure Diagram Type

| # | Task | Status |
|---|---|---|
| 2a-1 | Explore codebase: diagram type patterns, rendering pipeline, G-f condition (explorer agent) | ☑ done |
| 2a-2 | Design: control-structure diagram type blueprint (architect agent) | ☑ done |
| 2a-3 | `src/diagram_types/control_structure/` — new `module_class: assurance` diagram type | ☑ done |
| 2a-4 | PUML renderer: control-structure-nodes + control-actions + issues/acts-on/feedback loops | ☑ done |
| 2a-5 | binding_status rendering: bound=solid, unbound-pending=dashed+badge, out-of-scope=dotted | ☑ done |
| 2a-6 | G-f guard: ephemeral-only rendering — never write plaintext to diagram-catalog/rendered/ | ☑ done |
| 2a-7 | Register control-structure diagram type in app_bootstrap.py | ☑ done |
| 2a-8 | Tests for control-structure diagram type | ☑ done |

## Phase 2b — UCA Matrix + Traceability Matrix

| # | Task | Status |
|---|---|---|
| 2b-1 | `src/diagram_types/uca_matrix/` — bespoke assurance `uca-matrix` diagram type (control-action × guideword grid) | ☑ done |
| 2b-2 | UCA matrix renderer: cells show UCAs per (control-action, guideword) pair | ☑ done |
| 2b-3 | Register uca-matrix diagram type in app_bootstrap.py | ☑ done |
| 2b-4 | Traceability matrix: confirm generic `matrix` type reuse (constraint×hazard×requirement) — no new type | ☑ done |
| 2b-5 | Tests for uca-matrix diagram type | ☑ done |

## Phase 2c — stpa-basic-complete Coverage Checker

| # | Task | Status |
|---|---|---|
| 2c-1 | `assurance_stpa_complete` MCP tool in read_tools.py — §17(B) coverage profile | ☑ done |
| 2c-2 | Coverage checks: every hazard→≥1 loss; every UCA→≥1 hazard+control-action; every scenario→explains ≥1 UCA; every UCA/scenario→≥1 constraint | ☑ done |
| 2c-3 | Returns structured coverage report (gaps list + pass/fail per check) | ☑ done |
| 2c-4 | Tests for stpa-basic-complete (G-e: sample STPA passes the check) | ☑ done |

## Phase 2d — stpa-analysis Doc Type

| # | Task | Status |
|---|---|---|
| 2d-1 | Explore how doc types are defined + registered in the codebase | ☑ done |
| 2d-2 | `stpa-analysis` doc type: required sections (Purpose/Scope, Losses, Hazards, Control Structure, UCAs, Loss Scenarios, Constraints, References) | ☑ done |
| 2d-3 | E155 entity links enforced by the doc type | ☑ done |
| 2d-4 | Register stpa-analysis doc type | ☑ done |
| 2d-5 | Tests for stpa-analysis doc type | ☐ pending (covered by engagement_repo_template via existing doc type tests) |

## Phase 2e — "Model This" Workflow (US6)

| # | Task | Status |
|---|---|---|
| 2e-1 | `assurance_model_this` MCP tool in write_tools.py: returns task spec for create+bind workflow | ☑ done |
| 2e-2 | "Suggested model entities" notice: W501 verifier warning already surfaces unbound-pending nodes (Phase 1c) | ☑ done |
| 2e-3 | Tests for model-this workflow | ☐ pending (covered by Phase 1 verifier tests + manual testing) |

## Phase 2f — stpa-analysis Skill

| # | Task | Status |
|---|---|---|
| 2f-1 | `skills/stpa-analysis/SKILL.md` — trigger, steps, gotchas, ask-don't-assume rule | ☑ done |
| 2f-2 | `skills/stpa-analysis/references/stpa-method.md` — STPA method reference | ☑ done |
| 2f-3 | `skills/stpa-analysis/assets/stpa-analysis-template.md` — analysis-doc template | ☑ done |
| 2f-4 | `skills/stpa-analysis/examples/` — worked example | ☐ pending (deferred to Phase 3 — needs Phase 3 GRC/CAST content for a realistic end-to-end) |

## Quality Gate

| # | Task | Status |
|---|---|---|
| QG-1 | Run ruff + zuban | ☑ done |
| QG-2 | Run pytest (all tests green, 3 pre-existing failures excluded) | ☑ done |
| QG-3 | CodeRabbit review (uncommitted) — fix critical findings (8 min timeout) | ☑ done |
| QG-4 | feature-dev code-reviewer — convention compliance check | ☑ done |
| QG-5 | Update §24 checklist in PLAN-assurance-stpa-grc.md | ☑ done |
| QG-6 | Commit Phase 2 | ☑ done |

## Definition of Done (Phase 2)

From §24:
- [ ] US1: STPA end-to-end (losses→hazards→control structure→UCAs→scenarios→constraints) via skill + MCP tools
- [ ] US2: non-expert coaching via assurance_guidance + stpa-analysis doc template
- [ ] US4: classification validation via reference vocab (already Phase 1)
- [ ] US7: programmatic authoring via arch-assurance MCP
- [ ] US9: assurance never clutters architecture model/catalogs
- [ ] G-e: sample STPA analysis passes `stpa-basic-complete`
- [ ] G-f: rendered assurance diagrams never write plaintext to `diagram-catalog/rendered/`
- [ ] Tests green
