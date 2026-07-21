# PLAN — Model-Derived AIBOM (AI Bill of Materials)

## 1. Business context

An AIBOM is not an SBOM with AI-flavoured labels. An SBOM answers *what code is
in this build*, and is derived from package manifests. An AIBOM answers *what AI
is in this system, where did it come from, what does it consume, who is
accountable for it, and what did we assess about its behaviour* — and there is
no manifest that knows any of that.

That gap is why most AIBOM tooling is thin: it can enumerate `torch==2.3.1` but
cannot say which model that library serves, which dataset trained it, whose
personal data is in that dataset, or which stakeholder accepted the residual
bias risk. The OWASP AI SBOM initiative names this explicitly — "relationship
mappings for full traceability" is the hard requirement, and it is exactly what
manifest scanning cannot supply.

**We already hold that information, curated and typed.** The architecture
repository models components, data objects, services, the relationships between
them, and — through the motivation layer and assurance store — the stakeholders,
drivers, and accountability that surround them. The AIBOM we can emit is
therefore categorically better than a scanner's: not because our exporter is
cleverer, but because our *source* is a semantic model rather than a lockfile.

This plan makes that structural advantage real. It is the differentiating
capability, not a compliance checkbox.

### 1.1 Regulatory pull

AIBOM demand is arriving through procurement and audit rather than engineering:
EU AI Act technical documentation, ISO/IEC 42001 AI management systems, and
enterprise AI procurement questionnaires all ask for model provenance, training
data lineage, and accountability. These are motivation- and business-layer
questions. A repository that already models those layers is the natural place to
answer them.

## 2. Current state (verified, 2026-07-21)

Measured against the codebase, not assumed.

### 2.1 What exists and works

| Mechanism | Location | Verdict |
|---|---|---|
| Specializations (slug + name per base type) | `src/ontologies/archimate_4/specializations.yaml` | Reuse as-is |
| Attribute profiles, 1:1 with specialization (D13) | `src/domain/profiles.py` | Reuse as-is |
| Specialization-scoped schema files, **full JSON Schema** | `.arch-repo/schemata/attributes.{type}.{slug}.schema.json` | Reuse — supports arrays with `items` |
| Base-type schema files | `.arch-repo/schemata/attributes.{type}.schema.json` | Reuse |
| Shipped defaults + non-destructive upgrade | `DEFAULT_SCHEMATA`, `DefaultSchemataEnsureStep` | **Upgrade path already solved** |
| Profile merge with type-conflict detection | `profiles.merge_property_schemas` | Reuse |
| Typed attribute editor: string / boolean / integer / number / array / enum | `tools/gui/src/ui/components/TypedPropertyInput.vue` | Reuse — no new widget for flat or list attributes |
| Orphaned-specialization-schema detection | verifier rule W044 | Reuse |
| Heuristic AI-candidate scan | `ai_candidate_scanner.py` | Keep as *assistive*; demote from primary path |
| CycloneDX 1.6 emitter skeleton | `_aibom_exporter.py` | Rewrite the component body; keep the envelope |

### 2.2 What is broken or absent

1. **`assurance_mark_ai_component` does not exist.** `security_read_tools.py:146`
   instructs agents to call it after confirming candidates. Repo-wide grep finds
   the string only in that description. Agents are being directed at a
   nonexistent tool.
2. **AI-component identity cannot be persisted.** `ai_role` appears in no
   ontology definition, no schema file, no entity. The scanner's
   `if ent.get("ai_role"): continue` skip-branch is unreachable in principle.
3. **`modelCard` is emitted as an empty shell** — `{"bom-ref": ...}` with no
   `modelParameters`, `quantitativeAnalysis`, or `considerations`, ever.
4. **The GUI supplies three fields.** `selectedAiComponents` builds
   `{name, arch_entity_id, ai_role}`, and its `roleById` argument is passed `{}`
   at the call site, so every component in an export receives the same default
   role.
5. **No relationships are emitted.** The BOM has no dependency graph, so the
   traceability that is the whole point of an AIBOM is absent.
6. **The panel promises what it cannot do** — "Review coverage gaps" — and calls
   the removed `aibom_coverage` endpoint (404).

### 2.3 Honest characterisation

What we emit today is a **flat inventory of entity names carrying one shared
role label**. It is not an AIBOM in any sense a procurement or audit reader would
accept, and it uses almost none of the model's richness.

## 3. Target: what an AIBOM needs, and where it comes from

Authoritative field set from the CycloneDX 1.6 JSON schema (`modelCard`,
`componentData`), the format OWASP's AI SBOM initiative aligns on.

| ML-BOM target | Source | Derivable? |
|---|---|---|
| `component.type` (`machine-learning-model`, `data`, …) | AI specialization of the entity | Fully |
| `modelParameters.datasets[]` | connections from the model entity to dataset entities | **Fully — this is the differentiator** |
| `modelParameters.approach`, `task`, `architectureFamily`, `modelArchitecture` | attribute profile | Authored |
| `modelParameters.inputs`, `outputs` | attribute profile | Authored |
| `quantitativeAnalysis.performanceMetrics` | attribute profile (list) | Authored |
| `considerations.users`, `useCases` | motivation layer: stakeholders, drivers, goals reachable from the entity | **Largely derivable** |
| `considerations.technicalLimitations`, `performanceTradeoffs`, `ethicalConsiderations`, `environmentalConsiderations`, `fairnessAssessments` | attribute profile (lists) | Authored |
| `componentData.classification`, `sensitiveData` | dataset entity's sensitivity attribute (precedent: business-object `Sensitivity` → TLP) | Fully |
| `componentData.governance.owners/stewards/custodians` | `accountable-for` / `responsible-for` connections | **Fully — differentiator** |
| `supplier`, `publisher`, `licenses`, `hashes` | attribute profile | Authored |
| BOM `dependencies[]` | model connections between AI components | **Fully — differentiator** |

Four of the hardest rows are *derivable from relationships we already hold*. That
is the thesis of this plan.

## 4. Locked decisions

**D1 — Specializations carry AI semantics; base types stay clean.** AI
attributes attach to specializations, never to base entity types. A
`data-object` must not grow AI fields because some data objects are training
sets.

**D2 — Specialization set (initial).** Ship these, each with its own profile:

| Base type | Specialization | Represents |
|---|---|---|
| `application-component` | `ai-model` | A deployed/embedded ML model |
| `application-component` | `ai-agent` | An agentic component with tool access |
| `application-component` | `ai-orchestrator` | Prompt/RAG/tool-routing pipeline |
| `application-service` | `ai-inference-service` | A served inference endpoint |
| `data-object` | `ai-dataset` | Training / evaluation / fine-tuning data |
| `data-object` | `ai-prompt-asset` | System prompts, prompt templates |
| `data-object` | `ai-vector-store` | Embedding/vector index |
| `system-software` | `ai-runtime` | Serving runtime, inference engine |
| `application-interface` | `ai-tool-interface` | Tool/function surface exposed to an agent |

Rationale for spread across base types: an AIBOM's component `type` must be
truthful, and the ArchiMate layer already encodes the distinction between a
served capability (service), a deployed artefact (component), and passive data
(data-object). Collapsing them onto one base type would discard information we
already have.

**D3 — Profile duplication is solved at the ontology-authoring layer, not by
weakening D13.** D13 (profile ↔ specialization is 1:1, no shared registry) is a
deliberate architectural decision and this plan does not reopen it. The nine
specializations above share substantial attribute sets (provenance, licensing,
supplier). We therefore compose the *shipped defaults* from named attribute
fragments in Python (`repo_default_aibom_schemata.py`), emitting nine fully
self-contained schema files. The on-disk artefact stays 1:1 and independently
customisable; the duplication lives only in the generator, where it is cheap.

**D4 — Flat + list attributes only; no nested objects in profiles.**
`TypedPropertyInput.vue` supports string/boolean/number/integer/array/enum. The
ML-BOM's nesting is reconstructed by the *exporter*, not stored nested. E.g.
`Ethical Considerations` is authored as a string array and lifted into
`modelCard.considerations.ethicalConsiderations` at export. This keeps authoring
inside the existing editor and avoids a bespoke nested-form widget.

**D5 — Derive-by-default, override-explicitly.** Every derivable field is
computed from the model at export time. An authored attribute of the same name
overrides the derived value. The export reports, per field, whether the value was
derived or authored — so a reviewer can see what the model asserted versus what a
human typed.

**D6 — The model→ML-BOM mapping is declarative, in the ontology module.** The
connection-type-to-ML-BOM-role mapping (e.g. which relation from an `ai-model`
to an `ai-dataset` means "trained on") lives in a YAML mapping file, not in
exporter branches. See §5 for the flexibility analysis behind this.

**D7 — AIBOM content lives in the public architecture model.** Model cards,
dataset provenance, and governance are architecture facts, not confidential
assurance findings. They stay in the repository, ungated. *Vulnerabilities and
risk assessments about* AI components remain in the confidential assurance store
and are never inlined into an exported AIBOM.

**D8 — Attribute naming: Title Case, human-readable.** Following the
architecture schemata precedent (`"Problem Domain"`, `"Contained Information"`).
The assurance schemata's snake_case (`concern_class`) is a pre-existing
inconsistency; this plan does not propagate it and does not fix it either.

**D9 — Marking is explicit; scanning stays assistive.** An entity is an AI
component because it carries an AI specialization, full stop. The heuristic
scanner proposes candidates and never asserts. This makes the scanner's
already-written skip-branch meaningful for the first time.

## 5. Mapping flexibility — how much, and where

The question is how configurable the model→AIBOM projection should be. Too
rigid and it only fits our own conventions; too flexible and it becomes a
mapping DSL nobody can debug.

**Rejected — fully hardcoded.** Assumes every repo models "trained on" the same
way. Our own two repos already differ in connection conventions between groups;
an engagement repo will differ more.

**Rejected — general-purpose mapping DSL.** A user-authored query language from
arbitrary model shapes to arbitrary BOM paths. This is the viewpoint query
engine again, for one output format, and would need its own editor, validator,
and debugger. Disproportionate.

**Chosen — a closed set of named *derivation roles*, bound to connection types
by declarative configuration.** The exporter knows a fixed vocabulary of roles
it needs to fill:

```
trained-on · evaluated-on · fine-tuned-from · embeds-into
served-by · uses-tool · guarded-by · governed-by · consumes-prompt
```

The ontology module ships a default binding of each role to the connection
type(s) and target specialization(s) that realise it. A repository may override
the binding in `.arch-repo/`. The *roles* are closed (the exporter must know
what each means to place it in the ML-BOM); the *bindings* are open (each repo
declares how it expresses that role).

This gives real flexibility exactly where repos legitimately differ — their
modelling conventions — while keeping the output schema-correct by construction.
It also degrades honestly: an unbound role yields a coverage finding ("no
connection type is bound to `trained-on`"), not a silently empty BOM.

## 6. Work streams

**Stream A — Ontology foundation.** Specializations (D2), composed default
schemata (D3), derivation-role vocabulary and default bindings (D6), upgrade
step registration. Ends green with schemata present in a fresh repo and added
non-destructively to an existing one.

**Stream B — Derivation engine.** Pure application-layer projection: model
entities + connections + bindings → typed AIBOM component set, with per-field
derived/authored provenance (D5). No IO. This is the stream that carries the
differentiator and gets the heaviest unit testing.

**Stream C — Exporter rewrite.** Replace `_aibom_exporter.build_cyclonedx_16`'s
component body with a full ML-BOM: populated `modelCard`, `componentData` with
governance, and a real `dependencies[]` graph. Validate emitted documents against
the CycloneDX 1.6 JSON schema in tests.

**Stream D — Coverage.** The honest version of the dropped `aibom_coverage`:
per-entity "what is missing for a valid AIBOM" — absent required attributes,
unbound derivation roles, AI components with no governance edge. Answers the
question the current panel's help text already promises.

**Stream E — Surfaces.** REST + MCP at parity (per the standing convention:
both transports, one application layer, parity-tested). Includes building the
missing `assurance_mark_ai_component` — or rather its correctly-named
replacement, since marking is an *architecture* write, not an assurance one, and
belongs on `arch-repo-write`. Fixes the dangling description.

**Stream F — GUI.** Rework `AssuranceAibomPanel.vue`: drop the dead coverage
calls, per-component role assignment (fixing the shared-default-role defect),
model-card authoring through the existing `TypedPropertyInput`, and a coverage
view. Entity-detail integration so an AI component's model card is authored where
the entity lives, not in a separate wizard.

**Stream G — Self-model, docs, dogfooding.** Per the standing checklist.

## 7. Standing checklist verdicts

**Self-model sync: REQUIRED.** This adds a capability to the platform and
therefore to ENG-ARCH-REPO's self-model — the AIBOM derivation function, its
data objects, and its relationship to the existing assurance capability. Scoped
in Stream G, guidance-first, descriptions over new entities (per the motivation
entity discipline).

**Documentation: REQUIRED.** A new `docs/04-assurance/aibom.md` (what an AIBOM
is, why model-derived beats scanned, how to mark and author), the regenerated
MCP tool docs, and the REST reference. README touch only if AIBOM becomes a
headline capability — deferred to the owner.

**Upgrade + repair path: SOLVED BY REUSE, VERIFIED.** `DefaultSchemataEnsureStep`
already adds missing shipped schemata without overwriting operator
customisations, and reports customised files as informational findings. New
AIBOM schemata registered in `DEFAULT_SCHEMATA` inherit this behaviour. Older
repos need no migration: absent AI specializations simply mean no AI components,
which is a truthful state, not a broken one. **No data migration is required.**

**Dogfooding: REQUIRED and available.** This repository *is* an AI-integrated
system — MCP servers, agent workflows, an LLM-facing tool surface. We can and
should emit our own AIBOM, which is the honest test of whether the derivation
produces something a reader would accept.

## 8. Acceptance

1. A fresh repo and an upgraded existing repo both carry the AIBOM schemata,
   with operator customisations preserved.
2. Marking an entity with an AI specialization makes it appear in the AIBOM with
   no further input; the heuristic scanner never marks anything itself.
3. An exported document validates against the CycloneDX 1.6 JSON schema.
4. `modelParameters.datasets`, `componentData.governance`, and `dependencies[]`
   are populated *from model relationships* in the dogfooding export — the
   derivation must be demonstrated, not merely supported.
5. Every derived field is attributable as derived-or-authored.
6. An unbound derivation role produces a coverage finding, never a silent gap.
7. Coverage reports missing required attributes per AI component.
8. REST and MCP return identical bodies for the same export (parity test).
9. This repository's own AIBOM is generated, reviewed, and committed as a
   dogfooding artefact.

## 9. Open questions for the owner

**Q1 — Specialization breadth.** D2 proposes nine across five base types. Too
many for a first cut? A narrower start (`ai-model`, `ai-dataset`,
`ai-inference-service`) would prove the derivation with less ontology surface,
at the cost of a second migration later.

**Q2 — Marking tool placement.** Marking an entity is an architecture write, so
the tool belongs on `arch-repo-write`, not `arch-assurance-write` — which
contradicts the existing (dangling) `assurance_mark_ai_component` name. Confirm
the move; it is the principled placement but it crosses a server boundary.

**Q3 — SPDX 3.0 AI Profile.** The other AIBOM standard, favoured for regulatory
filings where CycloneDX is favoured for CI/CD. Out of scope here. Worth a second
emitter later, or explicitly never?

**Q4 — Ordering.** This stream needs ontology changes. The pending rename sweep
and the OpenAPI schema work both touch overlapping surfaces. Recommended order:
rename sweep → OpenAPI → AIBOM, so AIBOM's new REST surface is authored under
the finished schema discipline rather than retrofitted.
