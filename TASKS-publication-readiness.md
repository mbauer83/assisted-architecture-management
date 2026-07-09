# TASKS — Publication Readiness: ADRs, MCP-Doc Automation, Media, README, SysML Flag

Execution ledger for `PLAN-publication-readiness.md`. This file is the **source of truth for
progress**. Update it every session. The plan says *what* and *why*; this file tracks *where
we are*.

Status values: `todo` · `in-progress` · `blocked` · `review` (impl done, awaiting user/QC) · `done`.
Never mark `done` until all quality gates pass (backend: `pytest` 0-fail · `ruff` · `zuban`;
frontend WUs additionally: `lint` · `typecheck` · `test` in `tools/gui`).

---

## Session protocol (every new / post-compaction session)

1. Read this whole file, then the plan section for the WU you pick.
2. Pick the topmost `todo`/`in-progress` WU whose dependencies are all `done`. Set it
   `in-progress` with a dated log line. Decisions in the plan §4 are **settled** — do not
   relitigate.
3. Model-writing WUs (A1, A2): invoke the `architecture-modelling` skill first;
   `artifact_authoring_guidance` before creating; `dry_run=true` before every write;
   `artifact_verify` after every batch; all authoring via MCP tools, never hand-edited files.
4. Code WUs (A2b, B1–B3, C1, E1–E3): read the "General coding guidelines" standard
   (`STD@1777137196.ItT-3l`) first; respect 250/350 LoC file limits; no `Any`.
5. Run the gates, set status, add a progress-log line (files changed + test results).
   Commit per-phase only when the user asks or has standing approval.
6. Continue with the next unblocked WU while context budget suffices; end with a
   one-paragraph handoff.

**Backend restart caveat:** MCP/`artifact_*` tools and the GUI run against a long-running
backend; backend code changes need a user-performed restart before tools/GUI reflect them;
MCP-surface changes need a client session restart. `.arch-repo/documents/*.json` schema
changes are read per-operation (verify with a dry-run before relying on this). Sequence work
to avoid blocking on a restart mid-session; state clearly when one is needed.

**Media caveat:** C1/C2 need the backend + built GUI running against the bundled self-model.

---

## Status table

| WU | Title | Depends on | Status | Notes |
|----|-------|-----------|--------|-------|
| A1 | Author the nine core ADRs via `artifact_create_document` | — | done | ids ADR@1783406715.vX4p7z, .738.Y7bzLM, .752.kQ__1X, .774.id7tSC, .789.I82vuJ, .811.fm8W_z, .825.9bDM6y, .851.pGCuZn, .863.eEC2t0; all verify clean |
| A2 | `adr` schema per-section entity-type rules + place links in all 11 ADRs | A1 | done | adr.json per-section suggested types; entity links per-section; [@DOC:] cross-links 1↔storage, 6↔7, 8↔7/9, 9→5/8; back-links from both existing ADRs; repo verify 0/0 |
| A2b | Entity→document backlink surface (GUI entity detail + read tools) | A2 | done | shared document-link extraction; `read_artifact` + GUI entity detail show document refs; backend restart needed |
| A3 | `docs/architecture/decisions.md` index + links from docs/index & hexagonal page | A1 | done | 11-row table |
| B1 | `tools/generate_mcp_docs.py` (markers, `--check`, README name check) | — | done | `src/infrastructure/docs/mcp_docs.py` + entrypoint; tests cover marker rewrite/check diff |
| B2 | Regenerate tool tables; fix prose (scaffold desc, delete tools, assurance ref page) | B1 | done | modeling docs now include 9 read + 24 write; assurance page enumerates 21+16 grouped by capability |
| B3 | CI staleness gate + pre-commit trigger on `src/infrastructure/mcp/**` | B2 | done | CI runs `uv run tools/generate_mcp_docs.py --check`; pre-commit regenerates docs on MCP source changes |
| C1 | Playwright media harness (`tools/gui/tests/media/`, `npm run media`) | — | done | 1440×900 @2x → docs/media/; `test:e2e` is `--project=chromium`; gif stays manual |
| C2 | Recapture all screenshots + side-by-side review | C1 | done | final media harness run after E3; PNG set reviewed |
| C3 | Export selected motivation diagram renders + delete orphans | C1 | done | exports motivation-forces/goals-outcomes/story + assurance why-chain SVGs; orphan PNGs removed |
| D1 | README "Is this for you?" block | — | done | after self-model paragraph, before "What you get"; links #who-it-serves |
| D2 | Motivation diagram embeds in docs/01-motivation.md (narrative-first, ~3) | C3 | done | three motivation embeds; why-assurance chain placed in assurance index; README unchanged |
| E1 | `modules: {sysml_v2_min: {enabled: false}}` + configuration.md docs + integration test | — | done | mechanism: settings.py:109 → app_bootstrap.py:51 |
| E2 | Derive `_VALID_META_ONTOLOGIES` from registered modules; C4 tolerance test | E1 | done | group_registry_validation.py; mapping app_bootstrap.py:166 |
| E3 | Frontend module surfaces driven by `/api/modules` (domains.ts, wizard helpers) | E1 | done | offered options filtered; presentation metadata may stay static; Playwright assert no "SysML v2" |
| D3 | Final coherence pass (README + docs re-read, gates, `--check`) | all others | done | final docs coherence and full gates clean |

Recommended order: **A1 → A2 → A3 → B1 → B2 → B3 → C1 → C3 → D1 → D2 → A2b → E1 → E2 → E3 →
C2 (final run) → D3**. A2b and Phase E need backend restarts — batch them late so model/docs
work isn't blocked on restarts.

---

## Decision log

- Nine-ADR set, groups, and anchor entities: plan §5 table (settled).
- ADR linking = per-section body links via the shipped `DocumentSchema` feature; `adr` schema
  extended with per-section *suggested* entity types (settled).
- Assurance tool reference = expanded `docs/04-assurance/mcp-tools.md`, generated tables
  (settled).
- README: screenshots only, no model diagrams; motivation page embeds ~3 diagrams
  narratively — one synthesis view only (settled).
- SysML v2 disabled via existing `modules:` override; runtime filtering, `types.generated.ts`
  stays full superset (settled).

## Progress log

- 2026-07-07 — Ledger created from the approved plan. Starting WU-A1 (author nine ADRs).
- 2026-07-07 — WU-A2 schema slice done: `adr.json` extended with per-section
  `suggested_entity_type_connections` (Context: driver/assessment/principle/requirement;
  Decision: requirement/app-component/app-interface/business-object/data-object/service;
  Consequences: outcome/requirement); verified through `load_document_schemata`.
- 2026-07-07 — WU-A1: all nine ADR bodies drafted (style-matched to the existing two ADRs,
  entity links placed per-section per plan §5 anchor table) and persisted to the session
  scratchpad (`adr-manifest.md` + `adr-{1..9}-body.md`).
- 2026-07-07 — **Tool defect found & fixed during WU-A1** (fix-the-tool rule):
  `create_document` verified content in a sandbox at `docs/<subdir>/<file>`, dropping the
  group segment, so relative entity links written for the real depth
  (`docs/<subdir>/<group>/<file>`) mis-resolved → spurious W155 → write blocked (the write
  gate `_document_write_allowed` rejects on any issue incl. warnings — gate behavior left
  unchanged). Fix: `src/infrastructure/write/artifact_write/document.py` now derives
  `desired_name` from `path.relative_to(repo_root / DOCS)` (same derivation `edit_document`
  already used). Regression test
  `tests/tools/test_document_write.py::test_create_grouped_document_resolves_relative_entity_link`
  (verified failing pre-fix, passing post-fix). Gates: pytest 3779 passed/9 skipped, ruff
  clean, zuban clean. **Backend restart required** before `artifact_create_document` picks
  up the fix (no MCP-surface change → no client-session restart). Next: after restart,
  create ADRs 1–9 from scratchpad manifest, run `artifact_verify`, finish A2 cross-links.
- 2026-07-07 (post-restart) — A1 done: 9 ADRs created via MCP, all valid 0-issue (ids in
  status table). A2 done: [@DOC:] cross-links (1↔storage-ADR, 6↔7, 8→7+9, 9→5+8) + back-links
  added to both existing ADRs (loose "ADR-001/002" prose upgraded to [@DOC:] links); repo-wide
  artifact_verify 0 errors/0 warnings. A3 done: docs/architecture/decisions.md (11-row index)
  + pointers from docs/index.md and hexagonal-architecture.md. D1 done: README "Is this for
  you?" section. B1–B3 and C1+C3 delegated to parallel subagents; D2 pending C3 export names;
  A2b + Phase E remain (both need backend restarts — batch at the end).
- 2026-07-07 — B1/B2/B3 done: added generated MCP docs helper + `tools/generate_mcp_docs.py`,
  marker-managed tables in modeling and assurance docs, CI `--check` gate, and pre-commit
  regeneration on `src/infrastructure/mcp/**` changes. Generated docs now include
  `artifact_query_datatype_types`, delete document/entity/diagram tools, `artifact_admin_reindex`,
  and the corrected `artifact_diagram_scaffold` description; assurance docs enumerate 21 read +
  16 write tools. Gates: focused generator pytest 5 passed; `uv run tools/generate_mcp_docs.py
  --check` clean; `uv run ruff check src tests tools/generate_mcp_docs.py` clean; `uv run zuban
  check` clean; full `uv run pytest -q` 3784 passed/9 skipped in 74.50s. A sandboxed pytest run
  using `UV_CACHE_DIR=/tmp/uv-cache` was interrupted after exceeding expected runtime; rerun with
  normal uv cache passed.
- 2026-07-07 — C1 done: added `tools/gui/tests/media/media.spec.ts`, `npm run media`, and a
  Playwright `media` project with 1440×900 @2x screenshots written to `docs/media/`; changed
  `npm run test:e2e` to `--project=chromium` so media capture remains opt-in. Harness covers
  overview/browse, grouping, stored diagram examples, C4 create flow, and assurance views; the
  existing graph GIF remains manual with an inline recipe comment. Gates: `npm run lint` clean;
  `npm run typecheck` clean; `npm run test` 44 files/476 tests passed; Playwright `--list`
  confirms 32 chromium e2e tests and 4 media tests. `npm run media` intentionally not run yet;
  final recapture remains C2 after Phase E.
- 2026-07-07 — C3 done: added `tools/export_doc_diagrams.py` and exported four self-model SVGs
  into `docs/media/` (`motivation-forces`, `motivation-goals-outcomes`, `motivation-story`,
  `assurance-why-motivation-chain`). Removed orphan `docs/media/graph-explore.png` and root
  `diagram-after-fix.png`, `diagram-connections-after.png`, `diagram-final.png`. Gate:
  `uv run ruff check tools/export_doc_diagrams.py` clean; file existence/orphan checks clean.
- 2026-07-07 — D2 done: embedded `motivation-forces.svg`,
  `motivation-goals-outcomes.svg`, and `motivation-story.svg` in `docs/01-motivation.md`
  at the forces, goals, and solution-strategy sections; embedded
  `assurance-why-motivation-chain.svg` in `docs/04-assurance/index.md`. Each caption notes
  that the diagram is rendered from the self-model and links to the running app. README remains
  screenshot-only. Gate: media-reference existence check clean.
- 2026-07-07 — A2b done: added shared markdown document-link extraction in
  `src/application/document_links.py`; reused it in entity rename link rewriting; exposed
  `referenced_in_documents` through `ArtifactRepository.read_artifact` and `/api/entity-context`;
  rendered "Referenced in documents" on GUI entity detail; added unit/read-surface tests plus a
  Playwright smoke assertion for an ADR anchor entity. Gates: focused backlink/rewrite tests
  7 passed; source-length guard passed after moving enrichment out of the oversized index service;
  `uv run ruff check src tests tools/generate_mcp_docs.py tools/export_doc_diagrams.py` clean;
  `uv run zuban check` clean; `uv run pytest -q` 3786 passed/9 skipped in 68.44s; GUI
  `npm run lint`, `npm run typecheck`, and `npm run test` clean (476 tests). Backend restart
  required before live GUI/MCP sessions expose the new backlink field.
- 2026-07-07 — E1 done: checked-in `config/settings.yaml` now disables `sysml_v2_min`;
  `docs/reference/configuration.md` documents the `modules:` override shape and restart/runtime
  scope; added integration coverage proving an explicit disabled override removes SysML from
  the runtime registry, `/api/modules`, MCP authoring guidance, verifier type catalogs, and
  entity creation. SysML vocabulary tests now use `complete_vocabulary=True`. Gates: focused
  module/config/guidance tests 120 passed; `uv run ruff check src tests tools/generate_mcp_docs.py
  tools/export_doc_diagrams.py` clean; `uv run zuban check` clean; `uv run pytest -q` 3786
  passed/9 skipped in 74.00s. Earlier full-suite run failed once on unrelated assurance-load
  timing p95 (0.529s > 0.5s) and passed on rerun. Backend and frontend restarts are required
  before live sessions reflect the disabled module.
- 2026-07-07 — E2 done: removed the static SysML-valid meta-ontology set from
  `group_registry_validation`; backend startup now derives valid meta-ontology aliases from
  the active module registry via `registered_meta_ontology_values`, so `sysml-v2` groups are
  rejected when `sysml_v2_min` is disabled. Added derived-validation tests and a C4 regression
  test proving the C4 compatibility manifest tolerates the absent SysML ontology. Gates:
  focused startup/group/module tests 27 passed; `uv run ruff check src tests
  tools/generate_mcp_docs.py tools/export_doc_diagrams.py` clean; `uv run zuban check` clean;
  `uv run pytest -q` 3790 passed/9 skipped in 84.42s.
- 2026-07-07 — E3 done: added frontend `/api/modules` schema/repository/service support and
  changed meta-ontology pickers, framework/domain navigation, wizard cards, overview domain
  cards, entity filters, and reference-picker domain chips to use active modules or active
  write-help domains. Static colors/labels remain metadata only; the unfiltered
  `META_ONTOLOGY_OPTIONS` export was removed. Added pure helper tests and a Playwright smoke
  assertion that "SysML v2" is not offered after `/api/modules` loads. Gates: GUI `npm run
  lint`, `npm run typecheck`, and `npm run test -- --run` clean (45 files/480 tests);
  Playwright `--list --project=chromium` shows 34 tests including the disabled-SysML assertion;
  backend `ruff`/`zuban` clean and `uv run pytest -q` 3790 passed/9 skipped in 61.97s.
- 2026-07-07 — C2 in progress after backend/frontend restart: recapturing the media harness
  outputs into `docs/media/` and reviewing the resulting screenshot set.
- 2026-07-07 — C2 done: `npm run media` recaptured all 17 PNG screenshots into
  `docs/media/` after the post-E3 backend/frontend restart; all PNGs are non-empty at
  2880×1800, and representative visual review covered overview, entity list, ArchiMate
  diagram, and assurance overview (now captures the loaded page, not the loading state).
  Added a favicon asset to remove static 404 noise during capture and registered
  `/api/modules` in the real backend app so the frontend module filtering path works live.
  Gates: GUI `npm run lint`, `npm run typecheck`, `npm run test -- --run`, Playwright
  chromium `--list`, `npm run media`; backend `ruff`, `zuban`, generated-docs `--check`,
  and full `uv run pytest -q` clean (`3791 passed, 9 skipped in 63.26s`).
- 2026-07-07 — D3 in progress: final coherence pass over README/touched docs, stale
  SysML mentions, image references, generated-doc staleness, and already-run full gates.
- 2026-07-07 — D3 done: re-read README and touched public docs for screenshot/alt-text
  accuracy, generated-tool-doc consistency, decisions-index links, and status wording. Fixed
  two stale extensibility references so `sysml_v2_min` is described as shipped but disabled by
  default, with GUI/runtime filters following active modules. Local markdown image-reference
  check passed; stale SysML search leaves only configuration, optional-module docs, tests, and
  inactive metadata. Final gates: `uv run tools/generate_mcp_docs.py --check`, `uv run ruff
  check src tests tools/generate_mcp_docs.py tools/export_doc_diagrams.py`, `uv run zuban
  check`, GUI `npm run lint`, `npm run typecheck`, `npm run test -- --run`, and full
  `uv run pytest -q` all clean (`3791 passed, 9 skipped in 57.84s`).
