# TASKS — Datatype Attribute-Type Resolution

**Execution ledger for `PLAN-datatype-type-resolution.md`.** Work units (WUs) with files, signatures,
code skeletons, per-unit acceptance criteria, tests, and dependencies. **Read the PLAN's §1 four core
concepts and §11 decisions first.** Exact line anchors are in **Appendix A** (referenced by symbol in
each WU; re-find by symbol if lines drift).

## How to use
- Do WUs in dependency order. After each: gates — `uv run pytest --tb=short -q` (0 fail) ·
  `ruff check src/ tests/` (0, incl. E501) · `uv run zuban check`. GUI WUs also `cd tools/gui &&
  npm run lint && npm run typecheck`.
- All model writes via MCP tools (never hand-edit). Backend code changes need a backend restart;
  MCP-surface changes need a Claude session restart.
- Tick `[x]` + append a Progress Log line when a WU's Accept criteria pass.

---

## Phase P0 — Foundations

### WU-0.1 — `identity_scope`: ontology-authoritative, UI-derived
**Files:** `EntityTypeInfo` (ontology_types); `_parse_entity_types` (diagram_ontology_loader);
datatype ontology→UI merge `_apply_ontology_fields()` / `_merge_ontology_into_config` (datatype
`__init__`); `DiagramOwnEntityTypeUiConfig` (diagram_type_config).
**Do:**
1. Add to `EntityTypeInfo`: `identity_scope: Literal["diagram","workspace"] = "diagram"` and
   `id_prefix: str | None = None`. Parse both in `_parse_entity_types`:
   `identity_scope=str(cfg.get("identity_scope") or "diagram")`,
   `id_prefix=(str(cfg["id_prefix"]) if cfg.get("id_prefix") else None)`.
2. **The ontology is authoritative.** UI metadata (`DiagramOwnEntityTypeUiConfig.identity_scope` +
   `id_prefix`) is **derived** from the merged ontology entity-type, not configured independently — set
   it in the datatype module's ontology→UI merge so every catalog view reports the same values.
3. **Startup validation** (extend `src/application/startup_validation.py`): every `identity_scope:
   workspace` type must declare an `id_prefix` that (a) is present, (b) matches the accepted prefix
   grammar (uppercase letters, as `TYPE@…`), (c) is unique across all workspace-identified types;
   `diagram`-scoped types must not require one.
**Accept:** `classifier`'s `identity_scope=="workspace"` and `id_prefix=="CLF"` in **every** catalog
view; a `workspace` type lacking `id_prefix`, or a duplicate prefix, fails startup validation; absent
`identity_scope` → `"diagram"`.
**Tests:** `tests/domain/test_identity_scope_authoritative.py` (consistency across views);
`tests/application/test_startup_validation_id_prefix.py`.
**Deps:** none.

### WU-0.2 — Declare classifier workspace identity
**Files:** datatype `ontology.yaml` (entity_types.classifier).
**Do:** add under `classifier:`:
```yaml
identity_scope: workspace
id_prefix: CLF
```
**Accept:** loaded datatype module reports classifier as `workspace` with `id_prefix=="CLF"`; startup
validation passes.
**Tests:** extend `tests/diagram_types/test_datatype_taxonomy.py`.
**Deps:** WU-0.1.

### WU-0.3 — `IdentifierAllocator` + allocate endpoint + batch normalize
**Files:** new `src/application/identifier_allocator.py` (protocol); infra impl wrapping the existing
mint algorithm (grep `def _mint`/`generate_artifact_id`/`new_artifact_id`); new REST router
`src/infrastructure/gui/routers/identifiers.py`; new
`src/infrastructure/write/artifact_write/diagram_entity_identity.py`
(`normalize_diagram_entity_identities`).
**Do:**
```python
class IdentifierAllocator(Protocol):
    def allocate(self, *, prefix: str, name_hint: str | None) -> str: ...   # TYPE@epoch.random.slug
```
1. Default impl reuses the canonical mint algorithm. The **prefix is resolved only from the
   entity-type's `id_prefix` metadata** (WU-0.1); reject any caller-supplied/arbitrary prefix. Slug
   derives from `name_hint` (kebab/normalized).
2. `POST /api/identifiers/allocate {owner_kind, diagram_type, entity_type, name_hint}` →
   `{"id": "CLF@1781700000.AbCd12.customer"}`. **Non-persistent allocation** (no durable reservation).
   Resolve `prefix` from `entity_type`'s `id_prefix` metadata (classifier → `CLF`).
3. `normalize_diagram_entity_identities(diagram_type, diagram_entities, diagram_connections, bindings)`:
   for `workspace`-identity entities lacking a valid id (or carrying a temp ref), allocate and **rewrite
   the whole payload atomically** (entity id + dt-* endpoints + bindings + self-references).
**Accept:** endpoint returns a grammar-valid `CLF@…` id resolved from metadata; batch normalize
allocates + rewrites all refs; caller-supplied prefix rejected.
**Tests:** `tests/application/test_identifier_allocator.py`, `tests/infrastructure/gui/test_allocate_endpoint.py`.
**Deps:** WU-0.1.

### WU-0.3b — Route existing artifact creation through the allocator (bounded consolidation)
**Files:** the backend create paths for model entities, diagrams, documents, GARs (grep the call sites
of the existing mint algorithm); the classifier path lands in WU-1.1.
**Do:** make each existing create operation **delegate** id minting to `IdentifierAllocator` instead of
calling the mint algorithm directly. **No API redesign** — operations still allocate implicitly; they
just call the allocator. **Groups are out of scope** (keep their own grammar; do not claim allocator
use). This makes the PLAN's "system-wide source" true (PLAN §D21).
**Accept:** entity/diagram/document/GAR creation produces ids via the allocator; behaviour unchanged
(ids still grammar-valid, unique); group creation untouched.
**Tests:** `tests/infrastructure/write/test_allocator_consolidation.py` (one delegation test per path).
**Deps:** WU-0.3.

### WU-0.4 — Canonical workspace-id extraction (slugged, bare)
**Files:** `extract_diagram_entities` (_diagram_entity_extraction); call sites in `_service_incremental`
/ `scan_mount`.
**Do:** make the synthetic id depend on the entity-type's `identity_scope` (resolved via module catalog):
```python
if scope == "workspace":
    artifact_id = local_id          # bare canonical CLF@epoch.random.slug
else:
    artifact_id = f"{diag.artifact_id}#{entity_type}/{local_id}"
```
`host_diagram_id=diag.artifact_id` stays set in both branches. Keep `entities_by_diagram[host]`
membership working (keys on host_diagram_id).
**Accept:** classifier `CLF@1.ab.customer` in diagram `DT-X` is indexed under `artifact_id ==
"CLF@1.ab.customer"`, `host_diagram_id == "DT-X"`; `diagram`-scoped entities unchanged.
**Tests:** `tests/infrastructure/artifact_index/test_workspace_identity_extraction.py`.
**Deps:** WU-0.1, WU-0.2.

### WU-0.5 — `CandidateRepository` (settled overlay; the central seam)
**Files:** new `src/application/candidate_repository.py`.
**Do:** implement the PLAN §2.4 protocol with **one** settled architecture:
```python
@dataclass(frozen=True)
class _Overlay:
    additions: Mapping[str, EntityRecord | ConnectionRecord | DiagramRecord]  # parsed adds/replacements (by id)
    deletions: frozenset[str]                                                  # explicitly deleted ids

class CandidateRepository(Protocol): ...   # get_entity/list_entities/get_diagram/list_diagrams/scope_for_path

def committed_repository(repo_roots) -> CandidateRepository: ...        # filesystem-derived, empty overlay
def candidate_with(base, *, changed_diagrams=(), deleted_ids=frozenset()) -> CandidateRepository: ...
```
Semantics: committed filesystem view + additions/replacements − deletions; a multi-file transaction
produces **one** overlay; **never mutate the live SQLite index during verification**. Full-repo
verification uses the empty-overlay committed view — identical semantics to staged.

**Aggregate diagram replacement (PLAN §2.4) — `candidate_with` takes whole changed/deleted diagrams,
not hand-built child deletions.** For each entry in `changed_diagrams` (a parsed `DiagramRecord` + its
children) and each id in `deleted_ids` that names a diagram, the overlay must, per affected diagram:
1. suppress the committed diagram record;
2. suppress **every** committed diagram-owned entity/connection whose `host_diagram_id` is that diagram
   (use `_MemStore.entities_by_diagram` / `connections_by_diagram`);
3. for a replacement, insert the new diagram record and re-extract its children via the WU-0.4
   identity-aware extractor (`extract_diagram_entities`/`extract_diagram_connections`).
A single-file edit is the one-changed-diagram case; a batch reuses the same overlay.
**Accept:** within one transaction adding classifier `CLF@…` to diagram A and referencing it from B,
`get_entity("CLF@…")` returns it **before** any index refresh; deleting it returns `None` despite the
live index; replacing a diagram that previously owned `CLF-A`+`CLF-B` with one owning only `CLF-A` makes
`get_entity("CLF-B")` return `None` **without** `CLF-B` being in `deleted_ids`; deleting the host diagram
removes all its children.
**Tests:** `tests/application/test_candidate_repository.py` — cover: classifier removed from a replaced
diagram; classifier retained same id; new classifier added; full host-diagram deletion; replacement
that changes local connections but keeps classifier ids.
**Deps:** WU-0.4.

### WU-0.6 — Generic workspace-id uniqueness (E335), format & operational immutability
**Files:** new **generic** `RepositoryVerificationContribution` for E335 (registered centrally, not in
the datatype module — see WU-0.7b); write-path format/immutability in `diagram_edit` / `diagram` create.
**Do:**
1. **E335** — a **generic, per-transaction** repository contribution (PLAN §3 / §D20): scan all
   `identity_scope: workspace` entities in the candidate; two sharing an id → E335. Generic because
   identity is a generic contract; it must **not** live in the datatype module.
2. **Format** (write-time): a workspace id must match the type's prefix grammar
   (`^CLF@[0-9]+\.[A-Za-z0-9_-]+\..+$` for classifier).
3. **Immutability by set comparison** (PLAN §2.1/§D10): on a diagram write, compare submitted candidate
   workspace ids vs committed for that diagram's owned children — retained=edit, absent=removal
   (→ reference-impact E334, WU-3.1), new=creation (grammar + uniqueness). **No edit-id command.** Never
   match old/new by position/label/content.
**Accept:** duplicate workspace id → single E335 once per transaction (not per diagram); malformed id
rejected at create; a classifier's id cannot change on edit.
**Tests:** `tests/application/verification/test_workspace_identity_rules.py`.
**Deps:** WU-0.4, WU-0.5, WU-0.7b.

### WU-0.7 — Per-diagram verification-contribution hook
**Files:** new `src/domain/diagram_verification.py` (`BaseDiagramVerificationContext`,
`DiagramVerificationContribution[ProjectionT]` with default `run`); `DiagramTypeModule`
(add `diagram_verification_contributions()`); `DiagramTypeBase` (default `()`); central verifier
(`_verify_diagram_file` / `check_diagram_references_scoped`).
**Do:**
1. Define the protocol per PLAN §2.5 (generic; **no datatype import**).
2. In the central verifier, build a `CandidateRepository` for the file under verification and a
   `BaseDiagramVerificationContext`, resolve the diagram's module, and:
   ```python
   for contribution in module.diagram_verification_contributions():
       contribution.run(candidate, context, result)
   ```
   **Remove** the `if ontology_catalog is not None: check_datatype_backing_consistency(...)` block and
   the `_verifier_rules_datatype` import.
3. **Registry guard test:** every contribution's `diagnostic_codes` unique across modules, non-empty.
**Accept:** non-datatype diagrams verify unchanged; central verifier imports no datatype symbol;
contributions receive a `CandidateRepository`, never the store port or SQLite.
**Tests:** `tests/application/verification/test_verification_contribution_hook.py`.
**Deps:** WU-0.5.

### WU-0.7b — Per-transaction repository-contribution hook (runs once per transaction)
**Files:** `src/domain/diagram_verification.py` (`RepositoryVerificationContext`,
`RepositoryVerificationContribution[ProjectionT]`); `DiagramTypeModule`
(`repository_verification_contributions()` default `()`); a **central registry** of generic repository
contributions (for E335); the common mutation boundary (the verify step every write calls) + the
full-repository verify entry (`verify_all`).
**Do:** per PLAN §2.5 second hook. The boundary runs, **once per candidate transaction**: every generic
repository contribution (E335) **plus** each module's `repository_verification_contributions()` (E334
from datatype, WU-3.1). Full verification runs the same set once. A repository contribution receives
`RepositoryVerificationContext{committed, candidate, location}` — never the store port/SQLite.
**Accept:** E335/E334 emit **exactly once** per transaction and once in full verification (no per-diagram
duplication; not skipped when no datatype diagram is the anchor); generic E335 fires for any
workspace-identified type, not only classifiers.
**Tests:** `tests/application/verification/test_repository_contribution_hook.py` (incl. a full-verify
no-duplication test).
**Deps:** WU-0.5.

### WU-0.8 — Move E330/E331 behind contributions (parity)
**Files:** new `src/diagram_types/datatype/_contributions.py`; datatype `__init__`
(`diagram_verification_contributions`). Keep `_verifier_rules_datatype` / `datatype_consistency` as the
rule body, called from the contribution.
**Do:** wrap the existing backing check as a `DiagramVerificationContribution` with
`diagnostic_codes=("E330","E331")`, sharing the projection compiler added in WU-1.3 (for now its
`compile_projection` may return only what E330/E331 need; merge with E332/W333 in WU-1.5 so the
projection is compiled **once**).
**Accept:** **parity** — existing E330/E331 suite green unchanged.
**Tests:** existing datatype backing tests stay green; add `tests/diagram_types/test_contribution_registration.py`.
**Deps:** WU-0.7.

---

## Phase P1 — Resolution, projection & rendering

### WU-1.1 — Mint classifier ids via the allocator
**Files:** `diagram` create (`_build_model_backed`); MCP create/edit paths; use WU-0.3 allocator +
`normalize_diagram_entity_identities`.
**Do:** when a classifier lacks a valid `CLF@…` id (or carries a temp ref), allocate via the allocator
and rewrite the local entry + dt-* endpoints + bindings in the same payload. Existing ids preserved.
**Accept:** create with an id-less classifier yields a `CLF@epoch.random.slug` id; endpoints reference
the minted id.
**Tests:** `tests/infrastructure/write/test_classifier_id_minting.py`.
**Deps:** WU-0.3, WU-0.6.

### WU-1.2 — Discriminated-union attribute schema + E336
**Files:** datatype `ontology.yaml` (classifier `attributes` item schema); datatype contribution (E336).
**Do:**
1. Express the item schema as the PLAN §2.2 `oneOf` (two closed branches; `const` kind; non-empty
   `name`; id pattern; `additionalProperties: false`) in `ontology.yaml` — documents intent.
2. **E336 is a mandatory datatype per-diagram contribution, regardless of generic-validator support.**
   Do not make correctness depend on the unconfirmed generic `oneOf`/`const` path (diagram-entity
   schemas are largely exposed as authoring guidance, not enforced by the repo JSON-Schema validator).
   The contribution checks each attribute `type`: exactly one of the two branches, correct keys for the
   `kind`, non-empty `name`, id matching the pattern, no extra keys. This gives stable diagnostic-code
   behaviour. (Wire it via the shared projection in WU-1.5.)
**Accept:** `{kind:primitive,name:String}` and `{kind:classifier,id:CLF@1.ab.x}` pass;
`{kind:primitive,id:…}`, `{kind:classifier,name:…}`, empty/missing `type`, extra keys, or bad id pattern
→ **E336** (independent of any generic-schema behaviour).
**Tests:** `tests/diagram_types/test_datatype_attribute_schema.py`.
**Deps:** WU-0.8.

### WU-1.3 — `DatatypeVerificationProjection` compiler
**Files:** new `src/diagram_types/datatype/_projection.py`.
**Do:**
```python
@dataclass(frozen=True)
class ClassifierDefinition: type_id: str; label: str; kind: str; scope: str; status: str; host_diagram_id: str
@dataclass(frozen=True)
class AttributeTypeUsage: diagram_id: str; classifier_local_id: str; attr_name: str
@dataclass(frozen=True)
class DatatypeVerificationProjection:
    classifiers_by_id: Mapping[str, ClassifierDefinition]
    classifier_ids_by_name: Mapping[str, tuple[str, ...]]
    usages_by_id: Mapping[str, tuple[AttributeTypeUsage, ...]]

def compile_projection(candidate: CandidateRepository, ctx: BaseDiagramVerificationContext) -> DatatypeVerificationProjection: ...
```
Scope/status inherited from each classifier's host diagram (look up host in `candidate`). Build
`usages_by_id` by scanning every candidate datatype diagram's classifier attributes for
`{kind:classifier,id}`.
**Accept:** projection lists classifiers across both repos with correct scope/status; usages populated;
compiled from `CandidateRepository` only (no SQLite).
**Tests:** `tests/diagram_types/test_datatype_projection.py`.
**Deps:** WU-0.5, WU-0.8.

### WU-1.4 — `TypeResolver` (scope/status)
**Files:** new `src/diagram_types/datatype/_type_resolver.py`.
**Do:** `resolve(type_ref, referencing_scope, projection) -> Resolved | Unresolved`; `label_for(id)`.
Rules per PLAN §2.3: primitive by name; classifier by id; engagement→engagement+enterprise,
enterprise→enterprise-only; status conformity vs the referencing diagram's baseline status.
**Accept:** the scope/status matrix resolves correctly; out-of-scope/status → `Unresolved` with reason.
**Tests:** `tests/diagram_types/test_type_resolver.py`.
**Deps:** WU-1.3.

### WU-1.5 — E332 + W333 contributions (shared projection)
**Files:** datatype `_contributions.py` (merge with WU-0.8 so **one** `compile_projection` feeds
E330/E331/E332/W333/E336).
**Do:**
- **E332** (`("E332",)`): per attribute, `TypeResolver.resolve`; `Unresolved` → `Issue(ERROR,"E332",…,
  details={classifier, attr_name, type_ref, reason, candidates})`. No `actions`.
- **W333** (`("W333",)`): warn only about classifiers **defined in the verified diagram** whose
  normalized name collides (via `classifier_ids_by_name`) with another in-scope classifier or a
  primitive. Advisory.
**Accept:** E332 cases (unknown primitive / missing id / out-of-scope / status-violation) fire; W333
fires only on the defining diagram, never on a mere referencer; projection compiled once per diagram.
**Tests:** `tests/diagram_types/test_datatype_type_rules.py`.
**Deps:** WU-1.4.

### WU-1.6 — `PreparedDatatypeDiagram` render-prep + label resolution
**Files:** new generic render-prep seam on `DiagramTypeModule` (`prepare_render_model(...)`) +
`DiagramTypeBase` pass-through default; datatype impl + `renderer.render_body` / `_render_classifier`;
render call site (grep `renderer.render_body`).
**Do:** datatype `prepare_render_model` builds `PreparedDatatypeDiagram` resolving each attribute
`type`: primitive→name; classifier→`label_for(id)` (fallback to id if unresolved, so breakage is
visible). **The resolution source is lifecycle-appropriate (PLAN §2.6 / §D23):** during create/edit
preview and commit, resolve from the **current `CandidateRepository`** (so a classifier defined *and*
referenced in the same write renders its label, not its id); for later read-only re-rendering, the
committed read model may be used. Share a pure classifier-resolution helper with the verification path.
Renderer consumes the prepared model and stays I/O-free; wire the call site to prepare-then-render and
pass the right source per lifecycle.
**Accept:** **(a) rename contract** — define `Order` referenced elsewhere; render referencer → `Order`;
rename label → re-render referencer **without editing it** → new label. **(b) same-write contract** —
create a classifier **and** reference it in one submitted diagram; generated PUML shows its **label, not
its id** (resolved via the candidate, before any index refresh).
**Tests:** `tests/diagram_types/test_render_prep_label_resolution.py` (both contracts).
**Deps:** WU-1.4, WU-0.5.

---

## Phase P2 — Usage indexing & discovery

### WU-2.1 — `attribute_type_refs` overlay
**Files:** `SCHEMA_SQL` (_sqlite_schema); `_SqliteStore` upsert/delete; `_service_incremental`
(`apply_diagram_change`, `_delete_diagram_entities`); composition root (datatype-specific contributor —
PLAN §D5, **not** a protocol method).
**Do:** add table + `(type_id)` index:
```sql
CREATE TABLE IF NOT EXISTS attribute_type_refs (
  diagram_id TEXT NOT NULL, classifier_local_id TEXT NOT NULL, attr_name TEXT NOT NULL, type_id TEXT NOT NULL,
  PRIMARY KEY (diagram_id, classifier_local_id, attr_name));
CREATE INDEX IF NOT EXISTS idx_attr_type_refs_type ON attribute_type_refs(type_id);
```
Populate from datatype classifier attributes (`{kind:classifier,id}`) on diagram upsert; delete on
diagram delete. Register the contributor at the composition root.
**Accept:** edit updates rows; delete removes them; rebuilt-from-files == incremental.
**Tests:** `tests/infrastructure/artifact_index/test_attribute_type_refs.py`.
**Deps:** WU-1.2.

### WU-2.2 — Generic port lookups
**Files:** `ArtifactSearch` (ports); index impl (`service` + `_sqlite_queries`).
**Do:** add (generic over workspace-identity entities; no datatype vocabulary):
```python
def find_entity_by_workspace_id(self, artifact_id, *, scope="both") -> EntityRecord | None: ...
def find_entities_by_name(self, name, *, artifact_type=None, scope="both") -> list[EntityRecord]: ...
def diagrams_referencing_type_id(self, type_id) -> list[tuple[str,str,str]]: ...
```
**Accept:** correct rows; name match normalized-exact.
**Tests:** `tests/infrastructure/artifact_index/test_type_lookup_queries.py`.
**Deps:** WU-2.1.

### WU-2.3 — `DatatypeTypeCatalog` + REST **and** MCP discovery
**Files:** new `src/diagram_types/datatype/_type_catalog.py` (built from committed read model;
generation token); REST `routers/diagram_types.py`; MCP — prefer extending an existing generic query
tool (else a focused read tool); `artifact_authoring_guidance` (datatype contract text).
**Do:**
1. REST `GET /api/diagram-types/datatype/types?query=&scope=&kind=&limit=&cursor=&diagram_id=` →
   `{generation, primitives:[…], classifiers:[{type_id,label,kind,scope,host_diagram_id}…], next_cursor}`,
   filtered to the `diagram_id`'s visibility (PLAN §2.3). Plus `GET …/type-usages?type_id=`.
2. **MCP discovery — add a focused read tool now** (decided; not "if one fits"): the required contract
   (datatype-specific fields, visibility filter, pagination, generation token) is not naturally
   expressible by the existing generic artifact queries, and a focused tool avoids REST/MCP drift. Back
   it by the **same application query** that powers the REST endpoint (one query, two transports). Keep
   the MCP tool count discipline (memory) — one small tool. `artifact_authoring_guidance` explains the
   contract but does **not** enumerate the catalog.
**Accept:** discovery returns visible types only, paginated, with a generation token; the MCP tool
returns the same shape via the shared application query; structured-output + tool-description tests pass.
**Tests:** `tests/infrastructure/gui/test_type_discovery_endpoint.py`,
`tests/infrastructure/mcp/test_type_discovery_tool.py`.
**Deps:** WU-1.4, WU-2.2.

---

## Phase P3 — Lifecycle (removal protection)

### WU-3.1 — Reference-impact (E334) as a per-transaction repository contribution
**Files:** datatype `_contributions.py` — E334 implemented as a **`RepositoryVerificationContribution`**
(WU-0.7b), `diagnostic_codes=("E334",)`, registered via the datatype module's
`repository_verification_contributions()`; the common mutation boundary feeds it
`RepositoryVerificationContext{committed, candidate, location}`; delegation only at entry points
(`diagram_edit`, `cascade_delete` host/bulk/collection, promotion conflict replacement, migration/import).
**Do:**
1. **E334** (per-transaction, datatype): compare committed vs candidate workspace ids → removed ids;
   find candidate references still targeting removed ids and not also removed/retargeted; emit **one
   E334 per removed classifier** listing all affected usages; **suppress** the derivative E332 for those
   exact `(removed_id, usage)` pairs (PLAN §D12) — coordinate the suppression set with the per-diagram
   E332 (WU-1.5) so they agree. Runs **once per transaction** (WU-0.7b), not per diagram.
2. **No per-writer removal checks.** Entry points only construct the candidate transaction (changed/
   deleted diagrams via `candidate_with`, which applies aggregate replacement, WU-0.5) and call the
   common verification; protection is automatic wherever verification runs. **No "delete anyway".**
**Accept:** delete a referenced classifier → single E334 (no E332 spam, no per-diagram duplication);
remove classifier + refs together → ok; dropping a classifier from a *replaced* diagram (not in an
explicit deletion set) still triggers E334 via aggregate replacement; each removal route (edit,
direct/bulk/collection delete, promotion replacement, import) is guarded.
**Tests:** `tests/application/write/test_reference_impact.py` + **delegation tests** per route proving
the entry point invokes common candidate verification (not a duplicated rule).
**Deps:** WU-0.7b, WU-1.5, WU-2.2.

---

## Phase P4 — Promotion

### WU-4.1 — Index workspace classifiers in promotion planning
**Files:** `_promote_planning` (enterprise indices), `_promote_plan_content` (`plan_diagrams`).
**Do:** include `workspace`-scoped classifiers so same-id (idempotent) and same-name-different-id
(advisory, non-blocking) are detected (PLAN §6).
**Accept:** re-promote same id = no-op; name-clash different id = advisory.
**Tests:** `tests/infrastructure/write/test_promote_classifier_indexing.py`.
**Deps:** WU-0.4.

### WU-4.2 — Two-stage closure + staged enterprise-only verify
**Files:** `promote_to_enterprise` (`plan_promotion`, `PromotionPlan`); new `promote_type_closure.py`;
the execute path (final staged verify).
**Do:**
1. Stage 1: derive `referencing diagram → classifier id → owning datatype diagram` closure; add
   required host diagrams to the plan with reasons (`type_closure_additions`); broken-closure exclusion
   is blocking.
2. After conflict resolutions, build a **resolved promotion candidate** and **recompute** closure.
3. Verify the staged **enterprise-only** `CandidateRepository` with diagrams:
   `collect_verification_errors(staged_enterprise_root, include_diagrams=True)`. The enterprise
   candidate must **not** resolve engagement classifiers (don't borrow from the mounted engagement).
4. Publish only on success.
**Accept:** closure proposed with reasons; broken-closure exclusion blocks; conflict-resolution dropping
a required id is caught by the staged enterprise verify; post-promotion engagement refs resolve with no
rewrite.
**Tests:** `tests/infrastructure/write/test_promote_type_closure.py`.
**Deps:** WU-2.2, WU-3.1.

---

## Phase P5 — Authoring surface (GUI/MCP)

> **Absorbs GUI-plan F2 + F4** (decided): the closed-combobox rework touches `ClassifierCard.vue` /
> `DatatypeEditor.vue`, so the two trivial editor improvements ride this phase rather than a separate
> pass. GUI-plan F3 rides this plan's verifier hook (see WU-1.5-adjacent note) and F5 is the post-P5
> capstone — tracked in `TASKS-gui-correctness-and-assurance.md`.

### WU-5.1 — Frontend tagged-ref model
**Files:** `useDatatypeModel.ts` (`Attribute`); regen types after schema change.
**Do:**
```typescript
export type AttrTypeRef = { kind:'primitive'; name:string } | { kind:'classifier'; id:string }
export interface Attribute { name:string; type?:AttrTypeRef; multiplicity?:string; is_id?:boolean; is_unique?:boolean }
```
**Accept:** round-trips the tagged ref; `npm run typecheck` passes.
**Deps:** WU-1.2.

### WU-5.2 — Closed combobox + allocate-on-add
**Files:** `ClassifierCard.vue` (type field), replace `ClassifierCard.helpers.ts:buildTypeOptions`;
reuse `EntitySearchInput.vue` typeahead pattern; call `POST /api/identifiers/allocate` for "+ New
classifier".
**Do:** closed combobox: options = primitives ∪ visible classifiers (grouped Primitives / This diagram /
Engagement / Enterprise) from the discovery endpoint for the current `diagram_id`; display labels, store
the tagged ref; **no free commit**. "+ New classifier" allocates a `CLF@…` id via the endpoint, adds the
local classifier, selects it. **The id is never shown as editable.**
**Accept:** unknown value cannot commit; classifier choice stores `{kind:classifier,id}`; primitive
stores `{kind:primitive,name}`; displayed label follows the referent's current name.
**Tests:** `tools/gui/src/ui/diagram-types/datatype/__tests__/ClassifierCard.spec.ts`.
**Deps:** WU-5.1, WU-2.3, WU-0.3.

### WU-5.3 — Editor wiring + where-used + types regen
**Files:** `DatatypeEditor.vue`; verify `ConnRow.vue` endpoints unaffected; run
`uv run tools/generate_types.py` → `tools/gui/src/domain/types.generated.ts`.
**Do:** pass `diagram_id`/scope into ClassifierCard; show "N usages" from `type-usages`; regen TS types.
**Accept:** editor loads visible types; usages hint shown; lint + typecheck pass.
**Deps:** WU-5.2.

### WU-5.4 — Absorb GUI-plan F2 (relabels) + F4 (notes)
**Files:** `ClassifierCard.vue` / `ConnRow.vue` / `DatatypeEditor.vue`; datatype `ontology.yaml`
(classifier `note`; relation `note`); renderer (`_render_classifier` + connection render); regen types.
**Do (folds GUI-plan WU-F2 + WU-F4):**
- **F2 (labels only):** rename UI labels to **Multiplicity** (attribute) and **Source cardinality /
  Target cardinality** (relation), with placeholder examples (`1`, `0..1`, `1..*`, `*`) + tooltips. No
  data-model change.
- **F4 (notes):** add optional `note: string` to the classifier ontology (and relation, for symmetry);
  reuse the existing `NoteSection.vue` pattern (as in Activity/Sequence editors); render as a PlantUML
  `note on` the element.
**Accept:** the three cardinality/multiplicity fields are clearly labelled with examples; classifiers and
relations accept a note that renders in PUML; types regenerated; lint + typecheck pass. **On completion,
tick GUI-plan F2 and F4.**
**Tests:** extend `ClassifierCard.spec.ts`; `tests/diagram_types/test_datatype_renderer.py` (note render).
**Deps:** WU-5.2.

> **GUI-plan F3** (datatype `unique_constraints` + **mandatory verifier extension**) is implemented as a
> **datatype per-diagram verification contribution** on this plan's hook (WU-0.7), *not* the old central
> wiring. It is independent of type resolution but shares the contribution mechanism; schedule after
> P0/P1 (hook + projection exist). Its check: every constraint attribute-name exists on the classifier,
> no duplicate-name entries, no empty tuples. Track the checkbox in the GUI plan; build it here-style.
> **GUI-plan F5** (editor UX consolidation) is the capstone **after** P5 + F2 + F3 + F4.

### WU-6.1 — Conservative migration, refuse-on-ambiguity
**Files:** new `tools/migrate_datatype_type_refs.py`; `diagram-format-version` handling in the diagram
parser/formatter.
**Do (PLAN §7 / §D15):**
1. **Dry-run** scans + emits a machine-readable JSON report (per-attribute: convertible vs ambiguous
   with reason: primitive-shadow / multi-match / out-of-scope).
2. Ambiguities resolved via an explicit mapping file or manual fixes. **Apply is unavailable while any
   unresolved entry remains** (no schema duality).
3. Apply: allocate `CLF@…` ids for all classifiers (via the allocator) + update dt-* endpoints/bindings;
   convert **every** attribute string→tagged ref; stamp `diagram-format-version: 2`.
4. Verify the **complete candidate repository**; publish atomically; then enable blocking validation
   (WU-7.1). Covers ENG-ARCH-REPO + ENG-001.
**Accept:** dry-run lists every conversion + every refusal; apply blocked while unresolved remain;
applied repo has 0 bare-string types; candidate verify passes pre-publish.
**Tests:** `tests/tools/test_migrate_datatype_type_refs.py` (unique match / primitive-shadow / multi-match
/ out-of-scope / blocked-apply).
**Deps:** all of P1–P3.

---

## Phase P7 — Switch-on

### WU-7.1 — Enable blocking validation
**Files:** rule registrations; feature flag in `settings.py` (E042 precedent).
**Do:** flip E332/E334/E335/E336 inert→blocking once the migration report shows no unresolved legacy
values.
**Accept:** with clean data, an unresolved type blocks a write; flag off → non-blocking.
**Tests:** `tests/application/verification/test_type_validation_switch.py`.
**Deps:** WU-6.1.

---

## Phase P8 — Self-model

### WU-8.1 — Update the self-model (MCP only)
**Do:** PLAN §8 edits via `arch-repo-write`, motivation-first, stop-gate after motivation. Resolved
component ids (confirmed 2026-06-20; re-verify before editing):
- **SQLite Indexer** — `APP@1712870400.JOmFWy.sqlite-indexer` (edit desc: derives type-reference usages;
  **not** the acceptance authority).
- **Repository Promotion Service** — `SRV@1712870400.Uv9Wx9.repository-promotion-service` (derives
  promotion type-dependency closure); realizing component **Promotion Engine**
  `APP@1776633693.tIMxjr.promotion-engine`.
- **Diagram Authoring Service** — `SRV@1776633088.AIGnSY.diagram-scaffolding-service` (allocates ids via
  the allocator; enforces immutability); realizing component **Diagram Scaffolder**
  `APP@1776633697.SCKD2U.diagram-scaffolder`.
- **NEW APP** *Identifier Allocation Service* — the `IdentifierAllocator` code unit; aggregated by
  `APP@1712870400.yNhgdh` *Module Catalog* or wired to the authoring/scaffolder services as appropriate
  (pair-check at authoring).
Other anchors already in PLAN §8 (`REQ@…Ee3Ff3`, `REQ@…sbkuwf`, `REQ@…aDohcf`, `SRV@…vQKsM9`,
`FNC@…eAkU8w`, `FNC@…6PI0kV`, `BOB@…SQXLsh`, `APP@…ca3vm7`, `APP@…n8Pikk`, `APP@…yNhgdh`,
`BOB@…7gJz0U`).
**Accept:** `artifact_verify(repo_scope="engagement", return_mode="full")` → 0 errors;
`artifact_save_changes`.
**Deps:** code implemented (model describes reality).

---

## Resume protocol
1. Read the Progress Log for the last ticked WU. 2. Re-confirm Appendix-A anchors by symbol. 3. Re-run
gates for a clean baseline. 4. Continue at the first unticked WU whose Deps are all ticked.

## Progress Log
- (none yet)

---

## Appendix A — Exact code anchors (snapshot 2026-06-20)

Re-find by symbol if lines drift.

**Domain / ontology**
- `EntityTypeInfo` — `src/domain/ontology_types.py:74-96` · `ConnectionTypeInfo` — `…:101-119`
- `_parse_entity_types` — `src/domain/diagram_ontology_loader.py:70-91` · `_parse_connection_types` — `…:106-123`
- `DiagramTypeUiConfig` — `src/domain/diagram_type_config.py:50-58` · `DiagramOwnEntityTypeUiConfig` — `…:32-48`
- `diagram_type_ui_config_from_mapping` — `…:60-79` · `_own_entity_ui_config_from_mapping` — `…:82-116`
- `DiagramTypeModule` — `src/domain/ontology_protocol.py:126-177` · `DiagramRenderer` — `…:100-124`
- `DiagramTypeBase` — `src/diagram_types/_base.py:16-106`
- `ModuleCatalog.all_diagram_entity_types/is_diagram_entity_type/get_diagram_type` — `src/domain/module_catalog.py:215-223, 119-123`

**Verification**
- `ArtifactVerifier.__init__` / `_runtime_catalogs` — `src/application/verification/artifact_verifier.py:66-92`
- `verify_diagram_file` / `_verify_diagram_file` — `…:193-237`
- `check_diagram_references_scoped` + datatype call site (remove) — `src/application/verification/artifact_verifier_rules.py:125-134, 172-175`
- `check_datatype_backing_consistency` — `src/application/verification/_verifier_rules_datatype.py:30-63`
- `corresponds` / `admissible_backing_kinds` — `src/application/verification/datatype_consistency.py:17-46`
- `Issue` / `Severity` / `VerificationResult` — `src/application/verification/artifact_verifier_types.py:8-47`
- `RuntimeCatalogs` — `src/application/runtime_catalogs.py:16-24`
- `collect_verification_errors` — `src/infrastructure/write/artifact_write/verify.py:84-97`

**Index**
- `extract_diagram_entities` (id line **71**) / `extract_diagram_connections` — `src/infrastructure/artifact_index/_diagram_entity_extraction.py:49-93, 139-170`
- `EntityRecord` — `src/domain/artifact_types.py:40-57`
- `SCHEMA_SQL` — `src/infrastructure/artifact_index/_sqlite_schema.py:3-82`
- `_SqliteStore.upsert_entity/upsert_connection` — `src/infrastructure/artifact_index/_sqlite_store.py:118-141, 159-174`
- query styles — `src/infrastructure/artifact_index/_sqlite_queries.py:77-90, 106-112, 135-163`
- `apply_diagram_change` / `_delete_diagram_entities` — `src/infrastructure/artifact_index/_service_incremental.py:250-269, 272-281`
- `_ScopeRegistry` methods — `src/infrastructure/artifact_index/_scope_registry.py:45-73`
- `ArtifactIndex.scope_for_path` / `shared_artifact_index` / `__init__` — `src/infrastructure/artifact_index/service.py:457-470, 67-86`
- `_MemStore` — `src/infrastructure/artifact_index/_mem_store.py:9-63` · `ArtifactSearch` — `src/application/ports.py:38-98`

**Write / promotion**
- `edit_diagram` (slot after prune ~L185, before format ~L187) — `src/infrastructure/write/artifact_write/diagram_edit.py:40-244`
- `create_diagram` (dup-check ~L210-234) — `…/diagram.py:125-234`
- `_collect/_merge/_prune` reference helpers — `…/diagram_references.py`
- `cascade_delete` — `…/cascade_delete.py:74-104, 149-189, 271-290`
- `validate_entity_unique/validate_diagram_unique/extract_friendly_slug` — `…/_artifact_deduplication.py:29-104`
- `plan_promotion` / `PromotionPlan` — `…/promote_to_enterprise.py:163-259, 96-110`
- `_build_enterprise_name_index` — `…/_promote_planning.py:40-57` · `plan_diagrams` — `…/_promote_plan_content.py:48-80`
- `check_promotion_schema_compatibility` — `…/promote_schema_check.py:136-149`
- MCP `artifact_edit_diagram` / `artifact_create_diagram` — `src/infrastructure/mcp/artifact_mcp/edit_tools.py:156-231`; `…/write/diagram.py:64-150`
- existing id-mint algorithm — grep `def _mint`/`generate_artifact_id`/`new_artifact_id`

**Datatype module / render**
- `render_body` / `_render_classifier` / `collect_references` — `src/diagram_types/datatype/renderer.py:115-149, 58-92, 155-182`
- `_DatatypeDiagramType` + ontology→UI merge — `src/diagram_types/datatype/__init__.py:126-193`
- render call site — grep `renderer.render_body` (≈ `diagram_builder.py:236-245`) · primitives — `config.yaml:23-29`

**GUI**
- `ClassifierCard.vue` type field — `tools/gui/src/ui/diagram-types/datatype/ClassifierCard.vue:107-121` · `buildTypeOptions` — `…/ClassifierCard.helpers.ts`
- `DatatypeEditor.vue` — `…/DatatypeEditor.vue:18-31` · `Attribute`/`Classifier` — `…/useDatatypeModel.ts:9-25` · `ConnRow.vue` — `…/ConnRow.vue:19-21, 91-117`
- reusable typeahead — `tools/gui/src/ui/components/EntitySearchInput.vue` · slot reg — `…/datatype/index.ts`
- ui-config endpoint — `src/infrastructure/gui/routers/diagram_types.py:28-36` · entity-display-search — `src/infrastructure/gui/routers/diagrams.py:276-283`
- types regen — `uv run tools/generate_types.py` → `tools/gui/src/domain/types.generated.ts`
