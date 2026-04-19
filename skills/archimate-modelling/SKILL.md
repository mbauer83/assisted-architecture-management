---
name: archimate-modeling
description: >
  Use this skill whenever you are working with the ArchiMate NEXT architecture repository
  in this project — creating entities, adding connections, reading or exploring model
  content, or answering questions about architecture. Trigger on any request that involves
  modeling stakeholders, drivers, goals, outcomes, requirements, capabilities, courses of
  action, value streams, roles, processes, functions, services, application components,
  data objects, technology nodes, artifacts, work packages, deliverables, or plateaus.
  Also trigger when the user asks to "add to the model", "connect X to Y", "what's in the
  model", "create an architecture element", "update the architecture", or anything that
  references the model or architecture repository. Use this skill proactively — if there
  is any chance it applies, use it.
---

# ArchiMate NEXT Modeling Skill

All model access and mutations go through `model_*` MCP tools from the `sdlc-model`
server. Never read or write model files directly.

---

## Modeling Principles

Apply these before deciding what to create. They govern *when* and *how much* to model.

### Selective domain coverage

No engagement requires content in all domains. Determine which domains are relevant
by reading the user's request and conversational context, then confirming against
existing model content with targeted queries — not by asking the user directly. The
user's plans, goals, and the questions they are trying to answer usually make domain
scope clear. When they don't, `model_query_stats` and a targeted search will reveal
what is already modeled and where the gaps are. Only escalate to the user when domain
scope remains genuinely ambiguous after that discovery.

Domain applicability heuristics:
- **Motivation** — almost always relevant; goals, requirements, and drivers anchor
  every other modeling decision. Get this right first.
- **Common / Business / Application** — the typical working layers for most
  engagements. Proceed here once Motivation is solid.
- **Implementation & Migration** — only when the engagement explicitly plans or tracks
  change (work packages, deliverables, plateaus). Infer this from context (e.g. the
  user is discussing a project plan or transition roadmap); add it without prompting
  when the intent is clear, propose it when plausible but uncertain.
- **Strategy** — only when the engagement concerns changes to the structure of the
  business itself (capabilities, value streams, resources).
- **Technology** — often less frequent once stable infrastructure and deployment
  patterns are established. Add only when architectural questions directly concern
  infrastructure, deployment, or physical structure.

### Pareto principle — minimal sufficient coverage first

Over-modeling is a real risk: it consumes time, creates maintenance burden, and
obscures the signal in noise. On each iteration, identify the highest-leverage
elements — the ones without which the key architectural questions cannot be
answered — and model those first. Resist comprehensiveness. Three well-chosen
requirements are more useful than fifteen vague ones. On subsequent iterations,
apply the same test to what hasn't been modeled yet.

### Recommended sequencing for a planning or modeling effort

1. **Motivation first.** Goals, outcomes, and requirements must be coherent and
   connected to drivers and stakeholders before anything else is built. Improve or
   complete the motivation model if it is not yet adequate.
2. **Common, Business, Application.** Apply the Pareto principle throughout.
3. **Implementation & Migration** when the engagement explicitly involves planning or
   tracking change — infer from context.
4. **Strategy and Technology** only when specifically needed.

---

## Model vs. Diagram — Two Distinct Activities

These are related but different work, with different disciplines.

### Model creation
Building and maintaining the knowledge graph: creating entities, adding connections,
editing existing content. A modeling session may legitimately create elements across
multiple domains and at different levels of abstraction. Breadth is acceptable as long
as the Pareto principle is applied — include what is architecturally significant, not
everything that could be included. The model is the persistent, shared foundation;
its value compounds across sessions.

### Diagram creation
Selecting a focused subset of model elements to visualize for a specific audience
answering a specific architectural question. A diagram is a viewpoint — it is not a
map of everything in the model.

**Before creating a diagram, establish:**
- **Audience:** Who will read this? Executives, engineers, and project managers need
  different things. The audience determines which elements and relationships matter.
- **Viewpoint / question:** What is this diagram trying to answer or communicate?
  One clear question per diagram.
- **Scope boundary:** What is deliberately excluded? Keeping this boundary sharp is
  what makes a diagram useful.

**When composing a diagram:**
- **Start from one central element** and add others by following the most
  architecturally significant relationships for the target audience.
- **Keep each diagram small and focused.** Many small diagrams serving distinct
  viewpoints are more useful than one large diagram that tries to show everything.
- **Use matrix diagrams** for dense connections between many elements — they scale
  better than node-link diagrams and are easier to read.
- **Propose intermediate results for discussion.** A partial diagram shared early is
  more valuable than a complete one shared too late. Iterate toward the goal.

---

## MCP Tool Map

Quick reference for every available tool, organized by purpose. Use this to pick
the right tool without guessing.

### Orientation
| Tool | When to use |
|---|---|
| `model_query_stats` | When you need broad orientation — confirms server connection, shows counts by domain/type. Use at the start of a fresh session or when the scope of existing content is genuinely unclear. Skip when the user's request is specific enough to go straight to targeted search. |
| `model_write_help` | When uncertain about a type or connection identifier — returns the full catalog of valid `artifact_type` and `connection_type` names. Call once; names are non-obvious and guessing causes validation errors. |

### Reading and searching
| Tool | When to use |
|---|---|
| `model_query_list_artifacts` | List artifacts with AND-filtered metadata (domain, artifact_type, status); returns summaries only |
| `model_query_read_artifact` | Read one artifact by `artifact_id`; use `mode="summary"` for frontmatter + snippet, `mode="full"` for complete content |
| `model_query_search_artifacts` | Keyword search across all artifacts; use for duplicate checks and exploration |
| `model_query_find_connections_for` | Find connections touching a specific entity; filter by direction (`any`/`outbound`/`inbound`) and/or `conn_type` |
| `model_query_find_neighbors` | Graph traversal from an entity; controls `max_hops` and optional `conn_type` filter |

### Type and connection guidance
| Tool | When to use |
|---|---|
| `model_write_modeling_guidance` | Call when the right type or connection is unclear, or before creating elements in a domain you haven't modeled yet in this session. Returns `create_when`, `never_create_when`, and `permitted_connections` (outgoing/incoming/symmetric). The baked-in tables below cover quick orientation; this tool is authoritative and returns `permitted_connections` which the tables don't fully capture. `filter` accepts entity-type names (e.g. `["requirement", "goal"]`) OR domain names (e.g. `["Motivation"]`) — never mixed. Omit for all types. |

### Creating
| Tool | When to use |
|---|---|
| `model_create_entity` | Create a new entity; always call with `dry_run=true` first |
| `model_add_connection` | Add a connection between two entities; always `dry_run=true` first; automatically creates a GRF proxy when connecting to an enterprise entity |

### Editing
| Tool | When to use |
|---|---|
| `model_edit_entity` | Update `name`, `summary`, `properties`, `notes`, `keywords`, `version`, or `status` on an existing entity; always `dry_run=true` first |
| `model_edit_connection` | Update description/cardinalities (`operation="update"`) or delete a connection (`operation="remove"`); always `dry_run=true` first |

### Verification
Verification runs automatically on every write tool call. Check the `verification`
field in the response — it reports any constraint violations. There is no need to
call a separate verify tool after creating or editing.

---

## Modeling Workflow

### When to proceed vs. when to confirm

Scale your autonomy to the scope of the request:
- **Small, clear request** (1–3 entities, unambiguous types): proceed, then report what was created.
- **Medium batch or ambiguous types**: briefly state what you plan to create and why, then proceed unless the user objects. Don't wait for explicit approval on every element — a concise "I'll create X, Y, Z and connect them as follows…" is enough.
- **Large or structurally significant changes** (new domain, plateau boundaries, significant rewiring): present a plan and confirm before committing anything. These are hard to undo cleanly.

When creating multiple entities, dry-run the full batch first, show a compact summary of what would be written, then commit in one pass rather than reporting after every individual entity.

### Steps

**Step 1 — Understand and explore.**
Read the request and conversation context to identify what's being asked and which domains and types are likely involved. Do a targeted search to find related existing content and potential duplicates in one pass:
```
model_query_search_artifacts(query="<key concept>", limit=10)
```
If the request is broad enough that you genuinely need a count overview first, call `model_query_stats` — but don't load broad stats before you know what you're looking for.

**Step 2 — Resolve type and connection choices.**
When the right entity type or connection is unclear, call `model_write_modeling_guidance(filter=[...])`. When the type is already obvious from context and the baked-in reference, skip this call. If you're working in a domain you haven't touched this session, call it once for that domain as a warm-up.

**Step 3 — Check for duplicates.**
If Step 1 didn't already surface candidates, do a focused check before creating:
```
model_query_list_artifacts(artifact_type="...", domain="...")
```
Read a candidate with `model_query_read_artifact(mode="full")` to decide whether to reuse, edit, or create a genuinely distinct entity.

**Step 4 — Check for existing connections.**
Before adding a connection, confirm it doesn't already exist:
```
model_query_find_connections_for(entity_id="...", direction="any")
```
For symmetric types (e.g. `archimate-association`), one direction check is enough.

**Step 5 — Dry-run.**
Call with `dry_run=true`. Read the `content` preview — verify type, name, summary, and structure are correct before committing.

**Step 6 — Commit and verify.**
Call with `dry_run=false`. Check the `verification` field in the response. If it reports errors, fix the underlying issue (wrong type, missing required connection, invalid relationship) and re-dry-run before retrying. Report `artifact_id` values to the user.

### Writing good entity summaries

The `summary` parameter is the most important free-text field — it's what makes the model self-documenting and searchable. Write one sentence answering: *what is this element and what role does it play in the architecture?* Avoid restating the name or type. A requirement summary should state the actual constraint; a process summary should state what it does and why it matters.

---

## Entity Type Quick Reference

Use this table for quick orientation. Always confirm with `model_write_modeling_guidance`
before committing to a type — it provides the full guidance and permitted connections.

### Motivation Domain
| Type | Create when | Never create when |
|---|---|---|
| `stakeholder` | Generalized perspectives affected by and interested in the architecture | Every individual without abstraction |
| `driver` | Internal/external factors motivating the enterprise to define goals | Too operational, concrete, or solution-oriented |
| `assessment` | Statements/judgments about states of affairs related to drivers | Too vague, directional, or describes a role performing evaluation |
| `goal` | High-level statements of intent or desired states | Too specific (→ requirement), or describes an achieved result (→ outcome) |
| `outcome` | Observable strategic results, performance metrics, target states | General intent/direction (→ goal), or describes a strategy |
| `principle` | Broad, lasting normative rules informing how the enterprise operates | Too specific, narrow, or situative; widely understood policies without architectural impact |
| `requirement` | Specific statements of need, obligation, constraint, or prohibition | Too general or high-level (→ goal), or not directly relevant to the architecture |
| `meaning` | How specific stakeholders interpret architecture elements | Not specific or interest-relative; doesn't resolve relevant ambiguity |
| `value` | Worth, utility, or benefit of elements to external stakeholders | Not specific; doesn't clarify how the architecture provides value |

### Strategy Domain
| Type | Create when | Never create when |
|---|---|---|
| `capability` | Stable abilities/capacities of the enterprise (what it needs to do) | Too volatile, situative, or describes specific processes |
| `value-stream` | Sequences of activities creating value for stakeholders | Not focused on value-creation; confused with processes/functions |
| `resource` | Strategic tangible or intangible assets relevant to capabilities | Not a strategic asset; too volatile |
| `course-of-action` | Strategic/tactical plans about organizing resources to realize outcomes | Specific processes, low-level tasks, or deliverables |

### Common Domain
| Type | Create when | Never create when |
|---|---|---|
| `service` | Explicit, well-defined behavior provided to the environment by an active structure | Doesn't describe behavior grouped by external relevance/visibility |
| `process` | Causally/temporally ordered sequences of internal behavior | Mainly resource-oriented grouping (→ function), external view (→ service), or too detailed |
| `function` | Behavior grouped by resources, knowledge, or capacities | Causally ordered sequences (→ process) or external view (→ service) |
| `event` | Something that happens (state change) triggering or interrupting behavior | Not relevant as trigger/interruption; minor state changes |
| `role` | Abstract types of behavior-performing entities sharing responsibilities | Not a behavior-performing entity; decoupling from actors provides no value |
| `path` | Logical links through which active structure elements exchange data/energy | Better as direct Collaboration or as a specific network |

### Business Domain
| Type | Create when | Never create when |
|---|---|---|
| `business-actor` | Organizational entities performing behavior relevant to architecture | Every individual participant without abstraction |
| `business-interface` | Ways/channels through which services are made accessible to roles/actors | Represents specific behavior rather than access to it |
| `business-object` | Types of entities/concepts used or produced by business behavior | Not relevant to business behavior |
| `product` | Coherent collections of objects, services, artifacts offered as a whole | Not a coherent offering; no concrete elements aggregated |

### Application Domain
| Type | Create when | Never create when |
|---|---|---|
| `application-component` | Modular, deployable software units performing behavior | Specific behavior of a component; not actual deployable software |
| `application-interface` | Points of access where a component exposes services (contracts, parameters) | Better as service/process/function; no meaningful distinction |
| `data-object` | Types of data used/produced by application elements at architectural level | Not relevant to behavior elements; too granular for the architectural level |

### Technology Domain
| Type | Create when | Never create when |
|---|---|---|
| `technology-node` | Generic IT/physical structure hosting or interacting with others | Doesn't provide coherent hardware+software collection supporting applications |
| `device` | Specific (potentially virtualized) IT hardware for storage/processing | Better as technology-node (generic execution environment) |
| `system-software` | Software providing execution/storage environment for other software | Better as application-component (business-relevant) or technology-node (generic) |
| `technology-interface` | Points of access where nodes/devices/system-software makes services available | No meaningful distinction; no architectural relevance |
| `communication-network` | Sets of IT structures for routing/transmission/reception of data | Logical abstract channel (→ path); not relevant to architectural decisions |
| `artifact` | Tangible assets: databases, source files, images, scripts, documents | Too abstract; no architectural relevance above what it realizes |
| `equipment` | Physical non-IT assets (machinery, vehicles, tools) relevant to architecture | Information technology; not relevant to architecture |
| `facility` | Physical locations, buildings, rooms relevant to architecture | Better as Resource or Process; not architecturally relevant |
| `distribution-network` | Physical networks transporting energy or materials | Logical abstract channel (→ path); not relevant to architectural decisions |
| `material` | Physical substances/resources (including energy sources) | Carries out processes (→ equipment); not relevant to architecture |

### Implementation & Migration Domain
| Type | Create when | Never create when |
|---|---|---|
| `work-package` | One-off action sets to achieve objectives within resource/time constraints | Recurring daily processes; replacement for sprint planning; too low-level |
| `deliverable` | Tangible/intangible outputs produced as results of work packages | Not an output of implementation activities relevant to architecture |
| `plateau` | Significant architecture states at specific points in time (current/transition/future) | Not a significant stage; not sufficiently comprehensive or temporally localized |

> `global-entity-reference` (GRF) is created automatically by `model_add_connection`
> when connecting to an enterprise entity. Never create or edit GRF entities directly.

### Common disambiguation calls

**goal vs. outcome vs. requirement:** A goal states a desired direction ("improve reliability"). An outcome is a measurable, observable result that signals the goal is achieved ("99.9% uptime over 30 days"). A requirement is a specific constraint or obligation the architecture must satisfy to reach that outcome ("the system must recover from failure within 30 seconds"). When an element has both a directional intent and a specific measurable target, split it.

**process vs. function:** Ask whether the grouping principle is *sequence* (this happens, then that) or *resource/capability* (these activities share the same people, knowledge, or system). Sequence → process. Shared resource → function.

**capability vs. course-of-action:** A capability is what the enterprise *can* do and needs to maintain over time. A course of action is a specific *plan* for deploying capabilities and resources to achieve an outcome. A capability is stable; a course of action is chosen and may change.

**service vs. process/function:** A service is the *external view* — what is provided to consumers. A process or function is the *internal realization*. If you're describing what something offers to the outside world, it's a service. If you're describing how work is done internally, it's a process or function.

---

## Connection Types

### ArchiMate connections (use for all ArchiMate entities)
| Type | Direction | Key uses |
|---|---|---|
| `archimate-composition` | asymmetric | Strong whole-part (part cannot exist independently) |
| `archimate-aggregation` | asymmetric | Weak whole-part (part can exist independently); same-type grouping |
| `archimate-assignment` | asymmetric | Actor/role assigned to behavior; resource to capability |
| `archimate-realization` | asymmetric | Lower-level element realizes a higher-level element |
| `archimate-serving` | asymmetric | One element serves/supports another |
| `archimate-access` | asymmetric | Behavior element reads/writes a passive structure element |
| `archimate-influence` | asymmetric | One element influences another (mainly motivation domain) |
| `archimate-association` | **symmetric** | Generic undirected association — valid between all types |
| `archimate-specialization` | asymmetric | One type specializes another of the same type |
| `archimate-flow` | asymmetric | Flow of information or materials between behavior elements |
| `archimate-triggering` | asymmetric | One behavior causally triggers another |

### Diagram-specific connections (only within their diagram type)
- `er-*` — ER diagrams only
- `sequence-*` — sequence diagrams only
- `activity-*` — activity diagrams only
- `usecase-*` — use-case diagrams only

### Key permitted relationship patterns
- **Motivation chain:** `driver --association--> assessment --association--> goal`, `outcome --realization--> goal`, `requirement --realization--> outcome/principle`
- **Strategy:** `capability --realization--> course-of-action`, `resource --assignment--> capability`
- **Cross-layer realizations:** `process/function --realization--> service`, `artifact --realization--> application-component`, `data-object --realization--> business-object`, `application-interface --realization--> business-interface`
- **Universal:** `archimate-association` (symmetric, always valid between any two types)
- **Same type:** `archimate-aggregation`, `archimate-specialization` (always valid)

When uncertain whether a connection is permitted, call `model_write_modeling_guidance`
with the source type — its `permitted_connections` field is authoritative.

---

## Cardinalities

Add `src_cardinality` / `tgt_cardinality` on `model_add_connection` **only** when
multiplicity is architecturally significant. Leave absent otherwise.
Valid values: `"1"`, `"0..1"`, `"1..*"`, `"*"`. Not permitted on junction connections.

---

## Repo Scoping

- `repo_scope="engagement"` — default for all writes; targets the current engagement repo
- `repo_scope="both"` — default for queries; reads engagement + enterprise
- `repo_scope="enterprise"` — read enterprise repo only

Use `repo_preset` to target a named engagement (e.g. `"ENG-001-architecture"`) when
multiple engagements are configured. When connecting to an enterprise entity,
`model_add_connection` handles the GRF proxy automatically.
