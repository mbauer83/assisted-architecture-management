# PLAN — Named Attribute Profiles: Registry, Lifecycle, and Failure Semantics

## 1. Why this exists

Attribute profiles today are strictly 1:1 with a specialization (D13): a profile
is either a specialization's inline `attributes:` mapping or its dedicated
`attributes.{type}.{slug}.schema.json` attachment. There is no way to declare an
attribute set once and apply it to several (entity-type, specialization) pairs.

That constraint is stricter than both languages this repository derives from.
ArchiMate 3.1 §15.1 defines a profile as *"a data structure which can be defined
separately from the ArchiMate language but can be dynamically coupled with
elements or relationships"*, and its own worked example (cost/performance
analysis) applies one attribute set across services **and** serving
relationships. UML is equivalent: *"Each stereotype may extend one or more
metaclasses."*

The AIBOM work is the case that makes this concrete — nine specializations across
five base types sharing provenance, licensing, and supplier attributes — but the
need is general and the mechanism belongs to the ontology core, not to AIBOM.

This plan adds named, reusable profiles **as an opt-in**, and — the larger part
of the work — defines their lifecycle, versioning, and failure semantics.

## 2. Current state (verified)

| Fact | Location | Consequence |
|---|---|---|
| Merge is already N-ary | `profiles.merge_property_schemas(schemas: list[...])` | Multiple fragments already supported |
| The 1:1 limit lives in *resolution*, not merge | `artifact_schema.compute_effective_attribute_schema` appends ≤1 specialization fragment | Lifting it is a resolution change |
| Base-type schema is always fragment 1 | same function, lines 147-149 | **Parent-attribute inheritance already works** and is spec-conformant |
| Identical redefinition already legal; only differing `type` conflicts | `merge_property_schemas` | Correct semantics for composition already in place |
| Conflicts already blocking at verify time | rule E043 | Per-entity enforcement exists |
| Conflicts already returned to the GUI | `routers/entities.py:221` | The frontend already receives this data |
| Write path uses base schema only | `artifact_write_formatting.py:336` via `load_attribute_schema` | **Gap: the write boundary never sees specialization profiles** |
| Startup validation with hard fail is house style | `_group_registry_startup.py` | Precedent for the failure posture below |
| Schema-version tags are house style | `QUERY_SCHEMA_VERSION` | Precedent for versioning below |

The last three rows decide most of this plan.

## 3. Locked decisions

**P1 — Named profiles are opt-in; 1:1 stays the default.** A specialization
still gets its own profile from inline attributes or its attachment file. A
specialization may *additionally* bind named profiles. Nothing about existing
repos changes, and the common case stays the simple case.

**P2 — Resolution order is deterministic and explicit.**

```
base-type schema  →  bound named profiles (declaration order)  →  the
specialization's own profile
```

The specialization's own profile is last, so it always wins over a shared
profile it composes — the specific overrides the general. Parent-attribute
inheritance (fragment 1) is unchanged.

**P3 — Identical redefinition is legal; incompatible redefinition is an error.**
Two profiles declaring `Supplier: string` compose silently — that is the point
of reuse. Same name with a different `type` is an error, never a silent
last-writer-wins. This is today's `merge_property_schemas` semantic, preserved.

**P4 — Two version tags, each with a distinct job.**
- `profile_schema: <int>` on the registry file — the *declaration format*
  version, enabling format migration. Follows the `QUERY_SCHEMA_VERSION`
  precedent: an unrecognised value is a typed error, never a best-effort parse.
- `version: <int>` on each named profile — the *content* version. This exists to
  make reconciliation possible: today `DefaultSchemataEnsureStep` can only say
  "your file differs from the shipped default"; with content versions it can say
  "the shipped profile advanced to v3 while your customisation is based on v1",
  which is the difference between a warning and an actionable upgrade.

**P5 — Entities do not record the profile version they were authored against.**
Pinning entities to profile versions would mean mass file churn on every profile
edit and a second source of truth about what an entity's schema is. Instead
entities are validated live against the current effective schema, and drift
surfaces as verifier findings to reconcile. The model stays the single source of
truth.

**P6 — Only attached repositories are read and validated.** Validation walks the
configured engagement and enterprise roots. It never scans the filesystem for
repositories, and never validates a repository that is not attached.

**P7 — Failure posture is split by blast radius, not by severity feeling.** See
§4. This is the core of the plan.

**P8 — Enforcement lives at the write boundary, not in the UI.** Correctness must
not depend on the frontend having been updated. The GUI's role is to explain a
refusal that the backend already guarantees.

## 4. Failure semantics: fail hard globally, quarantine locally

Silent accumulation of schema errors is the worst outcome — it produces entities
authored against a schema nobody can reconstruct. But bricking an entire
repository because one specialization has one bad attribute is disproportionate.
The resolution is to classify by **blast radius**.

### Class A — Structural. The profile subsystem itself is untrustworthy.

Unparseable registry; unknown `profile_schema` version; a binding referencing an
undefined profile; malformed JSON in a schema file.

Nothing downstream can be trusted, because we cannot even determine what the
schema *is*. Behaviour follows the existing `groups.yaml` precedent exactly:

- **Engagement (primary, writable) repo → hard fail at startup**, with the
  offending file, the reason, and the fix. `_group_registry_startup.py` already
  does precisely this (`sys.exit(1)`) for a malformed group registry, so this is
  consistency with established behaviour, not a new posture.
- **Enterprise (attached, read-only) repo → log and continue.** Also the existing
  precedent: an attached repo's defect must not prevent the server serving the
  repo the user is working in.

### Class B — Scoped. Exactly one (entity-type, specialization) pair is affected.

An incompatible type conflict between two bound profiles, or between a profile
and the base schema.

The rest of the model is perfectly well-defined, so the failure is confined to
the affected pair, which enters **quarantine**:

| Aspect | Behaviour |
|---|---|
| Reads | Continue. Existing entities remain readable and listable. |
| Effective schema | Resolves to the last unambiguous fragment set (base + non-conflicting profiles), flagged `quarantined` with the reasons. |
| Creates/edits for that pair | **Rejected at the write boundary** with a typed error naming the colliding profiles, the field, and the conflicting types. |
| Other types and specializations | Entirely unaffected. |
| Verifier | E043 per affected entity, as today. |

Quarantine is *fail-closed at the affected scope*: no entity is ever written
against an ambiguous schema, and no undefined behaviour accumulates — which is
the outcome that matters.

### Why this needs no significant frontend work

Because P8 puts enforcement at the write boundary, a frontend that is unaware of
quarantine is still **correct**: a create or edit attempt returns a typed error
instead of writing ambiguous data. The GUI already receives `conflicts` from the
schema endpoint (`entities.py:221`), so surfacing quarantine is a banner plus a
disabled submit — reusing the existing conflict channel rather than adding a
feature area. Progressive enhancement, not a prerequisite.

### Defense in depth

Five independent layers, each of which alone prevents ambiguous writes:

1. **Authoring/CI** — shipped profiles validated in the test suite; a conflict in
   our own ontology fails the build. Users never see it.
2. **Startup** — attached repos validated; Class A hard-fails the engagement
   repo, Class B computes the quarantine set.
3. **Write boundary** — every entity mutation checks the quarantine set. Closes
   the verified gap where the write path uses `load_attribute_schema` (base
   only) and never sees specialization profiles at all.
4. **Verifier** — E043 blocking errors per entity (exists).
5. **Reconciliation tooling** — an upgrade step that reports and proposes fixes
   (§5).

Layer 3 is genuinely new and is the load-bearing one, because it is the only
layer that runs on every write regardless of transport.

## 5. Reconciliation

An `arch-repair` upgrade step, following `DefaultSchemataEnsureStep`'s
non-destructive contract (never overwrite operator content):

- Report each conflict: the two profiles, the field, the incompatible types, and
  which (type, specialization) pairs are quarantined as a result.
- Report content-version drift enabled by P4: shipped profile advanced while a
  customisation is based on an older version, with the intervening changes.
- Propose resolutions — rename the attribute, align the type, or unbind the
  profile — as manual instructions. Auto-migration is offered only where the
  resolution is unambiguous (e.g. the operator's file is byte-identical to an
  older shipped version, so advancing it loses nothing).

## 6. Work streams

**Stream P — Registry and resolution.** Registry format with both version tags,
loader, binding declaration, resolution order (P2), conflict classification.

**Stream Q — Failure semantics.** Class A startup validation for attached repos
only (P6); Class B quarantine set computation; the write-boundary gate (layer 3);
typed errors.

**Stream R — Reconciliation.** The upgrade step, content-version drift
detection, proposed resolutions.

**Stream S — Surfaces.** Quarantine state exposed on the schema endpoint (extend
the existing conflicts channel); REST + MCP parity; GUI banner and disabled
submit.

**Stream T — Docs and self-model.** Reference documentation for profile
authoring and the failure semantics; self-model sync.

## 7. Standing checklist verdicts

**Self-model sync: REQUIRED.** Profiles are an ontology-core capability.

**Documentation: REQUIRED.** Profile authoring, binding, versioning, and the
quarantine semantics need reference documentation — the failure behaviour
especially, since an operator meeting a quarantine must be able to act on it.

**Upgrade + repair path: REQUIRED, partly by reuse.** Existing repos have no
registry; its absence is a valid state meaning "no named profiles", so no
migration is needed. `DefaultSchemataEnsureStep` extends to registry-aware
reconciliation (Stream R).

**Backwards compatibility: TOTAL.** Every existing repo resolves identically —
1:1 profiles remain the default (P1), and the registry is optional.

## 8. Acceptance

1. A named profile bound to several (type, specialization) pairs contributes its
   attributes to all of them.
2. Resolution order (P2) holds: specialization-specific overrides shared.
3. Identical redefinition composes silently; incompatible redefinition
   quarantines.
4. Class A in the engagement repo fails startup with an actionable message;
   Class A in an attached enterprise repo logs and the server starts.
5. A quarantined pair rejects creates and edits at the write boundary **through
   every transport** — REST, MCP, and CLI — while other pairs are unaffected.
6. Reads of existing entities in a quarantined pair still work.
7. Unattached repositories are never read or validated.
8. Repos without a registry behave exactly as before (regression).
9. The reconciliation step reports conflicts and version drift, and never
   overwrites operator content.

## 9. Open question

**Q1 — Relationship profiles.** ArchiMate applies profiles to relationships as
well as elements, and `connection-metadata.*` schemata already exist. This plan
covers entity profiles only. Extending named profiles to connections is a natural
follow-on — confirm whether it should be in scope now or deferred.
