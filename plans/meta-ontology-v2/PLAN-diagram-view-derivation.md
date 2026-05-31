# Plan: DiagramViewDerivation — unify C4 projection, remove `collect_derived_items`

**Status**: done (implemented 2026-05-31)
**Companion**: `PLAN-c4-renderer-fix.md` task E; `PLAN-meta-ontology-v2.md` Phase 3 (strategies)

---

## Decision context

### What led here

Task E (`PLAN-c4-renderer-fix.md`) added `collect_derived_items()` to
`DiagramTypeModule` / `DiagramTypeBase` so the create-form preview endpoint can
return an auto-derived entity checklist to the UI. It was accepted as an
explicit stopgap, to be replaced once the derivation machinery covered the
preview path. This plan defines that replacement.

### Design directive (overrides the earlier draft)

The first draft of this plan proposed routing the preview through the registered
`c4.scope-projection` strategy and reconstructing the C4 item type with an
`_infer_c4_item_type` helper. A design review plus a code audit showed that
approach is unsound. The governing requirements for the rewrite are:

1. **Long-term, architecturally sound** — not a second stopgap.
2. **Single Responsibility** — membership, classification, selection, and
   rendering are distinct responsibilities with distinct homes.
3. **Hard modularity boundary** — *no diagram-type-specific logic in generic
   components*. Generic code may carry opaque, type-supplied strings but must
   never name or branch on C4 concepts.
4. **No backward-compatibility constraint** — major reworks are in scope where
   they improve soundness (file moves, deleting types, changing persisted
   metadata defaults).

### Current-state diagnosis (audited, with file:line)

The codebase has **two divergent C4 projection algorithms** and a **modularity
inversion**:

- **Generic package owns C4 logic.**
  `src/application/derivation/c4_scope_projection.py` contains C4-specific
  projection tables (system-context / container / component levels, person vs
  software-system classification). It physically lives in the *generic*
  `src/application/derivation/` package, and the generic package's
  `__init__.py:23` imports it by name. → modularity violation.

- **Dependency arrow points the wrong way.**
  `src/diagram_types/_c4_resolve.py:11` (the renderer engine, correctly under
  `src/diagram_types/`) imports `_NESTING_TYPES` / `_NEIGHBOR_TYPES` *from* the
  generic-located strategy file. The diagram-type module depends on a generic
  file for its own domain constants.

- **Two algorithms that disagree.**
  - `c4_scope_projection.derive` (the *strategy*) feeds refresh/diff via
    `CandidateSet`. For containers it filters structural children to
    `_CONTAINER_INTERNAL_TYPES` (`c4_scope_projection.py:138`).
  - `_c4_resolve._resolve_model_backed` (the *renderer*, also used by
    `collect_derived_items`) takes **all** nesting children as internal
    (`_c4_resolve.py:101-105`) and never consults the strategy.
  Membership shown in the preview / rendered diagram can therefore differ from
  membership the diff machinery computes. The plan's old premise — "the strategy
  is the source of truth" — was aspirational; the renderer never calls it.

- **Projection role is destroyed at the `CandidateSet` boundary.**
  `CandidateSet` (`types.py:12`) is `{entity_ids, connection_ids, paths}` only.
  The internal/neighbor role each projector computes is discarded. The old
  `_infer_c4_item_type` could not recover it: an `application-component`
  projects to `container` when internal but `software-system` when a neighbor —
  same model type, different C4 type. The inference is only correct for
  system-context (person vs software-system), which is the *only* level the
  browser AC exercised.

- **`collect_derived_items` is on the wrong protocol with the wrong signature.**
  It sits on the generic `DiagramTypeModule` *type-declaration* protocol
  (`ontology_protocol.py:282`), takes `repo_root: Path` (infrastructure type in
  a domain method), and returns raw `list[dict[str, str]]`.

- **Exclusions are honored in one path, ignored in the other.**
  `_c4_resolve` applies `_included/_excluded_entity_ids`
  (`_c4_resolve.py:122-127`); the strategy ignores them entirely
  (`supported_filters = {repo_scope}`). The old plan passed exclusions as
  strategy `params`, where nothing reads them.

- **`repo_scope` is inert today and defaulted wrong by the old plan.**
  No C4 derive fn reads `snapshot.repo_scope`; scope is determined by which roots
  the `ModelQuery`/index covers. Every other entry point defaults `repo_scope`
  to `"both"` (e.g. `query_list_read_tools.py:74`). The old plan hard-coded
  `"engagement"`, which is inconsistent and would wrongly exclude valid
  enterprise neighbors once the field is honored.

---

## Target architecture

One C4 projection engine, owned by the C4 module, exposed through two seams that
serve two responsibilities. Generic code never names a C4 concept.

```
                    src/diagram_types/c4* (DIAGRAM-TYPE MODULE)
                    ┌─────────────────────────────────────────┐
                    │  _c4_projection.py  (THE ENGINE)         │
                    │  project(diagram_type, root, query,      │
                    │          selection) -> C4Projection      │
                    │   • membership (structural children +    │
                    │     neighbors, per spec tables)          │
                    │   • per-member role + c4 item_type       │
                    │   • owns _NESTING_TYPES/_NEIGHBOR_TYPES   │
                    └───────────────┬──────────────┬───────────┘
            membership-only │                      │ classified items
        (.to_candidate_set) │                      │ (.to_view_items)
                            ▼                      ▼
   ┌────────────────────────────────┐   ┌──────────────────────────────┐
   │ SEAM B: strategy registration  │   │ SEAM C: ViewProjector.        │
   │ register_strategy(             │   │ project_view(...) capability  │
   │  "c4.scope-projection", v1)    │   │ implemented by _C4DiagramType │
   │ + register_module_projection   │   │                               │
   └──────────────┬─────────────────┘   └──────────────┬────────────────┘
                  │ CandidateSet                        │ list[ProjectedViewItem]
                  ▼                                     ▼
   GENERIC: refresh.py diff/selection,    GENERIC: preview endpoint forwards
   view_derivations persistence           opaque display_class to the UI
   (sees only sets — agnostic)            (never interprets it — agnostic)

   Renderer (_c4_resolve) ALSO calls the engine → preview == render by construction.
```

### Responsibilities (SRP)

| Responsibility | Home | Output | Consumer |
|---|---|---|---|
| **Membership** (what's in the view) | C4 engine → strategy adapter | `CandidateSet` | generic refresh/diff/persistence |
| **Classification** (role + C4 item type) | C4 engine → `ViewProjector` | `list[ProjectedViewItem]` | preview checklist + renderer |
| **Selection** (include/exclude) | generic `DerivationSelection` | flags on items | applied by generic preview service |
| **Rendering** (PlantUML text) | `_c4_resolve` / `c4_renderer` | puml | preview image / file render |

The engine is the single algorithm. The strategy adapter is literally
`engine(...).to_candidate_set()`, so refresh/diff, the preview checklist, and the
rendered diagram are guaranteed to agree.

### Generic contracts (carry **no** C4 vocabulary)

```python
# src/domain/view_projection.py  (NEW, generic)

@dataclass(frozen=True)
class ProjectedViewItem:
    """One model entity projected into a diagram view, ready for display.

    display_class and role are OPAQUE to generic code: the diagram-type module
    assigns them, generic code forwards them verbatim. For C4, display_class is
    "container"/"component"/"software-system"/"person" and role is
    "scope"/"internal"/"external" — but view_projection.py must never branch on
    those values.
    """
    entity_id: str
    name: str
    display_class: str
    role: str
    excluded: bool = False     # set by the generic selection step, not the module


@dataclass(frozen=True)
class ViewProjectionResult:
    """What a diagram-type module hands back for a model-backed view.

    `derivation` is the normalized, persistable spec (same shape as the
    view_derivations: frontmatter key) — it carries the strategy name, params,
    snapshot, and selection. `items` is the already-classified projection for
    the preview checklist / renderer. The module produces BOTH from one engine
    run, so they cannot disagree.
    """
    derivation: ViewDerivation
    items: tuple[ProjectedViewItem, ...]


@runtime_checkable
class ViewProjector(Protocol):
    """Capability protocol for diagram types that derive a model-backed view.

    Separate from DiagramTypeModule (SRP: type declaration vs view projection).
    A diagram-type module opts in by implementing project_view; the preview
    service discovers it via isinstance and stays diagram-type-agnostic.
    """
    def project_view(
        self,
        diagram_type: str,
        diagram_entities: Mapping[str, object],
        query: ModelQuery,
    ) -> ViewProjectionResult | None: ...
```

`project_view` returns the classified `items` **directly** — the generic preview
service does NOT re-run anything through the strategy registry to get them. The
module owns the one engine; it runs `project_c4` once and emits both the
normalized `derivation` (for persistence + the diff path) and the `items` (for
display). The strategy registry (Seam B) is a *separate* consumer used only by
the generic refresh/diff path, which needs membership-only `CandidateSet`s. The
two seams never chain: preview reads `items`, diff reads `CandidateSet`, both off
the same `project_c4`.

The `derivation` reuses the existing `ViewDerivation` domain type, so preview,
refresh, and persistence share one representation — and it kills the legacy
`_scope_entity_id` / `_excluded_entity_ids` ad-hoc transport at the derivation
boundary (those keys survive only as C4 authoring shorthand, which the module
translates into a `SourceModelSnapshot(repo_scope="both", ...)` + a normalized
`DerivationSelection`).

---

## Design

### 1. The engine (C4 module)

`src/diagram_types/_c4_projection.py` (NEW). Owns the connection-type constants
(moved out of the generic package) and the single projection algorithm.

```python
_NESTING_TYPES   = frozenset({"archimate-composition", "archimate-aggregation"})
_NEIGHBOR_TYPES  = frozenset({"archimate-serving", "archimate-flow",
                              "archimate-triggering", "archimate-access"})

@dataclass(frozen=True)
class C4ProjectedItem:
    entity_id: str
    name: str
    artifact_type: str
    role: str          # "scope" | "internal" | "external"
    item_type: str     # c4 node type, via _c4_item_type(...)

@dataclass(frozen=True)
class C4Projection:
    items: tuple[C4ProjectedItem, ...]
    connection_ids: tuple[str, ...]
    def to_candidate_set(self) -> CandidateSet: ...   # SEAM B
    def to_view_items(self) -> list[ProjectedViewItem]: ...  # SEAM C

def project_c4(
    diagram_type: str,
    root_entity_id: str,
    query: ModelQuery,
    *,
    internal_c4_type: str,
    scope_entity_type: str,
    person_archimate_types: frozenset[str],
) -> C4Projection: ...
```

- Follows the SPEC projection tables (`c4_scope_projection.py` docstring) as the
  **single** definition of membership. This means container internals are filtered
  to the allowed internal types — changing `_c4_resolve`'s current *unfiltered*
  behavior. Acceptable (no backcompat); it removes the divergence and matches spec.
- `_c4_item_type(role, diagram_type, artifact_type, person_types, internal_c4_type)`
  is the one pure mapping. scope→`scope_entity_type`; internal→`internal_c4_type`;
  external→`"person"` if `artifact_type in person_types` else `"software-system"`.
- Uses only the generic `ModelQuery` (no `repo_root: Path`, no index construction
  inside the engine).

### 2. Strategy registration (SEAM B) — moved into the C4 module

`src/diagram_types/_c4_strategy.py` (NEW, or a registration block in
`_c4_projection.py`):

```python
def _derive(params, snapshot, query) -> CandidateSet:
    root = snapshot.root_entity_id or str(params.get("scope_entity_id", ""))
    if not root:
        return CandidateSet()
    return project_c4(
        str(params.get("diagram_type", "")), root, query,
        internal_c4_type=str(params.get("internal_c4_type", "container")),
        scope_entity_type=str(params.get("scope_entity_type", "")),
        person_archimate_types=frozenset(params.get("person_archimate_types") or []),
    ).to_candidate_set()

register_strategy(StrategySpec("c4.scope-projection", 1, frozenset({"repo_scope"})), _derive)
register_module_projection("c4", 1, _derive)
```

Registration is triggered when the C4 packages import (they already load via
`src/diagram_types/__init__.py` → `register_default_diagram_types`). The generic
`src/application/derivation/__init__.py` **drops** its `c4_scope_projection`
import. Delete `src/application/derivation/c4_scope_projection.py`.

### 3. `ViewProjector` implementation (SEAM C) on `_C4DiagramType`

```python
# src/diagram_types/_c4_type.py
def project_view(self, diagram_type, diagram_entities, query) -> ViewProjectionResult | None:
    scope_id = str(diagram_entities.get("_scope_entity_id") or "").strip()
    if not scope_id:
        return None                      # standalone mode → no derivation
    projection = project_c4(            # the ONE engine run for preview/render
        diagram_type, scope_id, query,
        internal_c4_type=self._internal_c4_type(),
        scope_entity_type=self._scope_entity_type(),
        person_archimate_types=self._renderer._person_archimate_types,
    )
    derivation = ViewDerivation(
        id="__preview__",
        strategy="c4.scope-projection",
        strategy_version=1,
        source_model_snapshot=SourceModelSnapshot(repo_scope="both", root_entity_id=scope_id),
        parameters={
            "diagram_type": diagram_type,
            "internal_c4_type": self._internal_c4_type(),
            "scope_entity_type": self._scope_entity_type(),
            "person_archimate_types": sorted(self._renderer._person_archimate_types),
        },
        selection=_selection_from_entities(diagram_entities),  # _included/_excluded → normalized
    )
    return ViewProjectionResult(derivation=derivation, items=projection.to_view_items())
```

The `parameters` mirror the `project_c4` inputs so the registered derive fn
(Seam B) reconstructs the *same* membership when the diff path later runs against
the persisted entry — both go through `project_c4`. The preview itself does not
use Seam B; it reads `items` straight from this call.

### 4. Generic preview service

`src/application/derivation/preview.py` (NEW, generic, <40 lines). It does **not**
touch the strategy registry — it just asks the module for its projection and
applies the (generic) selection:

```python
def project_view_for_preview(
    module: object, diagram_type: str,
    diagram_entities: Mapping[str, object], query: ModelQuery,
) -> list[ProjectedViewItem] | None:
    """Return classified, selection-flagged view items, or None if the module
    does not support projection / the diagram is standalone."""
    if not isinstance(module, ViewProjector):
        return None
    result = module.project_view(diagram_type, diagram_entities, query)
    if result is None:
        return None
    excluded = set(result.derivation.selection.excluded_entity_ids) if result.derivation.selection else set()
    return [replace(i, excluded=i.entity_id in excluded) for i in result.items]
```

- **No registry round-trip, no re-derivation.** The classified `items` come
  directly from the module's single engine run. The strategy registry (Seam B) is
  used only by the *separate* refresh/diff path; the two seams are never chained.
- **Selection is applied here, at the generic layer** (Finding 2), reading the
  normalized `DerivationSelection` (a generic domain type — *not* the C4-shaped
  `_excluded_entity_ids` key, which only the module is allowed to parse). It
  **marks** items `excluded` rather than dropping them, so the checklist stays
  editable.
- The scope root arrives flagged `role="scope"`; the UI shows it but cannot
  uncheck it.
- This file contains zero diagram-type strings and zero C4 vocabulary.

### 5. Preview endpoint wiring

`src/infrastructure/gui/routers/_diagram_write.py` (preview builds a query once
and reuses it for both render and projection — Finding 7):

```python
from src.application.derivation.preview import project_view_for_preview
from src.infrastructure.artifact_index.service import shared_artifact_index

query = shared_artifact_index([repo_root])          # ModelQuery; reused for render + projection
...
module = get_diagram_type(body.diagram_type)
items = project_view_for_preview(module, body.diagram_type, de or {}, query)
derived_entities = None if items is None else [
    {"id": i.entity_id, "name": i.name, "item_type": i.display_class, "excluded": i.excluded}
    for i in items
]
```

No diagram-type string, no `repo_root: Path` passed into a domain method, no C4
concept named in infrastructure.

### 6. Renderer convergence

`_c4_resolve._resolve_model_backed` is refactored to call `project_c4` for
membership + classification, keeping only its presentation concerns (alias/label
generation, connection-label text, standalone mode). Its local import of
`_NESTING_TYPES`/`_NEIGHBOR_TYPES` now resolves to the C4-owned engine module, not
the generic package. This is what makes **preview == render** structural rather
than coincidental, and is the change that justifies calling this a long-term fix
rather than a second bridge.

### 7. Removals

- Delete `src/application/derivation/c4_scope_projection.py`.
- Drop its import from `src/application/derivation/__init__.py` and `__all__`.
- Remove `collect_derived_items` from `DiagramTypeModule`
  (`ontology_protocol.py:282`) and `DiagramTypeBase` (`:386`).
- Remove `collect_derived_items` from `_C4DiagramType` (`_c4_type.py:262`).
- The old `ViewDerivationRequest` / `DerivedViewItem` / `_infer_c4_item_type`
  designs are dropped (never built).

---

## Implementation tasks

### A — Engine: `_c4_projection.py` ✅

Create `src/diagram_types/_c4_projection.py` with `_NESTING_TYPES`,
`_NEIGHBOR_TYPES`, `C4ProjectedItem`, `C4Projection`, `project_c4`,
`_c4_item_type`. Port the spec-correct membership logic from
`c4_scope_projection.py` (filtered container internals) and the classification
from `_c4_resolve`.

**AC** — Verified 2026-05-31
- system-context: root + interaction-neighbors only; no structural children. ✓
- container: structural children filtered to allowed internal types → `internal`;
  neighbors → `external`. ✓
- component: structural children (allowed) → `internal`; neighbors → `external`. ✓
- `_c4_item_type` maps internal app-component → `container`/`component` per
  `diagram_type`; neighbor app-component → `software-system`; business-actor/role
  neighbor → `person`. ✓
- Engine takes only `ModelQuery`; no filesystem access. ✓
- Unit tests for all three levels + the role→item_type matrix. ✓ (tests/diagram_types/test_c4_projection.py)

### B — Strategy registration moves into the C4 module ✅

Add registration (`register_strategy` + `register_module_projection("c4", 1)`)
in the C4 module, delete `c4_scope_projection.py`, drop the generic-package
import.

**AC** — Verified 2026-05-31
- Importing the c4 package registers `c4.scope-projection` v1 and module
  projection `("c4", 1)`. ✓
- `grep -rn "c4_scope_projection" src` returns nothing. ✓
- `src/application/derivation/` contains no C4 token (test: grep the package for
  `c4`, `container`, `component`, `software-system`, `person` → none). ✓
- Existing refresh-derivation / diff tests for C4 still green (now backed by the
  unified engine). ✓

### C — Generic contracts: `view_projection.py` ✅

Create `src/domain/view_projection.py` with `ProjectedViewItem` (frozen) and the
`@runtime_checkable ViewProjector` protocol.

**AC** — Verified 2026-05-31: file exists; carries no C4 vocabulary; `ViewProjector` is runtime-checkable. ✓

### D — `_C4DiagramType.project_view` ✅

Implement `project_view` returning a `ViewProjectionResult` (or `None` for
standalone): run `project_c4` once, build the normalized `ViewDerivation`
(`repo_scope="both"`, params mirroring the engine inputs, `DerivationSelection`
from `_included/_excluded_entity_ids`), and attach `projection.to_view_items()`.

**AC** — Verified 2026-05-31
- standalone (`{}`) → `None`. ✓
- model-backed (`{"_scope_entity_id": "APP@…"}`) → result whose `derivation` has
  correct strategy/version/snapshot/params/selection, and whose `items` carry the
  engine's role + item_type. ✓
- `derivation.parameters` round-trip through the registered derive fn (Seam B)
  yield a `CandidateSet` whose `entity_ids` equal `{i.entity_id for i in items}`
  (proves the two seams share one definition). ✓ (tests/diagram_types/test_c4_project_view.py)

### E — Generic preview service: `preview.py` ✅

Create `src/application/derivation/preview.py` with `project_view_for_preview`.
It asks the module (via `ViewProjector`) for its `ViewProjectionResult` and
applies the normalized selection as `excluded` flags. **No strategy-registry
dispatch and no re-derivation** — classification comes straight from the module.

**AC** — Verified 2026-05-31
- Module without `ViewProjector` → `None`. ✓
- Module returns `None` (standalone) → `None`. ✓
- Excluded entity (in `derivation.selection`) → present with `excluded=True`
  (not removed). ✓
- Scope root → present with `role="scope"`. ✓
- Reads only the generic `DerivationSelection`, never the C4 `_excluded_entity_ids`
  key. ✓ (tests/application/derivation/test_preview.py)
- Contains no diagram-type string (grep test). ✓
- Large-set warning logged in the engine at >200 items. ✓

### F — Wire preview endpoint; converge renderer; remove `collect_derived_items` ✅

Update `_diagram_write.py` to build one `ModelQuery` and call
`project_view_for_preview`. Refactor `_c4_resolve._resolve_model_backed` to call
`project_c4`. Remove `collect_derived_items` from the protocol, base, and C4 type.

**AC** — Verified 2026-05-31
- Full test suite green: 1072 passed; `zuban check` clean (248 files). ✓
- `grep -rn "collect_derived_items" src` returns nothing. ✓
- **preview == render**: fixture asserts entity set from `project_view_for_preview`
  equals engine's `to_view_items()` for system-context, container, and component. ✓
  (tests/diagram_types/test_c4_project_view.py)
- Browser checks (Playwright MCP, 2026-05-31): ✓
  - GUI Authoring Tool system-context: "7 entities auto-derived" checklist with
    checkboxes, all classified as `software-system`. ✓
  - Architecture Management System (AMS) system-context: single «C4System» box +
    amber hint "No external connections found — consider a C4 Container diagram". ✓

---

## Future inflection point

When the GUI create form is wired to `artifact_edit_diagram mode=propose-bindings`
for model-backed diagrams, the checklist can be rebuilt on the propose-bindings
response. Note, however, that propose-bindings currently returns
`candidate_diagram_types` (admissible binding multi-choice via
`build_entity_proposals`), **not** a resolved single item type, and does **not**
run a strategy — so adopting it for the checklist requires extending
propose-bindings to run the projection first. Unlike the old `collect_derived_items`
stopgap, the structure introduced here is the intended long-term home: `project_view` /
`ViewProjector` and the unified engine remain valid; only the preview *transport*
would change. Record this when the propose-bindings GUI wiring is planned.

---

## What this plan deliberately does **not** do

- It does not add C4 vocabulary to `CandidateSet` or any generic type. Role and
  item type live in C4-owned outputs (`C4ProjectedItem`) and cross the generic
  boundary only as opaque `display_class` / `role` strings.
- It does not keep two projection algorithms. The renderer converges onto the
  engine (task F).
- It does not preserve the `_scope_entity_id` ad-hoc params as the derivation
  transport; it normalizes onto a draft `ViewDerivation`.

---

## Acceptance criteria summary — all verified 2026-05-31

| # | Check | Status |
|---|---|---|
| A | `_c4_projection.py` engine: 3 levels + role→item_type matrix correct; `ModelQuery`-only | ✅ |
| B | C4 strategy registered from the C4 module; `c4_scope_projection.py` deleted; `src/application/derivation/` free of C4 tokens | ✅ |
| C | `view_projection.py`: `ProjectedViewItem` + runtime-checkable `ViewProjector`, no C4 vocabulary | ✅ |
| D | `_C4DiagramType.project_view` returns draft `ViewDerivation` (`repo_scope="both"`) / `None` for standalone | ✅ |
| E | `project_view_for_preview`: selection marks `excluded`, root flagged, edge cases covered, no C4 string, large-set warning | ✅ |
| F | `collect_derived_items` gone; renderer uses the engine; **preview == render** fixture passes | ✅ |
| F | Browser checks: GUI Authoring Tool checklist (7 items) + AMS zero-neighbor hint | ✅ |
| — | No diagram-type string in `_diagram_write.py`, `preview.py`, or `view_projection.py` | ✅ |
| — | Full suite green (1072 passed); `zuban check` clean (248 files) | ✅ |
