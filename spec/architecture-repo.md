## When Reach exceeds Grasp

* Volume AND Velocity of code-generation is growing exponentially
* Reviews and QC can’t keep up → already also being outsourced to AI
* What about planning - who knows what is built and how it relates to what is desired or what must NOT happen?
* Examples of failure-modes with news-reports
* → Need way to keep up with planning & governance, and to improve coherence


## How Do We Adapt?

* Harvard Business Review: Change decision structure & topology for more autonomy and velocity of subunits, accepting higher failure rates for more innovation, iteration and capability. → Enterprise Architecture (cf contingency theory) →  need to to goal-directed evolution of Capabilities, Structures, Workflows → needs mapping thereof. More autonomy for subsystems of the enterprise is good, but businesses which can achieve integration (unity of effort, shared understanding of goals, values, requirements etc, re-usable learnings) even through such increased diversification will still outperform those who can’t.

* Spec-driven development is there to provide context → that’s what good architecture & planning should always have provided, in a more structured, durable & extendable way. → Needs persisted & discoverable structure → Architectural Models & Diagrams, Decision Records, Guidelines & Documentation, Reusable components. 

* This is a lot - and most companies can’t keep up with planning as-is. We can i) reduce coverage, ii) reduce granularity, iii) improve discoverability, iv) improve maintainability & evolvability [Diagram of forces / potentially archimate motivation layer]

* We might need to all a mixture of all of this. What are our requirements, and what’s the landscape?


## An Opinionated List of Requirements

* Consistent, unified formatting (→ Not JUST natural language)
* Human-readable and discoverable (→ Text, Files, Directory-Trees, Queryable and Discoverable via graph-relations, full-text, hierarchical structure, metadata, keywords)
* Deterministically parsable, explorable, graphable (→ structured frontmatter, keywords, relationships)
* Efficient ingestion and production by LLMs (→ markdown, natural language, not SVGs, binary data)
* Version-controlled (git)
* Not entirely binary based (not just DB-based)
* Should support textual (structured) documents for architectural decision records, specification-documents, guidelines etc.
* Should support all archimate layers, entity-types & connections
* Should support Matrix-Tables for displaying dense connections
* Should also support BMPN / Activity diagrams, UML sequence diagrams & ER diagrams
* Scalable to team- and at least small-business level.

→ Not pure DB. Karpathy’s markdown wiki is the right direction, but can be made to be more explorable, coherent and “validatable”.

## A Proposal

### Basic Structure

* Archimate ontology + connection-types for additional diagrams → standardized, proven, comprehensive (but can be extended)

* Primarily md-based in directory structure according to archimate ontology → LLM & human friendly, git-trackable, structured

* PUML for diagrams → expressive, short, extensible, great for LLMs & humans

* Markup with tables for dense connection matrices (linking to entity files)

* Entity-Id / Filename convention: [TYPE-ABBR.]@[epoch_seconds].[6-char-YT-like-random].[friendly-name].md → Revision-safe, human-readable, machine-readable

* YAML-based frontmatter with standardized fields, status (draft, active, deprecated), provenance-data, version, keywords etc. → Machine-readable, indexable, verifiable

* Delimiter-based section-structure for files: Human & LLM-readable general description, standard PUML archimate representation, definable additional schemata

* File per entity plus file per outgoing connections (adjacency-list style): [TYPE-ABBR.]@[epoch_seconds].[friendly-name].[6-char-YT-like-random].outgoing.md

* Standardized formal cross-reference style (including sub-anchors for sections)  for additional textual documentation-files (architectural decision records, guidelines, specification-documents)

### Discoverability

* Runtime indexing into database with extracted front-matter (& substructure like keywords, status, version, datetime-stats)

* Also pulls git-history to calculate volatility (absolute and relative) 

* Also extracts connections for graph-based stats, discovery & traversal - for model-entities, diagrams via entities, and other docs with cross-references

* Also indexes for semantic full-text-search (e.g. via TF-IDF, potentially also via vector-db)

* SQLite is sufficient, long-term state-tracking happens via git

* Provide efficiently usable & discoverable API in code, then adapters for CLI, REST, MCP

### Coherence

* Read access for agents at directory & file level & via MCP tools

* Write access exclusively via MCP tools which: 
  * Automatically adds formatted & schema-verified frontmatter
  * For entities, automatically generates & adds the default archimate PUML-fragment for diagram representation
  * For entities & connections, automatically updates a PUML macro which can be included in other files and permits referencing of all registered entities & connections (can be partitioned by diagram type when scale becomes a problem)
  * For diagrams & connections, validates referential integrity
  * For diagrams, validates PUML syntax
  * Automatically updates DB / indices
  * Automatically verifies referential integrity and status-conformity (draft-entities and draft-connections may only be referenced in draft diagrams)

### Knowledge Management & Reusability

Two-tiered structure: 

* Per-project / per-engagement repository (“local” work)

* Enterprise repository (globally re-usable)

This permits isolating work that has only local relevance from work that has global relevance and should guide local work.

Enterprise repository contains:

* Cross-cutting or globally applicable guidelines & decision documents

* Models, diagrams & documentation for the business itself and its software-products through all architectural layers

* Re-usable building blocks at any architectural level for individual projects / engagements

Per-project / per-engagement repository contains:

* Locally relevant information-collection, draft-artifacts and “internal” iteration artifacts not (yet) relevant across engagements / projects / teams

Individual artifacts can be selected for “promotion” to the enterprise-repository, which automatically includes the transitive closure of a dependency-operator on the directed dependency-graph. This promotion must validate the uniqueness of the id/name, and should be handled via specific tool.


## Future-Proofing

Use ArchiMate NEXT ontology (behavioral elements now common, "layers" renamed to "domains" to make clear this is not structure of abstraction layers and that processes can be performed with human and automated components / services realizing and/or assigned to various elements). Make sure to be strict about which relations are valid between which elements within and across domains, and follow best practices for how realizations, access, assignments, and serving relationships should be structured. Research ArchiMate NEXT to make sure you get it.