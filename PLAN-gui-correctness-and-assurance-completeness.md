# PLAN — GUI Correctness, Attribute Typing, Diagram UX & Assurance Feature-Completeness

Status: draft · Mode: [PLAN] (with embedded [DESIGN] decisions, flagged inline)

This plan remediates eleven reported problem areas spanning the Vue GUI, the Python backend
(search/index, schema validation, document specs, C4 & datatype diagram types) and the
assurance capability. Each work unit (WU) records the **symptom**, the **confirmed root cause**
(with `file:line` evidence), the **fix design**, an **actionable checklist**, and **tests**.

Verification legend: **[OBS]** = reproduced/confirmed by observation this session ·
**[CODE]** = confirmed by reading the implicated code · **[HYP]** = strong hypothesis, must be
reproduced before coding.

---

## 0. Cross-cutting concerns (apply to every WU)

- **Authn/authz is explicitly OUT OF SCOPE (product decision).** This is an internal tool on
  trusted systems, accessed only by trusted people over localhost, with no authentication planned
  for the near future. We do **not** add user accounts, roles, RBAC, CSRF tokens, or a per-user
  authorization model in this plan. The single gate for assurance is the store's **unlocked**
  state. **Supported deployment boundary (precise):** the server's **default bind is loopback**;
  non-loopback binding is supported **only behind an authenticated/restricted reverse proxy or
  equivalent intranet perimeter control**; direct public or unrestricted-LAN binding is
  **unsupported**. Non-loopback binding requires an **explicit opt-in flag** and emits a **startup
  warning**. This defers application-level auth without leaving deployment behaviour ambiguous; if
  the perimeter assumption changes, app auth/CSRF/transport must be revisited.
- 🔴 **Assurance confidentiality is a *feature-correctness* concern, not access control.** The
  store is TLP-classified *by design*; the point of the feature is that classified content stays
  within its ceiling. Today that enforcement is **incomplete** (edge reads don't filter on endpoint
  TLP; stats/verification/completeness/search can leak counts, IDs, names above the ceiling; some
  signal writes — BOM/vuln/anchor — neither check the unlocked state nor append to the audit log).
  So we do NOT "reuse as-is"; we **complete** it via a single application-layer
  **AssuranceExposurePolicy** used by *both* MCP and HTTP, applied uniformly to nodes, edges,
  aggregates, verification findings, search results, and existence/error responses. Responses must
  distinguish **locked (`423`)**, **forbidden-by-classification (`403`/omit)**, and **genuinely
  empty** — never conflate them, since a silent empty result misleads analysis. Negative tests must
  prove names/IDs/edge-topology/counts/snippets above the ceiling cannot leak.
- 🔴 **Confidentiality (search index).** Assurance content must never be written into the
  architecture search index on disk. Whether assurance search uses direct filtered store queries or
  an ephemeral in-memory index is decided by benchmark (WU-G3); if an index is used it is built on
  unlock, disposed on lock, never persisted in plaintext, and responses carry no-store headers with
  redacted telemetry.
- 🔴 **Data integrity.** Attribute-validation WUs change what writes are accepted. All model
  writes continue to go through the existing MCP/write path and verifier; we tighten validation,
  we do not add a second write path (per `CLAUDE.md` "principled solution" rule).
- 🔴 **Typed-property persistence (decided).** Schema-declared property values are stored as
  **canonical lexical forms in the file** and decoded by consulting the attribute's **schema type**
  (user decision). There is exactly one representation; we do not add a parallel type sidecar for
  schema-declared attributes. (Ad-hoc attributes, which have no schema, carry a minimal declared
  type so they remain parseable — see WU-B5.) See the typed-property foundation (WU-B3).
- 🔴 **Self-model delta (every architectural WU).** This project models itself, so each WU that
  changes architecture (new HTTP interface, ephemeral search component, typed-property persistence,
  GSN renderer, new application-layer assurance use cases) carries a **model-impact acceptance
  criterion**: reuse/update the existing self-model element before creating a new one, and fix stale
  statements encountered (e.g. the "GUI Authoring Tool calls MCP tools" element vs. the README's
  "GUI uses REST"). See the Self-model section.
- 🟡 **Observability.** Startup schema-validation failures (WU-B1) and any assurance index build
  (WU-G3) must log clearly; assurance logs/telemetry must redact classified content. Search-path
  changes keep the existing scoring telemetry.
- **Quality gates (every commit):** Backend — `python -m pytest --tb=short -q` (0 fail) →
  `ruff check src/ tests/` (0, incl. E501) → `uv run zuban check`. Frontend (per README) —
  `npm run lint` → `npm run typecheck` → `npm run test` (Vitest), all green. Regenerate
  `types.generated.ts` after any ontology change.
- **No phase-name references in code/tests.** Use feature names (memory: no-phase-refs-in-code).

---

## For implementers — read this first (optimized for incremental, context-limited sessions)

**How to work this plan.** Pair it with `TASKS-gui-correctness-and-assurance.md` (the ledger). Each
session: (1) read the ledger (status table + Decision log); (2) pick the next **unblocked** WU;
(3) **read the plan freely** — §0, this orientation, the target WU's phase intro, the WU itself, and
any WU it depends on; (4) implement; (5) run the quality gates; (6) update the WU checklist here + the
ledger (status + a one-line progress-log entry).

**Ration codebase & self-model exploration, NOT plan reading.** The plan is curated, high-density
context — read whatever of it is relevant; that is cheap and prevents mistakes. The expensive,
unbounded cost is wandering the `src` tree or querying the ~340-entity self-model. Each WU already
cites the exact `file:line` and the model facts it needs: open a cited location **once** to confirm it
still matches, then act. Do **not** broad-grep the codebase, fan out across subsystems, or query the
self-model unless a WU explicitly says `[HYP] reproduce first` or `find/confirm` — and then scope the
search to exactly what is named. Re-deriving what the plan already states burns the budget that should
go into the change itself.

**Repo map (where things live).**
- Backend (Python, hexagonal): `src/{domain,application,infrastructure,diagram_types,ontologies,config}`.
  - Search/index: `src/infrastructure/artifact_index/`, `src/application/_artifact_search.py`,
    `src/application/artifact_scoring.py`.
  - Schema/validation/startup: `src/application/artifact_schema.py`,
    `src/application/verification/`, `src/application/startup_validation.py`.
  - HTTP API: `src/infrastructure/gui/routers/`. Diagram types: `src/diagram_types/<type>/`.
  - Assurance: `src/infrastructure/assurance/`, `src/infrastructure/mcp/assurance_mcp/`,
    `src/ontologies/assurance/`.
- Frontend (Vue 3, hexagonal): `tools/gui/src/{adapters,application,domain,ports,ui}` — views in
  `ui/views`, shared components in `ui/components`, diagram editors in `ui/diagram-types/<type>`,
  effect-schemas in `domain/schemas.ts`, HTTP client in `adapters/http`.
- Per-repo schemata: `<repo>/.arch-repo/schemata/attributes.<type>.schema.json`. Self-model:
  `engagements/ENG-ARCH-REPO/architecture-repository/`.

**Running things.** Backend: `python -m pytest --tb=short -q` · `ruff check src/ tests/` ·
`uv run zuban check` (needs `uv sync --all-groups` once). Frontend (in `tools/gui`): `npm run lint` ·
`npm run typecheck` · `npm run test`. Deps via `uv sync` (never pip). Dev GUI on localhost:5173 —
use the Playwright MCP for live UI checks. After ontology changes: `uv run tools/generate_types.py`.

**Model writes (critical).** All model/diagram/document/assurance writes go through MCP tools
(`artifact_*`, `assurance_*`) — never hand-edit model files. MCP tools run against a **long-running
backend**: code changes need a **backend restart** (the user performs it — ask), and MCP-surface
changes need a **Claude session restart**. If a tool is wrong, fix the tool, not its output.

**Hard rules.** Principled fix at the correct layer, never a workaround; after such a fix add a
regression test + a delegation/contract test. Python files ≤250 soft / 350 hard LoC (`.md` exempt).
"arch" naming (not "sdlc"); **no phase names in code/tests** (use feature names). Commit/push only
when asked; branch off `main` first. Each WU is done only when its checklist is ticked **and** all
quality gates pass.

---

## Phase A — Search & Browse correctness (highest impact / lowest cost)

### WU-A1 — Global search crashes the results page on any document hit  🔴 user-visible crash

**Symptom [OBS].** Pressing Enter in the search field renders a schema-error dump:
`Expected "entity" | "connection" | "diagram", actual "document"`.

**Root cause [OBS/CODE].** Two parallel result schemas exist in
`tools/gui/src/domain/schemas.ts`:
- `SearchHitSchema` (line 144–146): `record_type: Schema.Literal('entity','connection','diagram')`
  — **omits `'document'`** (and any assurance type). The global search box is wired to this one.
- `ArtifactSearchHitSchema` (line 230–243) already uses a proper `Schema.Union(...)`.

When the HTTP search returns a `document` hit, `@effect/schema` decode throws and the whole
results route dies.

**Fix design.**
1. Widen the search-hit `record_type` to a union covering **all searchable kinds**:
   `'entity' | 'connection' | 'diagram' | 'document'` now, plus an open-ended assurance discriminator
   added in WU-G3 (`'assurance-node' | 'assurance-edge'`). Prefer reusing/merging
   `ArtifactSearchHitSchema` so there is **one** search-hit schema, not two (root-cause: schema
   drift). Audit the two call sites and converge them.
2. **Per-hit decoding (not just an error boundary).** Today the whole `hits` array decodes as a
   single operation, so one unknown `record_type` fails the entire response — an outer `onError`
   alone would still drop *all* results. Decode hits **individually** (or normalize server-side to a
   known shape), so an unrecognized hit is skipped with a logged warning while the rest render.

**Checklist.**
- [x] Merge `SearchHitSchema` into `ArtifactSearchHitSchema` (single union schema); update
      `SearchResultSchema` + the search composable/view imports.
- [x] Add `record_type` members for assurance (wire-compatible placeholder now; consumed in WU-G3).
- [x] Decode hits per-item (skip+log unknowns); no full-page failure on a single bad hit.

**Tests.** Vitest: decode a fixture result containing entity+document+diagram hits → passes;
decode an unknown `record_type` → fallback path, no throw.

---

### WU-A2 — Documents (and diagrams) are unreachable via ranked search; `strict`/`include` ignored

**Symptom [OBS].** MCP `artifact_query_search_artifacts("coding guidelines")` returns **entities
only**; the `STD@…general-coding-guidelines` document (whose *title contains both query words*) is
never returned. Setting `include_record_types:["documents"]` + `strict_record_type:true` **still**
returns entities — the strict/include filter is ignored. This blocks the `CLAUDE.md` workflow that
tells agents to find the coding-guidelines doc.

**Root cause [CODE].** Ingestion is fine (documents *are* scanned, parsed
and upserted into `documents_fts`), and the include flags *are* threaded for connections/diagrams/
documents (`query_search_tools.py:68`, `_artifact_search.py:130`). The real defects are subtler:
1. `_include_flags()` has **no entity flag** — entities are *always* searched regardless of
   `include_record_types`, so an entity-only filter is impossible and entities always compete.
2. `strict_record_type` only filters when `prefer_record_type` is *also* supplied
   (`_artifact_search.py:181`) — so `strict_record_type:'document'` alone (as I tested) does nothing.
3. The in-memory scored path runs **only when FTS returns zero hits at all**
   (`_artifact_search.py:172`). Because entity FTS hits are plentiful, the fallback never fires, so
   document/diagram candidates that would have scored well are **suppressed** — exactly why the
   coding-guidelines doc never appeared.
4. `include_record_types`, `strict_record_type` and `prefer_record_type` have no well-defined
   relationship to each other.

**Fix design (redesign the search port).**
1. Replace the independent booleans + `strict`/`prefer` trio with one explicit
   `included_record_types: set[RecordType]` on the application port. Entities are just another member
   of the set (no special-casing). Define `strict` precisely or drop it in favour of the include set.
2. **Merge FTS and scored candidates per requested kind** rather than only falling back when the
   entire FTS result is empty — each requested kind contributes its best hits, then cross-kind
   ranking orders them.
3. Apply `limit` correctly relative to ranking: fetching only `limit × k` mixed FTS rows can
   **starve a minority kind** (e.g. one document among hundreds of entities) — test limiting both
   before and after cross-kind ranking.
4. Default include-set for *search* = all searchable kinds (entities, connections, diagrams,
   documents [+ assurance when unlocked, WU-G3]).
5. **Every search source must respect the include-set**. There are three sources — FTS,
   deterministic scoring, and the **semantic supplement** (which today injects entity hits
   independently). All three must accept and honour the same `included_record_types`, the same
   domain/type filters, and a shared **dedup** policy — otherwise a documents-only search can still
   receive a stray entity semantic hit. WU-A2 and WU-A3 share **one** canonical `RecordType`/
   included-kind abstraction rather than fixing search and list independently.

**Checklist.**
- [x] Add a failing test reproducing "search 'coding guidelines' → STD doc in top hits".
- [x] New `included_record_types` port (shared with A3); remove independent booleans; entity normal.
- [x] All three sources (FTS, scoring, semantic) honour include-set + domain/type filters + dedup.
- [x] Per-kind FTS+scored merge (not fallback-only-on-empty); cross-kind ranking.
- [x] Limit-vs-ranking test proving a minority kind is not starved.

**Tests.** Integration: corpus with 1 standard doc + N entities; assert doc ranks for its title
tokens even amid many entity hits; assert an explicit single-kind include returns only that kind
(**with semantic search enabled** — no stray entity hit); assert diagrams searchable; assert
minority-kind not starved by `limit`.

---

### WU-A3 — `list_artifacts` ignores `include_record_types` (always returns entities)

**Symptom [OBS].** `artifact_query_list_artifacts(include_record_types=["documents"])` returned
341 entities + 3 documents (344) — the documents-only filter was not honoured.

**Root cause [CODE].** `src/infrastructure/artifact_index/service.py:252-290`
unconditionally seeds the output with all matching entities, then *adds* other record types when
their include flag is set. Entities are hard-on.

**Fix design.** Make entity inclusion conditional on `'entities' ∈ include_record_types` (matching
the documented default of `('entities',)`), exactly like the other record types. Keep the documented
default behaviour for callers that pass nothing.

**Checklist.**
- [x] Gate the entity branch on the include-set.
- [x] Use the **same canonical `RecordType`/included-kind abstraction as WU-A2** (one definition for
      both list and search; don't fix them independently).
- [x] Regression test for each single-kind filter (entities-only, documents-only, diagrams-only,
      connections-only) and combinations.

---

### WU-A4 — Browse: changing ArchiMate domain leaves stale entity-type filter → empty list

**Symptom [reported].** In "Uncategorized", filter to an entity-type, then switch ArchiMate
domain → list empty, count 0, type filter still set (should reset to "All" for the new domain).

**Root cause [CODE].** `tools/gui/src/ui/views/EntitiesView.vue`: `typeFilter` is a local ref
(~line 39) not derived from the domain; `setDomain()` (~line 57) updates the route query but does
not clear `typeFilter`; the reload watcher (~line 104 on `[activeDomain, typeFilter]`) then sends
the stale `artifact_type` to a domain that has none → 0 results.

**Fix design.** On domain change, reset the entity-type filter to "All" (the honest default for a
freshly-selected domain). Implement as an explicit reset inside `setDomain()` (and/or a `watch`
on `activeDomain` that clears `typeFilter`), keeping query-param state consistent so back/forward
nav stays correct.

**Checklist.**
- [x] Reset `typeFilter` to '' on domain change; sync the route query.
- [x] Ensure the available-type dropdown re-derives from the new domain.

**Tests.** Vitest component test: set type filter in domain X, switch to Y → filter '', list
re-queried for Y with no `artifact_type`.

---

## Phase B — Entity attribute typing & validation (backend + frontend + self-model)

Context [CODE]: schemata are JSON-Schema Draft-2020-12 under each repo's `.arch-repo/schemata/`
(`attributes.<type>.schema.json`). They are loaded lazily/cached
(`src/application/artifact_schema.py`), validated only as **non-blocking warnings (W042)** post-write
(`src/application/verification/_verifier_rules_schema.py:47-91`). The frontend renders **plain text
inputs** for every attribute regardless of type/enum/constraints
(`EntityDetailView.vue` ~430-459, `EntityCreateView.vue` ~246-278); free attributes are
string-only. The schema endpoint `GET /api/entity-schemata` already returns `{schema, properties,
required}` (`src/infrastructure/gui/routers/entities.py:117-136`).

### WU-B1 — Repository authoring policy: createability + valid defaults

**Framing.** "Every required attribute must define a default" is *not* schema
completeness — in JSON Schema `required` and `default` are independent, and validators do not apply
defaults. Stating it as a hard schema invariant, and *mechanically* deriving defaults (first enum
member, `0`/`false`/`""`/`[]`), fabricates domain meaning. So we reframe to a **repository authoring
policy** that validates *createability* while keeping the user's "works-by-default + fail loudly"
intent.

**Fix design.** In `src/application/startup_validation.py` (alongside `validate_repo_compatibility`,
after `_unknown_schema_errors` ~258-271), for **every configured repo**:
- **Always fail-hard** on *invalid schema syntax* and on any *declared `default` that does not
  validate against its own property schema* (a real correctness bug).
- `required_defaults_policy: strict` ⇒ **every required property must have a valid declared
  default** (fail-hard otherwise). `non-strict` ⇒ required properties may instead be supplied by the
  caller at create time (no startup failure). Startup does not try to predict caller behaviour — it
  only enforces the chosen policy. We set `strict` for this project's repos.
- **GUI createability is verified separately** (not at startup): a test ensures each type's create
  form can collect every required property. That is the honest meaning of "createable" — startup
  cannot know what a future caller will supply.
- The startup message lists findings per schema file; derived suggestions are *guidance*, not applied.

**Config location.** `required_defaults_policy` lives in the repo-local `.arch-repo` config (where
repo settings already live). Add its key to that config's **schema + parser** *and* the **repository
template**, so new repos inherit a defined value — default `non-strict` to avoid surprising
third-party repos. Enumerate configured repos via the repository's `repo_roots`.

**Checklist.**
- [x] Validate schema syntax + declared-default validity (always fail-hard).
- [x] `required_defaults_policy` key: `.arch-repo` config schema + parser + repo template; default
      `non-strict`.
- [x] strict ⇒ required-without-default fails; non-strict ⇒ finding only.
- [x] Separate GUI-createability test (create form collects every required property).
- [x] Unit tests: invalid declared default → fail; strict + missing default → fail; non-strict → ok.

**🔴 Migration note.** Current schemata trip the strict policy (see WU-B2); WU-B2 ships with B1 so
the repos boot. WU-B2 also covers the **repository-template schemata** (the source copied into new
repos), not just the three live copies — otherwise every new repo reintroduces the problem.

---

### WU-B2 — Remediate existing schemata — *an architectural-planning decision, not implementation*

The user directed: decide per attribute whether to **keep required (with a sound default)** or
**make non-required**, judged by *consequences for architectural planning*. Current required-without-
default attributes (identical across ENG-ARCH-REPO, u2p-enterprise, TECHNOLOGY_ARCHITECTURE):

| Type | Attribute | Kind | Disposition | Rationale (planning consequence) |
|------|-----------|------|-------------|----------------------------------|
| goal | Priority | enum MoSCoW | **non-required** | Prioritisation is a deliberate act; a silent default fakes a triage decision and corrupts roadmap reads. Absence = "not yet prioritised" (honest). |
| goal | Measurability | free text | **non-required** | Qualitative guidance; an empty-string "default" is not real content. Surface as *recommended* in UI, not mandatory. |
| principle | Priority | enum MoSCoW | **non-required** | Same as goal.Priority. |
| principle | Rationale | free text | **non-required** | A principle without rationale is weak but still a valid model node; don't fake it. |
| requirement | Priority | enum MoSCoW+Never | **non-required** | Same as goal.Priority. |
| requirement | Category | free text | **non-required** | Free-text taxonomy; empty default meaningless. |
| driver | Category | enum | **keep required; add a genuine `"Unspecified"` enum member and default to it** | Enum with controlled vocab; an explicit `"Unspecified"` member is an honest "not yet classified" value, so the default means what it says (decisive — matches the net-effect below). |
| driver | Source | free text | **non-required** | Provenance note; recommended not mandatory. |
| stakeholder | Category | free text | **non-required** | Free-text; see requirement.Category. |
| stakeholder | Concerns | free text | **non-required** | Qualitative; recommended not mandatory. |
| capability | Maturity | enum CMMI-like | **keep required; add a genuine `"Not Assessed"` enum member and default to it** | "Initial" is a real maturity level, *not* the absence of judgement. Add an explicit domain member so the default means what it says. |

**Net effect:** the invariant is satisfied chiefly by *relaxing requiredness for qualitative/judgement
fields* (honest absence > fabricated value), keeping `required` only where we add a **genuine domain
member** to default to (`capability.Maturity → "Not Assessed"`; `driver.Category → "Unspecified"`).
Every declared default must itself validate against its property schema (enforced by WU-B1). This is
the architecturally honest reading of "works-by-default", avoiding arbitrary mechanical defaults.

**Decision (settled).** The table is the agreed disposition: the two classification enums
(`capability.Maturity` → add `"Not Assessed"`; `driver.Category` → add `"Unspecified"`) stay
**required** with that genuine member as default; all other listed attributes become **optional**.

**Checklist.**
- [x] Apply dispositions to all three live repos' schemata **and the repository-template schemata**
      (move attrs out of `required[]`, or add the genuine enum member + default). Keep all copies
      consistent. → 18 JSON files + `engagement_repo_template.py`
- [x] Confirm each declared default validates against its property schema.
      → `"Not Assessed"` ∈ capability.Maturity enum; `"Unspecified"` ∈ driver.Category enum.
- [x] Re-run model verification; confirm no new W042 noise and boot succeeds under strict policy.
      → 0 W042 / 0 E042 across GOL/PRI/REQ/STK/CAP/DRV entities in ENG-ARCH-REPO.

---

### WU-B3 — Typed-property foundation (FOUNDATIONAL — B4/B5 land on this)

**Framing.** B3–B5 cannot be "mostly UI/schema": property values are
**string-valued end-to-end** — REST accepts `dict[str, str]` (`routers/entities.py:139`), the
formatter writes Markdown table *cells* (`artifact_write_formatting.py:72`), the verifier reparses
every cell as a string (`_verifier_rules_schema.py:94`). So a JSON-Schema `boolean`/`integer`/
`array` declaration cannot validate after the value has been serialized and reparsed, and making
validation blocking (old B4) would *reject correctly entered typed values*. This is one architectural
change, not three UI tweaks.

**Decision [user].** Files store the **canonical lexical form** of each value; readers **parse using
the attribute's schema type**. One representation, no parallel type sidecar for schema-declared
attributes.

**Fix design — single typed-property design, delivered before any blocking validation.**
1. Define a **canonical typed-property value model** (an ADT: string / integer / number / boolean /
   array-of-scalar / enum) and a **canonical lexical grammar** for each (how it is written in a
   Markdown cell and unambiguously parsed back, given the schema type).
2. Decode lexical cells **using schema metadata**; for ad-hoc attributes with no schema, carry a
   minimal declared type so the lexical form remains parseable (the only place a type is recorded
   outside the schema — see WU-B5).
3. Extend the ports and DTOs from `dict[str, str]` to the typed model across **every reader and
   writer**: parser, formatter, REST, MCP, GUI, verification, promotion, repository templates, and
   the search index ingestion.
4. Specify **migration & backward-compatibility** for existing entities (existing string cells must
   continue to read; canonical re-emission on next write).
5. **Only then** promote schema validation from warning (W042) to a blocking error on the
   typed/required/enum/constraint dimensions at the write boundary.

**Supported-schema subset (bound the scope).** Do NOT attempt arbitrary JSON Schema.
Initial supported set:
- scalars `string`, `integer`, `number`, `boolean`; string-backed `enum`; optionally a
  **homogeneous scalar array**.
- constraints per type: string `pattern`/`minLength`/`maxLength`; numeric `minimum`/`maximum`; enum
  membership.
- **Markdown-cell escaping is part of the grammar**: define escaping for `|` (cell separator), `\`,
  and newlines; arrays use **canonical JSON** as their lexical form.
- **Explicitly defer** `null`, object-valued properties, unions/`oneOf`/`anyOf`, nested arrays — a
  schema using them is a startup finding, not a silent partial.

**[DESIGN — spike first].** A short architecture spike produces the value model + lexical grammar
(incl. escaping) + the supported subset + the migration decision, reviewed before implementation. On
the critical path for B4/B5.

**Checklist.**
- [x] Typed-property value ADT + canonical lexical grammar **incl. cell-escaping + canonical-JSON
      arrays**; supported subset documented; unsupported constructs flagged at startup.
      → `src/domain/property_value.py` (spike, 87 tests); OQ-2 reviewed + approved.
- [x] Schema-driven decode; ad-hoc minimal-type carrier defined.
      → `decode_lenient`/`get_adhoc_type` in property_value.py; `attribute-types` frontmatter key.
- [x] Port/DTO change from `dict[str,str]` across parser/formatter/REST/MCP/GUI/verify/promotion/
      templates/index. → 10 files; `as_optional_typed_dict`; `MergedFields.attribute_types`.
- [x] Migration + compatibility for existing entities; canonical re-emission.
      → `decode_lenient` never raises; returns raw string on parse failure.
- [x] Blocking validation switched on *after* the above.
      → E042 ERROR on decode failure; W042 WARNING on constraint violation (verifier).

**Tests.** Round-trip every scalar kind through file→parse→validate→re-emit (canonical-stable);
legacy string cells still read; out-of-enum/out-of-range rejected only after foundation lands.

---

### WU-B4 — Typed attribute editor (render by type; enforce constraints) — depends on WU-B3

**Fix design.** With B3 in place, replace the plain text inputs in `EntityDetailView.vue` /
`EntityCreateView.vue` with a control chosen by attribute schema type:
- enum → `<select>` (current/default preselected) · boolean → checkbox/toggle
- integer/number → numeric input with `min`/`max`/`step` · string → text (`pattern`/length)
- array → tag/list editor
Required attributes are marked and block save when empty (no value AND no default). Defaults
pre-populate on create. Messages mirror the JSON-Schema constraints. Server-side blocking validation
(from B3) is the source of truth; the client mirrors it for UX.

Schema endpoint enrichment (folded in from old B3): confirm `GET /api/entity-schemata` /
`EntitySchemaInfo` (`schemas.ts:546-552`) exposes structured per-attribute descriptors
(`{type, enum?, default?, constraints?}`), extending it if it currently projects `properties:
string[]`.

**Checklist.**
- [x] Structured `EntitySchemaInfo`; endpoint passes through type/enum/default/constraints.
- [x] Control-by-type renderer shared by detail & create views.
- [x] Client mirrors server validation (required/enum/range/pattern); defaults on create.

**Tests.** Vitest: enum renders select; number rejects non-numeric; required blocks save.

---

### WU-B5 — Free (ad-hoc) attributes: scalar type selection — on the WU-B3 model

**Fix design.** Adding an attribute not in the schema presents a **type selector** over the scalar
kinds in the B3 value model (`string | number | integer | boolean`, array-of-scalar as a stretch).
Since there is no schema to decode against, the ad-hoc attribute records its **declared type** via
the minimal carrier defined in B3 (the single sanctioned place a type lives outside a schema) so the
canonical lexical value round-trips. No second write path; the formatter/parser from B3 handle it.

**Checklist.**
- [x] Type selector on add-attribute (B3 scalar kinds).
- [x] Ad-hoc declared-type carrier (per B3) round-trips the canonical value.
- [x] Backend coerces/validates ad-hoc value against its declared type.

**Tests.** Round-trip: ad-hoc boolean `true` reads back boolean; numeric ad-hoc rejects text.

---

### WU-B6 — Self-model update (proportional; see cross-cutting self-model criterion)

Existing: `REQ@1712870400.6ZR3nk.configurable-model-attribute-schemata`. Via MCP write tools only
(tool-based-authoring), extend *just enough*:
- A **requirement** for the repository authoring policy (createability + valid declared defaults +
  `required_defaults_policy`) — captures WU-B1, *not* the discredited "all required have defaults".
- A **requirement** for typed-property persistence (canonical lexical forms + schema-driven decode)
  and typed editing — captures WU-B3/B4/B5.
- Link both to the existing REQ and to the application component that performs validation. Do **not**
  model individual attributes/scalars (configuration, not architecture).
Per the cross-cutting self-model criterion, also reconcile any stale element touched.

**Checklist.**
- [x] `artifact_create_entity` ×2 + `artifact_add_connection` (refines/realises) via tools.
- [x] `artifact_verify`; regenerate types if any ontology touched.

---

## Phase C — Documents

### WU-C1 — Documents open in view/preview by default; single Edit toggle (mirror entities)

**Symptom [reported/CODE].** `DocumentDetailView.vue` opens in edit mode with editable fields and a
`MarkdownEditor.vue` that has its **own** edit/preview toggle (~lines 26, 128-162).

**Fix design.** Mirror the entity pattern (`EntityDetailView.vue` view-mode + "Edit" button).
- Page-level `editing = ref(false)`; render rendered HTML/preview by default.
- Single "Edit" button flips to edit mode; "Save"/"Cancel" return to view.
- **Audit `MarkdownEditor` callers first**. If it is single-purpose (only the document
  editor), strip its internal edit/preview switch and let the page own the mode (in view mode the
  editor isn't mounted — correctness by construction). If it has other callers, add a controlled
  `mode` prop instead of removing the toggle globally, so we don't regress those callers.

**Checklist.**
- [x] Grep `MarkdownEditor` usages; decide strip-vs-controlled-prop based on the audit.
- [x] Add page mode state + Edit/Save/Cancel to `DocumentDetailView.vue`.
- [x] View mode renders markdown (reuse existing renderer); edit mode mounts/enables `MarkdownEditor`.

**Tests.** Vitest: detail mounts in view mode; Edit reveals editor; Save persists & returns to view.

---

### WU-C2 — Document specs support section-templates (indexed by section-name)

**Symptom [reported/CODE].** Document specs declare `required_sections` only; new-doc scaffolding
uses a generic placeholder body (`_build_placeholder_body()` ~document.py:59-63).

**Fix design.** Extend the document spec (`.arch-repo/documents/*.json`) with an optional
`section_templates: { "<section name>": "<markdown boilerplate>" }`. At document creation, when
materialising each required section, inject its template body if present, else fall back to the
current comment placeholder (backward compatible). Thread the spec into `_build_placeholder_body`
(call site ~document.py:148). Surface via `create_document` MCP tool + HTTP create path.

**Checklist.**
- [x] Spec schema: add optional `section_templates` map **+ validation** (keys must be declared
      sections; values are strings) — fail loudly on a malformed spec.
- [x] Update the **document-spec repository template** so new repos carry the field.
- [x] Scaffolding: per-section template lookup with comment fallback.
- [x] Doc the field in `artifact_create_document`/`authoring_guidance`.

**Tests.** Create doc whose spec has a template for "Decision" → body pre-filled; section without a
template → placeholder comment.

---

## Phase D — Entity-Picker (shared component) — [DESIGN]

Context [CODE]: `tools/gui/src/ui/components/EntityPickerInput.vue` (chips ~line 309) +
`useEntityFilters.ts` (`availableEntityTypes` ~14-20) derive type chips **only** from
`selectedDomains` and the domain↔type map, ignoring any caller `fixedEntityTypes`. Hierarchy:
group → ArchiMate domain → entity-type → entity. Backend: `GET /api/reference-search`.

### WU-D1 — Apply implied higher-level filters when a specific entity-type is selected

**Fix design.** Selecting a specific entity-type implies exactly one thing structurally: its
**ArchiMate domain** (type→domain is a fixed mapping). Derive and display that implied domain. It
does **not** imply a *group* — groups (model-projects/collections) contain arbitrary types, so
inferring a group from a type would hide valid entities. Treat **group as an independent
user-selected or caller-fixed scope**, never auto-narrowed from type. (If type-aware group hints are
ever wanted, present them as result-count filtering over the repository taxonomy, not as an inherent
hierarchy level.) `availableEntityTypes` must also intersect any caller `fixedEntityTypes` so the
picker never offers a forbidden type.

**Checklist.**
- [x] `availableEntityTypes` = (types for selected domains) ∩ (`fixedEntityTypes` if provided).
- [x] Selecting a type derives & displays only its implied **domain** (not a group).
- [x] Group stays an independent scope (user-selected or caller-fixed); never inferred from type.

### WU-D2 — Constrained ("fixed") filter levels: display strategy — **decision below**

**[DESIGN] Two strategies evaluated (user asked to choose one):**
- **(A) Show the fixed level, non-editable** — the domain section renders disabled with the pinned
  value(s) visible. *Pro:* intelligibility (user sees the scope they're working within),
  consistency (same layout everywhere), discoverability. *Con:* a little more chrome.
- **(B) Hide the fixed level** — de-clutter. *Pro:* minimal UI. *Con:* hides *why* only certain
  entities appear; users can't tell whether a domain is fixed or merely empty; inconsistent layout
  between callers; harder to debug "where did the rest go?".

**Recommendation: (A), with a refinement.** Show fixed levels as **non-editable, but collapse to a
compact read-only chip when a single value is pinned** (e.g. "Domain: Business 🔒"). This keeps the
scope legible (intelligibility + consistency, which are part of usability) while avoiding clutter
when the constraint is trivial. Pure hiding (B) trades away legibility for marginal space and is
rejected.

**Config surface.** Add picker props: `fixedDomains?`, `fixedEntityTypes?`, and
`widenableTo?: 'none' | 'domain' | 'group'` describing the highest level the user may widen to, plus
optional set-constraints per level (the allowed superset when widening). Render fixed levels per
strategy (A).

**Checklist.**
- [x] Add `fixedDomains`/`fixedEntityTypes`/`widenableTo` (+ per-level allowed-set) props.
- [x] Render fixed levels read-only (compact chip when single value, disabled section when a set).
- [x] Enforce widen constraints (cannot widen beyond `widenableTo`/allowed sets).
- [x] Migrate existing callers (e.g. datatype DOB picker, activity picker) to the new props.

**Tests.** Vitest: pinned single domain → read-only chip, no widen; pinned set → disabled section
listing the set; `fixedEntityTypes` → forbidden types never offered.

---

## Phase E — C4 diagrams (view + edit)

Backend C4: `src/diagram_types/c4/{renderer.py,_resolve.py,_navigation.py,_type.py}`; the two
reported diagrams are **model-backed** (`diagram-entities: {}`, entities derived from the ArchiMate
graph via `entity-ids-used`/`bindings`). Frontend: `DiagramDetailView.vue` (viewer),
`EditDiagramView.vue` + `tools/gui/src/ui/diagram-types/c4/C4DiagramEditor.vue` (editor).

### WU-E1 — Person/actor nodes render without labels  (System Context + Container)

**Symptom [reported].** Person nodes show no label, though PUML emits
`actor "Architect" as ACT_…` (`renderer.py` ~180, body via `_render_item_body` ~204-210).

**Root cause [HYP].** The emitted `actor "<label>" as <alias>` is syntactically correct, so the
label loss is most likely a PlantUML rendering interaction (actor stereotype/skinparam) or a
multi-line `\n` body confusing the actor renderer. **Must reproduce first** by rendering the stored
PUML with `plantuml.jar` and inspecting the SVG.

**Fix design (after repro).** Most probable: actors with a multi-line body (`label\n tech\n desc`)
don't render the label as expected; switch persons to a labelled `rectangle`/C4 person glyph, or set
explicit `skinparam actor { FontColor … FontSize … }`, or put the label outside the `\n` body. Apply
in `renderer.py` person branch; keep single source for both diagrams.

**Checklist.**
- [x] Render `CSC@…amp-system-context` & `CC@…amp-containers` PUML locally; capture current SVG.
- [x] Identify exact label-loss cause; fix the person emission in `renderer.py`.
- [x] Golden-PUML/snapshot test asserting the person label text is present & visible.

### WU-E2 — Container: lines from persons start too far from the node

**Symptom [reported].** Edges originating at person nodes begin with a visible gap.

**Root cause [HYP].** `skinparam linetype ortho` + actor glyph anchor/padding mismatch
(`renderer.py` ~52-64 skinparams).

**Fix design (after E1 repro, same render harness).** Tune actor padding/margin or line routing
(`linetype` choice) so edges anchor at the node; verify visually. Likely folds into the E1 person
fix if persons become rectangles.

**Checklist.**
- [x] Reproduce gap; adjust skinparam/element so edges anchor to the person node.
      → Resolved by E1 fix: `actor` → `rectangle <<C4Person>>` gives rect border anchors,
         eliminating the glyph-tail gap. No further skinparam tuning required.
- [x] Snapshot test for the container diagram.
      → Covered by `test_c4_person_rendering.py` (renders standalone diagram, verifies no actor).

### WU-E3 — Drill-down via clicking an interaction element on an entity; up via banner — [DESIGN]

**Symptom/Goal [reported].** Drill-down should be initiated by clicking an affordance **on a
displayed entity** that has a drill-down relation; upward nav via a banner at the top.

**Current [CODE].** Navigation is a body panel of `RouterLink`s
(`DiagramDetailView.vue` ~625-678) built from `c4_navigation` (`_navigation.py:87-146`). SVG node
clicks only *select* (no drill). A `drilldown_diagram_id` per-entity prop is hinted but never
populated/acted on (`DiagramOwnEntityTypeSection.vue:12 HIDDEN_PROPS`).

**Fix design.**
1. **Model the relation.** Per displayed entity, compute whether a child C4 diagram is scoped by
   that entity (reuse `_navigation.py` down-link logic, keyed by entity id) and expose a
   `drilldownByEntityId: {entityId: childDiagramId}` map in the diagram context.
2. **Affordance on the node.** In the SVG overlay, for entities with a drill-down target, render a
   small "drill-down" affordance (e.g. a ⤵/＋ badge on the node corner). Click → route to the child
   diagram. Plain node click keeps select semantics (no accidental navigation).
3. **Up via sticky banner.** Convert the parent-link portion of the C4 nav into a **sticky top
   banner/breadcrumb** (level badge + scope name + "↑ up to <parent>"), pinned above the canvas.
   Keep child links reachable too, but the *primary* drill-down is now on-node.

**Checklist.**
- [x] Backend: `drilldownByEntityId` in C4 diagram context.
      (Computed on frontend from existing `child_diagrams[].scope_entity_id` — no backend change
      needed; `buildDrilldownByEntityId` helper in `DiagramDetailView.helpers.ts`.)
- [x] Viewer: per-node drill affordance; click navigates to child diagram.
      (SVG badge injected in `attachInteractivity` via `getBBox()` + `svgEl.appendChild`.)
- [x] Viewer: sticky up/breadcrumb banner; de-emphasise the old body panel.
      (`.c4-up-banner` sticky above canvas; `.c4-child-nav` replaces old nav panel.)

**Tests.** Context builder maps scope-entity→child diagram; Vitest: node with target shows
affordance & navigates; node without does not.

### WU-E4 — Edit view shows no entities/connections for model-backed C4 — usability overhaul

**Symptom [reported].** Switching System Context to edit shows an empty sidebar.

**Root cause [CODE].** The editor sidebar reads `diagramEntities[entity_type]` (diagram-owned
entities), which is `{}` for model-backed diagrams; `C4DiagramEditor.vue` (~202-209) shows only a
"derived from the model" hint. The agent's note that this is "by design" is **not acceptable as a UX
outcome** — the user expects to *see and curate* what the diagram shows.

**Fix design.** For model-backed C4, present the **derived** entities/connections (from
`entity-ids-used`/projection, in the diagram context as `context.entities`/`context.connections`)
intelligibly:
- List derived entities grouped by C4 role (persons, external systems, the scope, internal
  containers/components), each linking to the model entity; show binding status.
- **Entity curation only.** Each *entity* row offers include/exclude via the projection's existing
  `_included_entity_ids`/`_excluded_entity_ids`. **Connections are shown read-only and derived
  automatically** — the projection has **no connection-level selection field**, so we cannot exclude
  one connection while keeping both endpoints. Surface connections for visibility, not curation.
- Scope/bindings editable where appropriate; standalone-diagram editing unchanged.

**[DESIGN — deferred option].** Selective edge suppression would require new
`included_connection_ids`/`excluded_connection_ids` across projection model + schema + renderer +
editor. Out of scope unless confirmed as a real requirement; entity-only curation is the default.

**Checklist.**
- [x] Populate sidebar from `context.entities`/`connections` for model-backed diagrams.
      → `C4ModelBackedPanel.vue` consumes `props.entities` + `props.diagramConnections`.
- [x] Per-**entity** include/exclude wired to `_included/_excluded_entity_ids`; persists via edit-diagram.
      → `handleExcludedChange` in `C4DiagramEditor.vue` emits `diagramEntitiesChange`.
- [x] Connections shown read-only (derived); no connection-level exclude in this WU.
      → Connections rendered in `C4ModelBackedPanel.vue` with `read-only` badge, no controls.
- [x] Group rows by C4 role; binding status; links to model entities.
      → `groupEntitiesByRole` in `C4DiagramEditor.helpers.ts`; ↗ link to `/entity?id=…`.

**Tests.** Vitest: model-backed C4 edit shows derived persons/systems; toggling exclude updates
`_excluded_entity_ids`; standalone editing unaffected.

---

### WU-E5 — Diagram viewer: select any entity/connection for details — incl. diagram-only ones (C4, GSN, all types)

**Symptom [reported].** Several diagram types (C4, GSN) do not let you select a displayed entity to
see its details in the sidebar; this must work **even for diagram-owned (diagram-only) entities and
connections**.

**Root cause [CODE].** `DiagramDetailView.vue` resolves selection detail via
`selectEntity(id) → svc.getEntity(id)` (~line 300), which only resolves **standalone model
entities** (those with a file). The two cases are distinct:
- **GSN nodes** (`cx1/g1/s1/…`) are genuinely **diagram-only** (`host_diagram_id` set, no file).
- **Model-backed C4** persons/systems/containers are generally **model entities** that *do* resolve
  via `getEntity` — their selection issue is about click-target wiring on derived nodes, not a
  missing artifact. Don't conflate the two in the fix.
Connection selection (`selectConnection`, ~282) highlights but renders no detail panel for any type.

**🔴 Confirmed contract defect.** A live read of the GSN diagram-only id via
`artifact_query_read_artifact` returned **null** — the documented "accepts diagram-only ids" contract
is broken. This is a backend defect to **fix**, not an optional fallback to route around.

**Fix design.**
- Fix `artifact_query_read_artifact` (and the HTTP read path) to actually return diagram-only
  entities/connections from their host diagram's `diagram-entities` — restore the documented contract.
- Make the detail panel source-aware: model entity → `getEntity`; diagram-only → the (now-fixed)
  diagram-only read, or render directly from the already-loaded diagram context.
- **Connections:** show a connection-detail panel (endpoints, type, label, metadata) on
  `selectConnection`, for model and diagram-only connections alike.
- Ensure SVG click handlers are wired for diagram-only nodes/edges (GSN) and for derived C4 nodes.
This shared viewer mechanism then covers C4, GSN, datatype, activity, sequence.

**Checklist.**
- [x] **Fix the diagram-only read contract** in `artifact_query_read_artifact` + HTTP read (returns
      null today) — with a regression test reproducing the GSN-node null.
- [x] `selectEntity` branches on model vs diagram-only; diagram-only detail via the fixed read/context.
      (No branch needed: `svc.getEntity(id)` now resolves both via the fixed backend; `host_diagram_id`
      exposed via `EntitySummary`/`EntityDetail` for display.)
- [x] Connection-detail panel on selection (model + diagram-only). (Pre-existing panel at line 792;
      now populated for GSN connections via fixed `_extract_diagram_connections`.)
- [x] SVG click handlers wired for diagram-only nodes/edges (GSN) and derived C4 nodes.
      (`display_alias` now set to `node_id` so `buildAliasToId` maps GSN node aliases correctly;
      `buildAliasToId` extracted to `DiagramDetailView.helpers.ts` and tested.)
- [x] **Startup registry-compatibility excludes diagram-derived projections**
      (`validate_repo_compatibility`): diagram-only entities (`host_diagram_id` set) and synthetic
      `…#conn/…` connections are out of scope of the model-vocabulary check, so a free-ontology
      diagram's group-keys (`nodes`) and edge-kinds (`supported-by`/`in-context-of`) — now indexed for
      read/selection — do not abort backend startup. Regression:
      `tests/common/test_startup_validation.py::TestDiagramDerivedProjectionsExempt`.

**Tests.** Vitest: select a GSN diagram-only node → detail shows name + gsn_type; select a C4 person →
detail shows; select a connection → connection detail shows.

---

### WU-E6 — C4 nodes show name only; description excluded from label  🔴 user-visible clutter

**Symptom [reported/CODE].** C4 container and component nodes display the full entity description
(up to the 100-char `_short_description` excerpt) inside every node box, making labels unreadably
long. The user wants **name only** (plus optional technology tag) — matching the C4 standard intent
where description is a tooltip/side-panel detail, not a node label line.

**Root cause [CODE].** `src/diagram_types/c4/renderer.py:208-209` — `_render_item_body` always
appends `item.description` when non-empty. For model-backed entities, `_resolve.py:309` populates
`description` via `_short_description(entity)` (first sentence of body, ≤100 chars). Even a short
sentence clutters small node boxes.

**Fix design.**
1. Remove the description line from the default node-body render — `_render_item_body` emits **name
   + `[technology]`** only. This is the correct default: descriptions belong in detail panels, not
   node labels.
2. `_short_description` and the `description` field on `_ResolvedItem` are still populated (they
   remain useful for hover tooltips / future accessibility). Do not remove them from the data model.
3. Diagram-owned entities that explicitly set `description` in their `diagram-entities` block still
   carry that description in the resolved item for future use; they simply no longer emit it in the
   label by default. A diagram-level flag `show_node_descriptions: true` (optional, default `false`)
   re-enables the description line for authors who want it — add to the C4 `_type.py` config and
   thread through to `render_body` → `_render_item_body`.

**Checklist.**
- [x] Remove description line from default `_render_item_body` output; add `show_node_descriptions`
      diagram flag (default `false`) that re-enables it.
- [x] Thread the flag from `_type.py` config through `render_body`/`_render_item` to the body
      helper. `_short_description` and `_ResolvedItem.description` remain unchanged.
- [x] Golden-PUML snapshot test: default render omits description; `show_node_descriptions=True`
      includes it.

---

### WU-E7 — C4 standard node shapes by default; explicit shape where multiple options exist

**Symptom [reported].** All C4 nodes render as a plain `rectangle <<stereotype>>` regardless of
element type or technology. The C4 standard uses distinct shapes: person glyph for `person` roles;
technology-driven shapes for containers (cylinder for databases, queue for message brokers, folder
for directories, `component`-style box for services/applications). These shapes are the *default*
C4 representation — **they are always used, not opt-in**. Where a type supports multiple candidate
shapes (e.g. a container could be a database, a queue, or a generic box), the author can declare an
explicit `shape` attribute; otherwise the renderer infers the best shape from the `technology` field
and falls back to a generic rectangle.

**Root cause [CODE].** `renderer.py:186` — `_render_item` emits all items as
`rectangle ... <<stereotype>>` unconditionally. The C4 person branch (`_render_item:180`) already
uses `actor`, but all other element types default to `rectangle`.

**Notation authority.** `https://c4model.com/diagrams/notation` — C4 model notation overview. The
C4 model is **notation-independent**: it prescribes abstractions and hierarchy, not specific shapes.
The **chosen implementation style** is the **C4-PlantUML stdlib** (`plantuml-stdlib/C4-PlantUML`),
the standard PlantUML rendering of C4 and the implementation vehicle used by the official tooling
examples on the notation page. It is available in the PlantUML stdlib via `!include <C4/C4_Context>`
/ `!include <C4/C4_Container>` / `!include <C4/C4_Component>` (plantuml.jar ≥ 1.2022.8; no
external URL required). The `[HYP]` step below validates stdlib availability; native PlantUML
keywords (`database`, `queue`, `actor`) are the fallback if the include fails.

**Fix design.**
1. **Shape resolution order** (applied inside `_render_item`):
   a. If the diagram entity has an explicit `shape` attribute → use that C4 macro variant or native
      keyword directly.
   b. Else if the item has a `technology` field → normalise to lowercase and look up the
      **technology-to-variant mapping**; use the mapped macro/keyword if found.
   c. Else → generic C4 macro for the item type (`Container`, `Component`, `System`, `rectangle`).
   Person nodes always use `Person` / `Person_Ext` (existing branch, updated to the macro).

2. **Technology-to-variant mapping** (pure dict in `renderer.py`; resolved at render time):
   Technology keywords are matched case-insensitively. The mapping selects a C4-PlantUML **macro
   variant** when the stdlib is available, or a native PlantUML keyword as fallback:

   | Technology keywords (lowercase substring match) | Stdlib macro variant | Native fallback |
   |-------------------------------------------------|----------------------|-----------------|
   | `database`, `sql`, `postgres`, `mysql`, `oracle`, `mariadb`, `sqlite`, `mongodb`, `redis`, `cassandra`, `rdbms` | `ContainerDb` / `ComponentDb` / `SystemDb` | `database` |
   | `queue`, `kafka`, `rabbitmq`, `sqs`, `activemq`, `nats`, `bus`, `broker`, `pubsub` | `ContainerQueue` / `ComponentQueue` / `SystemQueue` | `queue` |
   | `web`, `spa`, `ui`, `react`, `vue`, `angular`, `browser`, `frontend`, `client` | `Container` (generic — no stdlib browser shape) | `boundary` |
   | `server`, `api`, `service`, `backend`, `microservice`, `daemon`, `worker`, `batch`, `lambda`, `function` | `Container` / `Component` (generic) | `component` |
   | folder, directory, ldap, ad, s3, blob, bucket, storage, filesystem, nfs, object store | `Container` (generic) | `folder` |

   The db/queue/generic discrimination applies consistently across container, component, and
   system-level items. Person nodes: `Person` for internal, `Person_Ext` for external; this
   replaces the current `actor` keyword. All macro calls include `(alias, label, techn, descr)`
   positional arguments; `descr` is always empty (WU-E6 removes description from node bodies).

3. **Explicit `shape` attribute on diagram entities.** Diagram entities in `diagram-entities`
   blocks may carry an optional `shape:` key naming the preferred macro variant or native keyword.
   This is the author's disambiguation mechanism (e.g. a container whose technology is
   "PostgreSQL on S3" could be either a Db or folder variant; `shape: ContainerDb` settles it).
   Model-backed entities with no `shape` key follow the technology inference path.

4. **`[HYP] — validate stdlib and native shapes with plantuml.jar first.`**
   a. Test `!include <C4/C4_Container>` with a minimal PUML calling `Person`, `Container`,
      `ContainerDb`, `ContainerQueue`, `System`, `SystemDb`; confirm the stdlib loads and shapes
      are recognisable.
   b. If stdlib is unavailable, test native keywords (`database`, `queue`, `actor`, `boundary`,
      `component`, `folder`) — confirm each renders the expected shape and that SVG click-targets
      are stable for WU-E5 selection.
   The outcome of this step decides which code path `renderer.py` uses; both paths should be
   coded (stdlib preferred, native fallback) with a renderer-level flag set once at startup.

5. **One consistent style.** The C4-PlantUML stdlib produces the standard colored-box style
   (blue/grey/green palette with `<<Person>>`, `<<Container>>`, `<<Database>>` stereotypes and
   person glyphs) — this is the "main styling" shown in the C4 tooling examples on
   `https://c4model.com/diagrams/notation`. Do **not** mix stdlib macros with conflicting skinparam
   overrides; extend only for external-element shading (muted tones) consistent with the stdlib
   palette. The existing stereotype hard-coding in `_render_item` is superseded by the macros; the
   skinparam block is reduced to colour/font tweaks that harmonise with, not override, the stdlib
   defaults.

**Checklist.**
- [ ] `[HYP]` (a) Test `!include <C4/C4_Container>` with a minimal PUML calling `Person`,
      `Container`, `ContainerDb`, `ContainerQueue`, `System`; confirm stdlib loads and shapes are
      recognisable. (b) If stdlib fails, test native keywords `database`, `queue`, `actor`,
      `boundary`, `component`, `folder`; confirm each shape is recognisable and SVG click-targets
      are stable. Outcome decides stdlib-vs-native code path in `renderer.py`.
- [ ] Technology-to-shape mapping dict in `renderer.py`.
- [ ] `_render_item` applies shape-resolution order (explicit `shape` → technology map → rectangle).
- [ ] `_ResolvedItem` gains an optional `shape: str | None` field; `_items_from_diagram_entities`
      reads `raw.get("shape")`; model-backed items default to `None` (technology inference applies).
- [ ] Skinparam block updated so all shape keywords render with consistent colour/border thickness.
- [ ] Golden-PUML tests: (a) entity with `shape: ContainerDb` → `ContainerDb` macro / `database`
      native keyword; (b) entity with `technology: PostgreSQL` and no explicit shape → db variant;
      (c) unknown technology → generic `Container` / `rectangle`; (d) person → `Person` macro /
      `actor` native; (e) external system → `System_Ext` / `rectangle <<External>>`.
- [ ] Update authoring guidance (`artifact_authoring_guidance` / C4 doc) with the `shape` attribute
      and technology-inference rules.

---

## Phase F — ER / Datatype (UML class) diagrams — usability + correctness

Backend: `src/diagram_types/datatype/{ontology.yaml,renderer.py}`,
`_verifier_rules_datatype.py`. Frontend: `tools/gui/src/ui/diagram-types/datatype/
{DatatypeEditor,ClassifierCard,ConnRow}.vue`, `useDatatypeModel.ts`. The ontology already declares
`attributes:[{name,type,multiplicity,is_id,is_unique,default}]`, `literals`, `is_abstract`,
`generalization_set` — but the UI under-exposes several fields.

### WU-F1 — Attribute type must be selectable (scalars + in-diagram classifiers)

**Symptom [CODE].** `ClassifierCard.vue` ~97-102: attribute `type` is free text.

**Fix design.** Replace with a **combobox** whose options = (a) a built-in scalar set
(`String, Integer, Number/Decimal, Boolean, Date, DateTime, UUID` — define once as the datatype
"primitive" set) **+** (b) every classifier defined in the current diagram (classes, datatypes,
enums, variants, primitives the user created) **+** allow free entry for not-yet-created types
(creating the reference). Source (b) from `useDatatypeModel` classifiers. Render unchanged in PUML
(`renderer.py:79-84`).

**Checklist.**
- [x] Define the built-in scalar/primitive catalog and expose it via the **diagram-type UI/config
      contract** (`config.yaml`/`type_ui_slots`), not a bespoke endpoint.
- [x] Attribute type combobox = scalars ∪ in-diagram classifiers ∪ free entry.

### WU-F2 — Clarify cryptic fields: "mult", "src card", "tgt card"

**Symptom [CODE].** `ClassifierCard.vue` ~104-109 "mult" = attribute **multiplicity**;
`ConnRow.vue` ~118-133 "src card"/"tgt card" = source/target **association-end cardinality**.
Roles are real but unlabelled/abbreviated.

**Fix design.** Rename labels to **Multiplicity** (attribute) and **Source cardinality / Target
cardinality** (relation), with helper text/placeholder examples (`1`, `0..1`, `1..*`, `*`) and a
small info tooltip explaining each. No data-model change.

**Checklist.**
- [ ] Relabel + add example placeholders + tooltips for all three fields.

### WU-F3 — Unique constraints for classes/datatypes (and attributes)

**Symptom [CODE].** Ontology declares `is_unique` per attribute, but the UI never exposes it
(`ClassifierCard.vue` has only `is_id`; `useDatatypeModel.ts` Attribute lacks `is_unique`) and the
renderer ignores it (`renderer.py` emits `{id}` only).

**Fix design.**
- Attribute-level: add `is_unique` checkbox; render `{unique}` (and `{id}`) markers in PUML.
- Classifier-level (multi-column uniqueness): add optional `unique_constraints: string[][]` (lists
  of attribute names) to the classifier ontology + a small editor; render as a UML constraint note
  on the class. (Covers composite keys that attribute-level `is_unique` cannot.)

**Verifier extension is mandatory.** Composite `unique_constraints` reference attribute
names, so the verifier must validate them: every referenced name exists on the classifier, no
duplicate-name entries, and no empty tuples. A uniqueness constraint pointing at a missing/renamed
attribute is a silent modelling error otherwise.

**Checklist.**
- [x] Add `is_unique` to frontend Attribute model + checkbox + PUML `{unique}`.
- [x] Add classifier `unique_constraints` to ontology + editor + PUML rendering.
- [x] **Extend the datatype verifier**: validate constraint attribute-name references (exist,
      non-duplicate, non-empty); regression tests.
- [x] Regenerate `types.generated.ts`.

### WU-F4 — Notes on classifiers (and relations)

**Symptom [CODE].** No way to annotate classifiers; Activity/Sequence have a `NoteSection` pattern
to reuse (`ActivityStepItem.vue` ~118-121, `NoteSection.vue`).

**Fix design.** Add optional `note: string` to the classifier ontology (and relation, for symmetry);
reuse `NoteSection`; render as a PlantUML `note on` the element.

**Checklist.**
- [ ] `note` field on classifier (+ relation) ontology; `NoteSection` in `ClassifierCard`/`ConnRow`.
- [ ] PUML note rendering; regenerate types.

### WU-F5 — General ER create/edit UX review (consistency & flow)

**Fix design.** With F1–F4 in place, do a consistency pass: clear section grouping
(Identity → Attributes → Constraints → Notes), consistent labelling/tooltips with other editors,
sensible add-buttons, and confirm the classifier↔data-object binding + backing-relation quick-fix
flow (`useDtBackingConstraint.ts`, E330/E331) reads clearly. Align look-and-feel with the activity/
sequence editors (the design-integration-as-usability point).

**Checklist.**
- [x] Reorganise `ClassifierCard`/`ConnRow` into labelled sections.
- [x] Consistency audit vs activity/sequence editors; fix divergences.
- [x] Verify backing-relation quick-fix copy is intelligible.

---

## Phase G — Assurance GUI feature-completeness

**Finding [CODE].** The assurance backend covers STPA/CAST/GRC,
GSN/assurance-cases, SBOM/vuln/AI-BOM, baselines/sealing, `model_this`, `promotion_preflight` via a
substantial MCP surface (roughly ~20 read + ~12 write tools — **the exact set must be inventoried,
not asserted**). Two caveats the plan must respect:
- The MCP tools are **often the implementation, not thin adapters** over reusable application
  services. So "delegate to the existing service layer" is not free — several capabilities need an
  **application-layer use case extracted first**.
- Specific capability gaps to verify rather than presume: generic node creation supports the ~11
  node types (not GSN-specific goal/strategy/solution/assumption/evidence helpers); there is **no
  assurance edge-delete tool**; baseline *listing* exists on the archive port but is **not a normal
  read tool**; `assurance_model_this` **only returns a cross-server task spec — it performs no
  creation or binding**; some writes invoke store/connector adapters directly; generic node writes
  **do not run a post-write verifier**; classification filtering is incomplete (see §0).

The **GUI/HTTP surface barely exists**: only `GET /api/assurance/status` + `POST /api/assurance/reload`
(`routers/assurance.py`). The store is SQLCipher, **single-writer serialised**, with sealed
**baselines** (excluded from live listing) and an append-only audit log; **no FTS index** today.

**Root cause of "Uncategorized visible but not navigable" [CODE].** Assurance "analysis-collection"
groups route to `GroupManagementView` (`router/index.ts:44`) — group *management*, not content.
Clicking a collection (incl. the default "Uncategorized") goes nowhere. (Separately, the architecture
browse shows a synthetic "uncategorized" group — keep the two distinct in the nav.)

**This phase runs LAST [user]:** this is primarily an architecture product, so all of A–F precede G.
To stop the largest phase from discovering foundational gaps late, its **first sub-unit is paper
design** (WU-G-INV) — capability matrix, exposure policy, index benchmark — completed and reviewed
before any G implementation. Confirmed [user]: drive to feature-completeness against the (verified)
MCP capability.

### WU-G-INV — Capability matrix, exposure policy & search benchmark (design-first, no implementation)

Before G1, produce three reviewed artifacts:
1. **Capability matrix** — one row per assurance capability, columns: *application use case · MCP read
   · MCP write · HTTP · GUI · unlock · TLP filter · audit · verification*. Fill from the actual code.
   This replaces all asserted capability claims; nothing is described as "existing" until the matrix
   proves it. It also reveals which capabilities need an application-layer use case extracted before a
   REST adapter (edge-delete, baseline-list, GSN-typed creation, post-write verification, model-this
   binding vs. task-spec).
2. **AssuranceExposurePolicy design** (§0) — the single classification/visibility filter applied by
   MCP and HTTP to nodes, edges, aggregates, verification findings, search, and existence/errors;
   defines locked(`423`)/forbidden(`403`)/empty semantics. (No authn — per §0 product decision.)
3. **Search benchmark** — measure direct filtered store queries on a realistic/large store under
   concurrent read load *before* deciding whether WU-G3 needs an in-memory index at all.
4. **Analysis aggregate (settled).** Assurance nodes today carry **no collection or analysis
   identifier** — only sealed baselines have an optional `analysis_id`, so per-analysis
   completeness/stats/search have nothing to scope to, and the visible "Uncategorized" is GUI group
   infrastructure, not a modelled collection. The model is a **first-class assurance-analysis
   aggregate**: an `analysis` (id, method ∈ {STPA, CAST, GRC}, the **architecture element it is
   about** — the WU-G0 anchor — status, and its baseline history); every assurance node **belongs to
   an analysis**. Completeness, sealing, stats, search and browse all scope to an analysis, so
   unrelated analyses cannot contaminate each other's coverage. This is a **store schema migration**
   (SQLCipher): design the aggregate, the node→analysis membership, and a forward/backward migration
   with audit. It rewrites G1 filters, G2 navigation, G5 wizards, G6 baselines and the matrix.
5. **GSN classification-gated dual home (settled).** GSN spans two stores and must not be conflated:
   the existing exemplar is an **architecture-repository** diagram with diagram-owned GSN nodes (NOT
   in the confidential graph); `assurance_draft_gsn` only returns a derived dict; generic
   assurance-node creation **cannot** create GSN goals/strategies/solutions. The bridge: (1) assurance
   services *produce a GSN draft* from assurance content; (2) the **persistence destination is chosen
   by the argument's TLP** — **confidential** cases stay in the assurance store and render as derived
   previews (never persisted to git, per §0/WU-G3); **cleared/non-classified** cases (incl. the
   self-model exemplar) are published to the architecture repo as `gsn` diagrams via
   **arch-repo-write**; (3) bindings connect GSN nodes ↔ assurance nodes/evidence ↔ architecture
   elements; (4) the existing (non-classified) exemplar is edited via `artifact_edit_diagram`, never
   via assurance-node tools.

**Checklist.**
- [x] Capability matrix committed; missing application use cases enumerated as prerequisites.
- [x] Exposure-policy design + locked/forbidden/empty/404 contract.
- [x] Benchmark results recorded; G3 index decision justified by data.
- [x] Analysis-aggregate schema + node membership + forward/backward migration (audited) designed.
- [x] GSN dual-home bridge defined (draft → TLP-gated destination → bindings); store ownership clear.

### WU-G0 — Governing design principle: assurance grounded in architecture (cross-cuts G1–G6)

**Directive [user].** Assurance UI/UX must *unify assurance work with, and ground it on,
architectural modelling work and artifacts* — fluently, not as a parallel silo. Two concrete
expressions to thread through every assurance WU:

1. **Assess assurance-characteristics *of modelled systems*.** Assurance is entered *from* the
   architecture, not only from a separate menu. From any architecture entity/diagram detail view,
   surface an **"Assurance" lens**: the hazards, UCAs, risks, constraints, obligations and
   vulnerabilities that *concern this element* (via the assurance→architecture `binds-to`/`concerns`/
   `register_arch_ref` edges). Conversely, an assurance node's detail (WU-G2) leads *back* to the
   architecture entity it is about. The architecture model is the spine; assurance is a lens on it.
2. **Flag modelling gaps during analysis, with one-click alleviation.** When assurance work
   references something not (well) modelled — an unbound node, a hazard on an unmodelled component,
   an incident touching a control with no architecture counterpart — the UI must **flag the gap
   inline** and offer to **alleviate** it: invoke `assurance_model_this` to propose the architecture
   entity and (if architecture-write scope is present) create+bind it without leaving the flow; else
   emit a task for an architecture-write session (separation of duties). This is most acute in **CAST
   incident analysis** (reconstructing what *should* have been modelled) and in STPA control-structure
   modelling — both must show coverage/gap badges and a "model & bind" affordance.

**Implications applied below:** G2 detail views are bidirectional (arch↔assurance); G5 wizards embed
gap-flagging + model-this at each step; the verification/coverage surfaces (G1) drive the gap badges;
binding status is shown wherever assurance content renders (G2, G6).

**Checklist.**
- [x] Analysis entry requires an architecture anchor and is available from architecture detail.
- [x] Architecture lens and assurance back-navigation contracts are explicit and one-way persistence is preserved.
- [x] Binding states and stable modelling-gap findings are defined once for all GUI surfaces.
- [x] Model-and-bind orchestration defines both direct-bind and separation-of-duties task outcomes.
- [x] Self-model reuses the assurance-linkage requirement and reflects REST-based GUI integration.

### WU-G1 — Unlock-gated HTTP read endpoints (the missing REST spine)  🔴 confidentiality

Add to `routers/assurance.py`, each routed through the **AssuranceExposurePolicy** (WU-G-INV) — not
just an ad-hoc `max_classification` check:
- `GET /api/assurance/nodes` (filters: node_type, status, concern_class, tlp, binding_status,
  **analysis/collection per WU-G-INV #4**)
- `GET /api/assurance/nodes/:id` (node + edges)
- `GET /api/assurance/edges`
- `GET /api/assurance/stats`, `GET /api/assurance/coverage`, `GET /api/assurance/verify`
- `GET /api/assurance/risk-register`, `GET /api/assurance/bom/components`,
  `GET /api/assurance/vulnerabilities`, `GET /api/assurance/baselines`
Delegate to assurance application services — but per WU-G-INV, where today's logic lives in an MCP
tool rather than a reusable service (e.g. baseline listing), **extract the application use case
first**, then have both MCP and HTTP call it.

🔴 **Complete the classification filtering the policy depends on** (the store does not do this fully
today): filter **edges by the TLP of *both* endpoints**; redact **aggregates** (stats/coverage/risk-
register) and **verification findings** so counts/IDs/names above the ceiling don't leak; apply the
same to search (WU-G3).

🔴 **Response semantics that don't themselves disclose existence**:
- **Locked store → `423`** (no content).
- **Collection/list reads** silently **omit** above-ceiling records (optionally a policy-safe
  "N withheld" count) — never an error.
- **Direct reads** (`/nodes/:id`) return an **indistinguishable `404`** for both absent and
  above-ceiling IDs — a `403` here would disclose that an inaccessible ID exists.
- Reserve `403` for operations whose target the caller already legitimately knows.

**Checklist.**
- [x] Endpoints above, routed through the exposure policy; typed DTOs.
- [x] Edge/aggregate/verification redaction completed and shared with MCP.
- [x] `423` locked / list-omit / direct-`404` semantics (no existence disclosure).
- [x] **Negative leak tests**: names/IDs/edge-topology/counts above the ceiling cannot leak; direct
      read of an above-ceiling ID is indistinguishable from absent; locked store serves nothing.

### WU-G2 — Navigable assurance browse + detail view

- New route + `AssuranceBrowseView`: **analysis/collection picker (per WU-G-INV #4; if (c) flat-graph
  was chosen, browse the flat graph)** → node list (faceted by type/status/concern_class/tlp/binding)
  → node detail (attributes + in/out edges + bound architecture refs + verification status).
- Make the navigation target **this browse view**, not `GroupManagementView`; keep group management
  reachable separately. (Meaningful only once #4 gives nodes an analysis/collection — until then the
  visible "Uncategorized" is GUI group infrastructure, not a modelled assurance collection.)
- Frontend search-hit + node schemas added (ties to WU-A1 union).

**Checklist.**
- [x] `AssuranceBrowseView` + route; collection→browse navigation.
      (`/assurance/browse` → `AssuranceBrowseView.vue`; `/assurance/analyses` redirects there;
      `AssuranceView.vue` updated to link to browse; full filter facets + node list.)
- [x] Node detail pane with edges + arch-ref links + verify status; **clicking an arch ref opens the
      architecture entity** (bidirectional, per WU-G0).
      (`AssuranceNodeDetail.vue`: node identity + content + arch_refs (RouterLink to /entity?id=…) +
      in/out edges; inline panel in browse view opened by clicking a node row.)
- [x] **Architecture-side "Assurance lens"** on `EntityDetailView`/`DiagramDetailView`: when unlocked,
      show hazards/UCAs/risks/constraints/obligations/vulns concerning this element (queried via
      assurance→arch edges), each linking into the assurance views. Hidden/locked when the store is
      locked.
      (`AssuranceLens.vue` + `AssuranceLens.helpers.ts`; added to `EntityDetailView.vue` after
      the connections section; silently hidden when locked or no findings.)

### WU-G3 — Ephemeral, unlocked-only assurance search → merged into global search  🔴 confidentiality / scale

**Decision [user]:** live unlocked-only is required; archived/sealed content need
not be searchable. **Benchmark first (WU-G-INV):** measure direct filtered store queries under
concurrent load before adding any index. The "O(matching), serves dozens of users" claim is dropped
as unsupported — only build an index if the benchmark shows the direct path is inadequate.

**🔴 Absolute persistence constraint [user].** If a searchable representation of confidential
assurance content exists, there must be **zero possibility** of it being written to disk unencrypted
or committed:
- It lives **only in process memory**, in a structure that is **never serialized** to any file, temp
  file, cache, or log — and **never under any repository or `.arch-repo`/`.arch-assurance` path**.
- **Defense in depth even though it should never be written:** an ignore rule covering any
  conceivable index artifact path, plus a test asserting no new untracked/written files appear after
  building+querying the index.
- Consider swap/core-dump exposure (best-effort: avoid long-lived plaintext buffers; document the
  residual risk). Responses carry **no-store** headers; telemetry/logs **redact** snippets and names.

**Fix design (if an index is warranted).** On unlock, build an **in-memory** index over **active**
assurance nodes (exclude sealed baselines + archive). **Edges are likely not worth indexing** —
low search value, extra leakage surface — default to nodes only. Dispose on a **guaranteed
lock-event lifecycle hook** (not best-effort). Updates are **transactionally coordinated** with the
single-writer write path (build/update/dispose ordering defined; failure recovery specified). Expose
`GET /api/assurance/search` (unlock-gated, exposure-policy filtered) and merge hits into global search
when unlocked, tagged `record_type: 'assurance-node'` (WU-A1 union). If the benchmark says direct
queries suffice, skip the index entirely and serve search from filtered store queries.

**Checklist.**
- [x] Benchmark direct filtered queries; decide index yes/no from data.
      → G-INV benchmark: p95 31.836ms; direct queries selected (no index).
- [x] If index: N/A — direct queries chosen; no index built; no plaintext persistence risk.
- [x] `/api/assurance/search` + global merge (unlocked-only), exposure-policy filtered; no-store
      headers; redacted telemetry.
      → `GET /api/assurance/search` in `_assurance_read.py`; `_try_assurance_hits()` merges into
        global `/api/artifact-search`; `SearchView.vue` links `assurance-node` hits to browse view.
- [x] Load/perf test under concurrent reads; test proving no plaintext file is ever produced.
      → `test_assurance_search_safety.py`: no-new-file test + concurrent HTTP requests test.

### WU-G4 — Unlock-gated HTTP write endpoints + create/edit forms  🔴 audit / confidentiality

Endpoints `POST/PATCH/DELETE /api/assurance/nodes`, `POST/DELETE /api/assurance/edges`,
`POST /api/assurance/baselines:seal`, `POST /api/assurance/model-this`, SBOM/vuln import — gated by a
**mutation policy / write use case** (not the read-oriented AssuranceExposurePolicy) that
owns unlock-check, classification-on-write, audit, and verification. **Per WU-G-INV, several backing
capabilities are not ready:**
- **Edge delete has no MCP tool** — add the application use case (+ MCP tool) before the REST verb.
- **`model_this` only returns a task spec** — it does not create or bind. The "create+bind in one
  step" UX (WU-G0/G5) needs a *new* binding use case; otherwise the endpoint just returns the spec
  and the UI emits a task. Do not claim one-click binding until that use case exists.
- 🔴 **Generic node writes do not run a post-write verifier today**, and **BOM/vuln/anchor writes
  neither check unlocked state nor append to the audit log**. To make the "same verifier and
  safeguard" premise true: route *all* mutations through a use case that (a) checks unlocked, (b)
  runs the post-write verifier including the **safety-disposition safeguard** (constraints/risks
  cannot be "accepted" without justification + sign-off — surface as a teaching message, never
  bypass), and (c) appends to the append-only audit log. This is backend work, not just a router.
- Frontend: type-aware node form (risk likelihood/impact/owner/treatment; UCA guideword; constraint
  concern_class/disposition) + typed edge picker.

**Checklist.**
- [x] Missing application use cases first (edge-delete, model-this binding, audited+verified writes).
- [x] Write endpoints over those use cases; unlock-gated + audited + post-write verified uniformly.
- [x] Type-aware node form + typed edge picker.
- [x] Safety-safeguard messaging; index update hook (WU-G3) only if an index exists.

### WU-G5 — Method wizards (STPA / CAST / GRC / Assurance-case) + supply-chain + model-this

Build the guided flows, each step calling backing capabilities + `assurance_guidance` for coaching.
**Per WU-G-INV, confirm per step which capability already exists vs. needs work first** (e.g. GSN
authoring goes through the #5 bridge — generic assurance-node creation **cannot** make GSN goals/
strategies/solutions; model-this *binding* is not yet a capability). Do not build a wizard step on a
tool the matrix shows is missing:
- **STPA:** Losses → Hazards(classify) → Control Structure → UCAs(guideword grid) → Constraints →
  `assurance_stpa_complete` → seal.
- **CAST:** recall baseline → incident → investigate(observed) → corrective actions →
  `assurance_cast_complete`.
- **GRC:** risk assessment → treatment → controls → obligations → coverage dashboard (safeguard).
- **Assurance case/GSN (via the WU-G-INV #5 dual-home bridge, not generic node creation):**
  `assurance_draft_gsn` produces a draft → TLP-gated destination (**confidential** → store-resident
  derived preview, never git; **cleared** → `gsn` diagram via **arch-repo-write**) → bind GSN nodes ↔
  assurance nodes/evidence ↔ architecture → completeness check.
- **Supply-chain:** SBOM upload+map, vulnerability dashboard, AI-BOM coverage/export, AI-candidate
  scan. **🔴 SBOM scope assignment (required):** import must capture and correctly assign the SBOM's
  *scope* against the **ArchiMate model** (C4 is only a view over it, so scope is expressed in
  ArchiMate terms, never C4 container/system). The SBOM may describe (a) a whole composite system,
  (b) a single service, or (c) a named subset of services — which map to ArchiMate elements such as a
  single **application-component** (one service), an **application-collaboration** or **grouping**
  (a system or subset of services), or the relevant **node/system-software** in the technology layer.
  The import flow forces selection of the target ArchiMate element(s) the SBOM applies to *before*
  ingest; components and vulnerabilities bind under that scope so the same component appearing in two
  services is not conflated and coverage/AI-BOM reconciliation is computed per-scope. Reuse the WU-D2
  entity-picker pinned (via `fixedEntityTypes`) to the admissible ArchiMate types for an SBOM anchor.
  (Backend: ensure `assurance_import_sbom`/component binding carries an ArchiMate scope/anchor; extend
  if the tool lacks it — principled-solution rule.)
- **Model-this:** surface unbound-node (W501) badges; click → `assurance_model_this`; create+bind if
  architecture-write scope present, else emit a task for an architecture-write session (separation of
  duties).

**Checklist.** (one sub-item per wizard; each = step components + completeness/verify call + diagram
hook), **each scoped to an analysis (WU-G-INV #4)**. Sequence STPA → GRC → CAST → GSN → supply-chain
→ model-this. **First shippable wizard milestone = STPA + GRC** (CAST needs baselines + an STPA
control structure; GSN needs the G7 renderer — both follow).

### WU-G6 — Assurance diagram rendering views + baselines view

**Distinguish three diagram sources — different read & persistence paths:**
1. **Architecture-repository assurance diagrams** (e.g. the GSN exemplar; control-structure views
   authored as diagram-type diagrams) — read/rendered via the existing architecture diagram pipeline
   (`artifact_*`), not an assurance endpoint.
2. **Dynamically-derived previews from the assurance store** (e.g. a control-structure/UCA matrix
   projected live from assurance nodes) — `GET /api/assurance/diagrams/:id/rendered`, exposure-policy
   filtered, ephemeral.
3. **Sealed assurance evidence/baselines** — `GET /api/assurance/baselines` (read-only); selection
   feeds CAST recall. (Diff/playback deferred.)
Detail views show binding status (solid/dashed/dotted) where applicable.

**Checklist.**
- [x] Architecture-repo assurance diagrams render via the existing diagram pipeline (no new endpoint).
- [x] Derived-preview endpoint (exposure-policy filtered) for store-projected diagrams.
- [x] Baselines list view; CAST wizard consumes selection.

### WU-G7 — GSN diagrams use correct, dedicated, reusable GSN notation (PUML component library)

**Symptom [OBS].** GSN renders with wrong shapes. The stored PUML for
`GSN@1781338120.3U4cRc` maps GSN element kinds to generic PlantUML keywords:
context → `usecase`, **strategy → `card`**, **solution → `database`**, goal → `rectangle`. None
match GSN notation (goal = rectangle, strategy = **parallelogram**, solution = **circle**,
context = **rounded-rectangle/stadium**, assumption/justification = **oval** with A/J tag,
undeveloped = **diamond/hollow** marker).

**Root cause [CODE].** There is **no GSN renderer** — `src/diagram_types/gsn/` has only
`config.yaml` + `__init__.py`; rendering goes through a generic config-mapped shape path that chose
poor approximations.

**Store ownership.** This is **architecture diagram-type subsystem** work
(`src/diagram_types/gsn`), independent of the confidential assurance store — grouped under Phase G
only by topic, and schedulable alongside the other diagram work (Phase E/F). It needs no assurance
store access.

**Fix design.** Add a **dedicated GSN renderer** plus a **reusable PUML component library** (a
preamble of `!procedure`/`!function` macros, one per GSN element — `$GsnGoal`, `$GsnStrategy`,
`$GsnSolution`, `$GsnContext`, `$GsnAssumption`, `$GsnJustification`, `$GsnUndeveloped`) that emit
the correct GSN shapes + the standard connector glyphs (`SupportedBy` = solid arrow with filled head,
`InContextOf` = hollow arrowhead). The renderer emits the include + one macro call per node. Define
the macros once as a shared asset so every GSN diagram (and the assurance-case wizard, WU-G5) reuses
them — single source of truth for GSN notation. (PlantUML parallelogram: use a `polygon`/`shape`
macro or a stereotyped rectangle with the correct skinparam; pick the approach that renders a true
parallelogram and document it.)

**[DESIGN — notation authority + prototype first, review].** Fix the reference notation (GSN
Community Standard shapes) as the authority, and build a **small rendering prototype** to validate
each shape *before* committing to custom macros — PlantUML's shape vocabulary is limited and a poor
approximation is worse than a clean stereotype. Acceptance criteria for the prototype: (a) shapes are
recognizably GSN (not approximations), (b) rendered nodes keep stable **SVG click targets** so
WU-E5 selection works, (c) basic accessibility (text contrast, labels present). This may justify a
separate assurance-diagram sub-plan rather than a single WU.

**Checklist.**
- [x] Notation authority fixed; rendering prototype validates every element shape (review gate).
- [x] GSN PUML component/macro library (one reusable definition per element + connectors).
- [x] Dedicated GSN renderer emitting the library + correct shapes; replace generic mappings.
- [x] Golden-PUML/snapshot tests per element type; SVG click-target + a11y checks; re-render
      `GSN@…3U4cRc` to verify shapes.
- [x] Regenerate any types if ontology touched. (N/A: no ontology/schema change.)

### WU-G8 — Rework the existing GSN assurance case for soundness (worked exemplar)

**Symptom [reported/OBS].** `GSN@1781338120.3U4cRc.assurance-case-confidential-assurance-store-gsn`
is weak: the three "solutions" (`Sn: Classification gate…`, `Activation-window re-lock`,
`Hash-chained Archive`) are **restated controls, not evidence**; a sound GSN solution must point to
*evidence that the claim holds* (test results, verification runs, the audit-log itself, a proof),
and the strategy/sub-goal decomposition should mediate cleanly from the top claim.

**Fix design.** After WU-G7 (correct shapes), rework the case. The exemplar is an
**architecture-repository diagram with diagram-owned GSN nodes**, so it is edited via
`artifact_edit_diagram` (tool-based-authoring) — **not** assurance-node write tools:
- Keep the top goal + context; refine the strategy so each sub-goal is a genuine premise of the top
  claim. Add **assumptions/justifications** where the argument relies on them.
- Replace restated-control "solutions" with **evidence solutions** referencing real artifacts
  (verification results for the classification gate / re-lock; the tamper-evident archive as Art. 12
  evidence). Evidence/architecture/assurance references use the WU-G-INV #5 bindings.
- Run the assurance-case completeness check to confirm the argument is complete.

**[DESIGN — needs your domain input].** The precise claim/strategy/evidence wording is an assurance
judgement; this WU proposes the structure and seeks your confirmation on the argument content.
Treat the result as the canonical GSN exemplar once sound.

**Checklist.**
- [x] Rework case structure (strategy/sub-goals/assumptions) via `artifact_edit_diagram`. → strategy
      reframed to assert a substantive property (not an "argument over"); added an assumption (supported
      deployment boundary) + justification (STPA-Sec decomposition completeness); split context into
      system (C1) and operating scope (C2).
- [x] Solutions reference real evidence artifacts, bound (per #5 bridge) to constraints/architecture.
      → the three restated-control "solutions" replaced with evidence solutions citing real verification
      artifacts (`test_assurance_exposure.py`/`test_assurance_http_read.py`, `test_assurance_store.py::
      test_unlock_and_lock`, `test_assurance_archive.py::test_verify_chain_with_entries`).
- [x] Completeness check passes; re-render with WU-G7 shapes. → diagram re-verified `valid` with no
      issues (all goals developed, solutions are leaves); on-demand SVG renders all 12 nodes with
      correct GSN shapes (goal rect, strategy parallelogram, solution circle, assumption/justification
      ovals, context stadium), 12 stable click targets, 13 aria-labels.

---

## Sequencing & rationale

Ordering honours the user's directive: **this is primarily an architecture product, so assurance
(Phase G) runs LAST.** The risk that the largest phase discovers foundational gaps late is addressed
*within* G by making its first sub-unit pure design (WU-G-INV), rather than by moving G earlier.

1. **Phase A (A1–A4)** — isolated correctness patch (search crash, ranked-search redesign,
   list-filter, browse reset). A1's union schema is a prerequisite for later assurance search hits.
2. **Typed-property foundation** — the WU-B3 spike (value model + canonical lexical grammar +
   migration decision) is foundational; then B1+B2 (ship together — boot depends on the strict
   policy), then B4/B5 on the foundation, then B6.
3. **Phase C, D** — independent, medium; D (entity-picker) feeds the datatype DOB picker used in F.
4. **Phase E, F** — diagram UX; E1/E2 need a quick PlantUML repro first; E5 includes the backend
   diagram-only read-contract fix.
5. **Phase G — last and largest.** Order: **WU-G-INV** (capability matrix + exposure policy + search
   benchmark + analysis-aggregate & GSN-bridge decisions, reviewed) → extract any missing application
   use cases → **G1+G2 = one read-only user milestone** (G1 is API-only and G2 depends on it, so they
   ship together: policy-enforced REST + navigable browse + bidirectional arch↔assurance lens) →
   **G3** search (index only if the benchmark warrants) → **G4** writes (audited, verified, gated) →
   **G5** method wizards → **G6** diagram views/baselines → **G7/G8** GSN renderer + exemplar
   (architecture-subsystem work; candidate for a *separate diagram sub-plan*). Shippable milestones:
   **G1+G2**, then G4, then each wizard in G5.

## Settled decisions

These were design choices; they are now folded into the WUs above and the ledger Decision log:
- **Schema remediation (B2):** the two classification enums (`capability.Maturity`,
  `driver.Category`) stay required with a genuine `Not Assessed`/`Unspecified` member; all other
  listed required attributes become optional.
- **Assurance scope (G-INV #4):** a first-class **assurance-analysis aggregate** (nodes belong to an
  analysis; everything scopes to it) — a store schema migration.
- **GSN home (G-INV #5):** **classification-gated dual home** — confidential cases stay in the store
  as derived previews; cleared cases publish to the architecture repo as `gsn` diagrams.
- **First wizard milestone (G5):** **STPA + GRC** first.
- **GSN notation (G7):** authority = **GSN Community Standard**; G7/G8 stay in this plan unless the
  rendering prototype reveals enough scope to warrant a separate diagram sub-plan.
- **Deployment/auth (§0):** authn out of scope; loopback default; non-loopback only behind a
  perimeter + explicit opt-in + startup warning.

## Implementation gates (resolved during execution, not user decisions)

- **B3 typed-property spike:** the value model + canonical lexical grammar + supported subset +
  migration are produced as a short spike and reviewed before B3 implementation (B4/B5 ride on it).
- **C4 person labels (E1/E2):** reproduce the label loss with `plantuml.jar` before choosing the
  rectangle-vs-skinparam fix.
- **Assurance search (G3):** direct filtered queries vs ephemeral in-memory index is decided by the
  WU-G-INV benchmark, subject to the absolute no-plaintext-persistence constraint.

## Self-model & docs touchpoints

Per the §0 self-model criterion, every architectural WU updates the model proportionally (no
over-modelling):
- **Reuse before create.** The model already has assurance MCP bridges, interfaces, store, verifier
  and a GUI component — update these rather than adding parallels.
- **Fix stale statements.** Reconcile the "GUI Authoring Tool calls MCP tools" element against the
  README's "GUI uses REST" (the GUI talks to the backend over REST; MCP is the agent surface).
- **Model the genuinely new structure** as it lands: the assurance HTTP interface, the
  AssuranceExposurePolicy, new application-layer assurance use cases, the ephemeral search component
  (if built), and the dedicated GSN renderer — settling the security/application-service model in
  WU-G-INV *before* implementation, not retrofitting after.
- Add B-phase requirements (authoring policy; typed-property persistence) per WU-B6.
- Update `docs/` (search behaviour, attribute editing, assurance GUI) as each phase completes.
