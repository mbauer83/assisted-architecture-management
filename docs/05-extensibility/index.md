# Extensibility — Modularity Everywhere

> Adapt the system to your organisation without forking the core. The ArchiMate NEXT
> vocabulary is the shipped default, and every layer below it is a plug-in point.

Extensibility and configurability is a *Must* principle of the project. Repository behaviour —
schemata, vocabularies, document structure, diagram notation — is configurable through
git-based files at both enterprise and engagement scope, and the modelling ontology extends
beyond the base ArchiMate NEXT element and connection types.

The system already ships three ontology modules and nine diagram types, which is the
extension story working in production rather than in theory.

| Layer | What you can add or constrain | Page |
|---|---|---|
| **Attribute profiles & frontmatter** | Required/optional fields per entity, connection, diagram | [Schemata & profiles](schemata-and-profiles.md) |
| **Document types** | New structured doc kinds with required sections and links | [Document types](document-types.md) |
| **Ontology modules** | New entity/connection vocabularies (ArchiMate, SysML, assurance, …) | [Ontology modules](ontology-modules.md) |
| **Diagram-type modules** | New view families and notations | [Diagram-type modules](diagram-type-modules.md) |
| **Hexagonal core** | Swap infrastructure adapters behind stable ports | [Hexagonal architecture](hexagonal-architecture.md) |

&nbsp;

## Configuration flows enterprise → engagement

Enterprise configuration provides defaults and constraints; engagement configuration extends
or specialises within those bounds. The clearest example is the **promotion superset rule**:
an engagement repo's schemata must be supersets of the enterprise schemata, so anything
promoted up still satisfies the enterprise constraints. See
[Configuration Reference](../reference/configuration.md).

&nbsp;

## What ships today

- **Ontologies** — `archimate_next` (the canonical default), `sysml_v2_min` (a minimal SysML
  v2 vocabulary), and `assurance` (STPA/CAST/GRC). The SysML v2 domain appears as its own
  filter in the GUI, alongside the ArchiMate domains.
- **Diagram types** — ArchiMate domain views (seven) plus layered, C4 (three levels),
  activity, sequence, matrix, and the four assurance views (bowtie, control structure, GSN,
  UCA matrix).

Startup validation cross-checks every type found in repo content against the registered
modules and aborts on any unknown type, so a removed or renamed module can never silently
corrupt existing artifacts.

---

*Next: [Schemata & profiles →](schemata-and-profiles.md)*
