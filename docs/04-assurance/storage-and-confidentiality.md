# Storage & Confidentiality

> Reference for how assurance data is stored, encrypted, archived, and accessed.

- [Store vs. archive](#store-vs-archive)
- [Store backends](#store-backends)
- [Archive backends](#archive-backends)
- [Credential storage](#credential-storage)
- [CLI reference](#cli-reference)
- [Key management & backup](#key-management--backup)

Assurance content is encrypted at rest and confidential by default. The architecture model
in git never holds it; the only link is a one-way reference from an assurance entity to an
architecture entity, which is never reverse-persisted into the model.

&nbsp;

## Store vs. archive

Every deployment runs two components in parallel, configured by separate keys.

| Component | Config key | Default | Role |
|---|---|---|---|
| **Store** (`ConfidentialAssuranceStore`) | `store_backend` | `sqlcipher` | Mutable encrypted workspace for live analysis |
| **Archive** (`AssuranceArchive`) | `archive_backend` | `standard` | Append-only, hash-chained evidence trail |

The store is a fully mutable encrypted graph — create hazards, update status, link controls,
delete drafts. Safety analysis evolves, so the store carries no immutability guarantees by
design.

The archive records every significant operation as a hash-chained entry that is never
modified or deleted. Its purpose is regulatory and forensic: proving after the fact what was
known, when, and in what state — the kind of tamper-evident log the EU AI Act (Art. 12)
expects for high-risk AI systems. It runs automatically alongside the store.

Confidentiality is a store concern; immutability is an archive concern. The two are
configured independently, with one exception: `archive_backend: worm` shares the SQLCipher
database file and therefore requires `store_backend: sqlcipher`. The cloud archive backends
write to their own storage and work with any store backend.

&nbsp;

## Store backends

| `store_backend` | Storage | Best for | System dependency |
|---|---|---|---|
| `sqlcipher` (default) | One AES-256 SQLite file at `.arch-assurance/store.db` | Individuals and small teams in one workspace | `libsqlcipher-dev` |
| `private-git` | Fernet-encrypted `.enc` files in a git-trackable tree (history is ciphertext) | Teams wanting file-level encryption with a diffable history | none (Python `cryptography`) |
| `pocketbase` | A [PocketBase](https://pocketbase.io) REST service | Shared team deployments across workstations | a running PocketBase instance |

```bash
arch-assurance init                       # sqlcipher (default)
arch-assurance init --backend private-git
arch-assurance use-backend pocketbase     # then: arch-backend --restart --daemon
```

Switching backends does not migrate data. Run `arch-assurance export -o backup.json` first
if you need to carry entries across.

**SQLCipher WAL mode.** The SQLCipher backend runs in WAL (Write-Ahead Log) mode, which
creates two sidecar files alongside `store.db`: `store.db-wal` and `store.db-shm`. Both files
are encrypted by SQLCipher to the same standard as the main database — no plaintext assurance
content reaches disk in any of the three files. The sidecar files are covered by the
`.arch-assurance/.gitignore` rules and will never appear as untracked files in the repository.

&nbsp;

## Archive backends

| `archive_backend` | Storage | Immutability mechanism | Dependency |
|---|---|---|---|
| `standard` (default) | Co-located with the store | SHA-256 hash chain (software) | none |
| `worm` | SQLCipher (same DB as store) | Hash chain + per-subject AES-256-GCM DEK + legal holds | `store_backend: sqlcipher` |
| `s3-worm` | Amazon S3 | S3 Object Lock (GOVERNANCE / COMPLIANCE) | `boto3`; bucket with Object Lock |
| `azure-blob-worm` | Azure Blob Storage | Container immutability policy | `azure-storage-blob`, `azure-identity` |

`standard` suits most teams: the hash chain detects tampering and store encryption protects
confidentiality. Move to a WORM backend when you need storage-layer enforcement —
cloud-provider guarantees against deletion even by a compromised account, legal holds that
survive key rotation, per-subject crypto-shredding for GDPR erasure, or RFC 3161 timestamp
tokens for non-repudiation.

```bash
# Local WORM (requires the SQLCipher store)
arch-assurance use-backend sqlcipher --archive-backend worm

# AWS S3 Object Lock (independent of store backend)
uv sync --extra s3-archive
export ARCH_S3_BUCKET="my-worm-bucket"          # Object Lock enabled at bucket creation
export ARCH_S3_OBJECT_LOCK_MODE="GOVERNANCE"    # or COMPLIANCE
arch-assurance use-backend sqlcipher --archive-backend s3-worm

# Azure Blob immutability (independent of store backend)
uv sync --extra azure-archive
export ARCH_AZURE_STORAGE_ACCOUNT="myaccount"
export ARCH_AZURE_CONTAINER="arch-assurance"    # immutability policy applied
arch-assurance use-backend sqlcipher --archive-backend azure-blob-worm
```

The `azure-blob-worm` adapter uses two containers: the archive container (WORM) and a mutable
state container holding the chain head, holds index, and DEKs. Apply the time-based
immutability policy to the archive container only.

&nbsp;

## TLP ceiling and withheld content

Every deployment is configured with a **TLP ceiling** — the highest classification that the
backend will expose over REST and MCP interfaces. Nodes, edges, and analyses above the ceiling
are withheld from all read responses; they are not counted, mentioned, or hinted at in any
response body, count, or finding.

The ceiling is set in `config/settings.yaml`:

```yaml
storage:
  assurance:
    max_classification: TLP:AMBER   # TLP:WHITE | TLP:GREEN | TLP:AMBER | TLP:RED
```

`TLP:RED` (the default) exposes everything the store contains — appropriate for a single
operator who holds the encryption key. Lower values let a team see analysis results without
accessing the most sensitive records, for example when RED entries contain unpublished
vulnerability details or PII.

When the ceiling omits records, the GUI shows a **withheld notice** that names the count and
the ceiling: for example *"3 items withheld above your TLP:AMBER ceiling."* This is the policy
working as intended, not an error. The notice appears in the browse view, node detail, and
assurance lens wherever visible counts are lower than the full store total. It does not reveal
the IDs, names, or contents of the withheld items.

&nbsp;

## Credential storage

The encryption key lives in an OS-appropriate credential backend, selected automatically, and
is never written to disk in plaintext.

| Environment | Backend | Notes |
|---|---|---|
| macOS | macOS Keychain | Always available; no setup |
| WSL2 on Windows | Windows DPAPI | Via `powershell.exe`; user-and-machine-scoped |
| Linux desktop | SecretService (D-Bus) | Needs gnome-keyring or kwallet running |
| Headless Linux / CI | Fernet-encrypted vault | Set `ARCH_ASSURANCE_MASTER_PASSWORD` |

```bash
# Headless / CI
export ARCH_ASSURANCE_MASTER_PASSWORD="your-long-random-passphrase"
arch-assurance init
arch-assurance unlock
```

`arch-assurance unlock` has a persistent effect: it verifies the key and sets the
*setup-confirmed* gate in the keychain, which enables auto-unlock in every process and across
restarts. After it, the store opens automatically on every backend start —
`arch-assurance status` reports `unlocked: true`. To reverse it, `arch-assurance lock` clears
the gate (the key stays in the keychain, so `unlock` re-enables access without the recovery
key).

&nbsp;

## CLI reference

| Command | Description |
|---|---|
| `arch-assurance init [--force] [--backend B] [--archive-backend A]` | Create the encrypted store; generate and save the key |
| `arch-assurance unlock` | Verify the key and persistently enable auto-unlock (reports `unlocked: true` thereafter) |
| `arch-assurance lock` | Persistently disable auto-unlock (clears the setup-confirmed gate; key stays in the keychain) |
| `arch-assurance status` | Show backends, DB path, key presence, and unlock state |
| `arch-assurance export-key` | Print the recovery key (store offline) |
| `arch-assurance rotate-key` | Generate a new key and re-encrypt the database |
| `arch-assurance backup [--backup-path P]` | Copy the encrypted DB to a timestamped backup |
| `arch-assurance export -o out.json` | Export all data as plaintext JSON |
| `arch-assurance verify` | Backend-aware chain integrity check (all archive backends) |
| `arch-assurance verify-chain` | Verify the audit hash chain (SQLCipher only) |
| `arch-assurance use-backend B [--archive-backend A]` | Switch store and/or archive backend |
| `arch-assurance import FILE [--replace]` | Restore an exported JSON bundle |
| `arch-assurance seed [--with-signals]` | Load a demo/bootstrap bundle, optionally ingesting signals |
| `arch-assurance export-aibom` | Emit a CycloneDX 1.6 AI-BOM |
| `arch-assurance scan-ai-candidates` | Heuristic scan of entities for AI-BOM relevance |

&nbsp;

## Key management & backup

The recovery key is a separate randomly generated token that can decrypt the database if the
OS credential entry is lost (for example after migrating machines). Print it once after init
and keep it offline:

```bash
arch-assurance export-key
```

Rotate the key when an operator leaves a team, and save the new recovery key:

```bash
arch-assurance rotate-key
arch-assurance export-key
```

Backups are encrypted with the same key as the live database. Keep at least one backup and
the recovery key in separate, durable locations.

---

*Next: [AI-BOM →](aibom.md)*
