# Phase 4 — Assurance Capability: Storage Breadth + Governance Depth

> Implementation of PLAN-assurance-stpa-grc.md §24 Phase 4.
> Canonical progress tracker: this file + the §24 checklist in the plan.

## Status legend: ☐ pending · ◐ in progress · ☑ done

## Phase 4a — PocketBase Adapter

| # | Task | Status |
|---|---|---|
| 4a-1 | Add `httpx>=0.25` and `cryptography>=42.0` to pyproject.toml main deps | ☑ done |
| 4a-2 | `src/infrastructure/assurance/_pocketbase_store.py` — HTTP adapter implementing `ConfidentialAssuranceStore` (parameterized filters, admin-token auth) | ☑ done |
| 4a-3 | `src/infrastructure/assurance/pocketbase_lifecycle.py` — health-check, collection-schema setup (check-before-create pattern) | ☑ done |
| 4a-4 | Add `pocketbase-init` + `pocketbase-status` commands to `arch_assurance.py` CLI | ☑ done |
| 4a-5 | Tests: `tests/assurance/test_pocketbase_store.py` (mocked HTTP) | ☑ done |

## Phase 4b — Private-Git Adapter

| # | Task | Status |
|---|---|---|
| 4b-1 | `src/infrastructure/assurance/_private_git_store.py` — file-backed adapter with atomic writes (tmp+os.replace) | ☑ done |
| 4b-2 | Tests: `tests/assurance/test_private_git_store.py` | ☑ done |

## Phase 4b+ — Shared ID Utils

| # | Task | Status |
|---|---|---|
| 4x-1 | `src/infrastructure/assurance/_id_utils.py` — extract `make_node_id`/`make_edge_id` from all three adapters | ☑ done |

## Phase 4c — WORM Archive + Crypto-Shredding

| # | Task | Status |
|---|---|---|
| 4c-1 | Extend `AssuranceArchive` port in `assurance_ports.py` with `WORMAssuranceArchive` protocol (legal-hold, shred, timestamp) | ☑ done |
| 4c-2 | Extend `_schema.py` — add `dek_store`, `legal_holds` tables + `timestamp_token_hex` migration | ☑ done |
| 4c-3 | `src/infrastructure/assurance/_worm_archive.py` — WORM archive: per-record AES-256-GCM DEK envelope, legal-hold enforcement, crypto-shred, RFC 3161 seal | ☑ done |
| 4c-4 | Tests: `tests/assurance/test_worm_archive.py` | ☑ done |

## Phase 4d — eIDAS Timestamping

| # | Task | Status |
|---|---|---|
| 4d-1 | `src/infrastructure/assurance/_rfc3161.py` — RFC 3161 timestamp client (manual DER, configurable TSA URL, opt-in) | ☑ done |
| 4d-2 | Extend `seal_baseline` in WORM archive to optionally call TSA and store token | ☑ done |
| 4d-3 | Tests: `tests/assurance/test_rfc3161.py` (mocked HTTP) | ☑ done |

## Quality Gate

| # | Task | Status |
|---|---|---|
| QG-1 | Run ruff + zuban | ☑ done |
| QG-2 | Run pytest (166 assurance tests green) | ☑ done |
| QG-3 | CodeRabbit review (uncommitted) — 4 findings found and fixed (major: atomic writes, DER parsing, filter injection; minor: check-before-create in lifecycle) | ☑ done |
| QG-4 | feature-dev code-reviewer — 2 issues found and fixed (noqa annotation, ID duplication extracted to _id_utils.py) | ☑ done |
| QG-5 | Update §24 checklist in PLAN-assurance-stpa-grc.md | ☑ done |
| QG-6 | Commit Phase 4 | ☐ pending |

## Definition of Done (Phase 4)

From §24:
- [ ] A team can run PocketBase as an alternative assurance store (PocketBase adapter works)
- [ ] Regulated users can enable WORM/legal-hold: baselines can be put under legal hold
- [ ] Crypto-shredding: shredding a subject's DEK makes their archive records permanently unreadable
- [ ] eIDAS-qualified timestamping: a TSA RFC 3161 token can be attached to sealed baselines
