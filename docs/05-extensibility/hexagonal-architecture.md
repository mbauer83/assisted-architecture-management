# Hexagonal Architecture

The codebase is layered ports-and-adapters, so the plug-in points above (ontologies, diagram
types, schemata, storage backends) attach at stable boundaries rather than threading through
the core. The dependency direction is enforced, not just documented — see
[`docs/architecture/dependency-policy.md`](../architecture/dependency-policy.md) and the
[glossary](../architecture/glossary.md).

&nbsp;

## The layers

| Layer | Path | Holds | May depend on |
|---|---|---|---|
| **Domain** | `src/domain/` | Pure protocols, value types, the module registry and focused catalogs | nothing outside the domain |
| **Application** | `src/application/` | Use cases, runtime catalogs, the verification engine, derivation strategies, startup validation | domain |
| **Config** | `src/config/` | Workspace and settings readers | domain |
| **Infrastructure** | `src/infrastructure/` | FastAPI REST, MCP servers, CLI, rendering, the artifact index, write I/O | application, domain |

The domain layer names *ports* (protocols such as `OntologyModule`, `DiagramTypeModule`,
`ModelQuery`, `DiagramRenderer`); infrastructure provides the *adapters*. A change of storage
backend, renderer, or transport happens behind a port without reaching into the domain.

&nbsp;

## Why it stays honest

- **Injectable catalogs, no service locator.** The module registry and catalogs are passed in,
  not fetched from a global — dependencies are explicit and testable.
- **Frozen module catalog.** The registry is immutable after startup, so ontology and
  diagram-type sets cannot drift mid-run.
- **Dependency-policy test.** An AST-based test fails the build if a layer imports across a
  forbidden boundary, so the diagram above is checked on every CI run rather than trusted.
- **Port / verifier segregation.** Query, write, and verification responsibilities sit behind
  separate ports.

&nbsp;

## The GUI mirrors the same shape

The Vue 3 + TypeScript SPA under `tools/gui/src/` is itself ports-and-adapters:

```
tools/gui/src/
  domain/        # framework-free types and logic
  application/   # use cases over ports
  ports/         # interfaces the UI depends on
  adapters/      # REST client and other concrete implementations
  ui/            # Vue components, views, router, diagram-type UI slots
```

Diagram-type-specific UI (the bespoke sequence and C4 editors) lives under
`ui/diagram-types/`, wired in through `type_ui_slots`, so adding a notation's editor does not
touch the generic authoring views.

&nbsp;

## Startup validation as a safety net

`src/application/startup_validation.py` cross-checks every entity, connection, and diagram
type found in repo content against the registered modules, and aborts startup with a report
if it finds an unknown type. Removing or renaming a module while repos still hold its
artifacts fails loudly instead of corrupting data silently.

---

*Back to [Extensibility overview](index.md) · Next: [Reference →](../reference/configuration.md)*
