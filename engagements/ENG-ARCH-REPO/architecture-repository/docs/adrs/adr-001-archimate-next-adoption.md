# ADR-001: Adopt ArchiMate NEXT Ontology

## Status

Accepted — 2026-04-12

Authors: architect

## Context

The system requires a formal architectural ontology to classify entities (stakeholders, goals,
requirements, capabilities, services, components, infrastructure) and the relationships between
them. Two candidates were evaluated:

- **ArchiMate 3.x** — the established OMG standard, widely supported by tooling.
- **ArchiMate NEXT** — an evolution that restructures the layer model, moves all behavioral
  elements (services, processes, functions, events, collaborations, roles) into a shared `common/`
  domain, and merges the physical layer into technology.

The key operational pressure is that this repository is authored and queried primarily by AI agents
via MCP tools, not by modelers using GUI diagram tools. The ontology therefore needs to be
*machine-legible* (precise, minimal, consistent) more than it needs to be compatible with legacy
diagram editors.

The repository also stores the ontology entirely in markdown files and PlantUML, making the choice
of ontology a matter of directory structure and element-type labels rather than a dependency on
any particular modeling tool.

## Decision

Adopt ArchiMate NEXT.

Behavioral elements (services, processes, functions, events, collaborations) and roles are placed
in `model/common/` regardless of whether they support business, application, or technology
concerns. The physical layer is not used; physical infrastructure is expressed under `technology/`.

The full directory structure is defined in
[@DOC:docs-overview#structure](../README.md).

See also
[@DOC:adr-002-markdown-file-based-approach#decision](adr-002-markdown-file-based-approach.md)
for the file-format decision that makes this ontology choice independent of external tooling.

## Consequences

**Positive:**
- Cleaner separation: structural entities in their domains; all behavioral in `common/`.
- Reduced ambiguity about where to place services and processes.
- Forward-compatible with expected ArchiMate NEXT standardisation.

**Negative / risks:**
- ArchiMate NEXT is not yet a ratified OMG standard; the ontology may still shift.
- Existing ArchiMate 3.x tooling (e.g., Archi, BiZZdesign) does not natively understand the
  `common/` domain; interoperability is limited to what the custom PlantUML stereotypes express.
- Team members familiar with ArchiMate 3.x need to learn the new behavioral placement rules.
