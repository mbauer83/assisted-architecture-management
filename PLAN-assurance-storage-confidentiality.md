# PLAN — Assurance Storage: Pluggability & Confidentiality (software changes)

> **What this is.** The concrete **software changes** surfaced reviewing the assurance architecture
> (`PLAN-assurance-architecture-model.md` §1.1; `PLAN-assurance-stpa-grc.md` §27.4). It does **not** change
> the architecture *model*; it closes the gap between the design ("Pluggable, Confidential Assurance
> Storage") and the shipped code.
>
> **Origin decisions (authoritative):** `PLAN-assurance-stpa-grc.md` §27.4 [RESOLVED 2026-06-05] + the
> pluggable-storage requirement. **Status:** draft 2026-06-05. Assurance build Phases 0–6 are done; these
> **refine the storage layer / Phase 5**, not core-capability blockers.
>
> **No backward-compat shims; existing content keeps working.** Pre-release ⇒ **no** backward-compatible code
> paths / dual-format readers (clean cutover). The only content that exists is the **architecture repos** — git
> source files with a derived, disposable read-model → they **re-index automatically** (no data migration; SC-5
> verifies). **No assurance store/signals content exists yet** (`.arch-assurance/` absent — confirmed), so
> SC-2/SC-3 just create clean. See the **Migration inventory** (§6).
>
> **Progress (update as you go — ☐ todo · ◐ wip · ☑ done):**
>
> | Change | Summary | Status |
> |---|---|---|
> | SC-1 | Shared `storage:` config + per-context factory + port-typed accessors | ☑ |
> | SC-2 | Confidential signals storage + TLP + minimisation | ☐ |
> | SC-3 | Encrypted private-git store adapter | ☐ |
> | SC-4 | MCP max-classification + exposure logging | ☐ |
> | SC-5 | Read-model composition root aligned (single backend kept) | ☐ |

## 1. Business context & why now

Assurance content is **sensitive analytical data**: hazards, loss scenarios, and especially an **SBOM of our
own system** (root component name+version, full dependency composition, vulnerabilities, mappings to our
named architecture entities) form an **attack-surface map**. The platform's audience is personal projects and
SMBs with no dedicated secure tooling, where **convenience is a security property** — so confidentiality must
be the *default*, configurable per deployment (personal → team → regulated), and regulation (EU AI Act / CRA)
expects controlled, traceable handling. **Why now:** the shipped code does **not** match the stated design —
signals are stored in plaintext, the alternative store backends are unreachable, and there is no
max-classification at the AI boundary. That is a **false-confidence risk** (users believe assurance data is
confidential when it is not), not a cosmetic gap. These changes make the design real.

## 2. Problem statement (verified in code)

1. **Adapter selection is hardcoded.** `assurance_mcp/context.py` builds `SQLCipherAssuranceStore` +
   `SQLCipherAssuranceArchive` + `SQLiteSecurityConnector` directly and types accessors as the **concrete
   classes**, not the ports. PocketBase / private-git store adapters exist but are **unreachable at runtime**.
   Only `ARCH_ASSURANCE_DB_PATH` / `ARCH_SECURITY_SIGNALS_DB_PATH` *path* overrides exist — no backend config.
   *Coupling to mind:* `context.py:45` wires the archive as `SQLCipherAssuranceArchive(lambda: store._conn)` —
   the archive **shares the store's private `_conn`**.
2. **Security signals stored unencrypted & unclassified.** `_security_connector.py` →
   `.arch-assurance/security-signals.db` is plain `sqlite3`; `_schema.py SECURITY_SIGNALS_SCHEMA_SQL` has
   **no TLP** on `bom_ingests`/`bom_components`/`vulnerabilities`/`anchor_mappings` — yet this is the
   attack-surface map above (§1).
3. **private-git is plain JSON.** `_private_git_store.py` writes unencrypted JSON; an encrypted variant is
   viable because the read model is built **in-memory on startup** (decrypt-on-load preserves queryability).
4. **No MCP max-classification.** No max-classification / redaction / exposure-logging exists anywhere
   (`grep` empty); store nodes default to `TLP:WHITE`. §27.4 presupposes signals are "subject to MCP
   max-classification" — that control must exist for "confidential by default" to hold at the AI boundary.

## 3. Strategy (cross-cutting decision — Option B, YAGNI-scoped, decided 2026-06-05)

Unify the *composition-root pattern and config location*, **not** the interfaces or a universal factory:
- **Shared `storage:` config namespace** (`config/settings.yaml` + `settings.py` loader), per-context
  subsections (`storage.assurance`, `storage.read_model`, …), consistent with the existing `modules:` pattern.
- **Per-context factories** read their slice and return **port-typed** instances behind a shared accessor
  **keyed by workspace/mounts**. Pattern shared; each context keeps its own ports.
- **Multi-backend selection only where backends exist (assurance).** The read-model keeps its **single
  SQLite + CoW backend** — **no DuckDB** (rejected: FTS needs a full rebuild on any change), **no
  multi-backend factory**; it only gains a port-typed accessor + the config seam (SC-5).
- **Interfaces stay separate:** `ArtifactStorePort` (rich query/CoW) ≠ `ConfidentialAssuranceStore`
  (CRUD + unlock + TLP). No generic `StoragePort`.
- **Cross-pollination:** the assurance factory adopts the read-model's *keyed-by-workspace* singleton
  (`get_shared_index`) instead of a single `lru_cache`.

## 4. Changes

### SC-1 — Shared `storage:` config + per-context factory + port-typed accessors
**Goal:** backend + confidentiality posture become per-deployment choices behind the ports; establish the
shared convention. **Default config = clean sensible defaults: SQLCipher store + confidential co-located signals.**
- [ ] Add the `storage:` namespace to `settings.py`/`settings.yaml` (this PR seeds `storage.assurance`):
      `store_backend: sqlcipher|pocketbase|private-git`, `signals_backend: sqlcipher-colocated|sqlite|encrypted`.
      Keep env *path* overrides. **Unknown/unsupported backend ⇒ startup error (fail-closed).**
- [ ] `src/infrastructure/assurance/store_factory.py`: build the configured store/archive/connector
      **typed as ports**, **keyed by workspace** (mirror `get_shared_index`). The factory **encapsulates the
      store↔archive connection sharing** internally (no `_conn` leak through the ports).
- [ ] Promote `is_unlocked()` onto `ConfidentialAssuranceStore`; each adapter implements it; integrate with
      `capability.py` gating so `is_available()` is adapter-agnostic.
- [ ] Rework `context.py` to call the factory; accessor return types = **ports**.
- [ ] `arch-assurance status` reports active store + signals backends.
- [ ] **CLI setup/switch** (mirror `arch-init` / `arch-switch-engagement`, respecting the key/unlock/encryption
      differences): extend `arch-assurance init` with `--backend <sqlcipher|pocketbase|private-git>` + `--signals
      <…>` to **write `storage.assurance` config and provision** the chosen backend (incl. private-git repo init);
      add `arch-assurance use-backend <…>` to switch the active backend in config (warn: switching a *populated*
      confidential store would need migration — N/A today). Reuse existing `unlock`/`backup`/`export`/`rotate-key`/
      `export-key`/`pocketbase-init` — extend, don't duplicate.
- [ ] Docs: `storage:` block in README Configuration Reference; CLI help.
- **Watch:** "no call-site changes" holds for *external* callers; the archive/store connection coupling moves
  *into* the factory (don't expose `_conn`). Verify `lru_cache.cache_clear` equivalents on the new keyed cache.
- **Files:** `settings.py`, `config/settings.yaml`, new `store_factory.py`, `context.py`, `assurance_ports.py`,
  `cli/arch_assurance.py`, README.
- **DoD:** default config selects SQLCipher store + confidential signals; switching `store_backend` to
  pocketbase/private-git works with no external call-site changes; accessors expose only port types;
  unknown backend fails closed at startup; locked/unlocked gating works; `status` shows backends; tests green.

### SC-2 — Confidential security-signals storage + classification + minimisation
**Goal:** signals confidential by default; plain-SQLite becomes the explicit *public-BOM opt-out* path.
- [ ] Confidential `SecuritySignalConnector` adapter — **preferred: co-locate signals tables in the SQLCipher
      `store.db`** (shares the store's sqlcipher connection, like the archive; one trust zone). Selected via
      `signals_backend`. **Make `sqlcipher-colocated` the default.**
- [ ] Add `tlp` (+ optional `confidentiality`) directly to the **base** signals schema; **default confidential**
      (not `TLP:WHITE`). Base schema written clean (no dual-format reader).
- [ ] Minimisation on ingest: store public refs (PURL/CVE/CPE), thin anchor mappings; classify the SBOM
      **root component** (our system identity); document what is/ isn't persisted.
- [ ] Gate the connector behind store-unlock when a confidential backend is active.
- [ ] Keep the `sqlite` backend purely as the explicit **public-BOM opt-out** path (not a legacy path).
- **Watch:** co-located adapter must use the **sqlcipher3** connection, not `sqlite3` (share the store's
  connection, like the archive).
- **Files:** `_schema.py`, `_security_connector.py` (+ co-located adapter), `_sbom_parser.py`, `store_factory.py`,
  `security_read_tools.py`/`security_write_tools.py`, README.
- **DoD:** with the default (confidential) backend, signals are encrypted at rest and carry TLP; ingest stores
  only minimised refs; locked ⇒ no signals; the public-SQLite path is opt-in and labelled public-only.

### SC-3 — Encrypted private-git store adapter
**Goal:** an encrypted private-git option (queryability preserved by the in-memory read model).
- [ ] Add encryption to the private-git adapter (`encrypt: true` flag or `_encrypted_private_git_store.py`):
      encrypt each record/file at rest with a **vetted** library; **decrypt-on-load** when building the read model.
- [ ] Reuse existing key management (OS keychain + recovery-key export in `lifecycle.py`) — **no bespoke crypto**.
- [ ] Selectable via `store_backend: private-git` + encryption flag.
- **Files:** private-git adapter, `lifecycle.py`, `store_factory.py`, README.
- **DoD:** encrypted private-git round-trips (write → commit → reload → in-memory query); on-disk JSON is
  ciphertext; git history has no plaintext; key recovery works.

### SC-4 — MCP max-classification + exposure logging *(in scope; pre-existing gap §27.4 presupposes)*
**Goal:** the AI-exposure control "subject to MCP max-classification."
- [ ] `arch-assurance-read` carries a configurable **max-classification ceiling** (in `storage.assurance` or a
      sibling config); artifacts above it — **store nodes AND signals** — are excluded/redacted at the tool boundary.
- [ ] Log exposures (what was returned at/under the ceiling, what was withheld) — define location + format.
- [ ] Choose + document a sane **default ceiling**; set confidential-by-default write-time TLP for sensitive
      node types/signals (`write_tools.py`, `_schema.py` defaults).
- **Files:** `assurance_mcp/read_tools.py`, `security_read_tools.py`, `context.py`/config, `write_tools.py`,
  `_schema.py` (defaults), README.
- **DoD:** an above-ceiling artifact (node *and* signal) is not returned by `arch-assurance-read` and the
  attempt is logged; raising the ceiling reveals it; default ceiling documented.
- **Note:** sequence last; may ship as its own PR but stays in this plan. SC-2 is at-rest-confidential without
  it, but "confidential by default *at the AI boundary*" needs it.

### SC-5 — Align the general read-model composition root (single backend kept; no DuckDB)
**Goal:** same convention, **no new capability** — consistency only.
- [ ] Type `shared_artifact_index()` / accessors as **`ArtifactStorePort`** (today expose concrete `ArtifactIndex`).
- [ ] `get_shared_index` reads the `storage.read_model` seam **only** to route the **gated Tantivy text-index
      fallback** flag (if/when pursued). Default unchanged: SQLite (FTS5 + CoW).
- [ ] Verify the existing architecture repos (ENG-ARCH-REPO, enterprise-repository) re-index from source and
      query correctly after the change — a derived-index rebuild, **not** a data migration.
- **Watch:** confirm `ArtifactStorePort` covers every method call sites use; if a caller needs an
  `ArtifactIndex`-only method, extend the port or keep that caller concrete with a noted reason — don't widen the port silently.
- **Explicitly not done:** no DuckDB, no multi-backend factory, no single-backend change.
- **Files:** `artifact_index/service.py`, `artifact_index/bootstrap.py`, `config/settings.yaml`, `settings.py`.
- **DoD:** call sites depend on `ArtifactStorePort`; **full existing suite green** (behaviour identical);
  existing architecture repos re-index + query correctly; `storage.read_model` seam exists and is read; no DuckDB anywhere.

## 5. Global definition of done (release gates — testable)

- **G-config:** default config selects SQLCipher store + confidential signals; `storage.*` switches backends via config + `arch-assurance` CLI (`init --backend`, `use-backend`); unknown backend fails closed. (SC-1)
- **G-signals:** default signals storage is confidential (encrypted/co-located) + TLP-tagged; locked ⇒ no signals; public path is explicit opt-out. (SC-2)
- **G-git:** encrypted private-git round-trips; on-disk ciphertext; new history plaintext-free. (SC-3)
- **G-ai:** above-ceiling node *and* signal withheld + logged at `arch-assurance-read`; raising ceiling reveals. (SC-4)
- **G-readmodel:** read-model call sites depend on `ArtifactStorePort`; full suite green; no DuckDB. (SC-5)
- **G-quality (all):** `uv run ruff check …` + `uv run zuban check` (after `uv sync --all-groups`) + pytest green;
  files within 250/350 LoC; **no plan-phase references in code/test names or content**; README + CLI help updated.
- **G-clean (all):** clean cutover — no backward-compat code paths / dual-format readers.
- **G-content (all):** existing architecture repos re-index from source + query correctly; no assurance content exists to migrate (verified, §6).

## 6. Migration inventory, sequencing, testing, out-of-scope

**Migration inventory (verified on disk 2026-06-05 — what needs migrating: essentially nothing).**
- **Architecture repos (ENG-ARCH-REPO, enterprise-repository)** — the only content that exists. Git source
  files + a derived/disposable read-model ⇒ **re-index from source automatically; no data migration.** SC-5
  adds the smoke-test that they still index + query.
- **Confidential assurance store + `security-signals.db`** — **do not exist** (`.arch-assurance/` absent; no
  assurance artifacts yet). ⇒ **nothing to migrate;** a fresh `arch-assurance init` writes the clean schema.
- **Contingency only (not needed here):** if some other environment already holds assurance content, the
  pre-release stance is **re-init (disposable)**; a one-shot `migrate-signals` / private-git re-encrypt is the
  fallback if it must be kept.

**Order:** SC-1 (convention + unblocks rest) → SC-2 → SC-3 → SC-4. SC-2/SC-3/SC-5 independent after SC-1;
SC-5 is small and can land alongside SC-1.

**Testing (per project conventions):** **separate test files** per adapter/factory; encrypted-adapter
round-trip tests; gating test (locked ⇒ no signals on a confidential backend); max-classification redaction
test (node + signal); a smoke test that the existing ENG-ARCH-REPO repo indexes + queries after SC-5. Risk
hotspot to test hardest: the store↔archive connection sharing routed through the factory (SC-1).

**Out of scope:** PostgreSQL/Supabase store adapters (planned, unbuilt); any architecture *model* change
(`PLAN-assurance-architecture-model.md`); WORM/legal-hold/crypto-shred (shipped, opt-in); **DuckDB / any
multi-backend factory for the read-model** (single SQLite+CoW kept by decision); the CoW concurrency rework
(`async-duckdb-migration-plan.md`).

## 7. Traceability

- SC-1/2/3 ⇐ §27.4 + the pluggable-storage requirement (model plan req 2 "Pluggable, Confidential Assurance Storage").
- SC-2 ⇐ §27.4 ¶1–2 · SC-3 ⇐ §27.4 ¶3 · SC-4 ⇐ §27.4 ¶1 + plan §16/§23 (AI-exposure control — currently absent).
- SC-5 + the strategy ⇐ the storage-strategy evaluation (Option B, YAGNI-scoped); honours the single-backend
  read-model decision in `async-duckdb-migration-plan.md` (no DuckDB).
