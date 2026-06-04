# Phase 5 — Assurance Capability: Cybersecurity & Supply-Chain Connectors

> Implementation of PLAN-assurance-stpa-grc.md §24 Phase 5.
> Canonical progress tracker: this file + the §24 checklist in the plan.

## Status legend: ☐ pending · ◐ in progress · ☑ done

## 5a — SecuritySignalConnector Port

| # | Task | Status |
|---|---|---|
| 5a-1 | Add `SecuritySignalConnector` protocol to `assurance_ports.py` | ☑ done |
| 5a-2 | `src/infrastructure/assurance/_schema.py` — add security_signals schema tables | ☑ done |
| 5a-3 | `src/infrastructure/assurance/_security_connector.py` — SQLite-backed connector | ☑ done |

## 5b — SBOM Parsing + AI-BOM Export

| # | Task | Status |
|---|---|---|
| 5b-1 | `src/infrastructure/assurance/_sbom_parser.py` — CycloneDX JSON + SPDX JSON | ☑ done |
| 5b-2 | `src/infrastructure/assurance/_aibom_exporter.py` — CycloneDX 1.6 export + reconcile | ☑ done |
| 5b-3 | `src/infrastructure/assurance/ai_candidate_scanner.py` — heuristic scan | ☑ done |

## 5c — MCP Tools

| # | Task | Status |
|---|---|---|
| 5c-1 | `src/infrastructure/mcp/assurance_mcp/security_read_tools.py` | ☑ done |
| 5c-2 | `src/infrastructure/mcp/assurance_mcp/security_write_tools.py` | ☑ done |
| 5c-3 | Wire security tools into context + read/write tool registrations | ☑ done |

## 5d — CLI Commands

| # | Task | Status |
|---|---|---|
| 5d-1 | `import-sbom`, `export-aibom`, `scan-ai-candidates` in `arch-assurance` CLI | ☑ done |
| 5d-2 | Extract handlers to `_security_commands.py` (LoC limit compliance) | ☑ done |

## 5e — GRC Skill Script

| # | Task | Status |
|---|---|---|
| 5e-1 | `skills/grc-management/scripts/sbom_cve_context_pull.md` | ☑ done |

## 5f — Tests

| # | Task | Status |
|---|---|---|
| 5f-1 | `tests/assurance/test_security_connector.py` | ☑ done |
| 5f-2 | `tests/assurance/test_sbom_parser.py` | ☑ done |
| 5f-3 | `tests/assurance/test_aibom_exporter.py` | ☑ done |
| 5f-4 | `tests/assurance/test_ai_candidates.py` | ☑ done |

## Quality Gate

| # | Task | Status |
|---|---|---|
| QG-1 | Run ruff + zuban — clean | ☑ done |
| QG-2 | Run pytest — 216 tests green (50 new) | ☑ done |
| QG-3 | CodeRabbit review — 4 warnings + 5 info; all warnings fixed | ☑ done |
| QG-4 | feature-dev code-reviewer — 3 issues found; all fixed (LoC, json import, column naming) | ☑ done |
| QG-5 | Update §24 checklist in PLAN-assurance-stpa-grc.md | ☑ done |
| QG-6 | Commit | ☐ pending |

## Definition of Done (Phase 5)

From §24:
- [x] An SBOM (CycloneDX/SPDX) can be ingested and its components mapped to architecture entities
- [x] Vulnerability records (OSV format) can be linked to BOM components
- [x] An AI-BOM (CycloneDX 1.6 ML-BOM) can be emitted from marked model components
- [x] A reconcile/drift report can compare modeled vs discovered AI components
- [x] `assurance_scan_ai_candidates` returns a ranked heuristic list
- [x] Anchor mappings persist across re-ingestion (idempotent re-ingest via deterministic SHA-256 IDs)
- [x] CLI commands: `import-sbom`, `export-aibom`, `scan-ai-candidates` work
