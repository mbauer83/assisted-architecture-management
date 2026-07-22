# Upgrading a Deployment

Operator guide for `arch-repair upgrade`: bringing repositories and a deployment's
operational data (settings, guidance cache, signal stores, the assurance store) from an
older persisted format to the current one. For command syntax, flags, and exit codes,
see the [CLI reference](cli-and-backend.md#repository-maintenance); this page covers
how to run an upgrade safely and what the reports mean.

- [What gets upgraded](#what-gets-upgraded)
- [Check first, then commit](#check-first-then-commit)
- [Deployment identity — how targets are discovered](#deployment-identity--how-targets-are-discovered)
- [Credentials and locked stores](#credentials-and-locked-stores)
- [Back up before committing](#back-up-before-committing)
- [What `--commit` does, in order](#what---commit-does-in-order)
- [Quarantine and blocking findings](#quarantine-and-blocking-findings)
- [Partial completion and resuming](#partial-completion-and-resuming)
- [Docker: upgrade before serving](#docker-upgrade-before-serving)
- [Reading a report](#reading-a-report)
- [What a clean report does and does not mean](#what-a-clean-report-does-and-does-not-mean)

&nbsp;

## What gets upgraded

An upgrade run evaluates **targets**. Repositories are always in scope; operational
targets are discovered only when the run has a deployment identity (next section):

| Target kind | What it is | Typical migration |
|---|---|---|
| Repository | An engagement or enterprise architecture repo | Frontmatter/format rewrites, e.g. renamed keys |
| Deployment settings | The operator-owned `settings.yaml` | Legacy value migration (e.g. the `signals_backend: encrypted` alias) |
| Guidance cache | The imported authoring-guidance cache | Format-version patch; a re-import from the licensed source is recommended to gain content newer formats carry |
| Public signals SQLite | The unencrypted security-signals database | Schema migrations; legacy-row quarantine (administrative only) |
| SQLCipher assurance store | The encrypted assurance/signals store | Transactional schema migrations (requires the store credential) |

Each target is one atomic unit — databases migrate in one transaction, text files by
atomic replace. There is deliberately **no cross-target atomicity**: targets commit in
a deterministic order, and a failure partway leaves earlier targets committed (see
[resuming](#partial-completion-and-resuming)).

&nbsp;

## Check first, then commit

The default invocation is a **dry run** — it never mutates anything and always exits `0`;
findings, blockers, and credential-uninspectable targets are report states, not errors:

```bash
arch-repair upgrade --repo-root <path>            # inspect one repo
arch-repair upgrade --workspace <path>            # inspect the workspace's repos
arch-repair upgrade --deployment-root <path>      # inspect repos + operational targets
arch-repair upgrade ... --json                    # machine-readable report
arch-repair upgrade ... --commit                  # apply
```

Read the dry-run report, resolve anything it marks blocking or manual, back up
(below), then re-run with `--commit`. A deployment already on the current format is a
true no-op under `--commit`: no writes, no index rebuild, no config change — safe to
run unconditionally.

&nbsp;

## Deployment identity — how targets are discovered

Without an explicit deployment identity, the command touches **repositories only** —
`--workspace` alone can never reach a guidance cache or a signal store, so a test
workspace cannot accidentally migrate your real deployment's data.

Operational targets are discovered when the run identifies its deployment through one
of (first hit wins):

1. `--settings <path>` — the operator-owned settings document, explicitly;
2. `--deployment-root <path>` — the directory whose `settings.yaml` is the settings
   document;
3. the `ARCH_SETTINGS_PATH` environment variable (the Docker entrypoint sets this to
   the container's live settings file).

The source-tree `config/settings.yaml` fallback is read-only and never a migration
target; if operational migrations are pending and only that fallback is selected, the
report carries a blocking "no operator-owned deployment settings" finding with
instructions to create one under the deployment root.

Individual operational paths can be overridden within an identified deployment
(`--guidance-cache`, `--signals-db`, `--assurance-store`), and
`--exclude-target <kind>` skips one target kind for an operator-run partial command —
the report then states that deployment readiness is **not** certified.

&nbsp;

## Credentials and locked stores

Only the SQLCipher assurance store requires a credential. A locked store whose schema
version cannot be read is a **blocking unresolved migration** (exit `3` under
`--commit`) — it is never assumed current. Provide the credential through the
non-interactive secret path — the OS keychain, or the
`ARCH_ASSURANCE_MASTER_PASSWORD`-protected vault on headless hosts — and re-run. Keys
never appear in reports or logs.

&nbsp;

## Back up before committing

| Target kind | Backup | Recovery |
|---|---|---|
| Repository | Commit or branch the repo (the CLI recommends this) | Re-run `--commit`; steps are idempotent and self-healing |
| Guidance cache (`~/.config/arch-repo/guidance-cache/` or deployment-scoped) | Copy the directory | Restore the copy, or re-import from the licensed source with `arch-import-guidance` |
| Public signals SQLite | Copy the `.db` file | Restore the copy and re-run; quarantined legacy rows stay inspectable via the admin surface |
| SQLCipher assurance store | `arch-assurance backup` (encrypted copy) | Restore the backup; the key stays in the OS keychain/vault |
| Deployment settings document | Copy the YAML file | Restore the copy; rewrites are atomic and byte-preserving outside the changed key |

&nbsp;

## What `--commit` does, in order

1. **Backend-not-serving — the only hard, non-overridable gate.** Probes
   `GET /api/backend-identity` on the configured backend port. A backend that responds
   but predates this endpoint fails closed — assume it might be serving the target
   repo. A backend serving an *unrelated* repo never blocks. This is the actual
   consistency invariant: two writers must not touch the same files.
2. **Stale temp-file sweep.** Removes orphaned atomic-write temp files a previous,
   killed run may have left behind.
3. **Transaction recovery.** Runs the same idempotent recovery the backend itself runs
   at startup, so upgrade steps always see a consistent repo regardless of
   git-sync/promotion history.
4. **Applies.** Git status is deliberately *not* a gate — an out-of-date, actively-used
   repo routinely has uncommitted edits to the very files that need migrating. Every
   step reads whatever is on disk right now and carries it into the rewrite, so an
   uncommitted edit is never lost or clobbered regardless of git state. When a touched
   file does have an uncommitted local edit, `--commit` prints an informational note
   naming the files so you know to review the combined diff before committing — it
   never refuses.

On success, each repo's `.arch-repo/config.yaml` records `format_contract_version` and
the applied step ids. These stamps are reporting metadata only: detection always
re-probes real content, so a hand-edited or stale stamp self-heals on the next run
rather than causing an incorrect skip.

&nbsp;

## Quarantine and blocking findings

Some findings are never auto-applied:

- **Legacy rows in the public signals database:** rows classified TLP:WHITE are moved
  to a quarantine area inside the same file (administrative migration — inspectable,
  reversible, nothing deleted). Any row **above** TLP:WHITE in the public file is a
  blocking finding: the commit writes nothing to that target, the report carries only
  table/primary-key metadata (never the payload), and the manual instructions offer a
  secure import into the co-located encrypted store or an explicitly verified
  purge/retirement. Confidential data is never left in, or written to, an unencrypted
  file by this tool.
- **`signals_backend: encrypted`** is a legacy settings alias. The migration rewrites
  it to the explicit `sqlcipher-colocated`; where a settings combination would lose a
  capability, the report raises an explicit finding for an owner decision instead of
  changing behavior silently.
- **Unknown, newer, or malformed formats** (e.g. a guidance cache written by a newer
  version) block with a manual finding rather than risking a partial rewrite.
  Downgrades are explicitly unsupported — older software fails clearly on newer
  formats rather than dropping fields.

&nbsp;

## Partial completion and resuming

`--commit` may be interrupted at any point — killed process, crash, power loss — and
safely re-run from scratch. Every step re-derives its finding from actual content, and
writes are atomic (temp file + rename), so a re-run picks up exactly the remaining
work. A run that fails after an earlier target committed exits `20` with an exact
partial report; re-running resumes from real state. Exit `21` means an
infrastructure or credential failure before anything was committed.

&nbsp;

## Docker: upgrade before serving

The container entrypoint runs `arch-repair upgrade --commit` against the resolved
workspace **before starting the backend** — so the backend-not-serving gate always
passes (this is the process about to start that backend), and a current deployment
boots with zero writes. The entrypoint exports `ARCH_SETTINGS_PATH` pointing at the
container's live settings file, giving the run its deployment identity; a configured
active target is never excluded. The exit mapping is strict — the container **halts
with the report** instead of serving on stale formats:

| `arch-repair upgrade` exit | Entrypoint behavior |
|---|---|
| `0` | Proceed to serve |
| `1` repository step errors | Halt |
| `3` unresolved blocking migration (nothing written) | Halt — resolve the listed choices |
| `20` partial apply | Halt — re-run (restart) to resume |
| `21` infrastructure failure before any commit | Halt |

Set `ARCH_REPAIR_UPGRADE=false` to skip the startup upgrade and run it manually
instead. See [Docker Compose deployment](docker-compose.md#operations).

&nbsp;

## Reading a report

A dry run against a deployment one release behind (an outdated guidance cache and a
public signals database on the previous schema) produces a report like this
(`--json`; paths shortened):

```json
{
  "report_schema_version": "1",
  "outcome": "success",
  "repos": [],
  "deployment_preflight": {
    "operator_owned": true,
    "settings_document": "/srv/arch/settings.yaml",
    "settings_source": "deployment_root_default",
    "pre_existing_repairs": [],
    "notes": []
  },
  "operational_targets": [
    {
      "kind": "guidance_cache",
      "display_location": "/srv/arch/guidance-cache",
      "state": "pending",
      "current_version": 1,
      "credential_requirement": "none",
      "committed": false,
      "findings": [
        {
          "step_id": "guidance-0002-format-v2",
          "finding_id": "guidance-format-outdated:core.guidance.yaml",
          "severity": "warning",
          "auto_migratable": true,
          "outcome": "skipped",
          "description": "core.guidance.yaml: guidance_format 1; the current format is 2",
          "rewrite_summary": "patch the guidance_format header to 2; re-import the guidance source to populate broader-level (domain) context"
        }
      ]
    },
    {
      "kind": "signals_sqlite",
      "display_location": "/srv/arch/.arch-assurance/security-signals.db",
      "state": "pending",
      "current_version": 1,
      "credential_requirement": "none",
      "committed": false,
      "findings": [
        {
          "step_id": "signals-0002-signal-snapshot-schema-public",
          "finding_id": "signals-schema-outdated",
          "severity": "warning",
          "auto_migratable": true,
          "outcome": "skipped",
          "description": "security-signals schema is at version 1; version 2 adds the signal-snapshot aggregate",
          "rewrite_summary": "apply the ordered signals migrations (signal-snapshot tables + version stamp)"
        }
      ]
    },
    {
      "kind": "deployment_settings",
      "display_location": "/srv/arch/settings.yaml",
      "state": "current",
      "credential_requirement": "none",
      "committed": false,
      "findings": []
    }
  ]
}
```

How to read it: each operational target reports its `state` (`current` needs nothing;
`pending` has findings), each finding says whether it is `auto_migratable` (applied by
`--commit`) or carries `manual_instructions`, and in a dry run every finding's
`outcome` is `skipped` — nothing was written. `deployment_preflight.operator_owned`
confirms the settings document is a real migration target, not the read-only
source-tree fallback. After a successful `--commit`, the same targets report
`committed: true` and the applied outcomes.

&nbsp;

## What a clean report does and does not mean

The upgrade tool covers known format changes from the point migration tooling was
introduced, forward — not every shape a very old repository might contain. Every
report states this (`coverage_note` in `--json`): **a clean report means "no known
issues," never "fully current."** A dedicated scan step flags frontmatter that matches
neither a current shape nor any known legacy pattern as an always-manual,
low-confidence finding — so an old or drifted repo's report looks honestly incomplete
rather than falsely clean. That step never rewrites anything; closing such a gap means
a new migration once the shape is understood, or manual repair through the ordinary
authoring tools.

---

*See also: [CLI & backend](cli-and-backend.md) · [Docker Compose deployment](docker-compose.md) · [Configuration](configuration.md)*
