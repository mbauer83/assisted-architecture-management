# Implementation Plan: Meta-Ontology Structural Kinds

**Status**: Approved design, ready to implement  
**No backwards compatibility required** — delete old mechanisms cleanly.

---

## 1. Goal

Replace the implicit, hardcoded structural assumptions in the diagram-type system
(hardcoded `_NOTE_DEF`, `kind_data_key` on entity types, `$defs/Step` generated from
connection keys) with a uniform, declarative ontology mechanism that works identically
for model ontologies and diagram-type entity ontologies.

---

## 2. Approved Design

### 2.1 Level vocabulary

`element_classes` is the Level 3 vocabulary — the system of kinds / meta-types. An entity
type's `element_classes` list declares its semantic and structural roles. Examples:

| Class | Meaning |
|---|---|
| `step` | Can appear in a steps/sequence array in a parent diagram or entity |
| `state` | Can appear in a states array (state-machine diagrams) |
| `class-member` | Can appear in a members array (class diagrams) |
| `grouping` | A grouping/partition entity; appears as a top-level collection in diagram-entities |
| `annotation` | An annotation; always embedded as a named property on a host entity |
| `control-flow` | Participates in control flow (semantic; may combine with `step`) |
| `structure-element`, `behavior-element`, … | Existing ArchiMate classes; unchanged |

No `structural_kind` field on entity types. Structural role is derived by the framework
from the entity type's element classes and its required connections.

### 2.2 Element class declarations

Element classes must be explicitly declared before use. Declaration location:

- **Model ontologies** (`src/ontologies/*/entities.yaml`): top-level `element_classes:` block
  alongside `entity_types:`. Each entry is a name + optional description.

  ```yaml
  element_classes:
    structure-element:
      description: "Static structural element (ArchiMate)"
    behavior-element:
      description: "Dynamic/behavioral element (ArchiMate)"
    # …
  ```

- **Diagram types** (`src/diagram_types/*/config.yaml`): top-level `element_classes:` block
  in `config.yaml` (not `ontology.yaml`). The class vocabulary is a kind-level identity
  concern, not a structural ontology rule.

  ```yaml
  # src/diagram_types/activity/config.yaml
  element_classes:
    step:
      description: "An entity type that can appear in a steps/sequence array"
    grouping:
      description: "A grouping or partitioning entity"
    annotation:
      description: "An annotation attached to another entity as a property"
    control-flow:
      description: "Participates in control flow within an activity"
  ```

`ModuleRegistry` merges all declared element classes at startup. Startup validation
(existing `startup_validation.py`) must check that every `element_classes` value
on every entity type references a declared class. Unknown class references abort startup.

### 2.3 Connection types — structural effects

Connection types may carry structural effects:

```yaml
connection_types:
  step-note-of:
    embedding: property       # "property": host entity gains a named property
    embed_key: note           # the property name injected into the host's schema
    cascade_delete_source: true  # host deleted → note deleted

  some-sequence-conn:
    embedding: array          # "array": parent gains a typed array property
    embed_key: steps          # the array key in the parent's schema / diagram-entities
    cascade_delete_source: true
```

`embedding` values: `property` | `array` | omit/`none` (no structural effect).

Connection types without `embedding` are plain permission/reference connections.

### 2.4 `required_connections` on entity types

Entity types that must always be attached to a host entity declare this:

```yaml
entity_types:
  note:
    element_classes: [annotation]
    required_connections:
      - connection_type: step-note-of
        target: "@step"      # @class-name or concrete entity type name
        cardinality: [1, 1]  # [min, max]; null max = unbounded
```

**No `target: _diagram` or `target: _diagram` sentinel exists.** Embedding into the
diagram itself is never specified via required connections — it is implicit from the
entity type's membership in a diagram type's ontology. See §2.4.

### 2.5 Top-level diagram type-data structure

Diagram-scoped entities that appear at the root of `diagram-entities` are declared by a
`kind_data_root` block in `ontology.yaml`:

```yaml
kind_data_root:
  - key: swimlanes       # key in diagram-entities YAML / JSON Schema root
    element_class: grouping   # all entity types with this class go in this array
  - key: steps
    element_class: step
```

The schema generator builds one top-level array per entry. Each array is typed as
`oneOf` all entity types in this diagram type that carry the specified element class.
No connection types to "the diagram" are needed; no sentinel values.

### 2.6 `permitted_relationships`

Diagram type `ontology.yaml` has the same `permitted_relationships` syntax as model
ontologies — `[source, target, [conn_types]]` — using entity type names or `@class-name`.
These are the general permission rules (what is allowed). `required_connections` on entity
types is separate (what is mandatory for a valid instance).

### 2.7 `scope` — parse-time only

`scope` is never declared by authors. The loader stamps it at parse time:
- `src/ontologies/*/` → `model` scope
- `src/diagram_types/*/ontology.yaml` → `diagram` scope

### 2.8 `target_storage` — removed

Not configurable. Rule: if either endpoint is a diagram-only entity type, the connection
is stored in the diagram's `diagram-entities`. Otherwise stored in the source entity's
`.outgoing.md`. No `target_storage` field exists anywhere.

### 2.9 Schema-property profiles

Remain repository-owned (engagement-level customization on top of module-level type
specs). No change to this mechanism.

---

## 3. New `ontology.yaml` for activity diagram

Create `src/diagram_types/activity/ontology.yaml`:

```yaml
kind_data_root:
  - key: swimlanes
    element_class: grouping
  - key: steps
    element_class: step

connection_types:
  step-note-of:
    embedding: property
    embed_key: note
    cascade_delete_source: true

  swimlane-maps-to: {}        # reference only; no structural effect

entity_types:
  swimlane:
    element_classes: [grouping]
    properties:
      {}                       # no domain-specific properties; id/label system-managed

  action:
    element_classes: [control-flow, step]
    properties:
      lane_id:
        type: string
        required: false
        description: ID of the swimlane this action belongs to
      link:
        type: string
        required: false
        description: URL attached to the action label as a hyperlink

  decision:
    element_classes: [control-flow, step]
    properties:
      condition:   {type: string, required: true,  description: Condition text shown in the diamond}
      then_label:  {type: string, required: true,  description: Label on yes/true branch arrow}
      else_label:  {type: string, required: true,  description: Label on no/false branch arrow}
      then_steps:
        type: array
        items: {$ref: "#/$defs/step"}
        required: true
        description: Steps taken when condition is true
      else_steps:
        type: array
        items: {$ref: "#/$defs/step"}
        required: true
        description: Steps taken when condition is false
      lane_id: {type: string, required: false}

  fork:
    element_classes: [control-flow, step]
    properties:
      branches:
        type: array
        items:
          type: array
          items: {$ref: "#/$defs/step"}
        required: true
        description: Array of branches; each branch is an array of steps
      lane_id: {type: string, required: false}

  partition:
    element_classes: [grouping, step]
    properties:
      steps:
        type: array
        items: {$ref: "#/$defs/step"}
        required: true
        description: Steps inside the partition

  note:
    element_classes: [annotation]
    required_connections:
      - connection_type: step-note-of
        target: "@step"
        cardinality: [1, 1]
    properties:
      side: {type: string, enum: [left, right], required: false}
      text: {type: string, required: true}

permitted_relationships:
  - [swimlane, business-actor,         [swimlane-maps-to]]
  - [swimlane, role,                   [swimlane-maps-to]]
  - [swimlane, application-component,  [swimlane-maps-to]]
```

---

## 4. Python data model changes

### 4.1 New dataclasses (add to `src/domain/ontology_types.py`)

```python
@dataclass(frozen=True)
class RequiredConnection:
    connection_type: ConnectionTypeName
    target: str          # entity type name, "@class-name", (never "_diagram")
    cardinality_min: int
    cardinality_max: int | None  # None = unbounded
```

### 4.2 `ConnectionTypeInfo` — add fields

```python
@dataclass(frozen=True)
class ConnectionTypeInfo:
    # existing fields …
    embedding: Literal["none", "array", "property"] = "none"
    embed_key: str | None = None        # array key or property name
    cascade_delete_source: bool = False  # source deleted → this entity deleted
```

### 4.3 `EntityTypeInfo` — add field, no removal needed

```python
@dataclass(frozen=True)
class EntityTypeInfo:
    # existing fields …
    required_connections: tuple[RequiredConnection, ...] = ()
```

### 4.4 `DiagramOwnEntityTypeUiConfig` (in `ontology_protocol.py`)

- **Remove** `kind_data_key: str` field.
- **Add** `required_connections: tuple[RequiredConnection, ...]` field (default empty tuple).
- All construction sites must be updated.

### 4.5 `KindDataRootEntry` — new dataclass (add to `ontology_protocol.py` or `ontology_types.py`)

```python
@dataclass(frozen=True)
class KindDataRootEntry:
    key: str               # diagram-entities array key (e.g. "steps", "swimlanes")
    element_class: str     # element class whose members populate this array
```

### 4.6 `DiagramKindUiConfig` — add field

Add `kind_data_root: tuple[KindDataRootEntry, ...]` (default empty tuple).  
This is loaded from `ontology.yaml` and passed through to the schema generator.

---

## 5. Files to create

| File | Purpose |
|---|---|
| `src/diagram_types/activity/ontology.yaml` | New ontology spec (§3 above) |
| `src/domain/diagram_ontology_loader.py` | Loader for diagram type `ontology.yaml` files |

---

## 6. Files to modify

### `src/domain/ontology_types.py`
- Add `RequiredConnection` dataclass (§4.1).
- Add `embedding`, `embed_key`, `cascade_delete_source` to `ConnectionTypeInfo` (§4.2).
- Add `required_connections` to `EntityTypeInfo` (§4.3).

### `src/domain/ontology_protocol.py`
- Remove `kind_data_key: str` from `DiagramOwnEntityTypeUiConfig`.
- Add `required_connections: tuple[RequiredConnection, ...]` to `DiagramOwnEntityTypeUiConfig`.
- Add `KindDataRootEntry` dataclass.
- Add `kind_data_root: tuple[KindDataRootEntry, ...]` to `DiagramKindUiConfig`.
- Update `_own_entity_ui_config_from_mapping()`: remove `kind_data_key` parsing, add
  `required_connections` parsing (parse list of `{connection_type, target, cardinality}` dicts).
- Update `diagram_kind_ui_config_from_mapping()`: accept optional `kind_data_root` list.
- Keep file at or under 350 lines (hard limit).

### `src/domain/module_registry.py`
- Add `all_element_classes() -> dict[str, ElementClassInfo]` (merged across all modules).
- Raise `ValueError` on duplicate element class name across modules.

### `src/domain/diagram_entities_schema.py`
Full rewrite of `derive_diagram_entities_schema()`. New signature:

```python
def derive_diagram_entities_schema(
    own_types: tuple[DiagramOwnEntityTypeUiConfig, ...],
    kind_data_root: tuple[KindDataRootEntry, ...],
    connection_types: dict[str, ConnectionTypeInfo],
) -> dict[str, object]:
```

Logic:
1. Build `$defs` — one entry per entity type (its JSON Schema fragment from `properties`).
2. For each `KindDataRootEntry(key, element_class)`: collect all entity types whose
   `element_classes` contains `element_class`. Build a `oneOf` union named `$defs/<element_class>`
   if more than one member; otherwise inline. Add `key: {type: array, items: ...}` to root
   `properties`.
3. For entity types with a required connection to a connection type where
   `embedding == "property"`: find all host entity types (those matching the `target`
   class/name in the required connection). For each host, inject
   `embed_key: <schema of the annotation entity type>` into its `$defs` properties.
4. Remove all hardcoded `_NOTE_DEF`. Remove the hardcoded `"note"` entry in `$defs`.
   The note schema is generated from the `note` entity type's `properties` in step 1.

### `src/diagram_types/activity/__init__.py`
- Load `ontology.yaml` via the new `diagram_ontology_loader`.
- Merge loaded entity types (from ontology) with UI metadata (from `config.yaml`
  `diagram_only_types`) by joining on `entity_type` name.
- Pass `kind_data_root` from ontology to `DiagramKindUiConfig`.
- Pass `connection_types` from ontology to `write_guidance()` → `derive_diagram_entities_schema()`.
- Remove `_OWN_ENTITY_TYPES` and `_OWN_CONNECTION_TYPES` empty dicts if they are
  replaced by loaded data; otherwise keep if still needed for protocol compliance.

### `src/diagram_types/activity/config.yaml`
- Remove `kind_data_key` from every `diagram_only_types` entry.
- Remove `element_classes` from every `diagram_only_types` entry (moved to `ontology.yaml`).
- Remove `properties` from every `diagram_only_types` entry (moved to `ontology.yaml`).
- Remove `permitted_connections` from every `diagram_only_types` entry (moved to
  `ontology.yaml` as `permitted_relationships`).
- The `$ref: "#/$defs/note"` entries in remaining properties (`then_steps`, `else_steps`,
  `branches`, `steps` on partition) move into `ontology.yaml` and are no longer in
  `config.yaml` at all (those properties now live in `ontology.yaml`).
- After migration, `diagram_only_types` entries in `config.yaml` should contain only:
  `entity_type`, `label`, `plural`, `min`, `max`, `create_when`, `never_create_when`,
  `permitted_mappings`, `mapping_required`.

### `src/diagram_types/activity/renderer.py`
- No structural changes expected; the renderer reads from `diagram_entities` which is unchanged.
- Verify that `note` property access on steps still works (it should, since the schema
  and diagram-entities key `note` come from `embed_key` on the connection type, which equals the
  old hardcoded key).

### `src/infrastructure/write/artifact_write/type_guidance.py`
- `_serialize_own_entity_type()`: stop serialising `kind_data_key` (field removed).

### `src/infrastructure/mcp/artifact_mcp/write/diagram.py` (and related write paths)
- Any code that reads `oe.kind_data_key` to determine where to write diagram-entities entries
  must be updated to use `kind_data_root` lookup by element class instead.

### `src/infrastructure/gui/routers/_diagram_write.py` (and frontend equivalents)
- Any server-side logic that groups entities by `kind_data_key` must switch to grouping
  by element class using the `kind_data_root` mapping.

### `tools/gui/src/` (frontend)
- Any TypeScript code reading `kind_data_key` from the entity type config must switch to
  using `kind_data_root` from the diagram type's UI config.
- Update `types.generated.ts` and `schemas.ts` to remove `kindDataKey` and add
  `kindDataRoot` / `elementClasses` / `requiredConnections` as needed.

### `tests/domain/test_protocol_compliance.py`
- Update any assertions about `kind_data_key` or `_NOTE_DEF`.

### `tests/rendering/test_activity_renderer.py`
- Verify tests still pass; update any that reference `kind_data_key` or `$defs/Note`.
- Add test: schema generator produces `$defs/step` (not `$defs/Step`) containing all
  step entity types.
- Add test: schema generator injects `note` property into step entity schemas.
- Add test: schema generator produces correct `swimlanes` and `steps` root arrays from
  `kind_data_root`.

### `src/diagram_types/README.md`
- Update `config.yaml` schema section: document removal of `kind_data_key`, `element_classes`,
  `properties`, `permitted_connections` from `diagram_only_types`.
- Add `ontology.yaml` schema section: document `kind_data_root`, `entity_types` (with
  `element_classes`, `required_connections`), `connection_types` (with `embedding`,
  `embed_key`), `permitted_relationships`.
- Update the "Diagram-only entity types" section to reflect split between `config.yaml`
  (UI metadata) and `ontology.yaml` (ontology spec).

### `src/ontologies/README.md`
- Add a brief note that `required_connections` and `RequiredConnection` are also valid
  in model ontology entity types (for non-ArchiMate ontologies that have owned/member
  entities such as class diagrams or SysML).

---

## 7. Files to delete

None. All existing files are modified in place.

---

## 8. Implementation phases

### Phase 0 — Element class declaration infrastructure ✅

- [x] Add `ElementClassInfo` dataclass (name, description) to `ontology_types.py`
- [x] Add `element_classes: dict[str, ElementClassInfo]` to `OntologyModule` protocol
      (and to `archimate_next` module's `_ArchimateNextModule` implementation)
- [x] Add `element_classes: dict[str, ElementClassInfo]` to `DiagramTypeModule` protocol
      (and to `DiagramKindBase` default implementation returning `{}`)
- [x] Add `all_element_classes() -> dict[str, ElementClassInfo]` to `ModuleRegistry`
- [x] Update `startup_validation.py` to validate element class references
- [x] Parse `element_classes:` block from `src/ontologies/archimate_next/entities.yaml`
- [x] Parse `element_classes:` block from `config.yaml` for the activity diagram type
- [x] `uv run pytest tests/` — 531 passed

### Phase 1 — Domain model ✅

- [x] Add `RequiredConnection` dataclass to `ontology_types.py`
- [x] Add `embedding`, `embed_key`, `cascade_delete_source` to `ConnectionTypeInfo`
- [x] Add `required_connections` to `EntityTypeInfo`
- [x] Add `KindDataRootEntry` dataclass to `ontology_protocol.py`
- [x] Remove `kind_data_key` from `DiagramOwnEntityTypeUiConfig`; add `required_connections`
- [x] Add `kind_data_root` to `DiagramKindUiConfig`
- [x] Update `_own_entity_ui_config_from_mapping()` and `diagram_kind_ui_config_from_mapping()`
- [x] `uv run pytest tests/` — 531 passed

### Phase 2 — New `ontology.yaml` loader ✅

- [x] Create `src/domain/diagram_ontology_loader.py`
- [x] Create `src/diagram_types/activity/ontology.yaml`
- [x] Update `_ActivityDiagramType.__init__()` to load and merge `ontology.yaml`
- [x] `uv run pytest tests/` — 531 passed

### Phase 3 — Schema generator rewrite ✅

- [x] Rewrite `derive_diagram_entities_schema()`: generic, no hardcoded "steps" names
- [x] Uses discriminated vs. direct schema based on union membership
- [x] Injects embedded properties via `embedding: property` connection types
- [x] `_NOTE_DEF` constant removed; note schema from entity type properties
- [x] `$defs/step` (lowercase) instead of `$defs/Step`
- [x] `uv run pytest tests/` — 531 passed

### Phase 4 — Activity diagram config cleanup ✅

- [x] `config.yaml` `diagram_only_types` entries contain only UI metadata fields
- [x] `uv run pytest tests/` — 531 passed

### Phase 5 — Write path and frontend updates ✅

- [x] `type_guidance.py`: `kind_data_key` removed from serialisation
- [x] No Python code reads `kind_data_key` anywhere
- [x] Frontend TypeScript: no `kindDataKey` references existed (confirmed by grep)
- [x] `uv run zuban check` — clean
- [x] `uv run pytest tests/` — 531 passed

### Phase 6 — Tests and documentation ✅

- [x] New schema generation tests in `tests/domain/test_diagram_entities_schema.py`
- [x] Updated `src/diagram_types/README.md` with ontology.yaml schema section
- [x] Updated `src/ontologies/README.md` with required_connections and element class notes
- [x] Full quality gate: ruff ✅ zuban ✅ pytest 531 passed ✅

---

## 9. Quality gates (must all be green before done)

```
uv run ruff check src tests
uv run zuban check          # requires: uv sync --all-groups first
uv run pytest tests/
```

File size constraint: no Python file over 350 lines (250 soft limit).

---

## 10. Key constraints for implementors

- `_diagram` sentinel does NOT exist anywhere — not in YAML, not in Python. Reject if found.
- `structural_kind` does NOT exist as a field on any entity type spec — not in YAML, not
  in Python. Structural role is derived from element classes and required connections.
- `target_storage` does NOT exist — storage location is determined at runtime by endpoint
  classification.
- `kind_data_key` does NOT exist on `DiagramOwnEntityTypeUiConfig` or in any YAML entity
  type spec after migration. Array membership is determined by `kind_data_root` + element
  class.
- `$defs/Step` (capital S) does NOT exist — it is `$defs/step` (lowercase, matching the
  element class name convention).
- `_NOTE_DEF` hardcoded constant does NOT exist after the schema generator rewrite.
- Required connections from an entity type to the diagram itself are NEVER declared —
  top-level diagram collection membership is declared in `kind_data_root`.
