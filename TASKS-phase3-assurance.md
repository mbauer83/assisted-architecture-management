# Phase 3 — Assurance Capability: CAST + GRC Depth

> Implementation of PLAN-assurance-stpa-grc.md §24 Phase 3.
> Canonical progress tracker: this file + the §24 checklist in the plan.

## Status legend: ☐ pending · ◐ in progress · ☑ done

## Phase 3a — CAST Capability

| # | Task | Status |
|---|---|---|
| 3a-1 | `src/application/verification/cast_complete.py` — §17(B) cast-complete coverage checker (baseline, investigates, derives) | ☑ done |
| 3a-2 | E505 verifier rule: incident without any investigates edge | ☑ done |
| 3a-3 | `assurance_cast_complete` MCP tool in read_tools.py | ☑ done |
| 3a-4 | `cast-investigation` doc type in _assurance_doc_types.py + engagement_repo_template.py | ☑ done |
| 3a-5 | `skills/cast-investigation/SKILL.md` + references/ + assets/ | ☑ done |
| 3a-6 | Tests: tests/assurance/test_cast_complete.py + test_verifier_cast_grc.py | ☑ done |

## Phase 3b — GRC Depth

| # | Task | Status |
|---|---|---|
| 3b-1 | `src/application/verification/grc_complete.py` — §17(B) grc-control-coverage-complete checker | ☑ done |
| 3b-2 | W504 verifier rule: obligation with no complies-with constraint | ☑ done |
| 3b-3 | W505 verifier rule: risk with no treatment attribute | ☑ done |
| 3b-4 | `assurance_grc_complete` MCP tool in read_tools.py | ☑ done |
| 3b-5 | `assurance_risk_register` MCP tool — query view over risk entities | ☑ done |
| 3b-6 | `assurance_coverage` MCP tool — coverage/gap summary dashboard | ☑ done |
| 3b-7 | `risk-assessment`, `risk-treatment-plan`, `compliance-statement` doc types in _assurance_doc_types.py | ☑ done |
| 3b-8 | `skills/grc-management/SKILL.md` + references/ + assets/ | ☑ done |
| 3b-9 | Tests: tests/assurance/test_grc_complete.py + test_verifier_cast_grc.py | ☑ done |

## Phase 3c — Promotion Safeguards

| # | Task | Status |
|---|---|---|
| 3c-1 | `assurance_promotion_preflight` write tool + `src/application/assurance_promotion.py` | ☑ done |

## Quality Gate

| # | Task | Status |
|---|---|---|
| QG-1 | Run ruff + zuban | ☑ done |
| QG-2 | Run pytest (all assurance tests green) | ☑ done |
| QG-3 | CodeRabbit review (uncommitted) — fix critical findings (8 min timeout) | ☑ done (0 findings) |
| QG-4 | feature-dev code-reviewer — convention compliance check | ☑ done (5 issues found and fixed) |
| QG-5 | Update §24 checklist in PLAN-assurance-stpa-grc.md | ☑ done |
| QG-6 | Commit Phase 3 | ☐ pending |

## Definition of Done (Phase 3)

From §24:
- [ ] US5: CAST investigation end-to-end (incident → investigates → hazard; observed UCAs/scenarios; corrective-actions → constraints)
- [ ] US8: risk register (risk entities with owners, register/coverage views, gaps reported)
- [ ] G-g: a CAST investigation without a sealed analysis_baseline fails cast-complete
