# REVIEW — WU-G2a Self-Model Alignment (Step 1: investigate → propose, revised)

Status: applied. 11 new entities created (2 BOB+DOB pairs, 1 DOB, 1 FNC, 3 REQ, 1 APP, 1 DOB),
1 rename (Configurable Entities and Connections), 4 description enrichments, 1 rename+enrich,
9 connections. Full-repo `artifact_verify` clean (45/45, 0 errors, 0 warnings) after every
batch.

**Diagram updates from the original plan, reconsidered and skipped**: (1) adding the 3 new
requirements to `MAT@1777452513.h0iI-_` would only populate empty cells — no genuine
realization connection to the matrix's outcome columns exists for any of them yet, and
fabricating one just to fill the table would misrepresent the model; deferred until a real
outcome-level connection is warranted. (2) the promotion activity diagram's action label
("Check engagement schemata ⊇ enterprise") is already appropriately generic — it doesn't
enumerate attribute/frontmatter/document schemas by name either, so singling out
specializations/profiles/viewpoints for enumeration would be inconsistent with its existing
style, not a genuine gap. No edit made.

**Correction — D17 (repository upgrade) was NOT deferred; it was wrongly claimed absent.**
The first pass here claimed "no upgrade code exists yet anywhere in the codebase (confirmed
by search)" and deferred the repository-upgrade entities on that basis. That claim was false
— `arch-repair upgrade` is a fully shipped, tested framework (WU-C4a/C4/C4b, all done):
`src/domain/repository_upgrade.py`, `src/application/repository_upgrade/{evaluate,apply,
registry,ports}.py`, `src/infrastructure/repository_upgrade/{fs_adapter,atomic_write,guard,
config_store}.py`, wired into `docker/entrypoint.sh`. The user caught this by simply asking
"until when, and why" — a search that should have been done properly the first time (a
narrower keyword search missed real, differently-named modules; the earlier
"Path.home()/config-dir" grep in this same session had even surfaced
`repository_upgrade/config_store.py` without the connection being made). Created the 4
entities this actually warrants: `REQ@1783872530.VyosDa.repository-format-upgrade`,
`APP@1783872532.OZbaBh.repository-upgrade-framework` (realizes it), `DOB@1783872535.aRpD3E.upgrade-report`
(the structured findings shape), `DOB@1783872536.ZX-QYj.repository-policy-file`
(`.arch-repo/config.yaml` — also fills a pre-existing gap: `Model Verifier` realized the
`Repository Authoring Policy: Required Attribute Defaults` requirement with no data-object
representing the file it reads at all; added that access connection too). `CLI Tool` enriched
with `arch-repair upgrade`. Full-repo `artifact_verify` clean after applying.

This is WU-G2a's *original* scope (distinct from the specialization-extension already applied
in `REVIEW-g2a-specialization-proposal.md`): bringing ENG-ARCH-REPO's self-model up to date
with the capabilities this compliance plan added — viewpoint mechanism (D15), specialization
customization with its one-to-one attribute profile (D4–D6/D13), deployment-level guidance
import (D2/D3), model exchange (D10), and repository format upgrade (D17, deferred).

Discipline followed: read-before-propose on every touched artifact; **descriptions > connections
> entities** — every candidate defaults to "enrich an existing artifact," a new one only where
no existing artifact's scope can reasonably stretch to cover it.

&nbsp;

## Corrections folded in from review

1. **Specialization and profile are one concept, not two** (existence-dependence: a profile
   cannot exist without its one specialization, direction confirmed composition not
   association) — one BOB+DOB pair, not a broadened "ontology configuration," and not two
   separate concepts.
2. **Guidance is deployment-level, not two-tier per repository** — no "overlay precedence
   enterprise → engagement." One imported source, one local out-of-repo cache, integrated at
   bootstrap regardless of which repo(s) are active.
3. **The guidance data-object represents the served *output*, not the raw import.** The
   `get_type_guidance()` bundle mixes always-present structural data (permitted-connections,
   specialization enumeration — the verifier depends on this too, never license-gated) with
   optionally-imported prose. The raw external source is a separate, smaller thing that gets
   loaded into it, via its own dedicated function.
4. **"Configurable entities" undersells its own scope** — specializations/profiles apply to
   connections too (`specializations.yaml` has both `entity:` and `connection:` sections).

&nbsp;

## New BOB+DOB pairs (one concept, business + technical realization — precedent:
`BOB@1777390173.lt7iFm.workspace-configuration` / `DOB@1776633700.I9qEoI.workspace-configuration`)

**"Specialization Profile"** (platform-core) — one concept: a specialization classifies an
instance *and* carries its own one-to-one attribute profile (inline `attributes:` and/or a
dedicated attachment schema file) — the schema authors actually fill in. No separate, reusable,
named-profile registry: a profile cannot exist independently of its specialization (the one
exception, the default profile for unspecialized elements, is the pre-existing base-type
schema file, not this concept). Applies to both entity and connection specializations.
- BOB: the business-perspective concept — "what specialization + its attribute profile mean
  to an author": pick a specialization from a dropdown, get its attribute schema.
- DOB: `.arch-repo/specializations.yaml` (module-shipped informative library + two-tier repo
  declarations) plus the optional `attributes.{type}.{slug}.schema.json` attachment files —
  the technical realization.

**"Viewpoint Definition"** (platform-core) — a declared viewpoint's scope/selection
(`entity_filters`/`expansion rules`), representation options, and styling.
- BOB: the business-perspective concept — a saved, reusable way of looking at the model.
- DOB: `.arch-repo/viewpoints.yaml` (module-shipped starter library + two-tier repo
  declarations), the `ViewpointCatalog` aggregation.

&nbsp;

## Description updates (enrich existing — no new entities beyond the two BOB+DOB pairs above)

| Entity | Current scope | Proposed addition |
|---|---|---|
| `DOB@1780656431.T8nsTi.architecture-modelling-guidance` | The authoring-guidance catalog + skill directories | Re-scope to represent the **served output** `get_type_guidance()` bundle: always-present structural data (permitted-connections, specialization enumeration — the verifier depends on this too) merged with the optionally-imported `create_when`/`never_create_when` prose. Loaded from the new deployment-level source below, never per-repo. |
| `REQ@1777369633.UoHGZy.configurable-entities` | Generic "central aspects of entities should be configurable" (frontmatter, attribute-profile) | Rename to **"Configurable Entities and Connections"**; name the actual D13 mechanism: a specialization (entity *or* connection) carries at most one, one-to-one attribute profile. |
| `APP@1712870400.yNhgdh.module-catalog` | Ontology/connection/diagram-type catalog views, injected via `RuntimeCatalogs` | Add that it also aggregates `SpecializationCatalog` and `ViewpointCatalog`. |
| `APP@1712870400.v9LvfK.query-engine` | Full-text/metadata/graph query translation over the SQLite index | Add viewpoint execution: translating a declared viewpoint's scope/selection into the four execution representations (exploration/table/matrix/diagram) — the natural home rather than a new "viewpoint engine" component. |
| `APP@1712870400.kjC6ex.cli-tool` + `AIF@1712870400.KxvY-B.cli-interface` | Entity/connection/diagram creation, verification, index management, querying, promotion | Add the new commands: `arch-import-guidance` (deployment-level guidance import), `arch-exchange` (D10 import/export). `arch-repair upgrade`/`git-repair` (D17) deferred with the rest of D17 — see below. |
| `DOB@1776633700.I9qEoI.workspace-configuration` | `.arch-repo/config.yaml` — workspace identity | No change from the original proposal for D17's format-contract stamp — deferred alongside repository-upgrade entities (no upgrade code exists yet). |

&nbsp;

## New entities beyond the two BOB+DOB pairs

1. **Data-object — "Guidance Import Source"** (platform-core). The raw, external,
   license-gated guidance-cache document fetched from `guidance_default_source` — prose-only
   (`create_when`/`never_create_when` per type/specialization), confirmed via
   `tools/extract_guidance.py`. Distinct from `Architecture Modelling Guidance` (the served
   output it gets loaded into) — a genuinely separate artifact with its own identity
   (fetched once per deployment, never committed to any repo).
2. **Function — "Load Guidance Content"** (platform-core). The application function that
   fetches/validates/filters the external source and loads it into the one deployment-level
   cache, integrated into the in-memory meta-ontology at bootstrap. Composed under a process
   — none of the existing processes fit (this isn't part of the "practice" processes'
   business decomposition); realized-by no existing service. Proposed as a standalone function
   with an `archimate-access` connection to both new data-objects, not nested under an
   existing process, since guidance import is an operator/CLI action independent of the
   modelling/implementation/conformance-review practice loops.
3. **Requirement — "Deployment-Level Guidance Import"** (motivation-narrative). No existing
   requirement names this mechanism; `Configurable Entities and Connections` is about
   specialization/profile customization, a different concern from guidance-text sourcing.
4. **Requirement — "Viewpoint-Based Model Presentation"** (motivation-narrative). Unchanged
   from the original proposal — no existing requirement mentions viewpoints; D15 is
   substantial enough (declarative scope/selection, four execution representations, styling,
   `execution_anchor`) to warrant its own requirement.
5. **Requirement — "Model Exchange Interoperability"** (motivation-narrative). Unchanged.
6. **Application-component — "Model Exchange Adapter"** (platform-core), realizing #5.
   Unchanged — maps to `src/infrastructure/exchange/archimate_model_exchange/`.
7. **Data-object — "Exchange Document"** (platform-core). Unchanged — the C19C exchange
   document flowing through import/export.

**Deferred (no code exists yet, confirmed by search)**: Repository Format Upgrade &
Compatibility Detection requirement, Repository Upgrade Engine component, Upgrade Report
data-object, and the Workspace Configuration format-contract-stamp enrichment — all D17.
Modeling a capability with zero implementation would misrepresent the self-model's own
dogfooding principle.

&nbsp;

## Connections

- `Specialization Profile` (BOB/DOB) --access-- from `Author`/`AI Agent` roles' authoring
  activity (via existing `Author Model Artifacts` etc.) is implicit through the existing
  attribute-schema validation function; no new connection needed there.
- `Viewpoint Definition` (DOB) --access-- `Query Engine` (viewpoint execution).
- `Load Guidance Content` (FNC) --access-- `Guidance Import Source` (reads/validates) and
  --access-- `Architecture Modelling Guidance` (writes/merges into the served output).
- `CLI Tool` --realizes-- `Deployment-Level Guidance Import` (via `arch-import-guidance`).
- `Model Exchange Adapter` --realizes-- `Model Exchange Interoperability`; --access--
  `Exchange Document`.

## Diagrams

- Add `Viewpoint-Based Model Presentation`, `Model Exchange Interoperability`, and
  `Deployment-Level Guidance Import` to `MAT@1777452513.h0iI-_` (Format, Discovery &
  Extensibility) — matches its existing scope.
- Update the promotion activity diagram action `ACT@1781338474.NTuMXo#action/a3` ("Check
  engagement schemata ⊇ enterprise") to read "specializations (with their one-to-one
  profiles)/viewpoints" per D14.
- No new application-view diagram — existing platform-core views can absorb these components.

## Documents

Covered by WU-G2's ADR. No coding-guidelines/standards doc references guidance authoring
specifically.

&nbsp;

## Apply plan (Step 3)

Batches via MCP: BOB+DOB pairs and new standalone entities first (`artifact_verify` between
batches), then description enrichments, then connections, then the two diagram updates. Then
tick WU-G2a's checkbox with a progress note.
