# CLI & Backend Reference

All commands are installed as console scripts by `uv sync` (defined in `pyproject.toml`).

&nbsp;

## Workspace & setup

| Command | Purpose |
|---|---|
| `arch-init` | Resolve `arch-workspace.yaml`, write `.arch/init-state.yaml` |
| `arch-init --initialize-engagement-repo-if-empty` | Scaffold a configured-but-empty engagement git repo |
| `arch-init --initialize-enterprise-repo-if-empty` | Scaffold a configured-but-empty enterprise git repo |
| `get-plantuml` | Download and verify `tools/plantuml.jar` from Maven Central |
| `get-diagram-runtime` | Pull the supported PlantUML + Graphviz runtime |
| `check-diagram-runtime` | Verify Graphviz ≥ 2.49.0 / PlantUML compatibility |

&nbsp;

## Engagement switching

```bash
arch-switch-engagement CLIENT-B                                   # switch active engagement, restart backend
arch-switch-engagement CLIENT-C --url git@github.com:org/c.git    # register a git-backed engagement (clones beside workspace)
arch-switch-engagement CLIENT-D --local ../client-d --create      # scaffold a new local engagement
arch-switch-engagement CLIENT-E --url git@github.com:org/e.git --create   # scaffold + attach origin
```

`--create` scaffolds the standard directory structure (`model/`, `docs/`, `diagram-catalog/`,
`.arch-repo/`), a git repo on the configured branch, an initial commit, and default
frontmatter / attribute-profile / document-type schemata.

&nbsp;

## Backend

```bash
arch-backend --daemon              # serve REST :8000, MCP :8000/mcp/{read,write}; GUI at / if built
arch-backend --status
arch-backend --stop
arch-backend --restart --daemon
```

| Mode | Flag | Effect |
|---|---|---|
| Normal (default) | — | Read/write engagement; enterprise read-only via promotion |
| Admin | `--admin-mode` | Direct enterprise writes via GUI/REST; GUI shows a banner |
| Read-only | `--read-only` | All writes blocked globally; MCP write server rejects mutations |

`--daemon` starts a detached session, redirects stdin from `/dev/null`, and writes to
`backend.log_path`. `arch-backend &` also works and detaches stdin when it detects a
background TTY job, but `--daemon` is the preferred operational form.

&nbsp;

## Repository maintenance

`arch-repair` has two subcommands. The legacy no-subcommand invocation (the flat
`--repo-root`/`--repair-branch`/`--confirm` form) is a **deprecated alias for
`git-repair`** for one release — it still works, prints a deprecation notice on
stderr, and will be removed once that release ships.

```bash
arch-repair git-repair --repo-root <path> --confirm    # guarded, resumable git repair
arch-repair upgrade --repo-root <path>                  # dry-run report (default; never mutates)
arch-repair upgrade --repo-root <path> --commit         # apply
```

**`arch-repair upgrade`** detects and (with `--commit`) applies persisted-format
migrations — version-aware, self-detecting, idempotent. A repo already on the
current format is a true no-op: no writes, no index rebuild, no
`.arch-repo/config.yaml` change, so it is safe to run unconditionally (the
[Docker Compose deployment](docker-compose.md#operations) runs it before every
backend start).

| Flag | Effect |
|---|---|
| `--repo-root <path>` | Repeatable; one or more repo roots to evaluate/upgrade |
| `--workspace <path>` | Resolve engagement + enterprise roots from `arch-init` state instead |
| `--commit` | Apply findings (default: dry-run report only) |
| `--json` | Emit the stable machine-readable report contract instead of human output |

Each repo root is evaluated/applied independently; findings and applied-step
ids are reported per root plus one aggregate summary for `--workspace` runs.

`--commit`, in order:

1. **Backend-not-serving — the only hard, non-overridable gate.** Probes
   `GET /api/backend-identity` on the configured backend port. A backend that
   responds but predates this endpoint fails closed — assume it might be
   serving the target repo. A backend serving an *unrelated* repo never
   blocks. This is the actual consistency invariant: two writers touching the
   same files.
2. **Stale temp-file sweep.** Removes orphaned atomic-write temp files a
   previous, killed run may have left behind.
3. **Transaction recovery.** Runs the same idempotent `recover_transactions`
   the backend itself runs at startup, so upgrade steps always see a
   consistent repo regardless of git-sync/promotion history.
4. **Applies.** Git status is deliberately *not* a gate — an out-of-date,
   actively-used repo routinely has uncommitted edits to the very files that
   need migrating, and every step reads whatever is on disk right now and
   carries it into the rewrite, so an uncommitted edit is never lost or
   clobbered regardless of git state. When a touched file does have an
   uncommitted local edit, `--commit` prints an informational note (which
   files) so the operator knows to review the combined diff before
   committing — it never refuses.

Resumability: every step's `detect()` re-derives its finding from actual repo
content, never from the `applied_upgrade_steps` stamp in `.arch-repo/config.yaml`
— the stamp is reporting metadata only. Combined with atomic (temp-file +
rename) writes and per-step/per-repo failure isolation, `--commit` may be
interrupted at any point (killed process, crash, power loss) and safely
re-run from scratch.

On success, each repo's `.arch-repo/config.yaml` records `format_contract_version`
and the applied step ids (`applied_upgrade_steps`) — metadata only; detection
always stays probe-based against real content, so a hand-edited or stale stamp
self-heals on the next run rather than causing incorrect skips.

**Supported floor.** `arch-repair upgrade` covers format changes introduced by
the ArchiMate-4-compliance effort (and its successors) forward — not this
project's full history, most of which predates any migration tooling at all.
Every report (human output and the `coverage_note` field in `--json`) states
this explicitly: **a clean report means "no known issues," never "fully
current."** The registered `unrecognized-structure-scan` step exists
specifically to narrow that gap without overclaiming — it flags frontmatter
that matches neither a current shape nor any other registered step's known
legacy pattern (missing/unrecognized `artifact-type`, malformed frontmatter)
as an always-manual, low-confidence finding, so an old or drifted repo's
report is honestly incomplete-looking rather than falsely clean. It never
attempts a rewrite. Closing a gap this step (or any other) can only flag,
not fix, means either writing a new step once the shape is understood, or
manual repair via the ordinary MCP write tools.

&nbsp;

## Model exchange

`arch-exchange` imports and exports C19C v3.1 model-exchange documents (the Open Group's
ArchiMate 3.x XML interchange format). Import applies the ArchiMate 4 migration table —
layer-specific 3.x types (`BusinessService`, `ApplicationProcess`, …) map to the ArchiMate 4
base type plus a specialization; composition is always preserved as composition, never
downgraded to association even when a relationship type turns out not to be permitted
between the resolved entity types (that case is reported, not silently substituted). Export
inverts the table: a specialized entity/connection exports as its native 3.x concrete type
where one exists, or as a compatible extension property (`archrepo-specialization`) on the
closest native type where it doesn't (e.g. `application-component`'s `module`/`service`/
`endpoint` specializations, which have no 3.x equivalent). Both directions go through the
ordinary `artifact_write` layer — the same validation the GUI/MCP use, never raw file
emission.

```sh
arch-exchange import --source model.xml --repo <path>              # dry-run report (default)
arch-exchange import --source model.xml --repo <path> --commit      # apply
arch-exchange import --source model.xml --repo <path> --commit --schema archimate3_Model.xsd
arch-exchange export --out model.xml --repo <path>                  # every entity in the repo
arch-exchange export --out model.xml --repo <path> --scope <id> <id> # a specific scope
```

**Import** is dry-run by default (`--commit` to write); `--repo` defaults to the workspace's
engagement repo. Re-importing the same document updates previously-imported entities
instead of duplicating them (a repo-local `.arch-repo/exchange-identity.json` sidecar, not a
frontmatter field, tracks the mapping — gitignored, since it is a local operational cache,
not a repository artifact). `--schema` points at a locally-fetched C19C XSD for
schema-validated import; it is a dev/test convenience only — the schema itself is
Open-Group-licensed and, like the ArchiMate 4 specification text, is never committed to
this repository.

**Export** defaults to every entity in the repo; `--scope` restricts it to the given
artifact ids (and every connection between two entities in that scope). Every unmapped or
out-of-scope item on either side is reported by kind and reason — never silently dropped.

&nbsp;

## Guidance import

`arch-import-guidance` fetches or reads a licensed `create_when`/`never_create_when`
guidance document and imports it into **one deployment-level cache**,
`~/.config/arch-repo/guidance-cache/` — never into a repository, and never split by
engagement/enterprise tier. Guidance is a deployment concern, not per-repo state: one running
instance of this software pulls one guidance source, applied to whichever repos it serves.

```sh
arch-import-guidance --source guidance.yaml                      # dry-run report (default)
arch-import-guidance --source guidance.yaml --dry-run            # explicit dry-run
arch-import-guidance --source https://example.org/guidance.yaml  # HTTPS fetch, then writes the cache
arch-import-guidance --source guidance.yaml --module archimate_4 # import only this module alias
arch-import-guidance --source guidance.yaml --strict             # abort on any unknown key instead of dropping it
```

Writes `<alias>.guidance.yaml` (the filtered, matched document) plus a provenance sidecar
`<alias>.guidance.meta.yaml` (source, SHA-256, format version, matched/unmatched counts) per
imported module alias. `--allow-http` permits a plain-HTTP source (HTTPS is required by
default). Restart the backend to pick up a newly imported cache. See [Ontology modules →
Guidance externalization](../05-extensibility/ontology-modules.md#guidance-externalization-license-compliance)
for the full precedence and empty-state behavior.

&nbsp;

## Other entry points

| Command | Purpose |
|---|---|
| `arch-mcp-stdio-read` / `arch-mcp-stdio-write` | Architecture MCP servers (stdio bridges) |
| `arch-mcp-stdio-assurance-read` / `arch-mcp-stdio-assurance-write` | Assurance MCP servers |
| `arch-write-cli` | Command-line authoring against the write pipeline |
| `arch-assurance …` | Assurance store/archive management — see [Assurance CLI](../04-assurance/storage-and-confidentiality.md#cli-reference) |

&nbsp;

## Deprecations

**ArchiMate connection "cardinality" → "multiplicity" (this release).** Persisted field
and annotation names were renamed for ArchiMate 4 terminology alignment:
`src_cardinality`/`tgt_cardinality` → `src_multiplicity`/`tgt_multiplicity` (REST/MCP
payloads, generated types), and the diagram frontmatter `diagram_connections[]` opt-in key
`include_cardinality` → `include_multiplicity`. There is no runtime backward-compatibility
code for these names — application code reads only the new names. A diagram authored
before this release whose `diagram_connections[]` entry still uses `include_cardinality`
simply stops rendering that connection's multiplicity annotation (non-destructive; every
other opt-in key on the entry keeps working) until migrated. Migration is via
`arch-repair upgrade` (registered step id `d9-multiplicity-rename`, dry-run by default,
`--commit` to apply) — it rewrites only the `include_cardinality` mapping key in place
(diagrams are `.puml` files with embedded YAML frontmatter for most diagram types,
`.md` for matrix-type diagrams; the step scans both), leaving every other line — including
any uncommitted edit — byte-for-byte untouched. The diagram-type-internal
`cardinality_min`/`cardinality_max` participation config is a separate, unrelated concept
and keeps its name.

&nbsp;

## Troubleshooting

If the GUI hangs on "Loading...", diagnose the transport before assuming a lock:

```bash
arch-backend --status
curl --max-time 5 http://127.0.0.1:8000/api/stats
curl --max-time 5 http://127.0.0.1:5173/api/stats   # if using the Vite dev server
tail -n 100 .arch/backend.log                        # or the configured backend.log_path
```

If `--status` reports `process state: T`, the backend is stopped while still holding the
port. Recover with:

```bash
arch-backend --stop
arch-backend --daemon
```
