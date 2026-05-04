# Diagram Kind Modules

Each subdirectory is a *diagram kind module* — a unit that declares which entity and connection types a diagram view accepts, and how those diagrams are rendered. The system loads all registered kinds at startup and exposes them via the `ModuleRegistry`.

## Structure

```
src/diagram_kinds/
  archimate_application/   ← one domain view
    __init__.py
    config.yaml
  archimate_layered/       ← multi-domain view
    __init__.py
    config.yaml
  matrix/                  ← free-ontology (accepts all entity types)
    __init__.py
    config.yaml
  _archimate_kind.py       ← config-backed loader for ArchiMate views
  __init__.py              ← register_default_diagram_kinds()
```

## `config.yaml` schema

```yaml
name: archimate-application          # (required) registry key; matches diagram_type in artifacts

accepted_domains: [application, common]
# Which entity type domain_dir values this view accepts.
# Omit entirely for free-ontology kinds that accept everything.

includes:
  - _archimate-stereotypes.puml      # PlantUML include files injected into every rendered diagram
  - _archimate-glyphs.puml           # relative to the diagram-catalog/ include root

grouping:
  by_field: domain_dir               # field on EntityRecord used to group entities into frame blocks
  stereotype_pattern: "{domain_dir|capitalize}Grouping"
  # PlantUML stereotype for the frame; {domain_dir|capitalize} → "ApplicationGrouping"

layout:
  nesting_connection_classes: [nesting]
  # Connection classes (from element_classes in entities.yaml) that produce visual nesting in the
  # rendered diagram. Connections of these classes draw child entities inside parent frames.

  flow_connection_classes: [flow]
  # Connection classes that produce directed flow arrows (as opposed to structural lines).
```

All fields except `name` are optional. Omitting a field uses the built-in default (empty lists, no grouping, no layout hints).

## Element-class filter table

For ArchiMate-style domain views, `accepted_domains` selects entity types by their `domain_dir`. The loader compares `EntityTypeInfo.domain_dir` against the list. Only entity types with a matching domain are included in `effective_entity_types()` and shown in the entity picker.

| Domain | `accepted_domains` value |
|---|---|
| Motivation | `motivation` |
| Strategy | `strategy` |
| Business | `business` |
| Application | `application` |
| Technology | `technology` |
| Implementation | `implementation` |
| Common (cross-domain) | `common` |

The `archimate-layered` kind accepts all domains and therefore lists the full vocabulary.

## When a custom `renderer.py` is needed

The `GenericPumlRenderer` (in `src/infrastructure/rendering/generic_puml_renderer.py`) handles all standard ArchiMate-style views using only `config.yaml`. You do **not** need a custom renderer for:
- Any domain view (motivation, strategy, business, application, technology, implementation, layered)
- Views that add or remove `accepted_domains` entries
- Views with different `includes`, `grouping`, or `layout` settings

You **do** need a custom renderer (implementing the `DiagramRenderer` protocol) when:
- The diagram format is not PlantUML ArchiMate (e.g. ER diagrams, sequence diagrams, matrix tables)
- The rendering logic requires entity-specific logic that cannot be expressed via config
- You are building a diagram kind for a non-ArchiMate ontology with its own notation

The `matrix` diagram kind is an example: it uses `_MatrixRenderer` that raises `ValueError` on `render_body` because matrix diagrams use a separate Markdown rendering path, not PlantUML. See `src/diagram_kinds/matrix/__init__.py`.

## Adding a new diagram kind

### Step 1 — Create the package directory

```
src/diagram_kinds/my_view/
  __init__.py
  config.yaml
```

### Step 2 — Write `config.yaml`

```yaml
name: my-view
accepted_domains: [application, technology]
includes:
  - _archimate-stereotypes.puml
  - _archimate-glyphs.puml
grouping:
  by_field: domain_dir
  stereotype_pattern: "{domain_dir|capitalize}Grouping"
layout:
  nesting_connection_classes: [nesting]
  flow_connection_classes: [flow]
```

### Step 3 — Implement `__init__.py`

For standard ArchiMate-style views, re-use the built-in loader:

```python
# src/diagram_kinds/my_view/__init__.py
from __future__ import annotations

from pathlib import Path
from src.diagram_kinds._archimate_kind import load_archimate_diagram_kind
from src.domain.ontology_protocol import DiagramKindModule

module: DiagramKindModule = load_archimate_diagram_kind(Path(__file__).parent)
```

For a free-ontology view (accepts all entity types, like the matrix), use `FreeOntology` as the primary ontology and override `accepts_entity_type` / `accepts_connection_type` to return `True`:

```python
# src/diagram_kinds/my_free_view/__init__.py
from __future__ import annotations

from pathlib import Path
from src.domain.module_types import ConnectionTypeName, DiagramKindName, EntityTypeName, FreeOntology
from src.domain.ontology_protocol import DiagramKindBase, DiagramKindModule
from src.domain.ontology_types import ConnectionTypeInfo, EntityTypeInfo
from src.domain.permitted_relationships import PermittedRelationshipSet

class _MyFreeViewKind(DiagramKindBase):
    def __init__(self, name: str) -> None:
        self._config: dict = {"name": name, "includes": [], "grouping": {}, "layout": {}}

    @property
    def name(self) -> DiagramKindName:
        return DiagramKindName(self._config["name"])

    @property
    def primary_ontology(self):
        return FreeOntology

    def accepts_entity_type(self, t: EntityTypeName) -> bool:
        return True

    def accepts_connection_type(self, t: ConnectionTypeName) -> bool:
        return True

    @property
    def own_entity_types(self) -> dict:
        return {}

    @property
    def own_connection_types(self) -> dict:
        return {}

    @property
    def own_permitted_relationships(self) -> PermittedRelationshipSet:
        return PermittedRelationshipSet.empty()

module: DiagramKindModule = _MyFreeViewKind("my-free-view")
```

### Step 4 — Register the module

In `src/diagram_kinds/__init__.py`, add the import and register call:

```python
from src.diagram_kinds.my_view import module as my_view

def register_default_diagram_kinds(registry: ModuleRegistry) -> None:
    for module in [..., my_view]:
        registry.register_diagram_kind(module)
```

### Step 5 — Verify

The protocol compliance test in `tests/domain/test_protocol_compliance.py` automatically checks every registered diagram kind. Run `uv run pytest tests/` — the new kind must pass all checks without modification.

## Protocol contract

Every diagram kind must satisfy the `DiagramKindModule` protocol (`src/domain/ontology_protocol.py`). Compliance is verified automatically on every test run:

- `isinstance(module, DiagramKindModule)` must return `True`
- `module.name` must equal the key under which the module is registered
- `effective_entity_types()` must only return types present in the global registry
- `effective_connection_types()` must only return types present in the global registry
- `accepts_entity_type(t)` must return `True` for every `t` in `effective_entity_types()`
- `accepts_connection_type(t)` must return `True` for every `t` in `effective_connection_types()`
