# Authoring Guidance

Authoring guidance is the per-concept "create when / never create when" text that the
GUI wizard, entity forms, and the `artifact_authoring_guidance` MCP tool serve while you
model: what a concept is for, when to create one, and when something else is the better
fit. This page covers where guidance comes from, how it is layered along a module's
concept hierarchy, and how to import it.

&nbsp;

## Why guidance is imported, not bundled

The `archimate_4` module ships its `create_when`/`never_create_when` slots **empty** —
the authored guidance text derives from licensed material and lives outside this
repository, never committed (the same rule that keeps the ArchiMate specification text
out of git). Until an import has run, the guidance surfaces do not fall silent:
`artifact_authoring_guidance` (MCP) and `GET /api/authoring-guidance` (REST) return
`guidance_status: "empty"` plus a `guidance_hint` naming the import command, and the GUI
modeling wizard shows the same hint — never a blank string that could be misread as "no
restrictions apply".

&nbsp;

## Layered guidance: the hierarchy

Guidance attaches to any level a module declares, and is **composed additively along the
concept's ancestry** when authoring support is served. Each module declares its own
ordered levels; for `archimate_4` they are:

```
domain  →  entity type  →  specialization
```

Asking for guidance on, say, an `application-component` with the `service`
specialization serves the specialization's guidance *plus* its ancestors' context — the
entity type's and the application domain's — so the broad modeling intent frames the
specific rule. Wherever type guidance appears in the GUI (the wizard, entity create/edit
forms), the broader-level context renders above it as clearly labeled, collapsible
sections, so it informs without crowding out the form.

The level declaration is owned by the module's ontology, never by a guidance document —
a document cannot invent levels, and validation (unknown level, missing parent, cycle)
happens at import time, not as a runtime surprise.

&nbsp;

## The guidance document format

A guidance document is YAML with a `guidance_format` version header. The current format
is **2**:

- the two leaf levels keep the flat maps (`entity_types:`, `connection_types:`) —
  a format-1 document's shape is unchanged there;
- broader levels are keyed by their level id (for `archimate_4`: `domain:`), carrying
  the per-node context text that composes above leaf guidance.

A format-1 document still imports; it simply carries no broader-level context. The
upgrade tool patches a cached format-1 document's header and recommends re-importing
from the source to gain the domain-level content — see the
[upgrade guide](../reference/upgrade-guide.md).

&nbsp;

## Importing

```sh
arch-import-guidance --source guidance.yaml                      # dry-run report (default)
arch-import-guidance --source https://example.org/guidance.yaml  # HTTPS fetch, then write
arch-import-guidance --source guidance.yaml --module archimate_4 # only this module alias
arch-import-guidance --source guidance.yaml --strict             # abort on any unknown key
```

The importer validates the document against the registered module, its declared levels,
and the specialization catalog, then writes one **deployment-level cache** —
`~/.config/arch-repo/guidance-cache/<alias>.guidance.yaml` plus a provenance sidecar
`<alias>.guidance.meta.yaml` (source, SHA-256, format version, matched/unmatched
counts). Guidance is a deployment concern, not a per-repository one: one running
instance imports one guidance source, applied to whichever repos it serves — never
split by engagement/enterprise tier, and never committed to either repo. `--allow-http`
permits a plain-HTTP source (HTTPS is required by default). Restart the backend to pick
up a newly imported cache.

**Precedence:** module-inline guidance (empty by default) < the imported deployment
cache. Committed repository declarations are never overridden by guidance.

There is no default `--source` yet: `guidance.default_source` in `config/settings.yaml`
stays empty until a hosting location for the published guidance document exists, so
every import names its source explicitly.

&nbsp;

## Guidance and attribute schemata

Guidance says *when* to create a concept; attribute profiles and frontmatter schemata
say *what shape* it has — including the attributes a specialization contributes. The two
meet in the GUI forms: guidance text above, typed attribute fields below. See
[Attribute profiles & frontmatter schemata](schemata-and-profiles.md).

---

*See also: [Ontology modules](ontology-modules.md) · [CLI & backend → Guidance import](../reference/cli-and-backend.md#guidance-import)*
