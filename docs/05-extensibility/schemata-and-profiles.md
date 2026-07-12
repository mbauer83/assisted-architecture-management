# Attribute Profiles & Frontmatter Schemata

Each repository may carry a `.arch-repo/schemata/` directory of JSON Schema files that extend
or constrain the global ontology for that repo.

```
.arch-repo/schemata/
  attributes.{entity-type}.schema.json                    # base attribute schema per entity type
  attributes.{entity-type}.{specialization-slug}.schema.json  # attached to one specialization
  frontmatter.entity.schema.json                          # constraints on entity frontmatter
  frontmatter.outgoing.schema.json                        # constraints on connection (outgoing) frontmatter
  frontmatter.diagram.schema.json                         # constraints on diagram frontmatter
  connection-metadata.{connection-type}.schema.json       # per-connection metadata block, per type
```

&nbsp;

## Attribute profiles

`attributes.{type}.schema.json` constrains the `properties:` section of entities of that
type. The `required` list enforces mandatory fields; `properties` declares their types and
allowed values. The GUI renders these as type-specific form fields and validates them on
write; an agent receives the same constraints as structured data before authoring.

For example, requiring a `rationale` and a `priority` enum on every `principle`:

```json
{
  "type": "object",
  "required": ["rationale", "priority"],
  "properties": {
    "rationale": { "type": "string" },
    "priority":  { "type": "string", "enum": ["Must", "Should", "Could", "Won't"] }
  }
}
```

&nbsp;

## Frontmatter schemata

`frontmatter.{entity|outgoing|diagram}.schema.json` constrains the YAML frontmatter fields
common to all entities, connections, or diagrams in the repo — the metadata layer above each
artifact's type-specific properties. These are **extend-only**: a repo may add fields and
tighten constraints, and the verifier checks every write against them.

&nbsp;

## Profiles are one-to-one with their specialization

A `ProfileDefinition` is a compiled, typed attribute set — slug, name, applicable entity
types, and attributes each with a `required | recommended | optional` level and an optional
default. A profile is **never independently reusable or named by reference**: it is either
the *default* (base-type) profile for unspecialized elements — today's on-disk
`attributes.{type}.schema.json`, unchanged — or it belongs to exactly one specialization,
compiled from that specialization's own declaration. Existence-dependence settles the
direction: a profile can't exist without its specialization, so specialization *contains*
profile, not the other way around and not a peer/associated pair (an earlier design had a
separate, named `.arch-repo/profiles.yaml` reusable across specializations; it was replaced
once this asymmetry was recognized).

A specialization (see [Ontology modules](ontology-modules.md#specializations)) attaches
attribute constraints via either of two mechanisms — both already 1:1 with that
specialization by construction:

- **Inline** `attributes: {}` on the specialization's own declaration, compiled to an
  anonymous profile.
- **A dedicated attachment file**, `attributes.{entity-type}.{specialization-slug}.schema.json`
  — a standalone JSON Schema, filename-scoped to that one slug.

Each compiles to a JSON Schema fragment (`required` for `required`-level attributes, the
extension keyword `x-recommended` for `recommended`-level ones — JSON Schema has no native
"recommended", so the verifier checks it explicitly rather than relying on `jsonschema`
itself).

An entity's **effective attribute schema** is the base-type schema merged with its own
specialization's contribution (an entity carries at most one specialization). A property
redefined incompatibly between the two (same name, different `type`) is a blocking error;
any other redefinition (e.g. a different `default`) resolves last-writer-wins. An
attachment file whose `{specialization-slug}` segment names no specialization declared for
that entity type is a verifier warning (orphaned attachment) rather than silently ignored.

&nbsp;

## Connection metadata schemata

`connection-metadata.{connection-type}.schema.json` constrains the per-connection metadata
block — the fenced YAML block immediately under a connection's `### ` heading in an
`.outgoing.md` file, distinct from the file's shared frontmatter. Today the only field
written there is `specialization` (see [Ontology
modules](ontology-modules.md#specializations)); the convention is open to future
per-connection metadata, validated the same way. Like the other schemata here, this one is
opt-in per connection type — absent a schema file, the metadata block validates freely.

&nbsp;

## Promotion superset rule

An engagement repo's schemata must be supersets of the enterprise repo's schemata — every
property and required field in an enterprise schema must also appear in the corresponding
engagement schema. Promotion is blocked, with a per-violation message, when this does not
hold, so a promoted entity always satisfies the enterprise constraints after transfer.

---

*Next: [Document types →](document-types.md)*
