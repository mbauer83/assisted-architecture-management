# Implementation Plan — Artifact Grouping (Model-Projects & Collections)

**Mode:** [PLAN] · **Status:** Implemented · **Owner:** TBD · **Date:** 2026-06-01

## Implementation Progress (as of 2026-06-03)

| Phase | Status | Key files created/modified |
|---|---|---|
| P0 — Domain & Registry | ✅ Done | `src/domain/groups.py` (new), `src/application/group_registry.py` (new), `src/domain/artifact_types.py` (group field on all 4 records + ArtifactSummary + summary_from_* updated) |
| P1 — Path Helpers | ✅ Done | `src/application/repo_path_helpers.py` (new: model_roots, group_fn_*, rendered_dir_for_diagram, repo_root_for_diagram_path, doc-link rewrite_doc_link), `src/infrastructure/artifact_index/_service_incremental.py` (scan_mount uses all_model_roots + sets group via replace()), `src/infrastructure/write/artifact_write/diagram_render.py` (rendered_dir + repo_root via helpers) |
| P2 — Migration | ✅ Done | `src/infrastructure/workspace/migrate_to_groups.py` (new: idempotent migration command, seeds groups.yaml, rewrites doc links) |
| P3 — Index & Query | ✅ Done | `_sqlite_schema.py` (group_name column + indexes on all 4 tables), `_sqlite_store.py` (row builders + INSERT stmts updated), `ports.py` (group param on list_*), `_artifact_query_helpers.py` (matches_* updated, read_* include group, summary_group_key supports 'group'), `artifact_repository.py` (list_* pass group), `service.py` (list_* + stats updated) |
| P4 — Read Surface | ✅ Done | `query_list_read_tools.py` (group param + single-family validation), `query_stats_tools.py` (group_by='group'), `_artifact_search.py` (count_artifacts_by supports 'group'), `artifact_repository.py` (count_artifacts_by Literal updated) |
| P5 — Create/Edit group | ✅ Done (T5.1+5.2+5.3) | `entity.py::entity_path` accepts group; `create_entity/diagram/document` take optional `group`; `edit_entity` + `artifact_edit_entity` MCP take optional `group` → re-home (moves entity + outgoing connections file, name+group simultaneously handled, all-model-roots scan fixed) |
| P6 — Group Lifecycle | ✅ Done | `group_ops.py` (create/rename/archive/unarchive/delete_collection; `_all_doc_group_dirs` helper; batched git rm; document-collection `_group_dir` fixed), `write/group.py` (artifact_group MCP + background refresh after rename/delete), registered in `write_tools.py` |
| P7 — Frontend | ✅ Done (T7.1+T7.2+T7.3+T7.4) | `GroupSelector.vue` (+management dialogs, "+"/⋯ UI, create/rename/archive/delete via REST); REST group endpoints (`GET /api/groups`, `POST/PUT/DELETE /api/group`, archive/unarchive); `DiagramsView.vue` + `DocumentsView.vue` (group selector sidebar + SSE); group badges + empty states in all three views |
| P8 — Group-aware Promotion | ✅ Done | `_promote_groups.py` (GroupMappingEntry, compute_group_mapping, remap_entity_rel, update_enterprise_groups), `_promote_plan_content.py` (plan_docs/plan_diagrams), `promote_to_enterprise.py` (group_mapping + available_enterprise_groups on PromotionPlan), `_promote_file_ops.py` (group_slug_remap in copy_entity), `promote_execute.py` (group_mapping_resolutions), `promote.py` REST (group_mapping_resolutions body + group_mapping in plan response), frontend: PromotionGroupMappingEntry in schemas.ts, ModelRepository.ts, usePromotionWorkflow.ts (groupMappingResolutions + unresolvedGroupConflicts + setGroupMapping), PromotionPlanSummary.vue (group-mapping section + dropdown), PromoteView.vue |
| P9 — Cascade Delete | ✅ Done | `cascade_delete.py` (cascade_delete_model_project, _cascade_preflight, _cascade_apply — two-stage dry_run), `_cascade_helpers.py` (file-parsing helpers), `group_ops.py` (model-project delete → cascade_delete, dry_run on group_op), `group.py` MCP (dry_run param) |
| P10/11 — Self-model + docs | ✅ Done | `REQ@1780505955.MdtfC3` (Independent Artifact Grouping req), `APP@…model-project-group-axis`, `APP@…diagram-collection-group-axis`, `APP@…document-collection-group-axis` (all via MCP tools), connections to `GOL@1712870400.Po1Qw3` + `GOL@1776628205.kCcPph`; README §Content Organisation added |

**Decisions locked (2026-06-03):**
- **T7.3**: GUI uses REST; group CRUD via `POST/PUT/DELETE /api/group*` endpoints delegating to `group_op()`.
- **P8**: User explicitly maps each engagement model-project to an enterprise group (or creates new); mapping is part of the promotion plan; reuse/extend existing conflict-resolution dialog; atomic transaction.
- **P9**: Two-stage via `dry_run` flag (consistent with rest of write API); diagram removal = full PUML regeneration via `_render_diagram_entities_puml()` (same as `artifact_edit_diagram`); **both dry-run report and apply result warn the user when any affected diagram has a customised PUML body** (i.e. body differs from a fresh derivation) — body will be lost on regeneration; revisit for surgical removal once the PUML-editing plan ships; structured impact report with names + paths; apply blocked when documents have breaking links.

**All phases complete.** P8–P11 delivered 2026-06-03.

---

> The repository gains **three independent grouping axes**, one per artifact family, so growing
> content stays navigable in the GUI's **Browse**, **Diagram**, and **Document** areas:
>
> | Axis | Groups | Storage | Lifecycle weight |
> |---|---|---|---|
> | **Model-project** | entities + connections | `projects/<slug>/model/<domain>/<type>/…` | rich — cascade delete |
> | **Diagram-collection** | diagrams | `diagram-catalog/diagrams/<slug>/…` (+ `rendered/<slug>/`) | light — folder |
> | **Document-collection** | documents | `docs/<doc-type-subdir>/<slug>/…` | light — folder |
>
> The axes are **mutually independent**: a diagram-collection is *not* tied to a model-project;
> a diagram or document references model entities across **any** model-projects. Grouping is a
> **soft partition** — it never constrains search, selection, or linking.
>
> **Framing:** this is a *path-semantics migration*, not merely a grouping feature. The physical
> layout is locked first (§2.1), all code is routed through path-helper APIs (Phase 1), and only
> then are files moved (Phase 2). The riskiest operation — model-project cascade delete — is
> **deferred** to the end (Phase 9) so the navigability win ships without waiting on it.

---

## 1. Business Context

The repository already partitions content along two *path-derived* facets: **scope** (engagement vs.
enterprise, from the repo root) and **domain/type** (from `model/<domain>/<type>/`). As a single repo
accumulates work across initiatives, users need a finer grouping to organise and navigate it
*without* splitting into separate git repos (which is what *engagements* already are — too heavyweight
for intra-repo organisation).

This serves **Plan Collaboratively in a Unified, Staged Repository System** (`GOL@…Lm2Bn2`) and
**Maintain Coherence and Traceability** (`GOL@…Po1Qw3`), and is anticipated by the **Extensibility and
Configurability** principle (`PRI@…uraDPR` — "directory structure conventions … shall be
configurable"). It does **not** replace the two-tier engagement/enterprise model; it is a finer
grouping *within* each tier.

**Design principles:**

1. **Grouping is directory-based, not a frontmatter field.** Artifact IDs (`PREFIX@epoch.random.slug`)
   are location-independent, and the structural references — connections and diagram bindings — are
   **by ID, not path**, so moving a file cannot break them. The one exception, **relative-path
   document links, is handled transactionally (§4.6)**. A directory is therefore the cleanest home for
   exclusive-membership grouping (single source of truth, `git mv` re-homing, git-native subtrees,
   filesystem discoverability).
2. **Three independent axes, not one universal "project."** Entities/connections *constitute* the
   model and carry lifecycle meaning. Diagrams/documents are *projections* whose cohesion is often
   cross-project (a landscape view, an enterprise standard); each family gets its own axis so
   cross-cutting views aren't forced into an arbitrary "home project."
3. **Human-readable slug as locator + stable id for identity.** A group's directory name is its
   human-readable `slug` (the locator); renaming it is a subtree `git mv`. A **stable opaque `id`** in
   `groups.yaml` carries identity across rename and tier (promotion/conflict matching) — directories
   stay readable, identity stays robust.

---

## 2. Architecture Summary

### 2.1 Canonical layout (locked) & derivation

Placement is **family-specific** because each family has different fixed structural levels — there is
**no uniform "first segment = group" rule** (that would turn `diagrams/`, `rendered/`, and the shared
`_archimate-*.puml` includes into accidental groups). The model axis *wraps* the model tree (so depth
*below* `model/` is unchanged); the lightweight collection axes are *inserted below* the stable family
subfolders (so source/rendered split and doc-type roots are preserved):

```
<repo-root>/                                    # engagement OR enterprise (scope — unchanged)
  projects/<model-project-slug>/model/<domain>/<type>/…   # model tree wrapped; depth below model/ intact
  diagram-catalog/
    diagrams/<diagram-collection>/…             # collection BELOW the stable diagrams/ root
    rendered/<diagram-collection>/…             # rendered mirrors the same collection
    _archimate-*.puml                           # shared includes stay at catalog root (never a group)
  docs/<doc-type-subdir>/<doc-collection>/…     # collection BELOW the doc-type subdir
  .arch-repo/
    groups.yaml                                 # registry — inside the staged-transaction boundary
    schemata/  documents/                       # unchanged
```

**`group_fn(path)` is family-aware**, built on the Phase-1 path helpers (never ad-hoc `parents[n]`):
- entity / connection → segment after `projects/` (connection from its **source** entity's path);
- diagram → segment after `diagram-catalog/diagrams/` (rendered mirrors it);
- document → segment after `docs/<doc-type-subdir>/`;
- fallback **`uncategorized`** when no group segment is present.

A **doc-collection spans doc-type subdirs** (its content is the union of `docs/*/<slug>/`); the GUI
groups it logically. `group` is **derived**, never written to frontmatter → no field to validate or
keep in sync.

### 2.2 Identity & naming (slug locator + stable id)

- **`slug`** = directory name = the human-readable handle passed to tools; unique per family per repo
  (filesystem-enforced). **Rename = atomic subtree `git mv` + registry update + reindex.** ID-based
  references (connections, diagram bindings) are unaffected; **relative-path document links are
  rewritten/maintained in the same transaction (§4.6)**.
- **`id`** (stable, opaque, e.g. `GRP@epoch.random`) in `groups.yaml` — **invisible plumbing** used
  only for **promotion/conflict matching**; survives slug rename and crosses tiers, so cross-tier
  identity does **not** drift on rename.
- **`name`, `description`, `order`, `archived`, `default`** = `groups.yaml` fields, cheaply mutable
  with no file move.
- **Cross-repo identity = dual match** at promotion (mirrors the existing artifact rule): same `id`
  → same group (preserve); same slug/name, different `id` → conflict surfaced for resolution; no match
  → create. Creation-time slug uniqueness is a **best-effort early warning** across *currently
  checked-out* registered repos only; **promotion-time conflict resolution is the authoritative
  backstop**.

### 2.3 Registry (`.arch-repo/groups.yaml`)

One section per axis; an entry carries `id`, `slug`, `name`, `description`, `order`, `archived`, and
(model axis only) `default`. **Present from day one for all three axes** (seeded at migration,
maintained by `artifact_group`), **schema-validated** against `.arch-repo/schemata/groups.schema.json`,
and **mutated inside the staged transaction** (§4.2). **Discovered-but-unregistered folder** (e.g. a
hand-created directory): auto-synthesised into the in-memory registry (slug = folder name, fresh `id`
allocated and persisted on the next registry write), appears in pickers, and is a **valid target** for
create/re-home. Only a slug that is *neither registered nor an existing folder* is rejected as
"unknown" (with guidance to `artifact_group create` it). Groups are runtime data → **not** in
`tools/generate_types.py` / `types.generated.ts`.

### 2.4 Default-group semantics

- **`uncategorized` is the uniform mechanical fallback** in every family (what `group_fn` returns when
  no group segment is present).
- Migration additionally creates an **engagement-named model-project** as the *initial home* for
  existing model content and the **default-selected** group in the GUI. This is a migration choice,
  not a different rule — diagrams/docs land in `uncategorized`; only the model axis gets an
  engagement-named starter group.

### 2.5 Layer mapping (hexagonal — keep the domain pure)

| Layer | Change |
|---|---|
| **Domain** (`src/domain/`) | `Group`/registry value types (`id`, `slug`, …); `group` field on record dataclasses. No infra imports. |
| **Application** (`src/application/`) | **path-helper APIs** (§Phase 1); `GroupRegistry` loader + schema; `group_fn`; `group` filter on `ArtifactStorePort.list_*`; lifecycle, re-home, cascade & promotion use-cases (orchestration only). |
| **Infrastructure** (`src/infrastructure/`) | index `group` column + filter; staged-transaction boundary incl. `.arch-repo`; REST; MCP; SSE; renderer/include resolution via helpers. |
| **Frontend** (`tools/gui/`) | per-area group selector + counts/badges/archived-toggle; group-management UI; owned/foreign + patch-preview delete dialog; pass `group` on create/move. |

### 2.6 Tool & interface surface (deliberately minimal — see §7)

| Surface | Change |
|---|---|
| `artifact_group` (**new, only new write tool**) | `kind` × `action` (create / rename / archive / unarchive / delete); typed `confirm` (slug) for destructive/non-empty ops |
| `create_entity` / `create_diagram` / `create_document` | `+1` optional `group` param (defaults to family default/uncategorized) |
| `edit_entity` / `edit_diagram` / `edit_document` | `+1` optional `group` param → **re-home** (safe `git mv`) |
| `add_connection` | **none** — inherits group from its source entity |
| read tools (`list` / `search`) | `+1` optional `group` filter, honored **only when the query is scoped to one record family** (else error — see §7) |
| `artifact_query_stats` | `'group'` added to `group_by` (per-kind bucketing) |

**Interfaces:** grouping is exposed via **MCP + REST + GUI**. **CLI is out of scope** for grouping
authoring/lifecycle — consistent with artifact authoring (also not CLI-driven); MCP/REST is the
supported automation surface. Revisit only if a concrete CLI need arises.

---

## 3. User Stories

- **US-1 Organise the model.** Create a model-project grouping related entities/connections as a unit
  with lifecycle meaning.
- **US-2 Organise views & docs independently.** Group diagrams and documents into their own
  collections, independent of model-projects.
- **US-3 Create into a group.** When creating an artifact, place it in a chosen group (default = the
  family's current/default group); connections inherit their group from their source.
- **US-4 Navigate by group.** Filter Browse by model-project, Diagram by diagram-collection, Document
  by doc-collection (each with "All", counts, and an archived-visibility toggle).
- **US-5 Link freely across groups.** Connect, reference, and search across any group boundary with
  **no constraints**.
- **US-6 Rename a group.** Change a group's display name cheaply (registry) or its slug/directory (a
  safe subtree move) without breaking any reference; identity (`id`) is stable across the rename.
- **US-7 Re-home an artifact.** Move an entity/diagram/document to another group of the same axis;
  references are by ID, so nothing breaks.
- **US-8 Archive a group.** Hide a group from default pickers while keeping its content indexed and
  linkable (non-destructive).
- **US-9 Delete a collection.** Delete a diagram/document collection — removes the folder and its
  diagrams/documents (typed confirmation when non-empty); no model impact.
- **US-10 Promote across tiers, group-aware.** Promote entities and have their model-project resolve
  to the right enterprise group (matched by `id`, conflicts surfaced), within the promotion
  transaction.
- **US-11 Delete a model-project (cascade).** Delete a model-project and have the system remove its
  entities/connections **and** clean every foreign artifact that referenced them — after a **patch
  preview** and typed confirmation, leaving the model verifiably consistent. *(Deferred — Phase 9.)*
- **US-12 Existing content keeps working.** After migration, all current content lives in default
  groups and every query, diagram, render, link, sync, and verify behaves exactly as before.

---

## 4. 🔴 Cross-Cutting Concerns

### 4.1 Security & Auth
- **No new trust boundary.** Grouping is a *view filter*, not isolation/permission. Existing controls
  unchanged: `--admin-mode` for enterprise writes, `--read-only` blocks all mutations incl.
  `artifact_group`, and the engagement/enterprise asymmetric-reference rule is untouched.
- **Typed confirmation:** any model-project `delete`, and `archive`/`delete` of a *non-empty*
  collection, require `confirm` == the target's slug (re-typed), not a boolean. Reversible ops take no
  typed gate. Group handles are validated against the registry / directory set.

### 4.2 Data Consistency & Integrity 🔴 (primary risk area)
- **Single source of truth:** membership is the directory; the indexed `group` is derived.
- **Rename & re-home safety:** a subtree `git mv` (rename) or single-file `git mv` (re-home) leaves
  ID-based references (connections, diagram bindings) untouched, but **requires maintaining the
  relative document links** affected by the move (§4.6) inside the same transaction. Gate: clean
  full-repo `verify` **incl. W155/E155** afterward.
- **Staged-transaction boundary now includes `.arch-repo/groups.yaml`.** Every op that touches both
  files and the registry (create/rename/archive/delete, migration, group-aware promotion) stages the
  registry change *and* the file changes together, schema-validates the registry, runs the verifier,
  and commits atomically — or aborts with no partial state. Registry-without-files (or vice-versa)
  half-states are thereby impossible.
- **Model-project cascade delete (Phase 9) is two-stage:**
  1. **Preflight + patch preview** — compute owned + foreign collateral *and* generate the exact diff
     (files removed, diagram edits, doc impacts, registry change) for review; mutates nothing.
  2. **Apply** — only on typed confirm: one staged bulk op (incl. registry), verify-before-commit,
     atomic.
  - **Owned:** delete the project's entities + connections.
  - **Foreign connections:** delete every connection with *either* endpoint in the deleted project.
  - **Foreign diagrams (any collection):** **remove the diagram element *and* its incident in-diagram
    connections** (no phantom nodes); diagram-syntax verifier must pass.
  - **Foreign documents:** **block by default** with an actionable report (which links/docs must be
    resolved, esp. schema-required links → E155); proceed only via an explicit, safe, schema-aware
    rewrite — **never silently strip prose links**.
  - Diagram/document **collections are never deleted** by a model-project delete.

### 4.3 Migration 🔴 (Phase 2, after path helpers land)
- **Forward (one commit per repo):** model → `projects/<engagement-label>/model/`; diagram sources →
  `diagram-catalog/diagrams/uncategorized/…` (+ `rendered/uncategorized/…`); documents →
  `docs/<doc-type-subdir>/uncategorized/…`; seed `groups.yaml` (with `id`s); **rewrite every
  relative document link to its new target (§4.6)** — model targets *and* documents both move, so all
  doc→model links shift. Idempotent.
- **Rollback:** `git revert` — safe and lossless (the commit includes the link rewrites).
- **Include & render paths:** collection nesting adds one path level; `!include` resolution and the
  `diagrams/→rendered/` mapping are handled by the Phase-1 helpers, not by hand-edited paths.
- **Index schema:** the `group` column is additive, rebuilt-on-startup. **Coordinate with the
  in-flight `async-duckdb-migration-plan.md`.**
- **Order dependency removed:** helpers accept both legacy and new layouts transitionally; the legacy
  branch is dropped in a later cleanup.

### 4.4 Domain Events / Observability 🟡→🔴
- **Every group lifecycle op MUST publish an SSE event** (`GET /api/events`) so pickers/open views
  refresh — parity with existing sync/write-lock events.
- **Logging:** each op logs at INFO with kind + slug; delete logs owned/foreign collateral counts
  before (intent) and after (result).

### 4.5 Operational test matrix (applies across phases)
File watchers during/after moves; git background-sync during a group rename/delete (write-block
interplay); save-dialog change summaries; rendered-diagram paths & `!include` resolution post-nesting;
verifier incremental-cache invalidation on move; **rollback after partial failure** of a staged op;
mixed-query group-filter rejection; **document-link integrity (W155/E155) after migration, project/
collection rename, and entity/document re-home**; promotion scenarios (§Phase 8).

### 4.6 Reference encoding — what a move actually breaks 🔴
Verified against current code:
- **Connections** and **diagram bindings** (`entity-ids-used`, `connection-ids-used`,
  binding `target.entity_id`) reference targets **by artifact ID**, resolved via the registry —
  **location-independent**; rename / re-home / migration do **not** break them.
- **Document body links are relative file paths** (`[…](../../model/…/REQ@….md)`), resolved on disk
  by the verifier (`(doc.parent / href).resolve()` → W155; E155 for schema-required links). They are
  **location-dependent** and break when *either* the target moves (entity re-home, model-project
  rename) *or* the document moves (doc re-home, doc-collection rename, the migration's depth change).
  Diagram `!include` paths are likewise relative (covered by the Phase-1 include-base helper).

**Decision — keep relative-path links (rewrite on move) + id-fallback resilience.** The relative path
is a *deliberate, valuable* design: links are traversable in git/GitHub, verifiable on a bare checkout
(no registry needed), human-readable, and consistent with the system's broader readable-reference
philosophy (slug directories/filenames, slug-bearing IDs, friendly diagram refs). ID-ifying them
(*rejected*) would sacrifice git traversability and make documents the lone opaque-reference outlier.
The fragility is **bounded to explicit move operations** that already run through the staged
transaction, so:
- Every file-moving op — **migration, project/collection rename, re-home** — recomputes the affected
  links (`relpath(target_new, doc_dir_new)`, inbound *and* outbound) and verifies **W155/E155 clean**
  before commit. The transform is deterministic (old→new paths are known).
- **ID-fallback resilience:** the link's basename already *is* the artifact id (`…/REQ@….md`). The
  verifier resolves the relative path first; on a miss it falls back to the embedded id via the
  registry and emits a **warning + auto-fix suggestion** rather than a hard E155 — a missed rewrite
  degrades gracefully instead of breaking the build.

**Scope note:** grouping operations change *paths only*, never an entity's slug or id — so the only
reference form they endanger is the document relative-path (handled above). The slug embedded in
diagram/ID references (a separate, intentional readability trade-off) is untouched by grouping; its
staleness is a pre-existing entity-*rename* concern, out of scope here.

---

## 5. Key Decisions

- **Path-semantics migration first** — lock the layout (§2.1), route all code through path helpers
  (Phase 1), then move files (Phase 2).
- **Directory-based, derived not authored** — membership is the folder; `group` is derived.
- **Three independent axes**; family-specific placement (model wraps `model/`; collections insert
  below `diagrams/`/`rendered/` and below the doc-type subdir). Grouping never constrains
  search/selection/linking.
- **Slug = readable directory locator; stable `id` = identity** for promotion/conflict (hybrid).
- **`groups.yaml` from day one, schema-validated, inside the staged transaction.**
- **`uncategorized` is the uniform fallback**; migration adds an engagement-named model-project as the
  default-selected starter.
- **Single `group` filter, single-family-scoped** on mixed queries (else error).
- **Typed confirmation** for destructive/non-empty ops; **cascade delete is two-stage (preview) and
  deferred** to Phase 9; docs **block by default**.
- **MCP + REST + GUI** surface; **CLI out of scope**.
- **No `_shared`/auto-reassign** — re-home first to keep elements; delete then cleans foreign edges.
- **Reference encoding (§4.6):** connections & diagram bindings are by-ID (move-safe). **Document
  links stay relative paths** — kept for git traversability / bare-checkout verifiability /
  readability — rewritten on every move (migration/rename/re-home), with a verifier **id-fallback**
  for resilience. Grouping changes paths only, never slugs/ids.

---

## 6. Phases, Tasks & Acceptance Criteria

> Delivered as **small cohesive PRs per phase** (the <350-line limit is a per-*file* standard, not a
> per-change cap). Each phase is independently shippable; navigability (P0–P7) ships before the
> deferred cascade (P9).

### Phase 0 — Domain & Registry Foundations
- **T0.1** `Group` value type + `GroupRegistry` (`id`, `slug`, `name`, `description`, `order`,
  `archived`, model-only `default`) in `src/domain/` (pure).
- **T0.2** `GroupRegistry` loader + `groups.schema.json` validation in `src/application/`; tolerant of
  missing file/sections (synthesise `uncategorized` + engagement-named model default).
- **T0.3** Add `group: str` to the four record dataclasses (`src/domain/artifact_types.py`).

**Acceptance:** registry loads & validates (present/absent → sensible defaults); `ruff` + `zuban check`
clean; touched files < 350 lines.

### Phase 1 — Path Semantics Abstraction (no file moves) 🔴
**Goal:** make every fixed-root assumption explicit and centralised *before* moving anything.
- **T1.1** Define helper APIs in `src/application/`: `model_roots(repo)`, `diagram_source_roots(repo)`,
  `rendered_path_for(diagram)`, `docs_roots(repo)`, `repo_root_for_artifact_path(path)`, include-base
  resolution, and family-aware `group_fn(path)`.
- **T1.2** Route **all** existing call-sites through the helpers: verifier (replace `path.parents[n]`
  model-root logic), writer/staged-transaction, renderer + `!include` resolution, promotion, GUI
  servers, file watcher, sync.
- **T1.3** Helpers accept **both** legacy and target layouts (transitional).
- **T1.4** Implement the **document-link helpers (§4.6)**: a deterministic relative-link rewriter
  (used by migration/rename/re-home) and a verifier **id-fallback** resolver (path first; embedded-id
  via registry on miss → warning + auto-fix suggestion).

**Acceptance:** with helpers in place but **no files moved**, the full suite + `verify` + a render pass
are green (pure refactor, zero behaviour change); a grep shows no remaining ad-hoc model-root/path-depth
derivation outside the helpers.

### Phase 2 — Storage Migration & Walker 🔴
- **T2.1** Migration command (per repo, idempotent) moving content into the §2.1 layout; seed
  `groups.yaml` with `id`s; create the engagement-named model-project + `uncategorized` folders.
- **T2.2** Indexing loader enumerates group roots per family via the helpers and tags `group`.

**Acceptance:** post-migration full-repo `verify` **clean (incl. W155/E155 — all document links
resolve, rewritten per §4.6)**; a **render** pass reproduces all diagrams (includes resolve); `stats`
counts **identical** before/after; `git revert` restores prior layout with clean `verify` + render
(rollback proven, incl. partial-failure rollback).

### Phase 3 — Index & Query Layer
- **T3.1** `group` column + index on all four record tables (`_sqlite_schema.py` + DuckDB equiv per
  §4.3); populate via `group_fn` on upsert.
- **T3.2** `group` on `_mem_store` records.
- **T3.3** Optional `group` on `ArtifactStorePort.list_*`; on mixed/unified queries it is honored only
  when scoped to one record family (else a typed error).
- **T3.4** `group_by='group'` (per-kind bucketing) on stats.

**Acceptance:** `list_*(group="X")` returns only that family's group members; mixed query + `group`
without single-family scope → clear error; search otherwise unchanged.

### Phase 4 — Read Surface (REST + MCP)
- **T4.1** Optional `group` on list/search REST endpoints (entities + siblings).
- **T4.2** Optional `group` on `artifact_query_list_artifacts` / `…_search_artifacts` (mirror `domain`;
  enforce single-family scoping; one-line description add).
- **T4.3** `'group'` added to `artifact_query_stats` `group_by` (enumeration/counts; **no new read
  tool**).

**Acceptance:** REST + MCP filter by group; stats enumerates groups with counts; read-tool count
unchanged; descriptions concise.

### Phase 5 — Create-Time Assignment & Re-home
- **T5.1** Optional `group` on `create_entity`/`create_diagram`/`create_document` (REST + MCP), default
  = family default/uncategorized; destination path via helpers.
- **T5.2** `add_connection`: no param — group derived from source.
- **T5.3** Optional `group` on `edit_*` = **re-home** (single-file `git mv`, same domain/type or
  doc-type subdir, ID unchanged); **maintain inbound/outbound document links per §4.6** in the same
  staged transaction.
- **T5.4** Target-group validation per §2.3 (registered or existing folder = valid; truly unknown =
  reject with create guidance); GUI passes its client-side current group explicitly.

**Acceptance:** create/`group="X"` writes under `X`; re-home moves the file and re-derives `group` with
**`verify` clean (incl. W155/E155 — document links maintained per §4.6)**; cross-group connection
inherits its source's group.

### Phase 6 — Group Lifecycle (safe ops) `artifact_group` 🔴
**Scope:** create / rename / archive / unarchive, plus **collection delete** — *not* model-project
cascade (deferred to P9).
- **T6.1** `artifact_group(kind, action, target=None, name=None, confirm=None)`; `confirm` = typed slug
  for gated ops.
  - `create` — register (allocate `id`) + lazily create the folder.
  - `rename` — display-name = registry edit; **slug = atomic subtree `git mv` + registry slug + reindex**
    (`id` stable); **maintain document links per §4.6** — both those *inside* a renamed doc-collection
    (their depth changed) and those *pointing into* a renamed model-project (the `<slug>` segment
    changed).
  - `archive`/`unarchive` — registry flag; `archive` of a non-empty collection needs the typed slug.
  - `delete` (**collection only** here) — remove folder + its diagrams/documents; typed slug when
    non-empty.
- **T6.2** All of the above run through the staged transaction incl. `.arch-repo/groups.yaml`
  (verify-before-commit, atomic).
- **T6.3** Emit SSE events for each op.

**Acceptance:** rename (both modes), archive/unarchive, collection delete all leave `verify` clean and
the registry consistent (no half-states); archived groups absent from default pickers but still resolve
as link targets; exactly **one** new write tool; ≤5 params; concise description; tests cover
git-sync-during-rename and watcher behaviour.

### Phase 7 — Frontend (Browse / Diagram / Document)
- **T7.1** ✅ Done — Per-area group selector (`GroupSelector.vue`), counts, archived-visibility toggle.
- **T7.2** ✅ Done — `group` threaded through `HttpModelRepository.ts`, schemas updated.
- **T7.3** ✅ Done — Group-management REST + UI. **Decision: GUI uses REST (not MCP direct).**
  - **T7.3.1** Add REST endpoints for group lifecycle: `POST /api/group` (create), `PUT /api/group`
    (rename — display-name or slug), `POST /api/group/archive`, `POST /api/group/unarchive`,
    `DELETE /api/group` (collection delete with `confirm` query param). All delegate to `group_op()`.
    Respects `is_read_only()` / `is_admin_mode()` guards. Same error-shape as other write endpoints.
  - **T7.3.2** `GroupSelector.vue` — add a `"+"` pill that opens a **Create Group dialog** (slug
    + display name; slug auto-derived from name, editable; validate unique). On submit: `POST /api/group`.
  - **T7.3.3** Per-pill context menu (⋯ button, visible on hover): **Rename** (display-name only;
    slug rename deferred — high risk), **Archive / Unarchive**, **Delete** (collections only; typed
    confirm input inline). Each calls the matching REST endpoint. Model-project delete renders a
    disabled menu item labelled "Delete (use cascade delete)".
  - **T7.3.4** Group badges in entity/diagram/document list rows: small chip showing the group slug
    (can be a `RouterLink` that sets the group filter). Only shown when more than one group exists.
  - **T7.3.5** Empty-state in each area when active group has no items: show the group name +
    "No [entities / diagrams / documents] in this group yet." (no "move here" action needed — re-home
    is an edit_entity operation, accessible from the entity detail).
  - **SSE refresh** ✅ Done (T7.4) — `artifact_write_completed` already triggers `load()` in
    `EntitiesView.vue`; extend to `DiagramsView` and document view when T7.3 REST endpoints land.
- **T7.4** ✅ Done — `EntitiesView.vue` SSE listener.

**Acceptance:** group create/rename/archive/delete all round-trip through REST and update the selector
live; badges visible when multiple groups exist; empty states are informative; `npm run lint` +
`npm run typecheck` clean; read-only mode disables management actions.

### Phase 8 — Group-Aware Promotion
**Goal:** user explicitly maps engagement model-projects to enterprise groups during promotion;
promotion transaction is atomic across entities, connections, and groups.yaml on both tiers.

**Decisions (locked):**
- The user chooses, for each engagement model-project that has selected entities, whether to **map to
  an existing enterprise group** (pick from a list) or **create a new enterprise group matching the
  source** (slug + name copied, fresh `id` allocated). This is an explicit UI step, never silent.
- The resulting group-mapping forms part of the **promotion plan** reviewed before apply.
- **Conflict rule**: same slug / different `id` on the enterprise side → surface in the existing
  conflict-resolution dialog as a "group conflict" (accept = use existing, merge = remap engagement
  id → enterprise id). Same `id` → reuse silently. Neither → create as new.
- Promotion transaction applies atomically: entity files, connection files, and `.arch-repo/groups.yaml`
  updates on the enterprise side (add/update group entries) are all staged together and verify-before-commit.
- The GRF proxy created on the engagement side by a promotion **inherits the source entity's
  model-project** (path-derivation gives this for free since the proxy lands next to the original).

**Tasks:**
- **T8.1** Extend `planPromotion` response to include a `group_mapping` section: for each unique
  engagement model-project slug in the selected entity set, return the match status
  (`matched_by_id`, `matched_by_slug`, `conflict`, or `new`) and the candidate enterprise group info.
- **T8.2** Extend the promotion-plan UI step (before the conflict-resolution dialog, or as a new
  tab/section within it): show the group-mapping table; user can change the mapping for each
  engagement project (dropdown: existing enterprise groups + "Create new"). The mapping is submitted
  as part of `executePromotion`.
- **T8.3** `executePromotion` reads the resolved group-mapping and, within the existing staged
  transaction: (a) updates the enterprise `groups.yaml` (add new groups / no-op for matched ones /
  error-out if a conflict was not resolved); (b) places promoted entities under the correct enterprise
  `projects/<slug>/model/...` path.
- **T8.4** Coherence check: the overall promotion flow (plan → review conflicts → review group-mapping
  → execute) must read as a single coherent process. Prefer integrating group-mapping into the
  existing `PromotionPlanSchema` / `PromotionResultSchema` rather than adding new round-trips.

**Acceptance:** (a) same slug/same `id` → silent reuse; (b) same slug/different `id` → surfaced in
conflict dialog, user resolves; (c) renamed engagement group (stable `id`) → matched by `id`, correct
enterprise group; (d) multi-project batch → all groups resolved in one execute call; (e) promotion is
atomic and `verify`-clean on both tiers; (f) flow is coherent — no extra dialogs or prompts beyond
what the existing promote UI already shows.

### Phase 9 — Model-Project Cascade Delete (deferred, riskiest) 🔴

**Decisions (locked):**
- **Two-stage via `dry_run` flag** (consistent with `create_entity`, `edit_entity`): `artifact_group(
  kind='model-project', action='delete', target='<slug>', confirm='<slug>', dry_run=True)` returns
  the full impact report without mutating anything. Same call with `dry_run=False` executes. The
  `confirm` field must always equal `target` (typed-slug gate applies in both dry and live modes).
- **Diagram element removal**: use the same mechanism as `artifact_edit_diagram` — remove the entity
  (and any of its connections) from the diagram's `entity-ids-used` / `connection-ids-used` frontmatter
  lists, then regenerate the PUML body via `_render_diagram_entities_puml()`. This is full regeneration
  consistent with the current diagram-editing approach. Note: once the PUML-editing plan ships (editable
  bodies), this will need revisiting — cascade delete will need surgical removal to preserve
  customisations. Tracked as a follow-up dependency on `PLAN-diagram-puml-editing.md`.
- **Foreign document handling**: block-by-default. The dry-run report includes the blocking documents
  (title, path, and the specific links that would break), so the user can resolve them manually before
  retrying the delete.
- **Report format**: both dry and live runs return a structured report with artifact names, IDs, and
  links, e.g.:
  ```json
  {
    "project": "my-project",
    "dry_run": true,
    "owned": { "entities": [{"id":"…","name":"…","path":"…"}], "connections": [...] },
    "foreign": {
      "connections": [{"id":"…","source":"…","target":"…"}],
      "diagrams": [{"id":"…","name":"…","path":"…","entities_removed":["…"],"connections_removed":["…"],"puml_customised":true}],
      "documents_blocking": [{"id":"…","title":"…","path":"…","broken_links":["…"]}]
    },
    "apply_blocked_by": ["DOC@….md", "…"]
  }
  ```
  Live run (`dry_run=False`) is rejected if `apply_blocked_by` would be non-empty.

**Tasks:**
- **T9.1** Implement `_cascade_preflight(repo_root, project_slug)` → returns the report dict above.
  Compute: all entities in `projects/<slug>/model/`, all their outgoing connections, all connections
  with either endpoint in the project, all diagrams with any entity from the project in
  `entity-ids-used`, all documents with any relative link resolving to an entity in the project.
- **T9.2** Implement `_cascade_apply(repo_root, project_slug, preflight_report)` (only called when
  `apply_blocked_by` is empty):
  - Delete owned entity files + their `.outgoing.md` connection files.
  - Delete foreign standalone connection files (`.outgoing.md` referencing deleted entities).
  - For each affected diagram: call the same entity-list update + `_render_diagram_entities_puml()`
    path used by `artifact_edit_diagram`. Stage via git. **Include a warning in the apply result**
    for every diagram that had a non-empty, non-derived PUML body before regeneration (i.e. detect
    whether the existing body differs from a fresh derivation); once the PUML-editing plan ships,
    users may have customised bodies that this operation would silently discard. The warning text:
    "PUML body of diagram '<name>' was regenerated; any manual customisations have been replaced."
  - Update `groups.yaml` (remove the project entry). Stage via git.
  - Run full-repo `verify`; roll back and raise if any errors.
  - Commit atomically.
- **T9.3** Wire `artifact_group(kind='model-project', action='delete', dry_run=…)` to dispatch to
  `_cascade_preflight` or `_cascade_apply` based on `dry_run`.
- **T9.4** (Coherence) Ensure the preflight report is human-friendly: entity/diagram names, not just
  IDs; relative paths rendered as repo-root-relative links (e.g. `model/domain/type/ENT@….md`).

**Acceptance:** dry-run returns an accurate report (owned counts, foreign connection count, diagram
names, blocking document list); apply with no blocking documents leaves a `verify`-clean repo (zero
dangling refs, valid diagram syntax, doc link-rules satisfied); apply is rejected when blocking
documents exist and `dry_run=False`; rollback is clean on partial failure; large project (100+
entities) completes in a single staged transaction.

### Phase 10/11 — Self-Describing Model, Meta-Ontology Alignment & Documentation
**Deliver as part of P9 completion, not a standalone phase.**

- **T10.1** Using MCP authoring tools (`artifact_create_entity`, `artifact_add_connection`), model the
  grouping concept in the architecture repo: create entities for the three axes (model-project,
  diagram-collection, document-collection) as `application-function` or `application-service` types
  (confirm against meta-ontology v2); connect them to existing capability / goal entities (e.g. the
  "Plan Collaboratively" goal `GOL@…Lm2Bn2` and "Maintain Coherence" `GOL@…Po1Qw3`).
- **T10.2** Add/link a requirement for "Independent artifact grouping" under motivation.
- **T11.1** Update `README.md`: canonical layout diagram (§2.1 paths), per-area filters, the
  `artifact_group` tool (all ops), `group` param on create/edit tools, migration command, and the
  explicit CLI-out-of-scope statement.

**Acceptance:** authored via tools; `verify` clean; README matches shipped behaviour; no manual edits
to model files.

---

## 7. Tooling / Surface Rationale (MCP context discipline)

- **One** new write tool, `artifact_group`, covers all axes × the lifecycle via `kind` × `action`
  (vs. 3×5 = 15 tools); the destructive `delete` path is gated inside it (typed `confirm` +
  preflight/preview), cascade semantics selected by `kind`.
- **Zero** new read tools: filtering reuses a `group` param (single-family-scoped on mixed queries —
  the chosen resolution to the ambiguity, preferred over three axis-specific params for surface
  economy); enumeration reuses `artifact_query_stats(group_by='group')`.
- **Assignment & re-home ride the create/edit tools** (one optional `group` param each; connections
  derive it), keeping `artifact_group` strictly about groups-as-containers.

Net delta: **+1 write tool, +1 optional `group` param on three create + three edit + two read tools,
+1 `group_by` value.**

---

## 8. Traceability (stories ↔ phases)

| Story | Phases |
|---|---|
| US-1 model-project | P0, P6 |
| US-2 independent collections | P0, P2, P6 |
| US-3 create-into | P5.1–5.2 |
| US-4 navigate-by | P3, P4, P7 |
| US-5 link-freely | P3 (filter≠constraint), P5.2 |
| US-6 rename | P6.1, §4.2 |
| US-7 re-home | P5.3, §4.2 |
| US-8 archive | P6.1 |
| US-9 collection delete | P6.1, §4.1 |
| US-10 group-aware promotion | P8 |
| US-11 model-project cascade delete | P9, §4.2 |
| US-12 migration-safe | P1, P2, §4.3, §4.5 |

---

## 9. Definition of Done

- All phase acceptance criteria met; full-repo `verify` (**incl. document-link rules W155/E155**)
  **and a render pass** clean in every state (post-helpers, -migration, -create, -rehome, -rename,
  -archive, -collection-delete, -promotion, -cascade-delete).
- Migration reversible (`git revert` proven, incl. partial-failure rollback); counts invariant.
- Path-helper refactor (Phase 1) leaves no ad-hoc model-root/path-depth logic outside the helpers.
- MCP surface delta limited to §7; descriptions concise; CLI scope stated.
- Operational test matrix (§4.5) covered.
- `ruff`, `zuban check`, frontend `lint`/`typecheck` clean; per-*file* < 350 lines; delivered as small
  cohesive PRs; new model content authored via tools.
- README + self-describing model updated and aligned with meta-ontology v2.
- All 🔴 concerns (§4) closed; key decisions (§5) honoured.
