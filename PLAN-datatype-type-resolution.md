# PLAN — Datatype Attribute-Type Resolution (cross-diagram & cross-repo)

**Mode:** [DESIGN] → [PLAN] · **Status:** Draft for review (two review rounds integrated) ·
**Owner:** Michael Bauer · **Date:** 2026-06-20

> **Goal.** Make a datatype-diagram attribute's **`type`** a *resolved reference*, not free text. A
> field's type must resolve to a **built-in primitive** or a **user-defined classifier**
> (`class | datatype | enumeration | variant | primitive`) discoverable across datatype diagrams in the
> engagement repo and the enterprise repo, subject to scope/status visibility. Unknown/non-conformant
> types are blocking errors; the editor offers only known types (no free entry). Renaming a classifier
> must not rewrite referencing diagrams.
>
> Closes the gap surfaced by **WU-F1** of `PLAN-gui-correctness-and-assurance-completeness.md` (the
> combobox is local-only + free-text; nothing validates a type against a real type).

This PLAN states **goals, invariants, architectural contracts, accepted decisions, and acceptance
criteria**. The companion **`TASKS-datatype-type-resolution.md`** holds exact files, signatures,
implementation sequence, tests, and dependencies. Implement from TASKS; consult this for the *why*.

**Companion plans:** `PLAN-datatype-er-diagrams.md` (datatype module + DOB binding + E330/E331, which
this extends), `PLAN-gui-correctness-and-assurance-completeness.md` (Phase F / WU-F1, revised here),
`PLAN-meta-ontology-v2.md`, `PLAN-diagram-puml-editing.md`.

---

## 1. The four core concepts

1. **`identity_scope`** — a generic canonical-identity policy for diagram-owned entities. `classifier`
   is `workspace`-scoped: its id is canonical, parent-unqualified, and unique across the workspace.
2. **`CandidateRepository`** — the authoritative *proposed* repository state (committed filesystem view
   + the transaction's additions/replacements − deletions). **All acceptance-oriented verification
   resolves against it.** The SQLite index is never an acceptance authority.
3. **`DatatypeVerificationProjection`** — an immutable, read-only semantic projection compiled from a
   `CandidateRepository` for datatype verification only. Distinct from the render model and the
   discovery catalog.
4. **`IdentifierAllocator`** — one system-wide source of canonical artifact IDs (model entities,
   diagrams, documents, GARs, and workspace-identified diagram entities such as classifiers).

---

## 2. Invariants & contracts

### 2.1 Identity & references
- **Classifier id is `CLF@<epoch>.<random>.<slug>`** (the project's `TYPE@epoch.random.slug` grammar),
  **immutable** after allocation. The `slug` is an allocation-time readability hint, **never used for
  resolution or display**; a stale slug after rename is valid and expected. `label` is the current
  display name. Regex: `^CLF@[0-9]+\.[A-Za-z0-9_-]+\..+$`.
- **The `CLF` prefix is authoritative ontology metadata** (`entity_types.classifier.id_prefix: CLF`),
  never hardcoded. Startup validation requires every `identity_scope: workspace` type to declare a
  unique, grammar-valid `id_prefix`; `diagram`-scoped types need none. The allocator resolves the prefix
  **only** from this metadata.
- This single id is used for: attribute references, dt-* endpoints, bindings, point lookup, reverse
  usages, promotion/deletion analysis. `host_diagram_id` is ownership/location metadata only — it does
  **not** contribute to identity.
- **Rename is free**: references hold the id; labels are resolved live. **No reference cascade.**
- **ID immutability is operational, by set comparison** of the submitted candidate vs committed
  (§2.4): ids retained = edits; absent = removals; new = creations. There is **no "edit classifier id"
  command**; the GUI never exposes the id as editable; old/new are never matched by array position,
  label, or content.

### 2.2 Attribute `type` is a discriminated union
```yaml
type:
  oneOf:
    - { kind: {const: primitive}, name: {type: string, minLength: 1}, additionalProperties: false, required: [kind, name] }
    - { kind: {const: classifier}, id: {type: string, pattern: "^CLF@[0-9]+\\.[A-Za-z0-9_-]+\\..+$"}, additionalProperties: false, required: [kind, id] }
```
Two roles, two codes: **schema/E336** rejects *malformed reference shapes*; **E332** rejects
*well-formed references that do not resolve or violate scope/status*. (If the generic frontmatter-schema
validator cannot express `oneOf`/`const`, the union's well-formedness is enforced by a datatype
verification contribution emitting **E336** — TASKS WU-1.2.)

### 2.3 Scope/status visibility
A classifier **inherits repository scope and status from its host diagram**. Resolution:

| Referencing context | May resolve classifiers in |
|---|---|
| Engagement | engagement + enterprise |
| Enterprise | enterprise only |

Plus: **status conformity** (a baselined/approved diagram may reference only classifiers whose host
satisfies the existing baseline status policy); **duplicate workspace ids are errors** (E335), never
resolved by precedence; during staged verification the candidate version of a classifier replaces its
persisted version.

> **Single-engagement mount invariant.** A workspace mounts at most one engagement repository together
> with the optional enterprise repository, so engagement identity need not participate in visibility and
> the scope discriminator stays `Literal["engagement","enterprise","unknown"]`. If multi-engagement
> mounting is introduced later, repository context must be extended beyond this discriminator.

### 2.4 `CandidateRepository` (the central seam)
```python
class CandidateRepository(Protocol):
    def get_entity(self, artifact_id: str) -> EntityRecord | None: ...
    def list_entities(self, *, artifact_type: str | None = None) -> tuple[EntityRecord, ...]: ...
    def get_diagram(self, artifact_id: str) -> DiagramRecord | None: ...
    def list_diagrams(self, *, diagram_type: str | None = None) -> tuple[DiagramRecord, ...]: ...
    def scope_for_path(self, path: Path) -> Literal["engagement", "enterprise", "unknown"]: ...
```
Represents **committed filesystem repository + proposed additions/replacements − proposed deletions**.
Settled architecture (no alternatives left to implementers): a filesystem-derived committed view plus an
**immutable overlay** holding parsed additions/replacements and a deleted-id set; a multi-file
transaction produces **one** overlay; verification never mutates the live SQLite index. The committed
(empty-overlay) view is used for full-repository verification too — so staged and full verification have
**identical semantics**.

**Diagram replacement is an aggregate operation.** Replacing a diagram implicitly replaces *all* its
previous diagram-owned children. `candidate_with(...)` accepts **changed files / diagram replacements**
(not hand-built child deletions) and, per replaced diagram: (1) suppresses the committed diagram record;
(2) suppresses every committed diagram-owned entity/connection whose `host_diagram_id` is that diagram;
(3) inserts the replacement diagram; (4) re-extracts its children per `identity_scope`. Without this, a
classifier dropped from a replaced diagram would stay resolvable, E334 would not fire, and projection
compilation would mix old and new diagram contents.

### 2.5 Typed verification contributions (generic code never imports datatype)
```python
@dataclass(frozen=True)
class BaseDiagramVerificationContext:
    frontmatter: Mapping[str, object]
    allowed_connections: frozenset[str]
    referencing_scope: Literal["engagement", "enterprise", "unknown"]
    location: str
    ontology: OntologyCatalog
    diagram_types: DiagramTypeCatalog

ProjectionT = TypeVar("ProjectionT")

class DiagramVerificationContribution(Protocol[ProjectionT]):
    diagnostic_codes: tuple[str, ...]
    def compile_projection(self, candidate: CandidateRepository, context: BaseDiagramVerificationContext) -> ProjectionT: ...
    def verify(self, context: BaseDiagramVerificationContext, projection: ProjectionT, result: VerificationResult) -> None: ...
    # default-implemented orchestration:
    def run(self, candidate, context, result) -> None:
        self.verify(context, self.compile_projection(candidate, context), result)
```
The central verifier calls only `contribution.run(...)`; it never stores, imports, or inspects a
datatype projection. A `DiagramTypeModule` exposes
`diagram_verification_contributions() -> tuple[DiagramVerificationContribution, ...]`. Datatype's
**per-diagram** rules E330/E331/E332/W333/E336 share **one** module-owned projection compiler (compiled
once per diagram, not per rule).

**Two contribution scopes — per-diagram vs per-transaction.** E334 (reference impact) and E335
(workspace-id uniqueness) describe **repository/transaction-wide** conditions, not a single diagram, and
must run **exactly once per candidate transaction** (and once in full verification) — otherwise full
verification double-emits, or skips them when no datatype diagram is the anchor. So there is a second
hook:
```python
@dataclass(frozen=True)
class RepositoryVerificationContext:
    committed: CandidateRepository      # empty-overlay baseline
    candidate: CandidateRepository      # committed + transaction
    location: str

class RepositoryVerificationContribution(Protocol[ProjectionT]):
    diagnostic_codes: tuple[str, ...]
    def compile_projection(self, ctx: RepositoryVerificationContext) -> ProjectionT: ...
    def verify(self, ctx: RepositoryVerificationContext, projection: ProjectionT, result: VerificationResult) -> None: ...
    def run(self, ctx, result) -> None: self.verify(ctx, self.compile_projection(ctx), result)
```
- **E335 is generic** (registered centrally over `identity_scope: workspace` types — identity is a
  generic contract, not a datatype rule).
- **E334 is a datatype** `RepositoryVerificationContribution` (it needs the datatype usages projection).
- A `DiagramTypeModule` also exposes
  `repository_verification_contributions() -> tuple[RepositoryVerificationContribution, ...]`.
The common mutation boundary runs the central generic repository contributions **plus** each module's
repository contributions once per transaction.

### 2.6 Three role-separated datatype types
- **`DatatypeVerificationProjection`** — compiled from `CandidateRepository`; used by E332/W333/E336 and
  reference-impact (E334). `{classifiers_by_id, classifier_ids_by_name, usages_by_id}`.
- **`PreparedDatatypeDiagram`** — resolved display strings for the **pure renderer**, built from a
  **lifecycle-appropriate resolution source**: the current `CandidateRepository` during create/edit
  preview and commit (so a classifier defined *and* referenced in the same write renders its label, not
  its id); the committed read model for later read-only re-rendering. Shares a pure
  classifier-resolution helper with the verification path but stays a distinct type.
- **`DatatypeTypeCatalog`** — built from the committed read model for **paginated/searchable
  discovery** (GUI/MCP). Carries a read-model generation token.

Shared pure helpers are fine; the three lifecycle-specific models stay distinct.

### 2.7 `IdentifierAllocator`
```python
class IdentifierAllocator(Protocol):
    def allocate(self, *, prefix: str, name_hint: str | None) -> str: ...   # → TYPE@epoch.random.slug
```
The permitted `prefix` is resolved **only** from the entity-type's `id_prefix` metadata (§2.1); external
callers must not submit arbitrary prefixes. A classifier must obtain its id **before** the diagram is
saved (unsaved editor state already contains dt-* endpoints, self-references, inter-classifier
references, bindings, Vue keys), so a narrow endpoint `POST /api/identifiers/allocate {owner_kind,
diagram_type, entity_type, name_hint}` performs a **non-persistent allocation** — it mints one id with no
durable reservation; final candidate verification still enforces uniqueness. Batch clients (MCP/CLI/
import) may omit ids and rely on backend `normalize_diagram_entity_identities(diagram_type,
diagram_entities, diagram_connections, bindings)`, which allocates and rewrites the whole payload
atomically. Both paths use the same allocator.

**Authoritative scope (so "system-wide" is true, not aspirational):** all artifact-id creation —
model entities, diagrams, documents, GARs, and workspace-identified diagram entities (classifiers) —
delegates to this allocator. Existing backend create operations keep allocating implicitly; they simply
delegate (no API redesign). **Groups** keep their own id grammar and are *not* claimed to use this
allocator unless that policy is separately normalized.

---

## 3. Diagnostics

| Code | Severity | Fires when |
|---|---|---|
| Code | Contribution scope | Severity | Fires when |
|---|---|---|---|
| **E332** | per-diagram (datatype) | error | well-formed type reference does not resolve, or violates scope/status (reason ∈ unknown-primitive, missing-id, out-of-scope, status-violation) |
| **E336** | per-diagram (datatype) | error | attribute `type` is a malformed tagged reference (shape) — enforced by a **mandatory** datatype check, not dependent on generic-validator `oneOf` support |
| **W333** | per-diagram (datatype) | warning (advisory) | a classifier **defined in the diagram being verified** has a normalized name colliding with another in-scope classifier or a primitive; never blocks; a separate repo-wide lint reports the full picture |
| **E334** | per-transaction (datatype) | error | a transaction removes a classifier still referenced by candidate references not also removed/retargeted — **one issue per removed classifier, listing all affected usages; suppresses the derivative E332 for those exact (removed_id, usage) pairs** |
| **E335** | per-transaction (**generic**) | error | two workspace-scoped entities share an id (identity is a generic contract, not a datatype rule) |

E330/E331 (DOB backing) are unchanged per-diagram datatype rules; they move behind the contribution
hook (§2.5). Per-transaction contributions run **once** per candidate transaction and once in full
verification (§2.5).

---

## 4. Authoring & UX (revises WU-F1)

- **Closed combobox** displaying labels, storing the tagged reference; options = primitives ∪
  classifiers visible from the diagram's scope (grouped Primitives / This diagram / Engagement /
  Enterprise), from the discovery catalog (§2.6). No free commit.
- **"+ New classifier"** calls the allocator endpoint (§2.7) to mint a `CLF@…` id, adds the local
  classifier, and selects it — the only way to introduce a new type. The id is never user-editable.
- **Where-used hint** ("N usages") from reverse usages; drives the removal confirmation.
- Every write **revalidates** the submitted reference against the candidate verification (acceptance
  authority), regardless of what discovery returned.

---

## 5. Lifecycle (rename, removal, move)

- **Rename — free** (§2.1).
- **Removal protection lives at the common mutation boundary**, not in individual writers: every write
  builds a `CandidateRepository` (including deletions) and runs verification before publishing, so the
  reference-impact contribution (E334) guards **all** routes — diagram edit, direct/bulk/collection
  diagram deletion, administrative deletion, promotion conflict replacement, migration/import. Entry
  points construct candidate transactions; they do **not** implement datatype-specific removal checks.
  **No "delete anyway"** in ordinary flows; deliberate corruption (if ever needed) is a separate admin
  repair mechanism (out of scope).
- **Move as an operation is out of scope.** Identity is move-ready (host-independent id), but no move
  command ships here.

---

## 6. Promotion (two explicit stages, enterprise-only candidate)

1. **Initial planning** derives the proposed classifier-host closure (`referencing diagram → classifier
   id → owning datatype diagram`) and adds required host diagrams with reasons; users may exclude, but
   an exclusion that breaks closure is **blocking**.
2. After conflict resolutions, build a **resolved promotion candidate** and **recompute** closure.
3. **Verify the staged *enterprise-only* `CandidateRepository`** with diagrams included
   (`collect_verification_errors(staged_enterprise_root, include_diagrams=True)`). The enterprise
   candidate must **not** resolve engagement classifiers merely because the engagement repo is mounted
   in the live workspace — this catches a conflict-resolution that drops a required id.
4. Publish only if verification succeeds. No reference rewriting (ids are stable across the verbatim
   copy); the shared index is the registry — no separate enterprise type registry.

---

## 7. Cross-cutting (skill 🔴/🟡)

- **🔴 Security.** Type discovery and where-used are read-only; `/api/identifiers/allocate` is a
  **non-persistent allocation** (mints an id, no durable reservation, no side effects beyond the
  counter). All share the existing read trust model; the allocator rejects arbitrary prefixes (resolves
  only from `id_prefix` metadata). Closed combobox narrows free-text reaching the PUML emitter. No
  secrets, no new auth.
- **🔴 Data consistency.** Invariants — resolvability + scope/status conformity (§2.3), workspace-id
  uniqueness/immutability (§2.1) — are enforced **authoritatively against `CandidateRepository`** (§2.4)
  for every acceptance path, closing accept-invalid / reject-valid races. Multi-file transactions use
  the existing staged-verify + atomic-publish + rollback; the SQLite index is refreshed only after
  commit and never gates acceptance.
- **🔴 Migration.** Conservative, deterministic, atomic, and **refuses to apply while any ambiguity
  remains** (no temporary schema duality): dry-run → resolve ambiguities via an explicit mapping file /
  manual fixes → apply (unavailable while unresolved) mints `CLF@…` ids for all classifiers + updates
  endpoints/bindings + converts every attribute string→tagged ref + stamps `diagram-format-version: 2`
  → verify the full candidate repository → publish atomically → enable blocking validation. Covers
  ENG-ARCH-REPO and ENG-001 (`PLAN-datatype-er-diagrams.md §4.6`).
- **🟡 Observability.** Log unresolved/out-of-scope/status counts; counters for E334 rejections and
  promotion closure additions; the migration emits a machine-readable report.
- **Domain events — N/A** (file+index architecture, no aggregate event bus).

---

## 8. Self-model adaptation (ENG-ARCH-REPO, via MCP, motivation-first)

Anchor minimally. Where an id is unknown below, **look it up at authoring** (`artifact_query_search_artifacts`)
— never invent ids.

- **NEW REQ** *Datatype Attribute-Type Reference Integrity* → `archimate-aggregation` ←
  `REQ@1712870400.Ee3Ff3`; assoc ↔ `REQ@1781704601.sbkuwf`.
- **NEW REQ (only if hooks are genuinely generic — they are)** *Pluggable Diagram-Type Verification &
  Rendering*, else update `REQ@1777369404.aDohcf` *Extensibility & Configurability*.
- **NEW function** *Resolve & Validate Datatype Attribute Types* → realizes `SRV@1776699512.vQKsM9`;
  assoc ← `APP@1781705596.n8Pikk`; served-by `FNC@1712870400.eAkU8w`.
- **EDIT** `BOB@1781705223.SQXLsh` *Classifier* (globally-identified, diagram-owned reusable type);
  `FNC@1712870400.eAkU8w` *Referential Integrity Check* (workspace-identity validation);
  `FNC@1777399927.6PI0kV` *Verify Staged Repository* (resolves against the candidate repository).
- **EDIT** (ids to look up) *SQLite Indexer* (usages, not acceptance authority), *Repository Promotion
  Service* (type-dependency closure), *Diagram Authoring Service* (allocates ids, enforces immutability),
  and a new *Identifier Allocation Service* component.
- **WIRE** `APP@1712870400.ca3vm7` *Model Verifier*, `APP@1781705596.n8Pikk` *Datatype Module*,
  `APP@1712870400.yNhgdh` *Module Catalog*, `BOB@1777390172.7gJz0U` *Diagram Type Definition* to the
  verification-contribution + render-prep + allocator extension points.

Acceptance: `artifact_verify(repo_scope="engagement", return_mode="full")` → 0 errors;
`artifact_save_changes`.

---

## 9. Acceptance criteria

1. An attribute type may be set only to a known primitive or a classifier visible from the diagram's
   scope; the editor offers no free entry; the id is never user-editable.
2. A datatype diagram whose attribute reference is malformed (E336) or does not resolve / violates
   scope/status (E332) fails verification; a clean diagram verifies with 0 errors.
3. Renaming a classifier breaks nothing, requires no edit to referencing diagrams, and renders the new
   label everywhere on next render.
4. Any transaction removing a still-referenced classifier (single edit, host/bulk/collection delete,
   promotion replacement, import) is rejected with a single **E334** per removed classifier (no
   derivative E332 spam); removing the classifier together with its references succeeds atomically.
5. A promoted classifier is referenceable from engagement diagrams with no edit; promoting a diagram
   whose host closure is broken is blocked; the staged enterprise-only candidate verifies before
   publish and does not borrow engagement classifiers.
6. All acceptance verification (create/edit/full/bulk/cascade/migration/promotion/admin) resolves
   against `CandidateRepository`; SQLite is used only for search/discovery/usage hints.
7. The datatype module owns its verification (via typed contributions) and render preparation; the
   central verifier imports no datatype symbol.
8. Classifier ids are `CLF@epoch.random.slug`, immutable, allocated by the system-wide
   `IdentifierAllocator`.

---

## 10. Build order

`TASKS-datatype-type-resolution.md` is the authoritative ledger (WU-0.1 … WU-8.1). Phase summary:

- **P0 Foundations** — `identity_scope` + authoritative `id_prefix` (startup-validated, UI derived);
  `IdentifierAllocator` + non-persistent allocate endpoint + bounded consolidation of existing create
  paths; `CandidateRepository` (settled overlay, **aggregate diagram replacement**); workspace-id
  extraction; generic E335 + format/immutability; **two** contribution hooks (per-diagram +
  per-transaction); move E330/E331 behind the per-diagram hook (parity).
- **P1 Resolution & rendering** — discriminated-union schema + E336; `DatatypeVerificationProjection`
  compiler; `TypeResolver` (scope/status); E332 + W333; `PreparedDatatypeDiagram` render-prep + label
  resolution (contract test: rename relabels everywhere).
- **P2 Usage & discovery** — `attribute_type_refs` overlay; generic port lookups; `DatatypeTypeCatalog`
  + REST **and** MCP discovery (searchable, paginated, generation-aware).
- **P3 Lifecycle** — reference-impact (E334, suppresses derivative E332) at the **common mutation
  boundary**; delegation tests per route.
- **P4 Promotion** — index workspace classifiers in planning; two-stage closure + staged enterprise-only
  verify.
- **P5 Authoring** — tagged-ref frontend model; closed combobox + allocate-on-add; discovery wiring;
  regenerate `types.generated.ts`.
- **P6 Migration** — conservative, refuse-on-ambiguity, format-version, atomic.
- **P7 Switch-on** — enable blocking E332/E334/E335/E336 once data is clean (feature-flagged).
- **P8 Self-model** — §8 edits via MCP.

---

## 11. Decisions (consolidated)

§D1 single immutable id `CLF@epoch.random.slug` (slug = readability hint, never resolution/display);
rename free · §D2 name uniqueness advisory (W333), scoped to the defining diagram + repo-wide lint ·
§D3 blocking E332, no quick-fix, no free entry · §D4 `CandidateRepository` is the sole acceptance
authority; SQLite = search/discovery only · §D5 typed `DiagramVerificationContribution[ProjectionT]`;
generic code never imports datatype; one projection compiled per diagram · §D6 three role-separated
types (verification projection / render model / discovery catalog) · §D7 `identity_scope` is a generic
ontology-authoritative contract; UI derived · §D8 system-wide `IdentifierAllocator`; ids minted server
side, never client-side; allocate endpoint for pre-save identity · §D9 single source of truth (derived
overlay/index, no tracking frontmatter field) · §D10 ID immutability operational by set comparison; no
edit-id command; GUI hides id · §D11 removal protection at the common mutation boundary; no "delete
anyway" · §D12 E334 (one per removed classifier) suppresses derivative E332 · §D13 promotion: two-stage,
staged enterprise-only candidate · §D14 single-engagement mount invariant (scope discriminator
suffices) · §D15 migration refuses to apply while ambiguity remains; no schema duality · §D16
module-declared primitives; custom primitives via `primitive`-kind classifiers · §D17 composite =
structured classifier; type expressions out of scope · §D18 move-as-operation out of scope (identity is
move-ready) · §D19 `id_prefix` is authoritative ontology metadata (`workspace` types must declare a
unique, grammar-valid prefix; startup-validated); allocator resolves prefix only from it · §D20 two
contribution scopes: per-diagram (E330/E331/E332/W333/E336) vs per-transaction (E334 datatype, E335
generic), the latter run once per candidate transaction; diagram replacement is an aggregate operation
in `CandidateRepository` · §D21 the allocator is authoritative for model entities, diagrams, documents,
GARs, and classifiers (bounded consolidation WU); groups excluded unless separately normalized · §D22
E336 is a mandatory datatype check independent of generic-validator `oneOf` support; MCP discovery is a
focused read tool backed by the same application query as REST · §D23 write-time rendering resolves
labels from the `CandidateRepository`, not the committed index.
