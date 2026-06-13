# Attribute Profiles & Frontmatter Schemata

Each repository may carry a `.arch-repo/schemata/` directory of JSON Schema files that extend
or constrain the global ontology for that repo.

```
.arch-repo/schemata/
  attributes.{entity-type}.schema.json   # required/optional fields per entity type
  frontmatter.entity.schema.json          # constraints on entity frontmatter
  frontmatter.outgoing.schema.json        # constraints on connection (outgoing) frontmatter
  frontmatter.diagram.schema.json         # constraints on diagram frontmatter
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

## Promotion superset rule

An engagement repo's schemata must be supersets of the enterprise repo's schemata — every
property and required field in an enterprise schema must also appear in the corresponding
engagement schema. Promotion is blocked, with a per-violation message, when this does not
hold, so a promoted entity always satisfies the enterprise constraints after transfer.

---

*Next: [Document types →](document-types.md)*
