# Phase 0 — Assurance Module Extension Mechanism: Task List

> Implementation of PLAN-assurance-stpa-grc.md §24 Phase 0.
> Canonical progress tracker: this file + the §24 checklist in the plan.

## Status legend: ☐ pending · ◐ in progress · ☑ done

| # | Task | Status |
|---|---|---|
| 1 | Explore codebase for Phase 0 | ☑ done |
| 2 | Architect Phase 0 implementation blueprint | ☑ done |
| 3 | Implement: `module_class` + `attribute_profiles` on protocols | ☑ done |
| 4 | Implement: module manifest + `settings.yaml` modules block | ☑ done |
| 5 | Implement: conditional bootstrap + `/api/modules` endpoint | ☑ done |
| 6 | Write companion specs in `plans/assurance-overlay/` | ☑ done |
| 7 | Update `PLAN-assurance-stpa-grc.md` §24 Phase 0 status | ☑ done |
| 8 | Run tests + regenerate `types.generated.ts` | ☑ done |
| 9 | CodeRabbit review — fix critical findings | ◐ in progress |
| 10 | feature-dev code-reviewer — convention compliance check | ☐ pending |
| 11 | Commit Phase 0 | ☐ pending |

## Definition of Done (Phase 0)

From §24:
- [x] §18 decisions confirmed (all [RESOLVED] in plan — no code changes needed)
- [x] UI boundary (§3.4) locked (confirmed in plan — bespoke surfaces on shared engines)
- [x] `module_class` in protocol/registry/bootstrap with default `architecture`
- [x] `attribute_profiles` on `OntologyModule` protocol
- [x] Module manifest `enabled`/`requires` + central `config/settings.yaml` `modules:` block
- [x] Bootstrap registers only enabled+satisfied modules (fail-closed)
- [x] `/api/modules` endpoint for conditional frontend rendering
- [x] Companion specs written in `plans/assurance-overlay/`
- [x] Tests green
- [x] `types.generated.ts` regenerated
