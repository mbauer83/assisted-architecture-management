# Phase 0 — Module Extension Mechanism: Companion Spec

> Companion to PLAN-assurance-stpa-grc.md §29 and §24 Phase 0 checklist.
> **Status:** Implemented (2026-06-04).

## 1. Decisions confirmed (§18)

All §18 decisions are [RESOLVED]. Specifically for Phase 0:

- `module_class` = declarative field on `OntologyModule` and `DiagramTypeModule` protocols;
  values: `"architecture" | "assurance"` (TypeAlias `ModuleClass`).
- `attribute_profiles` = optional `Mapping[str, dict[str, object]]` property on `OntologyModule`;
  entity-type → JSON Schema fragment; merges with per-repo `.arch-repo/schemata/` overrides (Phase 1b merging).
- Module `enabled`/`requires` = NOT protocol members (to avoid runtime_checkable breakage);
  declared as class attributes on concrete modules; read via `getattr(module, 'enabled', True)` in `module_filter`.
- UI boundary (§3.4) locked: bespoke assurance surfaces on shared engines.

## 2. `module_class` registry

### Protocol surface

```python
# src/domain/ontology_protocol.py
ModuleClass = Literal["architecture", "assurance"]

class OntologyModule(Protocol):
    @property
    def module_class(self) -> ModuleClass: ...

    @property
    def attribute_profiles(self) -> Mapping[str, dict[str, object]]: ...

class DiagramTypeModule(Protocol):
    @property
    def module_class(self) -> ModuleClass: ...

class DiagramTypeBase:
    module_class: ModuleClass = "architecture"  # mixin default
```

### Current registered modules and their `module_class`

| Module | `module_class` | `enabled` default | `requires` |
|---|---|---|---|
| `archimate-next-snapshot1` | `architecture` | `True` | `[]` |
| `sysml_v2_min` | `architecture` | `True` | `[]` |
| All built-in diagram types | `architecture` | `True` (via `DiagramTypeBase`) | `[]` |

The **assurance module** (Phase 1b) will add:

| Module | `module_class` | `enabled` default | `requires` |
|---|---|---|---|
| `assurance` | `assurance` | `True` | `["confidential_store"]` |

## 3. `attribute_profiles` convention

### Format

Each key is an entity-type name; the value is a JSON Schema `properties` fragment
(same format as per-repo `.arch-repo/schemata/attributes.<type>.schema.json`):

```python
attribute_profiles: Mapping[str, dict[str, object]] = {
    "loss": {
        "type": "object",
        "properties": {
            "concern_class": {
                "type": "string",
                "enum": ["safety", "security", "operational", "financial", "privacy"]
            }
        }
    }
}
```

### Merging precedence (Phase 1b merging point)

1. Module-contributed `attribute_profiles` (defaults).
2. Per-repo `.arch-repo/schemata/attributes.<type>.schema.json` (extends/overrides).

The merge point is `src/application/artifact_schema.py::load_attribute_schema()`.
In Phase 0 all modules return `attribute_profiles = {}` — no behavior change yet.

## 4. Module manifest + settings

### Module class-level attributes (concrete modules)

```python
class _SomeModule:
    name = "my-module"
    module_class: Literal["architecture", "assurance"] = "architecture"
    enabled: bool = True          # default enabled state
    requires: list[str] = []      # capability/module dependencies
    attribute_profiles: Mapping[str, dict[str, object]] = {}
```

### `config/settings.yaml` `modules:` block

```yaml
modules:
  sysml_v2_min:
    enabled: false   # override: disable this module
  assurance:
    enabled: true    # (future) override: enable assurance
```

Only `enabled` is a valid override key. `requires` is a module manifest declaration,
never a deployment override.

### `is_module_enabled()` logic (`src/domain/module_filter.py`)

```
effective_enabled = getattr(module, 'enabled', True)
if module.name in overrides and 'enabled' in overrides[module.name]:
    effective_enabled = overrides[module.name]['enabled']
if not effective_enabled: skip
for dep in getattr(module, 'requires', []):
    if dep not in registered_names: skip (fail-closed)
```

## 5. Conditional bootstrap

`build_module_registry()` in `src/infrastructure/app_bootstrap.py`:

1. Loads `module_overrides()` from settings.
2. Iterates `_ALL_ONTOLOGY_MODULES` in order; calls `is_module_enabled()`.
3. Registers only enabled+satisfied modules; logs skipped ones at INFO.
4. Passes `overrides` + `registered_names` to `register_default_diagram_types()`.
5. Runs `validate_registry_consistency()` on the filtered registry.

## 6. `/api/modules` endpoint

`GET /api/modules` — returns registered (enabled+satisfied) ontology modules:

```json
[
  {
    "name": "archimate-next-snapshot1",
    "module_class": "architecture",
    "enabled": true,
    "requires": [],
    "entity_type_count": 82,
    "connection_type_count": 25
  }
]
```

Frontend uses `module_class` to segregate "Assurance" nav from "Architecture" nav
(conditional rendering — Phase 1d).

## 7. New source files (Phase 0)

| File | Purpose |
|---|---|
| `src/domain/diagram_type_config.py` | Extracted dataclasses from `ontology_protocol.py` (LoC budget) |
| `src/domain/module_filter.py` | `is_module_enabled()` — pure domain function, no infrastructure imports |
| `src/infrastructure/gui/routers/modules.py` | `/api/modules` FastAPI router |
| `tests/domain/test_module_filter.py` | Unit tests for `is_module_enabled()` |
| `tests/common/test_module_settings.py` | Unit tests for `module_overrides()` |
| `tests/tools/test_modules_route.py` | Route tests for `/api/modules` |

## 8. Phase 0 DoD checklist (all ☑)

- [x] §18 decisions confirmed (all [RESOLVED] in plan)
- [x] UI boundary (§3.4) locked
- [x] `module_class` on `OntologyModule` + `DiagramTypeModule` protocols + `DiagramTypeBase` default
- [x] `attribute_profiles` on `OntologyModule` protocol + empty default on concrete modules
- [x] `enabled`/`requires` class attributes on concrete modules
- [x] `config/settings.yaml` `modules:` block + `module_overrides()` accessor
- [x] `is_module_enabled()` in `src/domain/module_filter.py`
- [x] Conditional bootstrap (fail-closed)
- [x] `/api/modules` endpoint registered
- [x] 21 new tests pass; full suite green (1 pre-existing failure unrelated)
- [x] `types.generated.ts` regenerated
