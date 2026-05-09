# Mini-RFC: Diagram-Kind UI Authoring Architecture

**Status:** Approved — Ready for Implementation  
**Date:** 2026-05-08  
**Scope:** Phase 2 — PUML activity diagram support and the general architecture that enables all future diagram types to be authored in the GUI and via MCP tools.

---

## 1. Problem Statement

The GUI diagram editor and MCP write tools currently treat all diagrams identically:
entities are chosen from the full model regardless of diagram type, there is no concept of elements that exist only within a diagram (e.g. swimlanes), and kind-specific authoring gestures (assigning entities to lanes, configuring groupings) are impossible.

As new diagram types are added — starting with UML activity diagrams — the system must:

1. **Restrict entity selection** to the types permitted by the active diagram type.
2. **Support diagram-only entity types** that live inside the diagram file and have no counterpart in the model's entity store.
3. **Expose kind-specific authoring UI** without hard-coding per-kind logic in the generic editor components.
4. **Remain extensible**: adding a new diagram type must not require modifying the core GUI or API; it requires only a new backend module and, for bespoke UX, a registered frontend slot component.

---

## 2. Design Goals

| Goal | Priority |
|---|---|
| Kind-scoped entity search and add/remove | Must |
| Diagram-only entity types with lifecycle in diagram file | Must |
| Declarative kind configuration drives generic UI | Must |
| Escape-hatch slot pattern for bespoke UX | Must |
| `diagram_entities` round-trips through create/edit without data loss | Must |
| MCP tools carry `diagram_entities` so AI agents can author fully | Must |
| New kinds require zero changes to core router/editor code | Should |
| Mapping from diagram-only type to model entity type (optional reference) | Should |

---

## 3. Key Design Decisions

### DD-1: Persistence of diagram-only entities

**Question:** Where are diagram-only elements (e.g. swimlanes) stored?

**Options:**
- A. As model entities in the entity store with a special `internal: true` flag.
- B. In a `diagram-entities:` frontmatter block inside the diagram's `.md` file; PUML is derived output only.

**Decision: B — `diagram-entities:` frontmatter.**

Rationale:
- Swimlanes, activity groups, etc. are diagram-scoped artefacts; they have no business existence outside the diagram.
- Storing them in the model would pollute entity search, connection graphs, and MCP entity queries.
- The diagram `.md` file is already the canonical source for the diagram; extending its frontmatter with a `diagram-entities:` block is consistent with the self-describing file model.
- PUML is **always** derived. On every save the renderer reads frontmatter + entity list + `diagram-entities:` and regenerates the `.puml` file. This avoids stale PUML state and makes diffs clean.

```yaml
# diagram .md frontmatter (example: activity diagram)
artifact-type: diagram
diagram-type: activity
diagram-entities:
  swimlanes:
    - id: sw-1
      label: "Customer"
      model_entity_id: ENT-001   # optional reference
    - id: sw-2
      label: "System"
  lane_assignments:
    ENT-042: sw-1
    ENT-017: sw-2
```

On edit, the API reads `diagram-entities:` back from frontmatter. PUML is never parsed to reconstruct state.

#### PUML size constraints

PlantUML has hard rendering limits — both the URL-encoded remote server (~4 000 characters) and local/server rendering become unreliable above roughly 200–300 diagram elements. Large `diagram_entities` structures (many swimlanes, many lane assignments, many connections between diagram-only entities) must not inflate the generated PUML body.

Two rules follow from this:

1. **The renderer owns compactness.** `diagram_entities` is never dumped verbatim into the PUML body. The renderer is responsible for translating it into the minimum PUML required — group blocks, partition declarations, layout hints — not a literal serialisation of the data structure. Type-specific renderers should emit a warning (and optionally refuse to render) when the output exceeds a configurable character threshold.

2. **The rendering pipeline strips frontmatter from `.puml` files before passing to PlantUML.** Any YAML block delimited by `---` at the start of a `.puml` file is removed before the content reaches the PlantUML process. This has two practical consequences:
   - `diagram_entities` MAY be stored as frontmatter directly in the `.puml` file (e.g. for kinds where state co-location with diagram source is preferable), without any rendering impact.
   - Future metadata fields can be added to `.puml` files freely without risk of breaking rendering.

   ```
   # .puml file structure (with optional frontmatter)
   ---
   diagram-entities:
     swimlanes: [...]
     lane_assignments: {...}
   ---
   @startuml
   ' rendered PUML — PlantUML sees only this
   ...
   @enduml
   ```

   The canonical source for `diagram_entities` remains whichever location the kind's loader reads from (`.md` frontmatter by default). The `.puml` frontmatter option is an opt-in per kind, useful when the `.puml` file is the more natural editing surface.

---

### DD-2: Connection rules for diagram-only entities

**Question:** How are relationships between diagram-only entities and model entities expressed?

**Options:**
- A. Model connections in the connection store (source or target may be a diagram-only ID).
- B. Diagram-local membership structures within `diagram-entities:` (e.g. `lane_assignments: {entity_id: swimlane_id}`).

**Decision: B — diagram-local membership in `diagram-entities:`.**

Rationale:
- Diagram-only entities have no stable cross-diagram ID; they cannot be connection endpoints in the model store.
- Membership (an entity belongs to a lane) is an authoring-time layout decision, not a business relationship. It must not appear in the model's connection graph, candidate connection suggestions, or MCP connection queries.
- The `diagram-entities:` block is the natural home: it is diagram-scoped and survives round-trips through the API.

If a future diagram type needs relationships _between_ diagram-only entities (e.g. activity transitions), those too are stored in `diagram-entities:` as typed edge lists, never as model connections.

---

### DD-3: Slot-pattern trade-off

**Question:** How much of the UI can be driven declaratively vs. requiring frontend code per kind?

**Resolution:**

Declarative config (in the kind's `config.yaml` and `ui_config` Python property) handles:
- Entity type allowlist shown in the entity-picker panel.
- Label/plural/min/max constraints for diagram-only entity types.
- `permitted_mappings` — the set of model entity types and/or element classes a diagram-only entity may optionally reference, plus whether that reference is mandatory.
- Connection type allowlist in the connection-picker panel.

Slot components handle:
- Any UX that requires layout-aware interaction (e.g. drag-entity-onto-swimlane).
- Custom rendering of diagram-only entities in the sidebar (e.g. the swimlane management panel).
- Any kind-specific workflow step that cannot be expressed as "pick from a list".

**Explicit acknowledgement:** Adding a diagram type with bespoke UX requires **both**:
1. A backend `DiagramTypeModule` implementation (Python).
2. A registered frontend slot component (Vue/TypeScript).

This is acceptable and intentional — `DiagramAuthoringExtensions` makes the dependency explicit rather than buried.

---

### DD-4: Mapping semantics for diagram-only entities

**Question:** What does `permitted_mappings` mean — is a diagram-only entity a projection of a model entity, or an independent entity that may optionally reference one?

**Decision: Optional reference, not a projection.**

- A diagram-only entity (e.g. a swimlane) is an independent artefact.
- It MAY hold a `model_entity_id` pointing to a model entity for display context (showing the entity's name and status in the lane header).
- A model entity is a permitted mapping target if its `artifact_type` appears in `permitted_mappings.entity_types` **or** any of its `element_classes` intersects `permitted_mappings.entity_classes`. Both lists may be combined; an empty `PermittedMappingSpec` means no mapping is offered or expected.
- This reference is **informational only**: it does not create a model connection, does not affect the entity's lifecycle, and does not prevent the diagram-only entity from existing without a reference.
- MCP entity queries return model entities; they do not return diagram-only entities.
- `mapping_required: false` is the default; setting it `true` enforces that the user must select a model entity for each diagram-only instance (for kinds where the lane's business identity is mandatory, e.g. an actor swimlane that must map to a known role).

---

## 4. Backend Architecture

### 4.1 `DiagramKindUiConfig` — new data type

```python
# src/domain/ontology_protocol.py  (additions)

from dataclasses import dataclass, field

@dataclass(frozen=True)
class PermittedMappingSpec:
    """Which model entities a diagram-only entity instance may reference.

    A model entity is a permitted target if its artifact_type appears in
    ``entity_types`` OR any of its element_classes intersects ``entity_classes``.
    Both lists may be used together; an empty spec means no mapping is offered.
    """
    entity_types: tuple[str, ...] = ()    # e.g. ("role", "business-actor")
    entity_classes: tuple[str, ...] = ()  # e.g. ("active-structure", "behavior")

@dataclass(frozen=True)
class DiagramOwnEntityTypeUiConfig:
    entity_type: str                        # e.g. "swimlane" — kind-scoped identifier, NOT an artifact-type
    label: str                               # e.g. "Swimlane"
    plural: str                              # e.g. "Swimlanes"
    min: int = 0
    max: int | None = None
    permitted_mappings: PermittedMappingSpec = field(default_factory=PermittedMappingSpec)
    mapping_required: bool = False           # True → user must pick a model entity for each instance

@dataclass(frozen=True)
class DiagramKindUiConfig:
    label: str
    description: str = ""
    entity_search_filter: bool = True        # restrict picker to kind-accepted types
    diagram_only_types: tuple[DiagramOwnEntityTypeUiConfig, ...] = ()
    kind_ui_slots: dict[str, str] = field(default_factory=dict)
    # kind_ui_slots: slot_name → component_key
    # e.g. {"entity_context_panel": "swimlane-assignment"}
```

### 4.2 `DiagramTypeModule` protocol — `ui_config` property

Add one property to the protocol and the `DiagramKindBase` mixin:

```python
# Protocol addition
@property
def ui_config(self) -> DiagramKindUiConfig: ...

# DiagramKindBase default (covers all existing archimate kinds with no change)
@property
def ui_config(self) -> DiagramKindUiConfig:
    return DiagramKindUiConfig(
        label=str(self.name).replace("-", " ").title(),
        entity_search_filter=True,
    )
```

Existing kinds inherit the default and are unaffected.

### 4.3 `config.yaml` schema extension

```yaml
# New optional `ui:` section in any kind's config.yaml
ui:
  label: "Activity Diagram"
  description: "UML activity diagrams with swimlanes and flow transitions"
  entity_search_filter: true
  diagram_only_types:
    - entity_type: swimlane    # kind-scoped type identifier — not an artifact-type
      label: Swimlane
      plural: Swimlanes
      min: 2
      max: null
      permitted_mappings:
        entity_types:           # match by entity type name (e.g. role, business-actor)
          - role
          - business-actor
        entity_classes:         # match by element class (broader grouping)
          - active-structure
      mapping_required: false   # true → user must select a model entity per instance
  kind_ui_slots:
    entity_context_panel: swimlane-assignment
    # slot_name: component_key registered in DiagramAuthoringExtensions
```

The `DiagramKindBase.load_config()` classmethod (or equivalent) parses this into a `DiagramKindUiConfig` instance. Kinds with no `ui:` block get the default.

### 4.4 New API endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/diagram-types` | List all registered kinds: `[{key, label, description}]` |
| `GET` | `/api/diagram-types/{diagram_type}/ui-config` | Full `DiagramKindUiConfig` for one kind |

The `/api/diagram-types` response replaces the hardcoded `DIAGRAM_TYPES` array in `CreateDiagramView.vue`.

The `/api/diagram-types/{diagram_type}/ui-config` response is fetched when the user selects a diagram type, or when the editor opens for an existing diagram. It drives:
- Which entity types appear in the entity picker.
- Which diagram-only type panels to show.
- Which slot components to mount.

### 4.5 `diagram_entities` in create/edit API

The create and edit diagram endpoints accept an optional `diagram_entities` body field (JSON object, passed through verbatim to the `diagram-entities:` frontmatter block). The API does not interpret or validate its internal structure beyond it being a valid JSON object — that is the kind's responsibility.

On read, the API response includes a dedicated `diagram_entities` field extracted from the diagram's frontmatter `diagram-entities:` key.

**Important:** `DiagramRecord.extra` (in `src/domain/artifact_types.py`) is the raw frontmatter dict and is unchanged. The backend router extracts `rec.extra.get("diagram-entities")` and exposes it as a top-level `diagram_entities` key in the JSON response — it does not rename or modify `extra`. On the frontend, `DiagramDetailSchema` in `tools/gui/src/domain/schemas.ts` gains a new `diagram_entities: Schema.optional(Schema.Unknown)` field; the existing `extra` field may be removed if it is not used by any current view, otherwise it is left in place.

### 4.6 `fuzzy_entity_hits` — kind-scoped entity search

`fuzzy_entity_hits` is the backend function that powers the **"add entity to diagram" search box** in the diagram editor. Given a free-text query, it scores every entity in the repository using fuzzy string matching against the entity's name, type, domain, subdomain, and a leading excerpt of its content. Entities with a similarity score above a threshold (currently 0.35) are returned ranked by score. The caller supplies an `excluded` set of entity IDs already present in the diagram so they are omitted from results.

Currently the function searches all entity types regardless of the active diagram type. This is the gap being addressed: a motivation diagram should not offer application components in its search results.

The change adds an optional `accepted_entity_types` filter — a set of entity type names (e.g. `{"driver", "goal", "requirement"}`) derived from the active kind's `effective_entity_types()`. When provided, only entities whose type is in the set are candidates.

```python
def fuzzy_entity_hits(
    repo: Any,
    q: str,
    limit: int,
    excluded: set[str],
    accepted_entity_types: set[str] | None = None,   # NEW — entity type names, not artifact-types
) -> list[dict[str, Any]]:
    ...
    for rec in repo.list_entities():
        if is_internal_entity_type(rec.artifact_type) or rec.artifact_id in excluded:
            continue
        if accepted_entity_types and rec.artifact_type not in accepted_entity_types:
            continue   # NEW: restrict to kinds's accepted entity types
        ...
```

The `accepted_entity_types` set is derived from `DiagramTypeModule.effective_entity_types()` by the router before calling this helper. Diagram-only element types are excluded (they are never in the entity store). The existing `/api/diagrams/{id}/context/entity-search` endpoint gains an optional `diagram_type` query parameter; when provided, the router resolves the kind and passes the accepted types set.

---

## 5. Frontend Architecture

### 5.1 Component responsibilities

```
CreateDiagramView / EditDiagramView
  │
  ├─ DiagramTypeSelect                 (new)
  │     Fetches /api/diagram-types
  │     Emits selected key
  │
  ├─ EntityPickerInput                 (extended)
  │     Props: excludedIds, acceptedTypes: Set<string>
  │     Filters search results client-side before display
  │     Server-side: passes diagram_type to entity-search endpoint
  │
  ├─ KindConfigPanel                   (new, generic)
  │     Props: uiConfig: DiagramKindUiConfig, kindData: unknown
  │     Emits: kindDataChange(patch: Record<string, unknown>)
  │     Renders:
  │       • For each diagram_only_type: DiagramOwnEntityTypeSection
  │       • For each kind_ui_slot: looks up and mounts slot component
  │
  └─ DiagramAuthoringExtensions        (new, module-level singleton)
        Map<string, Component>
        Populated at app startup by kind-specific plugin imports
        Example: extensions.set('swimlane-assignment', SwimlaneAssignmentPanel)
```

### 5.2 `DiagramOwnEntityTypeSection` — generic diagram-only entity manager

For each entry in `ui_config.diagram_only_types`, `KindConfigPanel` renders a section that:

1. Displays existing instances (read from `kindData`).
2. Allows add/remove within `min`/`max` constraints.
3. If `permitted_mappings` is non-empty (has at least one entry in `entity_types` or `entity_classes`), shows a model-entity picker on each instance; results are filtered to entities matching either list. If `mapping_required` is `true`, the instance cannot be saved without a selection.
4. Writes changes back as a `kindDataChange` event.

This component requires **no per-kind code** for the common case (e.g. adding/removing swimlanes with an optional role reference).

### 5.3 Slot extension pattern

When a kind declares `kind_ui_slots`, `KindConfigPanel` looks up the component in `DiagramAuthoringExtensions` and mounts it with a standard slot interface:

```typescript
interface KindSlotProps {
  diagramId: string
  uiConfig: DiagramKindUiConfig
  kindData: unknown
  entities: EntityDisplayInfo[]        // entities currently in diagram
  onKindDataChange: (patch: unknown) => void
}
```

Slot components have full access to diagram context and can implement arbitrary UX (drag-to-lane, step reordering, etc.). They are registered once at app startup; the generic editor mounts them without knowing their internals.

### 5.4 State flow in `EditDiagramView`

```
load diagram
  → fetch DiagramDetail (includes diagram_entities)
  → fetch /api/diagram-types/{type}/ui-config

user interacts with KindConfigPanel
  → kindDataChange events produce local kindDataPatch (deep-merged onto base diagram_entities)

user clicks Save
  → PUT /api/diagrams/{id}  body: { entity_ids, diagram_entities: merged }
  → backend writes diagram-entities: to frontmatter, regenerates PUML
  → success: re-fetch diagram to sync PUML preview
```

`kindDataPatch` is held in a `ref<Record<string, unknown>>` and merged into the payload on submit. The `EditDiagramView` does not interpret the structure; it is owned by `KindConfigPanel` and its children.

### 5.5 `CreateDiagramView` — diagram type selection

Replace the hardcoded `DIAGRAM_TYPES` array with a fetch from `/api/diagram-types` on component mount. On selection, fetch the `ui-config` for the chosen type and pass it to `KindConfigPanel`. This is a blocking fetch (no kind-specific UI shown until config arrives) with a skeleton loader.

---

## 6. MCP Tool Changes

### `artifact_create_diagram`

Add optional parameter:
```
diagram_entities: object | null
  Diagram-kind–specific structured data (e.g. swimlane definitions).
  Stored verbatim in the diagram's diagram-entities: frontmatter block.
  Structure is defined by the diagram type — pass null or omit if not needed.
```

### `artifact_edit_diagram`

Add optional parameter:
```
diagram_entities: object | null
  Replaces the diagram's diagram-entities: block entirely (deep merge not performed server-side).
  Read the current value via artifact_query_read_artifact before editing if partial update is needed.
```

### `artifact_query_list_artifacts` (diagrams)

No change to response shape. `diagram_entities` is already present via the `extra` → `diagram_entities` rename.

### `artifact_query_read_artifact`

Returns `diagram_entities` field in diagram records (populated from frontmatter). AI agents can read this, modify it, and write it back via `artifact_edit_diagram`.

---

## 7. Invariants and Contracts

1. **PUML is always derived.** No tool, API endpoint, or MCP operation writes PUML directly. It is regenerated on every save.
2. **Diagram-only entities do not appear in the entity store.** They are not returned by `list_entities`, `search_artifacts`, or any entity query.
3. **`diagram_entities` is opaque to the core API.** Validation of its internal structure is the diagram type's responsibility (in its renderer and potentially a dedicated validator method on `DiagramTypeModule`).
4. **`accepted_entity_types` filtering is advisory on the client, enforced on the server.** The entity-add endpoint rejects entity IDs whose type is not in `kind.effective_entity_types()`.
5. **Slot components are opt-in.** If a declared slot key is not found in `DiagramAuthoringExtensions`, `KindConfigPanel` logs a warning and omits the slot. It does not break the editor.
6. **Mapping references are soft.** A deleted model entity leaves a stale `model_entity_id` in `diagram_entities`. The renderer must tolerate missing model entity references gracefully (display the label only).
7. **The rendering pipeline strips `.puml` frontmatter before calling PlantUML.** Any leading `---…---` YAML block is removed from the string passed to PlantUML. This is always applied, regardless of whether the kind uses `.puml` frontmatter.
8. **Renderers are responsible for compact PUML output.** `diagram_entities` is never serialised verbatim into the PUML body. Renderers should warn when output size exceeds a configurable threshold (default: 8 000 characters rendered PUML) and may refuse to render when a hard limit is exceeded.

---

## 8. Activity Diagram Type — Concrete Example

To make the architecture tangible, here is the full specification for the `activity` kind that Phase 2 will implement:

```yaml
# src/diagram_types/activity/config.yaml
name: activity
accepted_domains: []   # all domains (activity participants can be from any layer)
ui:
  label: "Activity Diagram"
  description: "UML activity diagram with swimlanes"
  entity_search_filter: true
  diagram_only_types:
    - entity_type: swimlane
      label: Swimlane
      plural: Swimlanes
      min: 2
      max: null
      permitted_mappings:
        entity_types: [role, business-actor, application-component]
        entity_classes: []
      mapping_required: false
  kind_ui_slots:
    entity_context_panel: swimlane-assignment
```

`diagram_entities` shape for activity diagrams:
```typescript
interface ActivityKindData {
  swimlanes: Array<{
    id: string               // local UUID, e.g. "sw-1"
    label: string
    model_entity_id?: string // optional reference to a model entity
  }>
  lane_assignments: Record<string, string>  // entity_id → swimlane_id
}
```

Frontend slot component `SwimlaneAssignmentPanel`:
- Shows the entity currently focused in the diagram sidebar.
- Displays which swimlane it is currently assigned to (or "unassigned").
- Provides a dropdown to reassign — emits `kindDataChange` with updated `lane_assignments`.
- No drag-and-drop in Phase 2; drag is a Phase 3 enhancement.

PUML renderer for activity diagrams (`src/diagram_types/activity/renderer.py`):
- Groups entities inside `|swimlane_label|` / `|swimlane_label|` partition blocks.
- Unassigned entities go into a default "Unassigned" lane at the end.
- Connection lines are rendered between entities as ArchiMate relationships (same as other kinds).
- Swimlane header shows `model_entity_id` entity name if set, otherwise the swimlane `label`.

---

## 9. What Does NOT Change

- The `DiagramTypeModule` protocol's `accepts_entity_type` / `accepts_connection_type` interface — these remain the canonical gate for backend validation.
- The `PermittedRelationshipSet` — connection rules between model entity types are unchanged.
- Entity file format and storage — no changes to how model entities are stored.
- The MCP read tools — no new tools needed; the existing `artifact_query_read_artifact` returns `diagram_entities`.

---

## 10. Implementation Checklist (Phase 2)

Work through the groups in order — each group depends on the one above it.

### Group A — Protocol and config infrastructure

- [ ] `src/domain/ontology_protocol.py` — add `PermittedMappingSpec`, `DiagramOwnEntityTypeUiConfig`, `DiagramKindUiConfig` dataclasses; add `ui_config` property to `DiagramTypeModule` protocol
- [ ] `src/diagram_types/_archimate_kind.py` — add `ui_config` default to `DiagramKindBase`; extend YAML config parsing to handle the `ui:` section (label, description, entity_search_filter, diagram_only_types, kind_ui_slots)
- [ ] `src/infrastructure/rendering/generic_puml_renderer.py` — add frontmatter-stripping step (strip leading `---…---` YAML block from `.puml` content before passing to PlantUML); add configurable size-threshold warning (default 8 000 chars)

### Group B — New API endpoints

- [ ] `src/infrastructure/gui/routers/diagram_types.py` (NEW FILE) — implement `GET /api/diagram-types` (list all registered kinds with key/label/description) and `GET /api/diagram-types/{diagram_type}/ui-config` (full serialised `DiagramKindUiConfig`)
- [ ] `src/infrastructure/gui/routers/__init__.py` — register the new `diagram_types` router

### Group C — Diagram read/write `diagram_entities`

- [ ] `src/infrastructure/gui/routers/diagrams.py` — expose `diagram_entities` field in diagram detail response (extracted as `rec.extra.get("diagram-entities")`; `DiagramRecord.extra` is NOT modified)
- [ ] `src/infrastructure/gui/routers/_diagram_write.py` — add optional `diagram_entities: dict | None` to `CreateDiagramGuiBody` and `EditDiagramGuiBody`; pass through to write layer
- [ ] `src/infrastructure/write/artifact_write/diagram.py` — accept `diagram_entities` param; write it to the `diagram-entities:` frontmatter key; regenerate PUML after write
- [ ] `src/infrastructure/write/artifact_write/diagram_edit.py` — same for edit

### Group D — Kind-scoped entity search

- [ ] `src/infrastructure/gui/routers/_diagram_context.py` — add `accepted_entity_types: set[str] | None = None` param to `fuzzy_entity_hits()`; filter candidates when set
- [ ] `src/infrastructure/gui/routers/diagrams.py` — update entity-search endpoint to accept optional `diagram_type` query param; resolve kind via registry; derive `accepted_entity_types` from `kind.effective_entity_types()`; pass to `fuzzy_entity_hits()`

### Group E — MCP tool updates

- [ ] `src/infrastructure/mcp/artifact_mcp/write/diagram.py` — add optional `diagram_entities: dict | None` parameter to `artifact_create_diagram` and `artifact_edit_diagram`; pass through to write layer
- [ ] `src/infrastructure/mcp/artifact_mcp/write_tools.py` — update tool description strings
- [ ] `src/infrastructure/mcp/artifact_mcp/query_list_read_tools.py` — confirm `diagram_entities` is included in diagram read responses

### Group F — Activity diagram type

- [ ] `src/diagram_types/activity/` (NEW DIR) — `config.yaml` per RFC §8; `__init__.py`; `renderer.py` implementing `ActivityPumlRenderer` (swimlane `|Lane|` partitions; unassigned lane fallback; `model_entity_id` label resolution; compact output)
- [ ] `src/diagram_types/__init__.py` — register the `activity` kind

### Group G — Tests

- [ ] `tests/tools/test_diagram_type_routes.py` — extend with: `ui_config` endpoint returns correct shape; `diagram_kind_entity_type_items` respects hierarchy; `fuzzy_entity_hits` accepts `accepted_entity_types` filter
- [ ] `tests/tools/test_diagram_write_selection.py` (or new `tests/tools/test_diagram_kind_data.py`) — `diagram_entities` round-trips through create and edit; appears in detail response
- [ ] `tests/rendering/test_activity_renderer.py` (NEW) — renders swimlanes correctly; unassigned fallback lane; frontmatter stripped before PlantUML; size warning at threshold
- [ ] `tests/domain/test_protocol_compliance.py` — add `activity` kind to protocol compliance check

### Group H — Frontend

- [ ] `tools/gui/src/domain/schemas.ts` — add `PermittedMappingSpecSchema`, `DiagramOwnEntityTypeUiConfigSchema`, `DiagramKindUiConfigSchema`; add `diagram_entities: Schema.optional(Schema.Unknown)` to `DiagramDetailSchema`; verify whether `extra` is used in any view and remove if not
- [ ] `tools/gui/src/ports/ModelRepository.ts` — add `listDiagramKinds(): Effect<DiagramKindSummary[]>` and `getDiagramKindUiConfig(type: string): Effect<DiagramKindUiConfig>` to port
- [ ] `tools/gui/src/adapters/http/HttpModelRepository.ts` — implement the two new port methods
- [ ] `tools/gui/src/ui/lib/diagramAuthoringExtensions.ts` (NEW) — `DiagramAuthoringExtensions` as a `Map<string, Component>` singleton; export `registerExtension` and `lookupExtension`
- [ ] `tools/gui/src/ui/components/DiagramTypeSelect.vue` (NEW) — fetches `/api/diagram-types`; emits selected key and full summary object
- [ ] `tools/gui/src/ui/components/DiagramOwnEntityTypeSection.vue` (NEW) — generic add/remove panel for one diagram-only entity type; respects min/max; renders `permitted_mappings` picker when non-empty; blocks save if `mapping_required` and no entity selected
- [ ] `tools/gui/src/ui/components/KindConfigPanel.vue` (NEW) — receives `uiConfig` + `kindData`; renders one `DiagramOwnEntityTypeSection` per `diagram_only_types` entry; mounts slot component per `kind_ui_slots` entry via `lookupExtension`; emits `kindDataChange` patch
- [ ] `tools/gui/src/ui/components/EntityPickerInput.vue` — add `acceptedTypes: Set<string>` prop; client-side filter of search results; pass `diagram_type` query param to entity-search endpoint
- [ ] `tools/gui/src/ui/views/CreateDiagramView.vue` — replace hardcoded `DIAGRAM_TYPES` with `DiagramTypeSelect`; on type selection fetch `ui-config` and pass to `KindConfigPanel`; include `diagram_entities` in create payload
- [ ] `tools/gui/src/ui/views/EditDiagramView.vue` — fetch `ui-config` on load; integrate `KindConfigPanel`; hold `kindDataPatch` ref; deep-merge onto base `diagram_entities` on save
- [ ] `tools/gui/src/ui/components/SwimlaneAssignmentPanel.vue` (NEW) — slot component; shows current lane assignment for focused entity; dropdown to reassign; emits `kindDataChange` with updated `lane_assignments`
- [ ] `tools/gui/src/main.ts` — register slot components into `DiagramAuthoringExtensions` at app startup

### Group I — Docs

- [ ] `src/diagram_types/README.md` — replace `domain_dir` → `hierarchy[0]`; document the `ui:` config section and `DiagramAuthoringExtensions` slot pattern
