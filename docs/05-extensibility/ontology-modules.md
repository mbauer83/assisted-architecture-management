# Ontology Modules

An ontology module is a self-contained vocabulary of entity types, connection types, and
permitted-relationship rules. The system loads every registered module at startup and merges
them into one global `ModuleRegistry`. New ontologies — SysML, TOGAF, a domain-specific
language — drop in without touching the core.

Full contract and a complete loader example:
[`src/ontologies/README.md`](../../src/ontologies/README.md).

&nbsp;

## Shipped modules

| Module | Vocabulary | Domain (`hierarchy[0]`) |
|---|---|---|
| `archimate_next` | ArchiMate NEXT Snapshot 1 — the canonical default | motivation, strategy, business, application, technology, implementation, common |
| `sysml_v2_min` | A minimal SysML v2 vocabulary (parts, actions); shipped but disabled by default | its own domain when enabled |
| `assurance` | STPA / CAST / GRC types (stored in the encrypted assurance store, not git) | assurance |

&nbsp;

## Anatomy of a module

```
src/ontologies/my_ontology/
  __init__.py          # exposes `module` satisfying the OntologyModule protocol
  entities.yaml        # one entry per entity type
  connections.yaml     # connection types + permitted_relationships (optional)
  _loader.py           # optional; archimate_next loader is the template
```

An `entities.yaml` entry carries `prefix` (ID prefix, e.g. `PDF@…`), `hierarchy` (domain path
segments; `hierarchy[0]` is the grouping domain), `classes` (element classes used by diagram
filters and connection rules), and `create_when` / `never_create_when` authoring guidance.

`permitted_relationships` rules use `[source, target, [conn-short-names]]`, where source and
target accept a literal type, `@class`, `@all`, `@same`, or a list — so one rule can cover a
whole element class.

&nbsp;

## Rules the registry enforces at startup

- **Type-name uniqueness** — entity and connection type names are globally unique across all
  registered ontologies.
- **Single class ownership** — each element class is declared by exactly one module; others
  reference it without redeclaring.
- **Protocol compliance** — every module must satisfy the `OntologyModule` protocol, checked
  by `tests/domain/test_protocol_compliance.py` on every run.
- **Domain registration** — each new `hierarchy[0]` domain needs a colour/label entry in
  `tools/gui/src/ui/lib/domains.ts` so its chip renders correctly.

Adding a module is five steps: create the package, define `entities.yaml`, optionally define
`connections.yaml`, implement the `module` object, and register it in
`src/infrastructure/app_bootstrap.py`. A scaffold helper generates the package skeleton so
you start from a working module.

---

*Next: [Diagram-type modules →](diagram-type-modules.md)*
