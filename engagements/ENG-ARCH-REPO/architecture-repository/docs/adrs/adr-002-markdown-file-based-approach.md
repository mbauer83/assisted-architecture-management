# ADR-002: Markdown File-Based Architecture Repository

## Status

Accepted — 2026-04-12

Authors: architect

## Context

An architecture repository must store entities, relationships, and diagrams in a way that
supports versioning, diff review, AI-agent authoring, and human readability. The main
alternatives considered were:

- **Dedicated modeling tools with proprietary formats** (e.g., Archi `.archimate` XML,
  BiZZdesign EA): strong GUI, but opaque binary/XML formats with no meaningful diffs, no
  line-level AI access, and strong tool lock-in.
- **Graph databases** (e.g., Neo4j, ArangoDB): powerful query and traversal, but require
  infrastructure, offer no native git integration, and are not human-readable.
- **Markdown files + git** (chosen): each entity is a `.md` file; connections are in companion
  `.outgoing.md` files; diagrams are `.puml` files. All content is plain text, fully diffable,
  git-native, and accessible to AI agents via MCP tools without any intermediate translation layer.

## Decision

All model entities, connections, and diagrams are stored as plain text files in a git repository,
following the conventions defined in the repository's design decisions (D1–D7 in
[@DOC:IMPLEMENTATION-PLAN#d1-filename-convention-new-differs-from-eng-001](../../IMPLEMENTATION-PLAN.md)).

Entity files use the naming convention `TYPE@epoch.random.friendly-name.md`.
Connections are stored as `.outgoing.md` companion files.
Diagrams are `.puml` files in `diagram-catalog/`.
Non-model documentation (ADRs, standards, specs) lives in `docs/`.

All creation and editing of model content is done through MCP tools, not by direct file editing.

See [@DOC:adr-001-archimate-next-adoption#decision](adr-001-archimate-next-adoption.md)
for the related ontology decision that this file format makes tool-independent.

## Consequences

**Positive:**
- Full git history: every change is a commit, every review is a PR diff.
- AI-agent authoring: MCP tools can read and write entities without needing a GUI.
- No infrastructure dependencies beyond git and Python.
- Human-readable without tooling; any text editor shows valid content.
- Offline-capable; no server required for reads.

**Negative / risks:**
- No built-in graph query; requires an index (SQLite) built at query time by MCP tools.
- Diagram rendering requires PlantUML, which must be available in the environment.
- Large repositories (thousands of entities) may have performance limitations at scan time.
- Concurrent writes from multiple agents require coordination to avoid merge conflicts in
  `.outgoing.md` files.
