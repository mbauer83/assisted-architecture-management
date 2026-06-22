# Documentation

Architecture-as-code for humans and AI agents — a typed, git-versioned, verifiable model
reachable through a GUI, a REST API, a CLI, and MCP tools, with a confidential assurance
capability alongside it.

New here? Start with the [Quickstart in the README](../README.md#quickstart), then read the
[motivation](01-motivation.md) for the why.

&nbsp;

## Sections

| # | Section | For |
|---|---|---|
| 1 | [Motivation, Ideas, Goals & Scope](01-motivation.md) | Understanding why the project exists and what it does not try to do |
| 2 | [Installation & Setup](02-installation.md) | Getting it running on macOS, Linux, WSL2, or Docker |
| 3 | [Architecture Modeling](03-modeling/index.md) | Projects, views, graph exploration, diagramming, and the MCP/REST surface |
| 4 | [Assurance — Safety, Security, GRC](04-assurance/index.md) | STPA/CAST/GRC methods, assurance diagrams, confidential storage |
| 5 | [Extensibility](05-extensibility/index.md) | Attribute profiles, document types, ontology & diagram-type modules, the hexagonal core |
| — | [Reference](reference/configuration.md) | Configuration, CLI, and git sync/promotion facts |

&nbsp;

## Section 3 — Architecture Modeling

- [Overview](03-modeling/index.md)
- [Projects & grouping](03-modeling/projects-and-grouping.md)
- [Views & exploration](03-modeling/views-and-exploration.md)
- [Diagramming](03-modeling/diagramming.md)
- [Interfaces & MCP](03-modeling/interfaces-and-mcp.md)

&nbsp;

## Section 4 — Assurance

- [Overview](04-assurance/index.md)
- [Methods](04-assurance/methods.md)
- [Diagrams](04-assurance/diagrams.md)
- [Storage & confidentiality](04-assurance/storage-and-confidentiality.md)
- [MCP tools](04-assurance/mcp-tools.md)

&nbsp;

## Section 5 — Extensibility

- [Overview](05-extensibility/index.md)
- [Attribute profiles & frontmatter schemata](05-extensibility/schemata-and-profiles.md)
- [Document types](05-extensibility/document-types.md)
- [Ontology modules](05-extensibility/ontology-modules.md)
- [Diagram-type modules](05-extensibility/diagram-type-modules.md)
- [Hexagonal architecture](05-extensibility/hexagonal-architecture.md)

&nbsp;

## Reference

- [Configuration](reference/configuration.md)
- [CLI & backend](reference/cli-and-backend.md)
- [Git sync & promotion](reference/git-sync-promotion.md)
- [Docker Compose deployment](reference/docker-compose.md)
- [Dependency policy](architecture/dependency-policy.md) · [Glossary](architecture/glossary.md)

&nbsp;

## The model documents itself

The system's own architecture is modelled inside
[`engagements/ENG-ARCH-REPO/`](../engagements/ENG-ARCH-REPO/). Browse it through the GUI or
the `arch-repo-read` MCP tools — every screenshot in these docs is the tool describing its
own design.
