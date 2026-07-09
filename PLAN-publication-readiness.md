# PLAN — Publication Readiness: ADRs and README/Docs Uplift

Status: **draft for review** · Companion task ledger: `TASKS-publication-readiness.md` (to be created on approval)

---

## 1. Motivation and context

Before the project is published, two gaps need closing:

1. **The central architectural decisions are under-recorded.** The self-model already
   treats ADRs as a first-class document type (`.arch-repo/documents/adr.json`:
   sections Context/Decision/Consequences, connections suggested to `@all` entity
   types), and two ADRs exist (Adopt ArchiMate NEXT Ontology; Markdown File-Based
   Architecture Repository). But the most load-bearing decisions of the platform —
   the binding meta-model, the identity convention, the hexagonal dependency policy,
   the read-model architecture, the confidential assurance tier, the MCP surface
   design — live only in root `PLAN-*.md` files that will not accompany a published
   snapshot's narrative. A reader (or agent) exploring the self-model cannot discover
   *why* the system is shaped the way it is.

2. **The README/docs surface has drifted from the implementation.** The MCP tool
   listing in `docs/03-modeling/interfaces-and-mcp.md` is missing five tools and
   mis-describes one; nothing prevents future drift. All 19 `docs/media/` images are
   manual captures with no reproducible refresh path, and the GUI has evolved since
   they were taken. The motivation story is prose-only even though the self-model
   contains rendered motivation diagrams that would *show* the project practicing
   what it preaches.

Both gaps are also dogfooding opportunities: ADRs are authored *into the self-model*
through the MCP tools, and the motivation section gets illustrated by diagrams
*derived from the self-model* — the docs demonstrating the product.

## 2. Scope and non-goals

**In scope**

- Authoring the core ADR set as `adr` documents in ENG-ARCH-REPO, linked to
  self-model entities, plus a small docs-side index page.
- A generator/checker script for the MCP tool documentation, wired into CI.
- Correcting the current MCP tool documentation content.
- A repeatable media-capture harness; recapturing stale screenshots; exporting
  motivation diagrams from the self-model into `docs/media/`.
- README uplift: "Is this for you?" block, motivation-diagram embeds, image refresh.
- Disabling the SysML v2 ontology module via the existing declarative module
  override, and making every surface — backend and frontend — respect module
  enablement instead of hardcoding module knowledge.

**Non-goals**

- No new model *entities* (descriptions/documents/connections only — per the
  modeling-discipline rule that rationale belongs in descriptions and documents,
  not in new argumentative entities).
- No changes to the MCP tool *surface* itself (that is `PLAN-mcp-write-tooling-optimization.md`).
- No ADRs for subsystem-scoped decisions (C4 projection mechanics, datatype type
  resolution, body-authoritative PUML, bulk-staging internals) — these stay in
  their PLAN files; the ADR set is deliberately small.
- No restructuring of the docs/ tree (done in the README/docs rework).

## 3. Current state (verified 2026-07-07)

- **README** (`README.md`, 174 lines): strong opening (tagline, badges, hero image,
  problem prose, "What you get" table). MCP tools appear only as a config snippet +
  four example tool names (L116–132); the full listing is delegated to
  `docs/03-modeling/interfaces-and-mcp.md`. Three embedded images, all present on disk.
- **MCP tool docs vs code** (authoritative registries: `mcp_read`/`mcp_write` in
  `src/infrastructure/mcp/mcp_artifact_server.py:71,88`; `mcp_assurance_read`/`mcp_assurance_write`
  in `src/infrastructure/mcp/mcp_assurance_server.py:39,51`):
  - Undocumented tools: `artifact_query_datatype_types`, `artifact_delete_entity`,
    `artifact_delete_diagram`, `artifact_delete_document`, `artifact_admin_reindex`.
  - Materially wrong description: `artifact_diagram_scaffold` is documented as
    "generate a starting diagram skeleton for a type" but actually scaffolds a PUML
    body from a list of entity IDs.
  - Assurance tools (21 read + 16 write) are un-enumerated by design in
    `docs/04-assurance/mcp-tools.md`.
  - Enumeration is import-safe without store unlock: `server._tool_manager.list_tools()`
    (pattern precedented in `tests/tools/test_mcp_tool_descriptions.py`). CI already
    has a staleness-gate pattern for `types.generated.ts` (`.github/workflows/ci.yml:39-41`).
- **Media**: 19 images + 1 gif in `docs/media/`, all referenced ones exist; no script
  produces them (manual captures, "Phase B, controlled 1440×900 @2x" per README
  comment). Orphans: `docs/media/graph-explore.png` (unreferenced) and three stray
  untracked `diagram-*.png` at repo root. The Playwright e2e suite
  (`tools/gui/tests/e2e/smoke.spec.ts`) already drives all relevant views and takes
  screenshots — but only into test-results.
- **Self-model**: 392 entities / 757 connections / 32 diagrams / 3 documents.
  Motivation narrative is complete (5 drivers, 8 assessments, 9 goals, 15 outcomes,
  4 principles, 7 stakeholders, ~57 requirements) with six rendered motivation
  diagrams. Document↔entity linkage is currently **markdown body links only** —
  `artifact_query_find_connections_for` returns zero graph connections for all three
  existing documents; per-section document connections are a planned feature of
  `PLAN-modeling-ux-and-self-model-uplift.md` (in progress in the
  `modeling-ux-uplift` worktree).

## 4. Decisions (locked, except D8's README-diagram detail)

- **D1 — ADR set is the nine listed in §5, small and platform-scoped**, covering
  only decisions that shape the whole system. Existing ADRs for ArchiMate NEXT and
  markdown storage are kept and back-linked, not rewritten. ENG-001's ADR-001..005
  describe a *different modeled system* and are untouched.
- **D2 — ADRs are authored exclusively via MCP tools** (`artifact_create_document`
  + connection/edit tools), into the groups where their subject lives
  (`platform-core`, `promotion-and-tiering`, `assurance`). Never hand-edited files.
- **D3 — Entity linking uses the per-section document-link feature**, which is
  integrated and tested on main (modeling-UX WU-B1.1–B1.5: `DocumentSchema`
  per-section entity-type rules, verifier E156/W157 enforcement, write-path
  section hints, section-aware GUI picker, promotion schema diff). The `adr`
  document schema is extended with per-section suggested entity-type links
  (Context → drivers/assessments/principles; Decision → requirements/application
  components/business objects; Consequences → outcomes/requirements) so the
  verifier checks ADR↔entity linkage per section. Known gap handled in WU-A2b:
  there is currently no entity→document *backlink* surface (from an entity, the
  documents referencing it are not queryable in GUI or MCP).
- **D4 — MCP tool docs become generated, not hand-maintained.** A single script
  owns the tool tables between HTML markers in
  `docs/03-modeling/interfaces-and-mcp.md`; `--check` mode gates CI exactly like the
  `types.generated.ts` staleness gate. Prose around the tables stays hand-written.
- **D5 — The assurance docs section gets a full, generated MCP tool reference.**
  The existing `docs/04-assurance/mcp-tools.md` is expanded into the dedicated
  assurance tool-reference page: all 21 read + 16 write tools enumerated in
  generated tables (grouped by capability: STPA/CAST/GRC authoring, completeness
  & coverage, supply-chain/AIBOM, security signals, store administration), with
  hand-written prose for gating and classification behaviour. Tool names +
  descriptions leak nothing confidential — the live MCP handshake already exposes
  them. If the page grows unwieldy, split read/write into subpages under
  `docs/04-assurance/`.
- **D6 — Media capture becomes a scripted, repeatable Playwright flow** under
  `tools/gui/tests/media/` (separate from the e2e smoke suite; excluded from the
  default test run), writing directly to `docs/media/` at the established
  1440×900 @2x convention. All screenshots are recaptured through it once, so
  staleness triage is unnecessary.
- **D7 — Motivation diagrams are embedded as exports of self-model renders.**
  The export step copies rendered diagrams from the ENG-ARCH-REPO diagram catalog
  into `docs/media/` (SVG preferred; fall back to PNG only if GitHub rendering of
  a given SVG is defective). No hand-drawn duplicates.
- **D8 — README gets a short "Is this for you?" block, not a rewrite.** The opening
  (tagline → badges → hero → problem prose) is already strong; the block is ~12
  lines between the opening prose and "What you get", with honest "not (yet) for
  you if" bullets, linking to "Who it serves" in `docs/01-motivation.md`.

## 5. Work units

Phases A, B, C are independent of each other; D2 depends on C3; Phase E runs
after D1/D2. Because disabling SysML changes GUI pickers, the Phase C media
harness is re-run after E (that repeatability is the point of WU-C1) and the
final screenshots committed then; WU-D3 is the last work unit of the plan.
Within a phase, order is sequential.

### Phase A — ADRs in the self-model

**WU-A1 — Author the core ADR set.** Nine ADR documents via `artifact_create_document`
(doc type `adr`, status `accepted`, sections Context/Decision/Consequences,
`date`/`deciders` frontmatter like the existing two). Source material is the
respective PLAN file; the ADR distills decision + rejected alternatives +
consequences to roughly a page each — it does not replicate plan detail.

| # | ADR title (working) | Group | Primary sources | Anchor entities (link targets) |
|---|---|---|---|---|
| 1 | Artifact identity: `TYPE@epoch.random.slug` filenames; grouping by directory | platform-core | markdown-repo ADR body; `PLAN-projects-feature.md` | `APP@1781976554.AeU7V3` Identifier Allocation Service, `REQ@1712870400.Kk6Ll6` Verified Unique Identifiers, `REQ@1780505955.MdtfC3` Independent Artifact Grouping |
| 2 | Diagram–model correspondence via explicit bindings; no silent model mutation | platform-core | `PLAN-meta-ontology-v2.md`, `plans/meta-ontology-v2/FORMALIZATION.md` | `BOB@1777390172.7gJz0U` Diagram Type Definition, `REQ@1781976357.A5WgC8` Pluggable Diagram-Type Verification & Rendering, `REQ@1781704601.sbkuwf` Datatype–Data Object Consistency |
| 3 | Hexagonal core with a test-enforced dependency policy; no service locator | platform-core | `PLAN-domain-layer-purity.md` (D1–D18), `docs/architecture/dependency-policy.md` | `APP@1777293133.OYEmP1` Architecture Backend, `APP@1712870400.yNhgdh` Module Catalog, `PRI@1712870400.uraDPR` Extensibility & Configurability |
| 4 | Two-tier repositories with promotion as the governance gate | promotion-and-tiering | `PLAN-projects-feature.md` P8, promotion docs | `SRV@1712870400.Uv9Wx9` Repository Promotion Service, `BOB@1712870400.6Uok0b` / `BOB@1712870400.so7gfN` Enterprise/Engagement Repository, `REQ@1712870400.kOU3al` Two-Tiered Repository |
| 5 | Confidential assurance tier: separate gated store, one-way persisted references | assurance | `PLAN-assurance-stpa-grc.md` §3–4, §18, §26; `PLAN-assurance-storage-confidentiality.md` | `APP@1780656431.E0fzqZ` Confidential Assurance Store, `BOB@1780656241.SgtAoz` Confidential Assurance Repository, `PRI@1780655839.hVWaYW` Confidential by Default |
| 6 | One canonical artifact index per repo root; CombinedArtifactView for the pair | platform-core | `PLAN-canonical-artifact-index.md` | `DOB@1783266368.4f-C9z` Canonical Per-Repo Artifact Index, `REQ@1782080517.IIl8-4` Concurrent Reads Serialized Writes |
| 7 | Read model on single SQLite (FTS5) with Copy-on-Write; DuckDB rejected | platform-core | `async-duckdb-migration-plan.md`; `PLAN-assurance-storage-confidentiality.md` SC-5 | `DOB@1783266368.4f-C9z` Canonical Per-Repo Artifact Index, `DATATY@1782085920.9Nrbqf` Artifact Persistence Model |
| 8 | One unified backend authority: every write flows through the same verified pipeline; MCP/CLI surfaces are HTTP shims | platform-core | `PLAN-backend-runtime-unification.md` | `APP@1777293133.OYEmP1` Architecture Backend, `APP@1712870400.kRZYOA` MCP Endpoint Adapter, `APP@1777399926.PDJI8F` Operation Registry, `REQ@1712870400.m117_R` Write Access Only via Tools, `REQ@1712870400.JTRw1x` Verification Tools |
| 9 | MCP surface topology: split read/write servers, gated assurance servers, responsibility-decomposed tools | platform-core | `PLAN-mcp-write-tooling-optimization.md` D1–D6; `PLAN-assurance-stpa-grc.md` §16 | `AIF@1712870400.wuleEe` MCP Interface, `AIF@1780783713.Ik61W4` MCP Write Interface, `REQ@1712870400.peinbQ` Tool Interfaces MCP/CLI/REST |

Acceptance: 9 documents exist with all required sections; `artifact_verify` clean;
each names its rejected alternatives explicitly.

**WU-A2 — Link ADRs to anchor entities** per D3: extend the `adr` document schema
with the per-section entity-type rules, then place entity links in the matching
sections of each ADR; add cross-links between related ADRs (`[@DOC:…]` syntax)
and back-links from the two existing ADRs where they relate (e.g.
markdown-storage ADR ↔ identity ADR). Acceptance: `artifact_verify` passes the
per-section rules (E156 clean) for all eleven ADRs; every anchor entity in the §5
table is linked from at least one ADR.

**WU-A2b — Entity→document backlink surface.** Close the gap that document body
links are verified and rewritten-on-move but not queryable in reverse: expose
"referenced in documents" (document id, title, section) on the GUI entity detail
view and in the read surface (extend `artifact_query_find_connections_for` or
`artifact_query_read_artifact` output for entities — decide at the correct layer,
with the extraction logic shared with the existing rename-rewrite scanner, not
duplicated). Unit tests for the extraction + one end-to-end test asserting an ADR
appears on its anchor entity. This is what makes the ADRs *discoverable from the
model*, not just pointing into it.

**WU-A3 — Docs-side decisions index.** New page `docs/architecture/decisions.md`:
one table (decision, one-line summary, link to the ADR file in
`engagements/ENG-ARCH-REPO/…/docs/adr/`), plus a pointer from `docs/index.md` and
from `docs/05-extensibility/hexagonal-architecture.md`. Frames the ADR set as part
of the self-model ("the tool documenting its own decisions").

### Phase B — MCP tool documentation automation

**WU-B1 — Generator script** `tools/generate_mcp_docs.py` (respect the 250/350 LoC
limit; split a helper module if needed; no `Any`; consult the coding-guidelines
standard in the model before writing):

- Imports the four FastMCP instances, enumerates via `_tool_manager.list_tools()`
  (name, description first sentence, read-only/write/destructive annotation).
- Rewrites the regions between `<!-- mcp-tools:begin … -->` / `<!-- mcp-tools:end -->`
  markers in `docs/03-modeling/interfaces-and-mcp.md` (read + write tables) and
  `docs/04-assurance/mcp-tools.md` (read + write tables, per D5).
- Verifies that every tool name mentioned in README prose exists in the registry
  (report-only; README text stays hand-written).
- `--check` exits non-zero on any diff and prints it; default mode writes.

Acceptance: unit tests for marker rewriting and check mode; running twice is
idempotent; quality gates (pytest, ruff, zuban) pass.

**WU-B2 — Regenerate and correct content.** Run the generator; hand-fix the
surrounding prose where the generated tables change its claims (notably the
`artifact_diagram_scaffold` description and the write-tool grouping prose that
predates the delete tools). Acceptance: the five missing tools appear; the scaffold
description matches the code; the assurance tool-reference page (per D5)
enumerates all 21 + 16 tools grouped by capability.

**WU-B3 — CI gate.** Add `uv run tools/generate_mcp_docs.py --check` to
`.github/workflows/ci.yml` beside the types-staleness gate, and extend the shell
pre-commit hook to run it when `src/infrastructure/mcp/**` changes. Acceptance: CI
fails on an intentionally-introduced drift in a test branch, passes on main.

### Phase C — Media refresh

**WU-C1 — Capture harness.** Playwright spec(s) under `tools/gui/tests/media/`
(new `npm run media` project in `playwright.config.ts`, excluded from `test:e2e`),
reusing the smoke suite's navigation helpers: fixed 1440×900 viewport,
`deviceScaleFactor: 2`, seeded on the bundled self-model, writing each named
screenshot directly to `docs/media/`. One spec per docs area (overview/browse,
diagramming, grouping, assurance). The gif (`graph-explore.gif`) is out of scope
for automation; keep the current file and note the manual recipe in a comment.

**WU-C2 — Recapture all screenshots** via the harness against the current GUI, and
review each replaced image side-by-side before committing (a wrong-but-fresh
screenshot is worse than a stale one). Acceptance: every image referenced by
README/docs regenerated by script; visual review pass recorded in the PR
description; no references broken.

**WU-C3 — Diagram exports + cleanup.** Export step (small script or Make/npm task)
copies the rendered motivation diagrams selected in WU-D2 from the ENG-ARCH-REPO
diagram catalog into `docs/media/` (per D7). Delete the orphaned
`docs/media/graph-explore.png` and the three stray `diagram-*.png` at repo root.

### Phase D — README and motivation uplift

**WU-D1 — "Is this for you?" block** (per D8): after the opening prose, before
"What you get". Draft direction — *for you if*: your architecture needs to be
readable and writable by AI agents as much as by people; you want models in git
with review/diff/promotion instead of a modeling-tool database; you're a small
team that needs structured safety/security/GRC work without a dedicated assurance
department. *Not (yet) for you if*: you need certified conformance to a published
ArchiMate standard; you want WYSIWYG-first freeform diagramming; you need
multi-user real-time editing. Link to "Who it serves".

**WU-D2 — Motivation diagram embeds (docs only, narrative-first).** The README
stays screenshot-only (hero + the two "See it" shots, all refreshed by Phase C).
In `docs/01-motivation.md`, embed self-model-rendered diagrams *selectively*:
each embed must advance the narrative at the point where it appears — the page
must not restate the motivation layer or include diagrams for completeness'
sake. Candidate placements (final cut decided while writing, ~3 embeds, matrices
excluded): Forces diagram under "The forces at work"; Goals & Outcomes under
"What the project aims for" / "Outcomes we expect"; **one** synthesis view —
"The Story in One View" *or* "Motivation Chain", not both — under "Solution
strategy". The Why-Assurance chain goes to `docs/04-assurance/index.md` if it
fits that page's narrative, not into the motivation page. Each embed is captioned
as rendered from the self-model, with a link to the diagram in the running app.

**WU-D3 — Final coherence pass (last work unit of the whole plan, after
Phase E and the post-E media re-run).** Re-read README + touched docs
end-to-end: image alt texts still accurate after recapture, "What you get"
table consistent with the generated tool docs, decisions index linked, Status
section still true, no SysML mentions left in docs that the disabled module
contradicts. Run the full quality gates and the `--check` mode; commit
per-phase.

### Phase E — Disable SysML v2 via the declarative module flag

Mechanism (verified): `config/settings.yaml` has a `modules:` section
(currently `{}`); `module_overrides()` (`src/config/settings.py:109`) reads it
with `enabled` as the single supported override key, and
`build_module_registry()` (`src/infrastructure/app_bootstrap.py:51`) skips
disabled modules, so `/api/modules` and the runtime catalogs exclude them.
The self-model contains no SysML-typed artifacts, so disabling breaks nothing
in verification. `types.generated.ts` deliberately stays the full vocabulary
superset (`complete_vocabulary=True` codegen) — runtime filtering, not
regeneration, is the mechanism on the frontend.

**WU-E1 — Declarative disable + documentation.** Set
`modules: {sysml_v2_min: {enabled: false}}` in `config/settings.yaml`; document
the `modules:` override key (shape, single `enabled` key, manifest defaults) in
`docs/reference/configuration.md`. Integration test: with the override active,
the module registry, `/api/modules`, MCP authoring guidance, and the verifier
expose no `sysml_v2_min` types, and creating a SysML-typed entity fails with a
clear unknown-type error.

**WU-E2 — Backend: no hardcoded module knowledge.** Audit surfaces that name
SysML statically instead of consulting the module catalog, and fix at the right
layer: `_VALID_META_ONTOLOGIES` in `src/application/group_registry_validation.py`
(derive valid meta-ontology values from registered modules via the existing
`"sysml-v2" → "sysml_v2_min"` mapping in `app_bootstrap.py:166`, so a group
declaring a disabled meta-ontology is rejected with a clear message);
`c4/_projection.py`'s `compatible_ontologies` tuple (verify it tolerates the
module being absent — expected yes; add a regression test). Unit tests for the
derived validation.

**WU-E3 — Frontend: module surfaces driven by `/api/modules`.** Replace the
hardcoded meta-ontology/domain offerings in `tools/gui/src/ui/lib/domains.ts`
(SysML domain entry, `sysml-v2` meta-ontology entry and picker option) and
`ModelWizardView.helpers.ts` with lists derived from the `/api/modules`
response: presentation metadata (colors, labels) may stay keyed by module/domain
name, but *offered options* (wizard paths, domain filters, meta-ontology
pickers, type pickers) must be filtered to enabled modules — per the
no-ontology-logic-in-generic-components rule. Vitest tests for the filtering;
Playwright assertion that no "SysML v2" option appears anywhere in the GUI with
the module disabled (and that it reappears when re-enabled in a test fixture).

## 6. Security and confidentiality considerations

- Enumerating assurance *tool names/descriptions* (D5) exposes capability metadata
  only — the same metadata any connecting MCP client receives; no analysis content,
  store contents, or classification-gated data is rendered into docs. The generator
  imports module-level FastMCP instances and must not unlock or read any store.
- ADR 5 (assurance tier) must describe the confidentiality *design* without
  quoting any confidential analysis content; sources are the PLAN files and public
  docs pages only.
- Screenshots are captured against the bundled self-describing model only — never
  against a workspace containing engagement data from real clients, and never with
  the assurance store unlocked unless the shot is of the assurance GUI seeded with
  the demo/self-model content.
- No new endpoints, auth paths, or data mutations; migrations: none.

## 7. Acceptance criteria and quality gates

1. All nine new ADRs exist in the self-model, verify clean (including per-section
   link rules), and are reachable from the docs index page and — via the WU-A2b
   backlink surface — from their anchor entities' detail views.
2. `tools/generate_mcp_docs.py --check` passes in CI and fails on seeded drift;
   the documented tool set equals the registered tool set for all four servers.
3. Every image in README/docs is reproducible by `npm run media` (plus the one
   documented manual gif recipe) and reflects the current GUI.
4. README contains the "Is this for you?" block and refreshed screenshots (no
   model diagrams); `docs/01-motivation.md` embeds the selected motivation
   diagrams woven into its narrative.
5. With `sysml_v2_min` disabled in `config/settings.yaml`, no SysML type, domain,
   meta-ontology option, or wizard path is offered by MCP guidance, REST, or the
   GUI; re-enabling restores them without code changes.
6. Standard gates on every commit: `pytest` 0 failures, `ruff check src/ tests/`
   0 errors, `uv run zuban check` clean; frontend `npm run lint` + `typecheck`
   for GUI-side changes.

## 8. Open questions

None — all previously open questions are resolved and folded into §4/§5.
