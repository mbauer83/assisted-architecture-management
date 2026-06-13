# Configuration Reference

Two files configure a workspace: `arch-workspace.yaml` declares the repositories;
`config/settings.yaml` configures the backend. Per-repository schemata live in each repo's
`.arch-repo/` directory.

&nbsp;

## `arch-workspace.yaml` — repositories

Single active engagement:

```yaml
engagement:
  local: engagements/ENG-ARCH-REPO/architecture-repository
  # or git: { url: "https://...", branch: main, path: .arch/repos/engagement }

enterprise:
  local: enterprise-repository
  # or git: { url: "https://...", branch: main, path: .arch/repos/enterprise }
```

Multiple engagements with an active selector:

```yaml
engagements:
  active: ENG-ARCH-REPO
  available:
    ENG-ARCH-REPO:
      local: engagements/ENG-ARCH-REPO/architecture-repository
    CLIENT-B:
      git: { url: "git@github.com:your-org/client-b-architecture.git", branch: main, path: ../client-b-architecture }

enterprise:
  local: enterprise-repository
```

`arch-init` resolves this file and writes absolute paths to `.arch/init-state.yaml`, which all
tooling reads on startup. `arch-switch-engagement <name>` updates the active entry and
restarts a running backend. See [CLI & Backend](cli-and-backend.md).

&nbsp;

## `config/settings.yaml` — backend

```yaml
backend:
  port: 8000                  # TCP port (default 8000)
  log_path: .arch/backend.log # workspace-relative if not absolute
  min_log_level: INFO         # DEBUG | INFO | WARNING | ERROR | CRITICAL

diagrams:
  archimate_type_markers: icons   # icons | labels
  sprite_scale: 1.5
  render_dpi: 150
  plantuml_limit_size: 16384

repo_init:
  default_branch: main
  commit_author_name: arch-switch-engagement
  commit_author_email: arch-switch-engagement@local.invalid
  engagement:
    # optional per-repo-kind overrides used by arch-switch-engagement --create
    default_branch: main
    commit_author_name: Architecture Bot
    commit_author_email: architecture-bot@example.com

storage:
  assurance:
    store_backend: sqlcipher              # sqlcipher | private-git | pocketbase
    signals_backend: sqlcipher-colocated  # sqlcipher-colocated | sqlite | encrypted
    archive_backend: standard             # standard | worm | s3-worm | azure-blob-worm
    max_classification: TLP:RED           # TLP:WHITE | TLP:GREEN | TLP:AMBER | TLP:RED
```

These apply globally and are read at startup; they are not configurable via
`arch-workspace.yaml`. The `storage.assurance` keys are written automatically by
`arch-assurance init` and `arch-assurance use-backend` — see
[Assurance: storage & confidentiality](../04-assurance/storage-and-confidentiality.md).

&nbsp;

## Per-repository schemata (`.arch-repo/schemata/`)

```
.arch-repo/schemata/
  attributes.{entity-type}.schema.json
  frontmatter.entity.schema.json
  frontmatter.outgoing.schema.json
  frontmatter.diagram.schema.json
```

These extend or constrain the global ontology per repo. Engagement schemata must be supersets
of enterprise schemata, or promotion is blocked. Full detail in
[Attribute profiles & frontmatter schemata](../05-extensibility/schemata-and-profiles.md).

&nbsp;

## Document types (`.arch-repo/documents/*.json`)

Each file defines one document type — abbreviation, name, subdirectory, frontmatter schema,
required sections, and required/suggested entity links. See
[Document types](../05-extensibility/document-types.md).
