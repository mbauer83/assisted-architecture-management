# Phase 6 — Assurance Capability: Assurance Cases & Polish

> Implementation of PLAN-assurance-stpa-grc.md §24 Phase 6.
> Canonical progress tracker: this file + the §24 checklist in the plan.

## Status legend: ☐ pending · ◐ in progress · ☑ done

## 6a — Bowtie Diagram Type

| # | Task | Status |
|---|---|---|
| 6a-1 | `src/diagram_types/bowtie/__init__.py` — PUML renderer (threat→event→consequence with barriers) | ☑ done |
| 6a-2 | `src/diagram_types/bowtie/config.yaml` | ☑ done |
| 6a-3 | Wire bowtie into `src/diagram_types/__init__.py` | ☑ done |

## 6b — GSN (Assurance-Case) Diagram Type

| # | Task | Status |
|---|---|---|
| 6b-1 | `src/diagram_types/gsn/__init__.py` — PUML renderer (claim→subgoal→evidence) | ☑ done |
| 6b-2 | `src/diagram_types/gsn/config.yaml` | ☑ done |
| 6b-3 | Wire gsn into `src/diagram_types/__init__.py` | ☑ done |

## 6c — Assurance-Case Doc Type

| # | Task | Status |
|---|---|---|
| 6c-1 | Add `assurance-case` doc type to `src/infrastructure/workspace/_assurance_doc_types.py` | ☑ done |

## 6d — MCP Tools (argument completeness + GSN draft)

| # | Task | Status |
|---|---|---|
| 6d-1 | `assurance_draft_gsn` tool — scaffold GSN from hazards→constraints→evidence | ☑ done |
| 6d-2 | `assurance_case_completeness` tool — argument-completeness check | ☑ done |

## 6e — Guidance Entries

| # | Task | Status |
|---|---|---|
| 6e-1 | Add `assurance-case` guidance entries to `src/infrastructure/mcp/assurance_mcp/guidance.py` | ☑ done |

## 6f — Assurance-Case Skill

| # | Task | Status |
|---|---|---|
| 6f-1 | `skills/assurance-case/SKILL.md` | ☑ done |
| 6f-2 | `skills/assurance-case/references/gsn-method.md` | ☑ done |
| 6f-3 | `skills/assurance-case/assets/assurance-case-template.md` | ☑ done |
| 6f-4 | `skills/assurance-case/scripts/draft_gsn_from_hazards.md` | ☑ done |
| 6f-5 | `skills/assurance-case/scripts/completeness_check.md` | ☑ done |

## 6g — Tests

| # | Task | Status |
|---|---|---|
| 6g-1 | `tests/assurance/test_bowtie_diagram.py` | ☑ done |
| 6g-2 | `tests/assurance/test_gsn_diagram.py` | ☑ done |
| 6g-3 | `tests/assurance/test_draft_gsn.py` | ☑ done |
| 6g-4 | `tests/assurance/test_case_completeness.py` | ☑ done |

## Quality Gate

| # | Task | Status |
|---|---|---|
| QG-1 | Run ruff + zuban — clean | ☑ done |
| QG-2 | Run pytest — all tests green | ☑ done (275 assurance tests green) |
| QG-3 | CodeRabbit review — fix critical findings | ☑ done (0 findings; LoC + import-order fixed) |
| QG-4 | feature-dev code-reviewer — confidence-score issues | ☑ done (2 issues fixed) |
| QG-5 | Update §24 checklist in PLAN-assurance-stpa-grc.md | ☑ done |
| QG-6 | Commit | ☐ pending |

## Definition of Done (Phase 6)

From §24:
- [x] Bowtie diagram type renders (threat→event→consequence with barriers)
- [x] GSN diagram type renders (claim→subgoal→evidence)
- [x] `assurance-case` doc type exists with required sections
- [x] `assurance_draft_gsn` MCP tool scaffolds a GSN from store content
- [x] `assurance_case_completeness` MCP tool checks argument completeness
- [x] `assurance-case` skill directory with references, assets, scripts
- [x] All new tests green
