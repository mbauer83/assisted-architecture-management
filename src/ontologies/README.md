# Ontology Modules

Each subdirectory is a self-contained *ontology module* — a pluggable vocabulary of entity types, connection types, and permitted relationship rules. The system loads all registered modules at startup and merges them into the global `ModuleRegistry`.

## How it fits together

```
src/ontologies/
  archimate_next/     ← shipped module
  <your-ontology>/    ← your module here
  __init__.py

src/infrastructure/app_bootstrap.py   ← register modules here
src/domain/ontology_protocol.py       ← OntologyModule protocol definition
src/domain/module_registry.py         ← ModuleRegistry class
```

## Adding a new ontology module

### Step 1 — Create the package directory

```
src/ontologies/my_ontology/
  __init__.py
  entities.yaml
  connections.yaml        (optional — only if the ontology defines connection types)
  _loader.py              (optional — use the archimate_next loader as a template)
```

### Step 2 — Define entity types in `entities.yaml`

```yaml
# entities.yaml
entity_types:
  block:
    prefix: BLK
    domain: system
    subdir: blocks
    archimate_element_type: ~          # null if not an ArchiMate element
    has_sprite: false
    classes: [structure-element]
    create_when: "Create blocks to model physical or logical components of a system."
    never_create_when: "Don't use blocks for behavioural elements; use activities instead."

  activity:
    prefix: ACT
    domain: system
    subdir: activities
    archimate_element_type: ~
    has_sprite: false
    classes: [behavior-element]
    create_when: "Create activities to model what a block does."
    never_create_when: ""
```

Required fields for each entity type:

| Field | Type | Purpose |
|---|---|---|
| `prefix` | string | Short uppercase prefix used in generated artifact IDs (e.g. `BLK@...`) |
| `domain` | string | Filesystem domain directory under `model/` |
| `subdir` | string | Subdirectory within the domain |
| `archimate_element_type` | string or `~` | CamelCase ArchiMate type name; `~` for non-ArchiMate ontologies |
| `has_sprite` | bool | Whether a diagram sprite exists (only meaningful for ArchiMate rendering) |
| `classes` | list of strings | Classification classes used by diagram type filters and connection rules |
| `create_when` | string | Agent/user guidance — when to create this type |
| `never_create_when` | string | Agent/user guidance — when not to create this type |

The special `internal: true` flag marks an entity type as system-managed (e.g. `global-artifact-reference`). Internal types are excluded from all user-facing type catalogs and domain listings.

### Step 3 — Define connection types and rules in `connections.yaml` (optional)

```yaml
# connections.yaml
connection_types:
  my-connects:
    conn_lang: sysml
    archimate_relationship_type: ~
    puml_arrow: "-->"
    symmetric: false
    classes: [flow]

permitted_relationships:
  - [block, block, [my-connects]]
  - [block, activity, [my-connects]]
  - ["@behavior-element", "@structure-element", [my-connects]]
```

The source/target columns accept:
- A literal entity type name: `block`
- `@<class>` — all entity types with that `classes` entry
- `@all` — every entity type in this ontology
- A list: `[block, activity]` — union of the listed types/classes
- `@same` — the same entity type as the source (for self-referential rules)

### Step 4 — Implement the module object

The simplest implementation uses a loader that produces an `OntologyModule`-compatible object:

```python
# src/ontologies/my_ontology/__init__.py
from __future__ import annotations

from pathlib import Path
from collections.abc import Mapping
from src.domain.module_types import ConnectionTypeName, ElementClassName, EntityTypeName
from src.domain.ontology_types import ConnectionTypeInfo, EntityTypeInfo
from src.domain.permitted_relationships import PermittedRelationshipSet

class _MyOntologyModule:
    name = "my-ontology"

    def __init__(
        self,
        entity_types: dict[EntityTypeName, EntityTypeInfo],
        connection_types: dict[ConnectionTypeName, ConnectionTypeInfo],
        permitted: PermittedRelationshipSet,
    ) -> None:
        self._entity_types = entity_types
        self._connection_types = connection_types
        self._permitted = permitted

    @property
    def entity_types(self) -> Mapping[EntityTypeName, EntityTypeInfo]:
        return self._entity_types

    @property
    def connection_types(self) -> Mapping[ConnectionTypeName, ConnectionTypeInfo]:
        return self._connection_types

    @property
    def permitted_relationships(self) -> PermittedRelationshipSet:
        return self._permitted

    def entity_types_with_class(self, cls: ElementClassName) -> frozenset[EntityTypeName]:
        return frozenset(n for n, info in self._entity_types.items() if cls in info.classes)

    def connection_types_with_class(self, cls: str) -> frozenset[ConnectionTypeName]:
        return frozenset(
            n for n, info in self._connection_types.items()
            if cls in info.classes
        )

    def permits_connection(
        self, src: EntityTypeName, tgt: EntityTypeName, conn: ConnectionTypeName
    ) -> bool:
        return self._permitted.permits(src, tgt, conn)


# Load at import time so `from src.ontologies.my_ontology import module` works
# (same pattern as archimate_next)
def _load() -> _MyOntologyModule:
    # parse entities.yaml, connections.yaml → build entity_types, connection_types, permitted
    # see src/ontologies/archimate_next/_loader.py for a full example
    ...

module = _load()
```

See `src/ontologies/archimate_next/_loader.py` for a complete loader implementation including YAML parsing, `@class` expansion, and `permitted_relationships` rule processing.

### Step 5 — Register the module

In `src/infrastructure/app_bootstrap.py`:

```python
from src.ontologies.my_ontology import module as my_ontology_module

def build_module_registry() -> ModuleRegistry:
    registry = ModuleRegistry()
    registry.register_ontology(archimate_next_module)
    registry.register_ontology(my_ontology_module)   # ← add this line
    register_default_diagram_types(registry)
    return registry
```

The registry merges all ontologies: `registry.all_entity_types()` returns the union of every registered ontology's entity vocabulary. Type names must be globally unique across all registered ontologies.

### Step 6 — Add a diagram type (optional)

If the new ontology needs a purpose-built diagram view, add a diagram type package under `src/diagram_types/`. See `src/diagram_types/README.md` for the extension contract.

## Cross-ontology connection rules and ownership

Connection rules are globally unique: entity type names must not collide across registered ontologies (enforced at startup). This means an ArchiMate `permitted_relationships` rule referencing a `business-actor` source unambiguously identifies the same type regardless of which ontology contributed it.

Cross-ontology reuse inside diagram types is handled separately from canonical model ownership. Diagram-owned entity types may declare `permitted_mappings.sources` to transparently reuse model entity types or element classes from one or more ontologies. Keep those mappings in the diagram type module rather than duplicating canonical entity types across ontologies.

Connections fall into two ownership categories:

| Category | Who declares the rule | Who owns the connection instance |
|---|---|---|
| **Model-to-model** | `permitted_relationships` in any `OntologyModule` | The model; stored as `ConnectionRecord` in the model store |
| **Diagram-owned** | `permitted_connections` on a `DiagramOwnEntityTypeUiConfig` | The diagram; stored in `diagram-entities:` frontmatter |

A connection between two model entity types is always model-owned. A connection that involves at least one diagram-only entity type (a type declared in `diagram_only_types` of some diagram type) must be declared as a diagram-owned rule. Use `ModuleRegistry.is_diagram_entity_type(name)` to classify a type at runtime.

`DiagramKindBase.effective_permitted_relationships` automatically merges:
1. Ontology `permitted_relationships` filtered to accepted entity/connection types
2. The diagram type's `own_permitted_relationships`
3. All `permitted_connections` rules from every `diagram_only_types` entry

## Protocol contract

Every ontology module must satisfy the `OntologyModule` protocol defined in `src/domain/ontology_protocol.py` (it is `@runtime_checkable`). The protocol compliance test suite in `tests/domain/test_protocol_compliance.py` verifies all registered modules on every CI run:

- `isinstance(module, OntologyModule)` must return `True`
- `permitted_relationships._rules` must only reference entity type names present in `entity_types`
- `permitted_relationships._rules` must only reference connection type names present in `connection_types`
- `entity_types_with_class(cls)` must return a subset of `entity_types`

## Required connections and owned entity types

`EntityTypeInfo` supports a `required_connections` field (tuple of `RequiredConnection`). This is primarily used by diagram types for annotation/owned entity types (e.g. `note` entities that must always be attached to a host step). Non-ArchiMate model ontologies with owned member entities (class diagrams, SysML block-and-part diagrams) may also use `required_connections` to declare mandatory structural relationships.

`RequiredConnection` fields:
- `connection_type` — name of the connection type
- `target` — entity type name or `@class-name` reference
- `cardinality_min`, `cardinality_max` — bounds (`None` max = unbounded)

For diagram types, `required_connections` on diagram-owned entity types drives annotation schema injection: when a connection type has `embedding: property`, the annotation entity's schema is injected as a named property (under `embed_key`) into the `$defs` of each matching host entity type in the generated diagram-entities JSON Schema.

At runtime, note→step relationships are stored as `ConnectionRecord` objects (with the declared `conn_type`), not as properties on the note entity. Renderers receive the `connections` sequence alongside `diagram-entities` and build a step-id → note index from connections of the relevant type.

## Element class declarations

Every element class referenced in the `classes` field of any entity type must be declared in the originating module. Model ontologies declare them in `entities.yaml` under a top-level `element_classes:` block:

```yaml
element_classes:
  structure-element:
    description: Static structural element (ArchiMate)
  behavior-element:
    description: Dynamic/behavioral element (ArchiMate)
```

Diagram types declare their element classes in `config.yaml` under `element_classes:`. The `ModuleRegistry.all_element_classes()` method merges all declared classes; startup validation aborts if any entity type's `classes` field references an undeclared class.

## Startup validation

At backend startup, `src/application/startup_validation.py` compares every entity type, connection type, and diagram type found in indexed repo content against the registered modules. Startup is aborted if any unsupported type is found, with a report listing each unknown type and an example artifact ID. This prevents silent data corruption when an ontology module is removed or renamed while repos still contain artifacts of that type.

The validator also checks element class declarations: every `classes` value on every registered entity type and diagram-only entity type must be present in `registry.all_element_classes()`. Unknown class references are reported as errors.
