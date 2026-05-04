# Ontology Module System — Architecture & Implementation Plan

## Context

The system manages architectural content across a two-tier repository (engagement /
enterprise). Its entity and connection ontology is declared in two YAML files
(`config/entity_ontology.yaml`, `config/connection_ontology.yaml`) and loaded once
at import time by `src/domain/ontology_loader.py`. The result is a set of module-level
dicts and frozensets consumed by application, domain, and infrastructure layers alike.

This works well for a single fixed ontology, but has two compounding problems:

1. **Leakage.** Type names, classifications, and groupings that belong to the ontology
   are hardcoded in ~40 places across the infrastructure layer — frozensets of junction
   types, hierarchy connection types, domain name sets, and the `global-artifact-reference`
   literal. The YAML is the nominal source of truth but in practice is mirrored ad hoc.

2. **No extension mechanism.** Adding a second ontology (e.g. ArchiMate 3.2, SysML v2)
   or a new diagram kind (e.g. activity diagrams rendered with smetana) requires changes
   across multiple layers because there is no registry or contract for what a
   well-formed ontology or diagram kind looks like.

This plan introduces a module system that resolves both problems while keeping changes
incremental and backward-compatible during the migration.

---

## Design Principles

- **The ontology is the domain.** All entity types, connection types, and permitted
  relationships live inside module packages. Nothing outside a module declares type names.
- **YAML carries data; code carries behaviour.** Type names, prefixes, and permitted
  relationship rules live in YAML within the module. Filter predicates, rendering logic,
  and validation hooks live in Python within the same module.
- **Entity-ontology and connection-ontology are inseparable.** A single `OntologyModule`
  owns both. Permitted relationships reference entity types from the same module.
- **Diagram kinds bind to exactly one ontology.** A diagram kind may filter and extend
  its primary ontology, but it does not mix entity types from two different ontologies.
  The only exception is `FreeOntology` — a typed sentinel for ontology-agnostic diagram
  kinds (e.g. matrices) that carry no structural connection rules of their own.
- **All derived constants come from registry queries.** No consumer outside a module
  package may hardcode an ontology type name. Queries go through the `ModuleRegistry`.
- **The registry is the sole authority for all type enumerations.** Validation, listing,
  guidance, and rendering all route through the registry and its modules. No generic
  tool — MCP, GUI API, or CLI — maintains its own closed list of types. Registering a
  new ontology or diagram kind automatically makes all its types valid, creatable,
  queryable, and renderable without touching any tool code.
- **Rendering is generic by default; code is the escape hatch.** A single generic PUML
  renderer handles all diagram kinds through YAML-declared config (includes, grouping,
  layout hints, element-class rendering patterns). A diagram kind module needs no
  `renderer.py` unless it genuinely requires non-generic behaviour (a different engine,
  a non-PUML output format, or a novel layout algorithm). Most modules contain only YAML
  and `__init__.py`.
- **Incremental migration.** The existing `ontology_loader` interface is preserved as a
  shim throughout the migration and deleted only at the end.

---

## Core Abstractions

### 1. Type Identity

Strong `NewType` wrappers prevent silent string confusion at type-check time:

```python
# src/domain/module_types.py
from typing import NewType

EntityTypeName     = NewType("EntityTypeName",     str)
ConnectionTypeName = NewType("ConnectionTypeName", str)
DiagramKindName    = NewType("DiagramKindName",    str)
ElementClassName   = NewType("ElementClassName",   str)
```

### 2. FreeOntology Sentinel

`FreeOntology` is the only value of `_FreeOntologyType`. Diagram kinds that genuinely
have no structural ontology bind to it. It is never `None`; callers pattern-match on
the union type.

```python
# src/domain/module_types.py
from typing import Final, final

@final
class _FreeOntologyType:
    """Singleton. Diagram kinds bound here accept entities from any registered ontology."""
    _instance: ClassVar[_FreeOntologyType | None] = None
    def __new__(cls) -> _FreeOntologyType:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    def __repr__(self) -> str:
        return "FreeOntology"

FreeOntology: Final[_FreeOntologyType] = _FreeOntologyType()
PrimaryOntology: TypeAlias = "OntologyModule | _FreeOntologyType"
```

### 3. PermittedRelationshipSet

A value type that carries connection rules and knows how to compose:

```python
# src/domain/permitted_relationships.py
from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from src.domain.module_types import EntityTypeName, ConnectionTypeName

@dataclass(frozen=True)
class PermittedRelationship:
    source_type: EntityTypeName
    target_type: EntityTypeName
    connection_type: ConnectionTypeName

@dataclass(frozen=True)
class PermittedRelationshipSet:
    _rules: frozenset[PermittedRelationship]

    def permits(
        self,
        src: EntityTypeName,
        tgt: EntityTypeName,
        conn: ConnectionTypeName,
    ) -> bool:
        return PermittedRelationship(src, tgt, conn) in self._rules

    def permitted_connection_types(
        self,
        src: EntityTypeName,
        tgt: EntityTypeName,
    ) -> frozenset[ConnectionTypeName]:
        return frozenset(
            r.connection_type
            for r in self._rules
            if r.source_type == src and r.target_type == tgt
        )

    def by_source(self) -> dict[EntityTypeName, list[tuple[EntityTypeName, ConnectionTypeName]]]:
        out: dict[EntityTypeName, list[tuple[EntityTypeName, ConnectionTypeName]]] = {}
        for r in self._rules:
            out.setdefault(r.source_type, []).append((r.target_type, r.connection_type))
        return out

    def filter_to(
        self,
        entity_types: frozenset[EntityTypeName],
        connection_types: frozenset[ConnectionTypeName],
    ) -> PermittedRelationshipSet:
        return PermittedRelationshipSet(frozenset(
            r for r in self._rules
            if r.source_type in entity_types
            and r.target_type in entity_types
            and r.connection_type in connection_types
        ))

    def __or__(self, other: PermittedRelationshipSet) -> PermittedRelationshipSet:
        return PermittedRelationshipSet(self._rules | other._rules)

    @staticmethod
    def empty() -> PermittedRelationshipSet:
        return PermittedRelationshipSet(frozenset())
```

### 4. Updated Domain Types

`EntityTypeInfo` gains no new fields beyond what the YAML already carries — `element_classes`
is the existing classifier mechanism and is the correct way to group types behaviourally.
`ConnectionTypeInfo` gains a `classifications` field, replacing all hardcoded frozensets
like `_STRUCTURAL_CONNECTION_TYPES` and `_HIERARCHY_TYPES`:

```python
# src/domain/ontology_types.py  (updated)
@dataclass(frozen=True)
class EntityTypeInfo:
    artifact_type: str
    prefix: str
    domain_dir: str
    subdir: str
    archimate_element_type: str | None   # nullable: non-ArchiMate types omit this
    element_classes: tuple[str, ...]
    create_when: str
    never_create_when: str
    has_sprite: bool = False
    internal: bool = False

@dataclass(frozen=True)
class ConnectionTypeInfo:
    artifact_type: str
    conn_lang: str
    archimate_relationship_type: str | None = None
    symmetric: bool = False
    puml_arrow: str = "-->"
    classifications: tuple[str, ...] = ()   # e.g. ("structural", "hierarchy")
```

The `classifications` field on `ConnectionTypeInfo` is populated from updated connection
YAML entries:

```yaml
# connections.yaml (inside the archimate-next module)
connection_types:
  archimate:
    archimate-composition:
      archimate_relationship_type: Composition
      puml_arrow: "--*"
      classifications: [structural, hierarchy]
    archimate-triggering:
      archimate_relationship_type: Triggering
      puml_arrow: "-[#green]->"
      classifications: [flow]
```

Consumers that currently write `conn_type in _STRUCTURAL_CONNECTION_TYPES` will instead
call `registry.connection_types_with_classification("structural")`.

### 5. OntologyModule Protocol

```python
# src/domain/ontology_protocol.py
from typing import Protocol, Mapping, runtime_checkable
from src.domain.module_types import EntityTypeName, ConnectionTypeName, ElementClassName
from src.domain.ontology_types import EntityTypeInfo, ConnectionTypeInfo
from src.domain.permitted_relationships import PermittedRelationshipSet

@runtime_checkable
class OntologyModule(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def entity_types(self) -> Mapping[EntityTypeName, EntityTypeInfo]: ...

    @property
    def connection_types(self) -> Mapping[ConnectionTypeName, ConnectionTypeInfo]: ...

    @property
    def permitted_relationships(self) -> PermittedRelationshipSet: ...

    def entity_types_with_class(self, cls: ElementClassName) -> frozenset[EntityTypeName]: ...

    def connection_types_with_classification(
        self, classification: str
    ) -> frozenset[ConnectionTypeName]: ...

    def permits_connection(
        self,
        src: EntityTypeName,
        tgt: EntityTypeName,
        conn: ConnectionTypeName,
    ) -> bool: ...
```

### 6. DiagramRenderer Protocol

```python
# src/domain/ontology_protocol.py (continued)
from src.domain.artifact_types import EntityRecord, ConnectionRecord
from pathlib import Path

@runtime_checkable
class DiagramRenderer(Protocol):
    def render_body(
        self,
        entities: Sequence[EntityRecord],
        connections: Sequence[ConnectionRecord],
        diagram_type: str,
        repo_root: Path,
    ) -> str: ...

    def inject_includes(self, body: str, repo_root: Path) -> str:
        """Inject diagram-type-specific preamble (e.g. ArchiMate stereotype includes)."""
        ...
```

The concrete default implementation is `GenericPumlRenderer` in
`src/infrastructure/rendering/generic_puml_renderer.py`. It reads all rendering
decisions — grouping strategy, layout hints, includes, element-class declaration
templates — from the diagram kind's YAML config. Diagram kind modules do not provide
a renderer unless they need to override this default.

### 7. DiagramKindModule Protocol and Base

The protocol is the public contract. `DiagramKindBase` provides default implementations
for `effective_permitted_relationships`, the two enumeration methods, and `renderer`
(wired to `GenericPumlRenderer` from the module's YAML config). Subclasses override
only when they need non-generic behaviour.

```python
# src/domain/ontology_protocol.py (continued)
from src.domain.module_types import DiagramKindName, PrimaryOntology, _FreeOntologyType

@runtime_checkable
class DiagramKindModule(Protocol):
    @property
    def name(self) -> DiagramKindName: ...

    @property
    def primary_ontology(self) -> PrimaryOntology: ...

    # Validation predicates (used by write operations and connection checks)
    def accepts_entity_type(self, t: EntityTypeName) -> bool: ...
    def accepts_connection_type(self, t: ConnectionTypeName) -> bool: ...

    # Enumeration (used by tool metadata, GUI selection lists, scaffold tool)
    def effective_entity_types(self) -> Mapping[EntityTypeName, EntityTypeInfo]: ...
    def effective_connection_types(self) -> Mapping[ConnectionTypeName, ConnectionTypeInfo]: ...

    @property
    def own_entity_types(self) -> Mapping[EntityTypeName, EntityTypeInfo]: ...

    @property
    def own_connection_types(self) -> Mapping[ConnectionTypeName, ConnectionTypeInfo]: ...

    @property
    def own_permitted_relationships(self) -> PermittedRelationshipSet: ...

    @property
    def effective_permitted_relationships(self) -> PermittedRelationshipSet: ...

    @property
    def renderer(self) -> DiagramRenderer: ...


class DiagramKindBase:
    """Mixin providing default implementations for DiagramKindModule.

    Subclasses must declare: name, primary_ontology, accepts_entity_type,
    accepts_connection_type, own_entity_types, own_connection_types,
    own_permitted_relationships, and _config (the loaded config.yaml dict).

    renderer defaults to GenericPumlRenderer(_config) and should only be
    overridden when non-generic rendering is genuinely required.
    """

    @property
    def effective_permitted_relationships(self) -> PermittedRelationshipSet:
        if isinstance(self.primary_ontology, _FreeOntologyType):  # type: ignore[attr-defined]
            return PermittedRelationshipSet.empty()

        ontology: OntologyModule = self.primary_ontology  # type: ignore[assignment]

        accepted_base_entities = frozenset(
            t for t in ontology.entity_types
            if self.accepts_entity_type(t)  # type: ignore[attr-defined]
        )
        accepted_base_conns = frozenset(
            t for t in ontology.connection_types
            if self.accepts_connection_type(t)  # type: ignore[attr-defined]
        )

        # Inherited rules: ontology rules filtered to accepted base types only.
        # Own entity/connection type names are not in the ontology's permitted set,
        # so the filter here operates exclusively on base vocab.
        inherited = ontology.permitted_relationships.filter_to(
            accepted_base_entities,
            accepted_base_conns,
        )

        return inherited | self.own_permitted_relationships  # type: ignore[attr-defined]

    def effective_entity_types(self) -> Mapping[EntityTypeName, EntityTypeInfo]:
        """Merged entity type vocabulary available in this diagram kind.

        Combines filtered base ontology types with own extensions. Used by tool
        metadata, GUI selection lists, and the scaffold tool.
        """
        if isinstance(self.primary_ontology, _FreeOntologyType):  # type: ignore[attr-defined]
            # FreeOntology: defer to the registry at call time (caller must supply context)
            return dict(self.own_entity_types)  # type: ignore[attr-defined]

        ontology: OntologyModule = self.primary_ontology  # type: ignore[assignment]
        out = {
            t: info for t, info in ontology.entity_types.items()
            if self.accepts_entity_type(t)  # type: ignore[attr-defined]
        }
        out.update(self.own_entity_types)  # type: ignore[attr-defined]
        return out

    def effective_connection_types(self) -> Mapping[ConnectionTypeName, ConnectionTypeInfo]:
        """Merged connection type vocabulary available in this diagram kind."""
        if isinstance(self.primary_ontology, _FreeOntologyType):  # type: ignore[attr-defined]
            return dict(self.own_connection_types)  # type: ignore[attr-defined]

        ontology: OntologyModule = self.primary_ontology  # type: ignore[assignment]
        out = {
            t: info for t, info in ontology.connection_types.items()
            if self.accepts_connection_type(t)  # type: ignore[attr-defined]
        }
        out.update(self.own_connection_types)  # type: ignore[attr-defined]
        return out

    @property
    def renderer(self) -> DiagramRenderer:
        from src.infrastructure.rendering.generic_puml_renderer import GenericPumlRenderer
        return GenericPumlRenderer(self._config)  # type: ignore[attr-defined]
```

### 8. ModuleRegistry

The registry is instantiated once at application startup and injected wherever needed.
It is not a module-level singleton; it is a dependency.

```python
# src/domain/module_registry.py
from typing import Mapping
from src.domain.module_types import EntityTypeName, ConnectionTypeName, ElementClassName
from src.domain.ontology_types import EntityTypeInfo, ConnectionTypeInfo
from src.domain.ontology_protocol import OntologyModule, DiagramKindModule

class ModuleRegistry:
    def __init__(self) -> None:
        self._ontologies: dict[str, OntologyModule] = {}
        self._diagram_kinds: dict[str, DiagramKindModule] = {}

    # ── Registration ────────────────────────────────────────────────────────

    def register_ontology(self, module: OntologyModule) -> None:
        if module.name in self._ontologies:
            raise ValueError(f"Ontology '{module.name}' already registered; use replace_ontology")
        self._ontologies[module.name] = module

    def unregister_ontology(self, name: str) -> None:
        if name not in self._ontologies:
            raise KeyError(name)
        del self._ontologies[name]

    def replace_ontology(self, module: OntologyModule) -> None:
        self._ontologies[module.name] = module

    def register_diagram_kind(self, module: DiagramKindModule) -> None:
        if module.name in self._diagram_kinds:
            raise ValueError(f"DiagramKind '{module.name}' already registered; use replace_diagram_kind")
        self._diagram_kinds[module.name] = module

    def unregister_diagram_kind(self, name: str) -> None:
        if name not in self._diagram_kinds:
            raise KeyError(name)
        del self._diagram_kinds[name]

    def replace_diagram_kind(self, module: DiagramKindModule) -> None:
        self._diagram_kinds[module.name] = module

    # ── Ontology queries ────────────────────────────────────────────────────

    def get_ontology(self, name: str) -> OntologyModule:
        try:
            return self._ontologies[name]
        except KeyError:
            raise KeyError(f"No ontology registered with name '{name}'")

    def find_ontology(self, name: str) -> OntologyModule | None:
        return self._ontologies.get(name)

    def all_ontologies(self) -> Mapping[str, OntologyModule]:
        return dict(self._ontologies)

    # ── Diagram kind queries ─────────────────────────────────────────────────

    def get_diagram_kind(self, name: str) -> DiagramKindModule:
        try:
            return self._diagram_kinds[name]
        except KeyError:
            raise KeyError(f"No diagram kind registered with name '{name}'")

    def find_diagram_kind(self, name: str) -> DiagramKindModule | None:
        return self._diagram_kinds.get(name)

    def all_diagram_kinds(self) -> Mapping[str, DiagramKindModule]:
        return dict(self._diagram_kinds)

    # ── Aggregated entity/connection type queries ────────────────────────────
    # These merge across all registered ontologies; for entity-type-specific
    # queries where the owning ontology matters, use ontology_for_entity_type().

    def all_entity_types(self) -> Mapping[EntityTypeName, EntityTypeInfo]:
        out: dict[EntityTypeName, EntityTypeInfo] = {}
        for om in self._ontologies.values():
            out.update(om.entity_types)
        return out

    def all_connection_types(self) -> Mapping[ConnectionTypeName, ConnectionTypeInfo]:
        out: dict[ConnectionTypeName, ConnectionTypeInfo] = {}
        for om in self._ontologies.values():
            out.update(om.connection_types)
        return out

    def get_entity_type(self, name: EntityTypeName) -> EntityTypeInfo:
        for om in self._ontologies.values():
            if name in om.entity_types:
                return om.entity_types[name]
        raise KeyError(f"Entity type '{name}' not found in any registered ontology")

    def find_entity_type(self, name: EntityTypeName) -> EntityTypeInfo | None:
        for om in self._ontologies.values():
            if name in om.entity_types:
                return om.entity_types[name]
        return None

    def entity_types_with_class(self, cls: ElementClassName) -> frozenset[EntityTypeName]:
        result: set[EntityTypeName] = set()
        for om in self._ontologies.values():
            result.update(om.entity_types_with_class(cls))
        return frozenset(result)

    def connection_types_with_classification(
        self, classification: str
    ) -> frozenset[ConnectionTypeName]:
        result: set[ConnectionTypeName] = set()
        for om in self._ontologies.values():
            result.update(om.connection_types_with_classification(classification))
        return frozenset(result)

    def ontology_for_entity_type(
        self, name: EntityTypeName
    ) -> OntologyModule | None:
        for om in self._ontologies.values():
            if name in om.entity_types:
                return om
        return None

    # ── Domain ordering ──────────────────────────────────────────────────────
    # Preserves the insertion order from each ontology module.

    def domain_order(self) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for om in self._ontologies.values():
            for et in om.entity_types.values():
                if not et.internal and et.domain_dir not in seen:
                    seen.add(et.domain_dir)
                    result.append(et.domain_dir)
        return result
```

---

## Module Package Structure

Each module is a Python package directory containing YAML data files and Python
implementation code. The module is self-contained: it loads its own YAML and exposes
an instantiated module object.

Ontology modules require a `_loader.py` because loading YAML into the protocol types
is non-trivial. Diagram kind modules typically contain only YAML and `__init__.py`;
`renderer.py` is present only when the generic renderer is insufficient.

```
src/
  domain/
    module_types.py              # EntityTypeName, ConnectionTypeName, FreeOntology, etc.
    permitted_relationships.py   # PermittedRelationship, PermittedRelationshipSet
    ontology_protocol.py         # OntologyModule, DiagramKindModule, DiagramRenderer, DiagramKindBase
    module_registry.py           # ModuleRegistry
    ontology_types.py            # EntityTypeInfo, ConnectionTypeInfo (updated)
    artifact_types.py            # EntityRecord etc. (Domain literal derived from registry)
    connection_ontology.py       # delegates to registry (updated)
    archimate_relation_rendering.py  # delegates to registry (updated)
    ontology_loader.py           # shim during migration → deleted at end
    archimate_types.py           # shim during migration → deleted at end

  infrastructure/
    rendering/
      generic_puml_renderer.py   # GenericPumlRenderer: reads diagram kind config.yaml;
                                 # handles all known element-class rendering patterns,
                                 # grouping, layout nesting, and include injection
      diagram_builder.py         # retained during migration; gutted in Phase 3
      ...

  ontologies/                    # concrete OntologyModule implementations
    __init__.py
    archimate_next/
      __init__.py                # exports: module: OntologyModule
      entities.yaml              # migrated from config/entity_ontology.yaml
      connections.yaml           # migrated from config/connection_ontology.yaml
      _loader.py                 # private: YAML → EntityTypeInfo/ConnectionTypeInfo/PermittedRelationshipSet

  diagram_kinds/                 # concrete DiagramKindModule implementations
    __init__.py
    archimate_motivation/
      __init__.py                # exports: module: DiagramKindModule
      config.yaml                # rendering config + filter (see schema below)
                                 # no renderer.py needed — GenericPumlRenderer handles this
    archimate_strategy/
      __init__.py
      config.yaml
    archimate_business/
      __init__.py
      config.yaml
    archimate_application/
      __init__.py
      config.yaml
    archimate_technology/
      __init__.py
      config.yaml
    archimate_implementation/
      __init__.py
      config.yaml
    archimate_full/
      __init__.py
      config.yaml
    matrix/
      __init__.py                # primary_ontology = FreeOntology; no connection rules
      config.yaml                # no includes, no grouping, no layout hints
      # no renderer.py — GenericPumlRenderer with minimal config handles matrix layout
```

### Diagram kind config.yaml schema

All rendering decisions are declared in config.yaml. `GenericPumlRenderer` reads
this at construction time. A diagram kind module never needs to know which renderer
will execute it; `DiagramKindBase.renderer` constructs `GenericPumlRenderer(self._config)`
automatically.

```yaml
# src/diagram_kinds/archimate_business/config.yaml
primary_ontology: archimate-next-snapshot1   # validated against registry at startup
accepted_domains: [business, common]         # entity filter: domain_dir must be in this list

grouping:
  by_field: domain_dir                       # group entities by this EntityTypeInfo field
  stereotype_pattern: "{domain_dir|capitalize}Grouping"  # PUML grouping stereotype

includes:                                    # paths relative to repo_root/diagrams/
  - _archimate-stereotypes.puml
  - _archimate-glyphs.puml

layout:
  nesting_connection_classes: [structural]   # connections with this classification drive nesting
  flow_connection_classes: [flow]            # connections that imply left→right direction hints
```

`GenericPumlRenderer` resolves entity declaration format from `element_classes` using
a stable, finite pattern table (no config needed for this — the patterns are fixed):

| element_classes contains | PUML declaration |
|---|---|
| `junction` | `circle " " as {alias}` |
| `archimate-element` + `has_sprite=true` | `rectangle "<$archimate_{element_type}> {label}" <<{element_type}>> as {alias}` |
| `archimate-element` | `rectangle "{label}" <<{element_type}>> as {alias}` |
| _(default)_ | `rectangle "{label}" as {alias}` |

Future element classes (e.g. `sysml-block`) default to plain rectangle until a new
row is added to this table. Adding a row requires a one-line change to the generic
renderer, not a new renderer.py in the module.

### Example: ArchiMate NEXT module

```python
# src/ontologies/archimate_next/__init__.py
from pathlib import Path
from src.domain.ontology_protocol import OntologyModule
from src.ontologies.archimate_next._loader import load_archimate_next_module

module: OntologyModule = load_archimate_next_module(Path(__file__).parent)
```

```python
# src/ontologies/archimate_next/_loader.py
from pathlib import Path
import yaml
from src.domain.ontology_types import EntityTypeInfo, ConnectionTypeInfo
from src.domain.permitted_relationships import PermittedRelationship, PermittedRelationshipSet
from src.domain.module_types import EntityTypeName, ConnectionTypeName, ElementClassName

class _ArchiMateNextModule:
    name = "archimate-next-snapshot1"

    def __init__(
        self,
        entity_types: dict[EntityTypeName, EntityTypeInfo],
        connection_types: dict[ConnectionTypeName, ConnectionTypeInfo],
        permitted_relationships: PermittedRelationshipSet,
    ) -> None:
        self._entity_types = entity_types
        self._connection_types = connection_types
        self._permitted_relationships = permitted_relationships
        self._class_index: dict[ElementClassName, frozenset[EntityTypeName]] = {}
        for name, info in entity_types.items():
            for cls in info.element_classes:
                self._class_index.setdefault(
                    ElementClassName(cls), set()
                ).add(name)
        self._class_index = {k: frozenset(v) for k, v in self._class_index.items()}
        self._classification_index: dict[str, frozenset[ConnectionTypeName]] = {}
        for name, info in connection_types.items():
            for clf in info.classifications:
                self._classification_index.setdefault(clf, set()).add(name)
        self._classification_index = {k: frozenset(v) for k, v in self._classification_index.items()}

    @property
    def entity_types(self):
        return self._entity_types

    @property
    def connection_types(self):
        return self._connection_types

    @property
    def permitted_relationships(self):
        return self._permitted_relationships

    def entity_types_with_class(self, cls):
        return self._class_index.get(ElementClassName(cls), frozenset())

    def connection_types_with_classification(self, classification):
        return self._classification_index.get(classification, frozenset())

    def permits_connection(self, src, tgt, conn):
        return self._permitted_relationships.permits(src, tgt, conn)


def load_archimate_next_module(package_dir: Path) -> _ArchiMateNextModule:
    # ... load entities.yaml, connections.yaml, build types and rules ...
```

### Example: archimate_business diagram kind

No `renderer.py` — `DiagramKindBase.renderer` constructs `GenericPumlRenderer(_config)`
automatically. The `__init__.py` is minimal: load config, declare accepted domains,
expose the module instance.

```python
# src/diagram_kinds/archimate_business/__init__.py
from pathlib import Path
import yaml
from src.domain.ontology_protocol import DiagramKindBase, DiagramKindModule
from src.domain.module_types import DiagramKindName
from src.domain.permitted_relationships import PermittedRelationshipSet
from src.ontologies.archimate_next import module as archimate_next

_config = yaml.safe_load((Path(__file__).parent / "config.yaml").read_text())
_accepted_domains = frozenset(_config["accepted_domains"])

class _ArchiMateBusinessDiagramKind(DiagramKindBase):
    name = DiagramKindName("archimate-business")
    primary_ontology = archimate_next
    own_entity_types = {}
    own_connection_types = {}
    own_permitted_relationships = PermittedRelationshipSet.empty()
    _config = _config  # DiagramKindBase.renderer reads this

    def accepts_entity_type(self, t):
        info = archimate_next.entity_types.get(t)
        return info is not None and info.domain_dir in _accepted_domains

    def accepts_connection_type(self, t):
        return t in archimate_next.connection_types

module: DiagramKindModule = _ArchiMateBusinessDiagramKind()
```

The full config.yaml is shown in the schema section above. A diagram kind that needs
a custom renderer — say, one targeting smetana or SVG output — overrides the `renderer`
property and provides a `renderer.py`:

```python
# src/diagram_kinds/some_custom_kind/renderer.py
from src.domain.ontology_protocol import DiagramRenderer
class CustomRenderer:
    def render_body(self, entities, connections, diagram_type, repo_root): ...
    def inject_includes(self, body, repo_root): ...

# src/diagram_kinds/some_custom_kind/__init__.py  (excerpt)
class _CustomDiagramKind(DiagramKindBase):
    ...
    @property
    def renderer(self) -> DiagramRenderer:
        return CustomRenderer()
```

---

## Application Startup Wiring

The registry is built once and injected as a FastAPI dependency (or equivalent):

```python
# src/infrastructure/app_bootstrap.py
from src.domain.module_registry import ModuleRegistry
from src.ontologies.archimate_next import module as archimate_next_module
from src.diagram_kinds.archimate_business import module as archimate_business_kind
# ... other diagram kind imports ...
from src.diagram_kinds.matrix import module as matrix_kind

def build_module_registry() -> ModuleRegistry:
    registry = ModuleRegistry()
    registry.register_ontology(archimate_next_module)
    registry.register_diagram_kind(archimate_business_kind)
    # ... register all diagram kinds ...
    registry.register_diagram_kind(matrix_kind)
    return registry

# FastAPI dependency
from functools import lru_cache

@lru_cache(maxsize=1)
def get_module_registry() -> ModuleRegistry:
    return build_module_registry()
```

Infrastructure adapters (MCP tools, CLI) that currently import directly from
`ontology_loader` are migrated to accept the registry as a parameter, obtained from
the same bootstrapped instance.

---

## Migration Strategy

Migration is strictly incremental. The existing `ontology_loader` API is preserved as
a shim at each phase. Consumers are migrated file-by-file; the shim is only deleted
after all consumers are migrated.

### Shim contract during migration

```python
# src/domain/ontology_loader.py  (shim — exists only during migration)
from src.ontologies.archimate_next import module as _m

ENTITY_TYPES = dict(_m.entity_types)
CONNECTION_TYPES = dict(_m.connection_types)
PERMITTED_RELATIONSHIPS = {
    (r.source_type, r.target_type): frozenset(
        rr.connection_type for rr in _m.permitted_relationships._rules
        if rr.source_type == r.source_type and rr.target_type == r.target_type
    )
    for r in _m.permitted_relationships._rules
}
# ... reconstruct remaining derived constants from module data ...
```

This means the data moves to the module in Phase 1 without breaking any of the ~15
existing import sites.

---

## Phased Implementation Checklist

### Phase 0 — Contracts (no behaviour change)

- [x] Add `src/domain/module_types.py`: `EntityTypeName`, `ConnectionTypeName`,
      `DiagramKindName`, `ElementClassName`, `FreeOntology`, `_FreeOntologyType`,
      `PrimaryOntology`
- [x] Add `src/domain/permitted_relationships.py`: `PermittedRelationship`,
      `PermittedRelationshipSet` with `filter_to`, `__or__`, `empty`
- [x] Update `src/domain/ontology_types.py`: make `archimate_element_type` nullable
      (`str | None`); add `classifications: tuple[str, ...]` to `ConnectionTypeInfo`
- [x] Add `src/domain/ontology_protocol.py`: `OntologyModule`, `DiagramKindModule`,
      `DiagramRenderer` protocols; `DiagramKindBase` mixin
- [x] Add `src/domain/module_registry.py`: `ModuleRegistry` class (all methods)
- [x] Write unit tests for `PermittedRelationshipSet` (filter_to, union, permits)
- [x] Write unit tests for `ModuleRegistry` (register/unregister/replace, aggregated
      queries, error cases)

### Phase 1 — ArchiMate NEXT module + shim wiring

- [x] Create `src/ontologies/__init__.py`, `src/ontologies/archimate_next/__init__.py`
- [x] Write `src/ontologies/archimate_next/_loader.py`:
      - Move YAML loading logic from `ontology_loader.py`
      - Build `_ArchiMateNextModule` with class index and classification index
      - Expand `@class` / `@all` / `@same` refs in permitted_relationships during load
      - Generalise `archimate-` prefix injection so it's part of the module config
        (YAML entry key is the bare name; loader adds the `conn_lang` prefix)
- [x] Migrate `config/entity_ontology.yaml` → `src/ontologies/archimate_next/entities.yaml`
- [x] Migrate `config/connection_ontology.yaml` → `src/ontologies/archimate_next/connections.yaml`
      and add `classifications` entries to each connection type
- [x] Verify that `element_classes` in entities.yaml correctly classifies all types that
      are currently hardcoded as special cases:
      - `and-junction`, `or-junction` → `element_classes: [junction]`
      - `global-artifact-reference` → `element_classes: [internal]` (already `internal: true`)
- [x] Replace `src/domain/ontology_loader.py` with the shim described above
- [x] Add `src/infrastructure/app_bootstrap.py` with `build_module_registry()`
- [x] Wire registry into FastAPI app factory; expose as dependency
- [x] All existing tests pass unchanged (shim ensures backward compat)

### Phase 2 — Derived constants and validation → registry queries

Goal: eliminate all hardcoded type name literals outside module packages; make all
create/edit validation and type enumeration flow through the registry.

**Hardcoded constants → registry queries**
- [x] Replace `frozenset({"and-junction", "or-junction"})` in all 4 sites with
      `registry.entity_types_with_class(ElementClassName("junction"))`
- [x] Replace `frozenset({"global-artifact-reference"})` and string comparisons
      with `registry.entity_types_with_class(ElementClassName("internal"))` where
      the `internal` flag is used as a membership check
      (note: only `_INTERNAL_TYPES` in `help.py` migrated; direct string comparisons in
      domain-specific business logic left as-is — they are not class membership checks)
- [x] Replace `_STRUCTURAL_CONNECTION_TYPES`, `_LAYOUT_FLOW_CONNECTION_TYPES`,
      `_HIERARCHY_TYPES` in `diagram_builder.py` and `entity_listing.py` with
      `registry.connection_types_with_classification(...)`:
      - Added `nesting` classification (composition + aggregation only) for visual nesting
      - Used `flow` classification for layout flow direction hints
      - `_HIERARCHY_TYPES` derived from `hierarchy_priority` field on `ConnectionTypeInfo`
- [x] Replace `_HIERARCHY_PRIORITY` dict in `entity_listing.py` — `hierarchy_priority`
      field added to `ConnectionTypeInfo` and set in connections.yaml; derived via registry
- [x] Remove `Domain = Literal[...]` hardcoded union from `artifact_types.py` and
      `DOMAIN_NAMES` frozenset; derived from `registry.all_entity_types()` (includes
      all domain_dirs + "unknown", preserving "common" for GAR parsing)
- [x] Remove `archimate_prefix_to_type()` from `domain_vocabulary.py`; derive from
      `{info.prefix: name for name, info in registry.all_entity_types().items()}`
- [x] Update `connection_ontology.py` to delegate through registry rather than
      `ontology_loader` constants directly
- [x] Update `archimate_relation_rendering.py` similarly
- [x] Fix `_sqlite_store.py:399`: replaced with `is_symmetric()` from
      `connection_ontology` (which calls `registry.find_connection_type().symmetric`)

**Write operation validation → registry**

These are the gatekeepers for create/edit; they must use the registry so that types
from any registered ontology are accepted without code changes.

- [x] `entity.py:58` — replaced with `registry.find_entity_type(EntityTypeName(...)) is None`
- [x] `connection.py:89` — replaced with `registry.find_connection_type(ConnectionTypeName(...)) is None`
- [x] `admin_ops.py:72` — same as entity.py above
- [x] `help.py:36,54,60,74` — replaced with `registry.all_entity_types()` /
      `registry.all_connection_types()`
- [x] `type_guidance.py:28` — replaced with `registry.all_entity_types()`

**Entity creation template enrichment** (deferred to Phase 2b)

Entity creation (`format_entity_markdown`) currently infers required fields from
`EntityTypeInfo.create_when` (free text). To support generic template generation for
any registered ontology's types, add structured fields to `entities.yaml`:

- [x] Add `required_fields: [field-name, ...]` and `optional_fields: [field-name, ...]`
      to each entity type entry in `archimate_next/entities.yaml`
- [x] Update `format_entity_markdown` to read these fields from `EntityTypeInfo`
      (add corresponding typed fields to `EntityTypeInfo` dataclass)
- [x] `global_artifact_reference.py:66` — replace direct `ENTITY_TYPES[_GAR_TYPE]`
      lookup with `registry.get_entity_type(EntityTypeName(_GAR_TYPE))`

- [x] All existing tests pass; add regression tests for each replaced lookup
      (446 tests passing, including regression coverage for app-state registry wiring
      and ontology-driven entity template scaffolding)

### Phase 3 — Diagram kind modules and generic renderer

Goal: eliminate all diagram-type string dispatch outside the registry; no new MCP
tools or API routes for new diagram kinds — the generic tooling routes through the
registry and each kind's `renderer`.

**Generic renderer**
- [x] Implement `src/infrastructure/rendering/generic_puml_renderer.py`:
      - Constructor accepts a diagram kind config dict (loaded from config.yaml)
      - `render_body`: groups entities by `grouping.by_field`, emits grouping
        stereotypes per `grouping.stereotype_pattern`, renders entity declarations
        from the element-class pattern table, renders connection lines from
        `ConnectionTypeInfo.puml_arrow`, applies nesting via `layout.nesting_connection_classes`
      - `inject_includes`: reads `includes` list from config, injects relative include
        paths using the same convention as the current `inject_archimate_includes`
      - Element-class pattern table is a module-level constant in this file; adding
        support for a new element class (e.g. `sysml-block`) is a one-line addition here
- [x] Write unit tests for `GenericPumlRenderer` covering: grouping, include injection,
      each element-class rendering pattern, nesting hints

**Diagram kind packages**
- [x] Create `src/diagram_kinds/__init__.py`
- [x] For each ArchiMate domain view, create a diagram kind package
      (`archimate_motivation`, `archimate_strategy`, `archimate_business`,
      `archimate_application`, `archimate_technology`, `archimate_implementation`,
      `archimate_full` / current compatibility kind `archimate_layered`) containing:
      - `config.yaml`: full rendering config (accepted_domains, grouping, includes, layout)
      - `__init__.py`: minimal — load config, declare accepted domains, expose module
      - No `renderer.py` — `DiagramKindBase.renderer` handles it
- [ ] Create `src/diagram_kinds/matrix/` with `FreeOntology` primary:
      - `config.yaml`: no grouping, no includes, no layout hints
      - `__init__.py`: accepts all entity types, no connection rules
      - Matrix layout logic (currently in `matrix_builder.py`) folds into
        `GenericPumlRenderer` as a layout mode, or matrix keeps its own renderer.py
        if the layout logic is sufficiently distinct — decide during implementation

**Registry wiring and dispatch migration**
- [ ] Register all diagram kinds in `app_bootstrap.py`
- [ ] Replace `if diagram_type == "matrix"` and `if "archimate" in diagram_type`
      dispatch in routers and `diagram_builder.py` with
      `registry.get_diagram_kind(name).renderer.render_body(...)`
- [ ] Replace `startswith("archimate-")` checks in `entities.py`, `diagrams.py`,
      `_diagram_context.py` with `registry.find_diagram_kind(name) is not None` or
      `isinstance(registry.get_diagram_kind(name).primary_ontology, _FreeOntologyType)`

**Scaffold tool and GUI selection**
- [ ] Migrate `query_scaffold_tools.py` to call
      `registry.get_diagram_kind(diagram_type).renderer.render_body(entities, connections, ...)`
      instead of building PUML declarations directly; remove hardcoded `_ARROW`, `_LABEL`,
      `_entity_decl` — these are now in `GenericPumlRenderer` driven by module config
- [ ] Migrate `_diagram_context.py` entity/connection selection lists to call
      `registry.get_diagram_kind(diagram_type).effective_entity_types()` and
      `effective_connection_types()` instead of hardcoded domain lists
- [ ] Expose a `/diagram-kinds/{name}/entity-types` and `/connection-types` read-only
      API endpoint (or extend the existing entities endpoint) that returns the effective
      vocabulary for a given diagram kind — this is the API surface the future GUI canvas
      will call; no new write tools needed

### Phase 4 — Remove legacy shims

Prerequisites: Phases 1–3 fully migrated and all tests green.

- [ ] Delete `src/domain/ontology_loader.py`
- [ ] Delete `src/domain/archimate_types.py` (all consumers now use registry)
- [ ] Delete `src/domain/domain_vocabulary.py` (prefix map derived from registry)
- [ ] Remove `DOMAIN_NAMES` constant from `artifact_types.py`
- [ ] Delete `config/entity_ontology.yaml` and `config/connection_ontology.yaml`
      (data now lives in the module package)
- [ ] Remove any remaining `from src.domain.ontology_loader import` statements

### Phase 5 — TypeScript type generation

- [ ] Write `tools/generate_types.py`: queries the registry, emits
      `tools/gui/src/domain/types.generated.ts` containing string literal unions
      for entity type names, connection type names, domain names, and diagram kind names
- [ ] Add generation step to the frontend build (`package.json` `prebuild` or similar)
- [ ] Replace hardcoded domain colour map and option lists in `tools/gui/src/ui/lib/domains.ts`
      with imports from `types.generated.ts` (domain names) plus a config file for
      UI-specific display properties (colours, icons) keyed on those generated names
- [ ] Remove `artifact_type: Schema.String` / `domain: Schema.String` in `schemas.ts`
      and replace with generated literal union schemas where appropriate

### Phase 6 — Cleanup and hardening

- [ ] Audit all `global-artifact-reference` special-case sites now gated behind
      `entity_types_with_class("internal")` — consolidate duplicated guard logic into
      shared predicate functions in the application layer
- [ ] Add protocol compliance tests: each registered `OntologyModule` and
      `DiagramKindModule` is checked with `isinstance(m, OntologyModule)` / `isinstance(m, DiagramKindModule)`
      (using `runtime_checkable`) and a suite of contract assertions (e.g. that
      `effective_permitted_relationships` only references type names present in the
      module's entity/connection vocabulary)
- [ ] Document the extension contract in `src/ontologies/README.md`: how to add a new
      ontology module (SysML v2 example skeleton), how to register it, what the YAML
      schema must contain
- [ ] Document the diagram kind extension contract in `src/diagram_kinds/README.md`:
      the full config.yaml schema, when `renderer.py` is and is not needed, the
      element-class pattern table and how to extend it for a new element class
- [ ] Update project README to reflect new structure

---

## Accepted Concessions

**ArchiMate NEXT as the current baseline.**
The YAML schemas and loader are designed around ArchiMate NEXT Snapshot 1. The
`archimate_element_type` field on `EntityTypeInfo` is the main ArchiMate-specific
coupling; making it nullable (Phase 0) is the concession that allows SysML and other
ontologies to define entity types without requiring an ArchiMate mapping.

**Connection YAML still uses `@class` expansion.**
The permitted relationship rules in `connections.yaml` use `@class` and `@all`
pseudo-references that the loader expands. This expansion logic lives inside the
ArchiMate NEXT module's loader and does not leak into the domain layer. Future
ontology modules may use different YAML schemas for their connection rules as long as
their loaders produce a valid `PermittedRelationshipSet`.

**No hot-reload.**
Modules are registered at startup. Changing an ontology or diagram kind requires a
server restart. This is acceptable for the current deployment model.

**Cross-ontology diagrams are not supported.**
A diagram with `primary_ontology = FreeOntology` can display entities from any
ontology, but has no structural connection rules. A diagram with a specific primary
ontology may only contain entities from that ontology. Mixing ArchiMate and SysML
entities in one constrained diagram is out of scope; it would require a third
"composed ontology" module with explicitly declared cross-module connection rules.

---

## Out of Scope

- SysML v2 ontology implementation (the architecture accommodates it; implementation is future work)
- Activity diagram renderer with smetana (the `DiagramRenderer` protocol accommodates it)
- Interactive GUI canvas diagram builder (the `accepts_entity_type` / `accepts_connection_type`
  contract on `DiagramKindModule` provides the API surface this feature needs; the GUI
  work itself is out of scope here)
- Hot-reload or runtime module replacement
