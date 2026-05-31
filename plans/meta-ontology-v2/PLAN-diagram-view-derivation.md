# Plan: DiagramViewDerivation — replacing collect_derived_items

**Status**: planned  
**Companion**: `PLAN-c4-renderer-fix.md` task E; `PLAN-meta-ontology-v2.md` Phase 3 (strategies)

---

## Decision context

### What led here

Task E (`PLAN-c4-renderer-fix.md`) added `collect_derived_items()` to
`DiagramTypeModule` / `DiagramTypeBase` so the preview endpoint can return
auto-derived entity lists to the UI without type-specific logic in
infrastructure code. That is structurally better than a `startswith("c4-")`
check, but `collect_derived_items` is still the wrong abstraction:

- It duplicates the call to `resolve_c4_state` that already happens inside the
  renderer, whereas the correct source of truth is the registered
  `c4.scope-projection/v1` strategy in `StrategyRegistry`.
- It returns raw `list[dict]` instead of building on the `CandidateSet` +
  `DeriveFn` + `ModelQuery` types that the derivation layer already owns.
- It is named and shaped for a single use-case (the preview checklist), not for
  a general model-view correspondence capability.
- `DiagramTypeModule` is a *type declaration* protocol. View derivation is a
  *model-query behavior*. Mixing them inflates the protocol's surface.

### Why the approach was still accepted for task E

`collect_derived_items` as a stopgap on `DiagramTypeModule` is better than the
alternatives available at the time:
- Adding it to `DiagramRenderer` mixed rendering with model-query (worse).
- Calling `resolve_c4_state` directly in the preview handler would put
  diagram-type knowledge in infrastructure (forbidden).
- A full strategy-based refactor would have blocked a bug fix and UI improvement
  that were independently useful.

The method was accepted with an explicit note that it should be replaced once
the `view_derivations` machinery is extended to cover the preview call path.

### Why the strategy registry is the right home

The `view_derivations` machinery in `src/application/derivation/` already has:
- `DeriveFn: (params, SourceModelSnapshot, ModelQuery) → CandidateSet`
- `StrategyRegistry` with registered `c4.scope-projection/v1` (and four other
  strategies)
- `refresh.py` calling `lookup_derive_fn(name, version)` then `derive_fn(...)`
  — exactly the dispatch pattern we need

`collect_derived_items` is doing a manual ad-hoc call to `resolve_c4_state`
that bypasses this machinery. The correct path is:

1. The diagram type module declares *which strategy + params* to run for a
   given `diagram_entities` state (i.e. "for model-backed C4 with
   `_scope_entity_id = APP@…`, run `c4.scope-projection/v1` with
   `root_entity_id = APP@…`").
2. A generic `run_preview_derivation` function in the application layer takes
   that declaration, calls the registered strategy, and enriches the
   `CandidateSet` entity IDs with names from the repo.
3. The preview endpoint calls (1) then (2) — no diagram-type strings, no
   `resolve_c4_state` calls anywhere outside the strategy itself.

This is the same structure `refresh.py` already uses for `propose-bindings`.
The preview checklist becomes a thin wrapper over the same dispatch path.

### What this is NOT

This plan does NOT replace the full `view_derivations` + `propose-bindings`
workflow. It replaces only the `collect_derived_items` stopgap with a clean
path to the existing strategy machinery. When `propose-bindings` is fully wired
through the GUI create form (a separate future task), the
`DiagramViewDerivation` protocol introduced here may itself become redundant —
the create form would call `propose-bindings` and receive full binding proposals
instead of just names. The plan notes that inflection point explicitly.

### Alternative considered: capability protocol

A separate `DiagramViewDerivation(Protocol)` checked via `isinstance` was
considered. It is structurally cleaner (no default method on the module
protocol), but adds an extra named protocol for a capability that every C4
diagram type will share. The `DiagramTypeBase` default-`None` pattern is
already established by `build_context_extras` and `read_diagram_extras`, so
`get_view_derivation` following the same pattern is more consistent than
introducing a parallel capability protocol. If non-C4 diagram types eventually
need view derivation in meaningfully different ways, the capability protocol
should be revisited at that time.

---

## Design

### New types

```python
# src/application/derivation/view_derivation_request.py
@dataclass(frozen=True)
class ViewDerivationRequest:
    """Declares which registered strategy to run and with what inputs.

    Returned by DiagramTypeModule.get_view_derivation() for diagram-type
    modules that support model-backed derivation. The preview endpoint uses
    this to call run_preview_derivation() without knowing the diagram type.
    """
    strategy: str                        # registered strategy name
    strategy_version: int                # e.g. 1
    params: dict[str, object]            # strategy-specific params
    source_model_snapshot: SourceModelSnapshot


@dataclass(frozen=True)
class DerivedViewItem:
    """One model entity that was auto-derived for a diagram, enriched with display data.

    entity_id is the model artifact_id. c4_item_type is the projected C4 node type
    (software-system, person, container, component). is_scope is True for the root
    entity (excluded from the UI checklist; it cannot be excluded).
    """
    entity_id: str
    name: str
    artifact_type: str    # model type (e.g. "service", "business-actor")
    c4_item_type: str     # projected diagram type (e.g. "software-system", "person")
    is_scope: bool = False
```

### Protocol change

```python
# src/domain/ontology_protocol.py — DiagramTypeModule protocol

def get_view_derivation(
    self,
    diagram_type: str,
    diagram_entities: Mapping[str, object],
) -> ViewDerivationRequest | None: ...

# DiagramTypeBase default:
def get_view_derivation(self, diagram_type, diagram_entities) -> None:
    return None
```

### C4 override in `_C4DiagramType`

```python
def get_view_derivation(self, diagram_type, diagram_entities):
    scope_entity_id = str(diagram_entities.get("_scope_entity_id") or "").strip()
    if not scope_entity_id:
        return None
    excluded = list(diagram_entities.get("_excluded_entity_ids") or [])
    return ViewDerivationRequest(
        strategy="c4.scope-projection",
        strategy_version=1,
        params={
            "diagram_type": diagram_type,
            "excluded_entity_ids": excluded,
        },
        source_model_snapshot=SourceModelSnapshot(
            repo_scope="engagement",
            root_entity_id=scope_entity_id,
        ),
    )
```

### Application function

```python
# src/application/derivation/preview.py  (new file, <50 lines)

def run_preview_derivation(
    request: ViewDerivationRequest,
    query: ModelQuery,
) -> list[DerivedViewItem]:
    """Run a registered strategy and enrich the CandidateSet with display data.

    Returns DerivedViewItems for all candidate entities *excluding* the scope
    root (which is always shown and cannot be excluded). Returns [] if the
    strategy produces no candidates beyond the root.
    Raises ValueError if the strategy is not registered.
    """
    derive_fn = lookup_derive_fn(request.strategy, request.strategy_version)
    if derive_fn is None:
        raise ValueError(
            f"Strategy '{request.strategy}' v{request.strategy_version} not registered"
        )
    candidate_set = derive_fn(request.params, request.source_model_snapshot, query)
    root = request.source_model_snapshot.root_entity_id or ""
    # Enrich with entity names; skip root (the scope entity itself)
    items: list[DerivedViewItem] = []
    for eid in sorted(candidate_set.entity_ids):
        if eid == root:
            continue
        entity = query.get_entity(eid)
        if entity is None:
            continue
        items.append(DerivedViewItem(
            entity_id=eid,
            name=entity.name,
            artifact_type=entity.artifact_type,
            c4_item_type=_infer_c4_item_type(entity, request.params),
        ))
    return items
```

(`_infer_c4_item_type` uses the person_archimate_types from the C4 ontology to
classify business-actor/role as "person", everything else as "software-system".
This logic is already in `_c4_resolve.py`; extract it into a small pure function.)

### Preview endpoint

```python
# src/infrastructure/gui/routers/_diagram_write.py

module = get_diagram_type(body.diagram_type)
vd_request = module.get_view_derivation(body.diagram_type, de or {})
derived_entities = None
if vd_request is not None:
    from src.application.derivation.preview import run_preview_derivation
    query = _model_query_from_repo(repo)       # existing adapter
    items = run_preview_derivation(vd_request, query)
    derived_entities = [
        {"id": i.entity_id, "name": i.name, "item_type": i.c4_item_type}
        for i in items
    ]
```

### Removal

Once the above is in place and passing:
- `collect_derived_items` removed from `DiagramTypeModule` protocol
- `collect_derived_items` removed from `DiagramTypeBase`
- `collect_derived_items` removed from `_C4DiagramType`
- No other files reference it

---

## Implementation tasks

### A — New types: `ViewDerivationRequest`, `DerivedViewItem`

Add to `src/application/derivation/view_derivation_request.py`.
Import `SourceModelSnapshot` from `src.domain.view_derivations`.

**AC**: file exists; both dataclasses are frozen; `DerivedViewItem` has
`entity_id`, `name`, `artifact_type`, `c4_item_type`, `is_scope`.

---

### B — Add `get_view_derivation` to protocol and `DiagramTypeBase`

Add to `src/domain/ontology_protocol.py`:
- `DiagramTypeModule` protocol: `get_view_derivation(diagram_type, diagram_entities) -> ViewDerivationRequest | None`
- `DiagramTypeBase`: default returns `None`

**AC**: protocol compliance test still green; no existing module needs changes
(they inherit the default `None` from `DiagramTypeBase`).

---

### C — Override in `_C4DiagramType`

In `src/diagram_types/_c4_type.py`, implement `get_view_derivation`:
- Returns `None` when `_scope_entity_id` is absent (standalone mode)
- Returns `ViewDerivationRequest(strategy="c4.scope-projection", ...)` for model-backed

**AC**: unit test: standalone `diagram_entities={}` → `None`; model-backed
`diagram_entities={"_scope_entity_id": "APP@…"}` → `ViewDerivationRequest`
with correct strategy/params/snapshot.

---

### D — `run_preview_derivation` in `src/application/derivation/preview.py`

New file. Calls `lookup_derive_fn`, runs it, enriches results.
Needs a `_model_query_from_repo(repo)` adapter — check if one already exists
in `refresh.py` or `binding_proposals.py`; reuse it rather than creating a
new one.

**AC**:
- Empty `CandidateSet` → `[]`
- Root entity excluded from results
- Entity with `artifact_type in person_archimate_types` → `c4_item_type="person"`
- Non-existent entity ID in `CandidateSet` → silently skipped
- Unregistered strategy → `ValueError`
- Unit tests cover all five cases

---

### E — Wire preview endpoint; remove `collect_derived_items`

Update `src/infrastructure/gui/routers/_diagram_write.py`:
replace the `module.collect_derived_items(...)` call with
`module.get_view_derivation(...)` + `run_preview_derivation(...)`.

Then remove `collect_derived_items` from:
- `src/domain/ontology_protocol.py` (protocol + `DiagramTypeBase`)
- `src/diagram_types/_c4_type.py`

**AC**:
- Full test suite green (≥ 1042 tests); `zuban check` clean
- `grep -r "collect_derived_items" src/` returns nothing
- Browser: GUI Authoring Tool system context preview still shows checklist
- Browser: AMS system context preview still shows zero-neighbor hint

---

## Future inflection point

When the GUI create form is wired to call `artifact_edit_diagram` with
`mode=propose-bindings` instead of the preview endpoint for model-backed
diagrams, `DiagramViewDerivation` / `get_view_derivation` becomes redundant:
the propose-bindings path already returns full binding proposals (including
entity names) via the same strategy dispatch. At that point:

- `get_view_derivation` should be removed from the protocol
- `run_preview_derivation` and `preview.py` should be deleted
- The UI checklist should be rebuilt on top of the propose-bindings response

Add that as a note to the propose-bindings GUI wiring task when it is planned.

---

## Acceptance criteria summary

| # | Check |
|---|---|
| A | `ViewDerivationRequest`, `DerivedViewItem` types exist and are frozen |
| B | Protocol has `get_view_derivation`; all existing modules pass compliance test |
| C | `_C4DiagramType.get_view_derivation` returns correct request for model-backed; `None` for standalone |
| D | `run_preview_derivation` handles all five edge cases; unit tests pass |
| E | `collect_derived_items` absent from codebase; browser tests pass; suite ≥ 1042 green |
| — | No diagram-type strings in `_diagram_write.py` |
| — | `zuban check` clean |
