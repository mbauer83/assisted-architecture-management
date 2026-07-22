# Docker Compose Deployment

Run the whole stack — GUI, REST API, and all MCP endpoints — as a single
container, with optional profiles for a TLS reverse proxy and alternative
assurance storage. Everything starts **non-interactively**: git and assurance
credentials come from the environment, never from a prompt.

- [Quick start](#quick-start)
- [What runs](#what-runs)
- [Configuration model](#configuration-model)
- [Profiles](#profiles)
- [Non-interactive secrets](#non-interactive-secrets)
- [Assurance storage matrix](#assurance-storage-matrix)
- [VPN access & the reverse proxy](#vpn-access--the-reverse-proxy)
- [Connecting MCP clients](#connecting-mcp-clients)
- [Operations](#operations)

&nbsp;

## Quick start

```bash
cp .env.example .env                 # edit secrets/toggles
$EDITOR arch-workspace.server.yaml   # point at your git repos
docker compose up -d --build         # GUI + MCP on :8000, assurance OFF
```

Open `http://<host>:8000` for the GUI; `curl http://<host>:8000/health` to check
the backend. That default stack is a complete **no-assurance** deployment.

&nbsp;

## What runs

A single `app` container runs the unified backend, which serves every interface
on one port (`8000`):

| Path | Interface |
|---|---|
| `/` | GUI (pre-built Vue SPA) |
| `/api/*` | REST API |
| `/api/events` | Server-Sent Events stream |
| `/mcp/read`, `/mcp/write` | Architecture MCP (query / authoring) |
| `/mcp/assurance-read`, `/mcp/assurance-write` | Assurance MCP (gated; locked unless enabled) |

The image is multi-stage: a Node stage builds the SPA, a `uv` stage resolves
Python dependencies and fetches the pinned `plantuml.jar`, and a slim runtime
stage carries Java, Graphviz, and the fonts the diagram renderer needs. It runs
as a non-root user.

&nbsp;

## Configuration model

Three layers, each with a clear job:

| Layer | File | Holds |
|---|---|---|
| **Secrets & toggles** | `.env` (from `.env.example`) | git/assurance credentials, profile selection, backend selection, ports |
| **Repositories** | `arch-workspace.server.yaml` (mounted read-only) | which git repos to clone & sync |
| **Backend settings** | `config/settings.server.yaml` (baked into the image) | port, diagrams, TLP ceiling, storage defaults |

`config/settings.yaml` lives inside the image (owned by the runtime user) so the
entrypoint and `arch-assurance` can update the active storage backend without
bind-mount permission conflicts. Override declarative values through `.env`
(e.g. `ARCH_MAX_CLASSIFICATION`), or mount your own `settings.yaml` — if you do,
make it writable by the runtime uid (`10001`) and uncomment the mount in
`docker-compose.yml`.

&nbsp;

## Profiles

Profiles add optional services. Combine them on the command line, or set
`COMPOSE_PROFILES` in `.env` to make a set sticky.

| Profile | Adds | Use when |
|---|---|---|
| *(none)* | `app` only | GUI + MCP, **no assurance** — the default |
| `proxy` | Caddy TLS reverse proxy | exposing GUI + MCP over HTTPS on the VPN |
| `pocketbase` | PocketBase service as the assurance store | a shared, multi-workstation assurance store |

```bash
docker compose up -d                              # default, no assurance
docker compose --profile proxy up -d              # + HTTPS reverse proxy
docker compose --profile pocketbase up -d         # + PocketBase store backend
COMPOSE_PROFILES=proxy docker compose up -d       # equivalent, via .env
```

Assurance itself is a toggle, not a service, so it is controlled in `.env`
(`ARCH_ENABLE_ASSURANCE`) rather than by a profile — see below. The default
(`false`) is the no-assurance deployment.

&nbsp;

## Non-interactive secrets

All credentials are read from the environment; the container has no TTY, so the
prompts that would otherwise appear are skipped by design.

**Git sync** — set whichever your remotes need (in `.env`):

```ini
# Simplest: a personal access token alone (GitHub/GitLab ignore the username for
# token auth, so none is required):
ARCH_GIT_HTTPS_TOKEN=<personal-access-token>
# Explicit username + password/token instead (e.g. Bitbucket app passwords, or to
# override the token's default username). Takes precedence over ARCH_GIT_HTTPS_TOKEN:
ARCH_GIT_HTTPS_USERNAME=ci-bot
ARCH_GIT_HTTPS_PASSWORD=<personal-access-token>
# or, for SSH remotes:
ARCH_GIT_SSH_PASSWORD=<key-passphrase>
```

For SSH remotes, also mount the private key and tell git to use it, e.g. add to
the `app` service:

```yaml
environment:
  GIT_SSH_COMMAND: "ssh -i /home/arch/.ssh/id_ed25519 -o StrictHostKeyChecking=accept-new"
volumes:
  - ./secrets/id_ed25519:/home/arch/.ssh/id_ed25519:ro
```

**Assurance** — when enabled with the SQLCipher store, the encryption key is
managed in a headless Fernet vault keyed by a master password:

```ini
ARCH_ENABLE_ASSURANCE=true
ARCH_ASSURANCE_MASTER_PASSWORD=<long-random-passphrase>
```

On first boot the entrypoint creates the store, then activates auto-unlock. The
vault (`$HOME/.config/arch-assurance`) and the store (`/app/.arch-assurance`)
live in named volumes, so every later restart unlocks automatically with no
ceremony. Save the recovery key offline once:

```bash
docker compose exec app arch-assurance export-key
```

&nbsp;

## Assurance storage matrix

Enabled only when `ARCH_ENABLE_ASSURANCE=true`. Selected in `.env`; the
entrypoint applies the choice on start.

```ini
ARCH_ASSURANCE_STORE_BACKEND=sqlcipher          # sqlcipher | private-git | pocketbase
ARCH_ASSURANCE_SIGNALS_BACKEND=sqlcipher-colocated
ARCH_ASSURANCE_ARCHIVE_BACKEND=standard         # standard | worm | s3-worm | azure-blob-worm
ARCH_MAX_CLASSIFICATION=TLP:AMBER               # exposure ceiling over REST/MCP
```

- **`sqlcipher`** (default) — one encrypted file in the `arch-assurance` volume;
  fully automated init + unlock as above.
- **`private-git`** / **`pocketbase`** — supported, but need a one-time bootstrap.
  For PocketBase, run the `pocketbase` profile, set
  `ARCH_POCKETBASE_URL=http://pocketbase:8090` plus admin credentials, then once:
  ```bash
  docker compose exec app arch-assurance pocketbase-init \
    --base-url http://pocketbase:8090 --admin-token <token>
  ```
- **Cloud WORM archives** need no extra service, only env:
  ```ini
  ARCH_ASSURANCE_ARCHIVE_BACKEND=s3-worm
  ARCH_S3_BUCKET=my-worm-bucket        # Object Lock enabled at creation
  ARCH_S3_OBJECT_LOCK_MODE=GOVERNANCE
  AWS_ACCESS_KEY_ID=...
  AWS_SECRET_ACCESS_KEY=...
  ```
  The `cloud-archive` SDKs (boto3 + Azure) are in the image by default. For a
  leaner image without them, build with `--build-arg ARCH_PIP_EXTRAS=""`.

Full backend semantics: [Assurance storage & confidentiality](../04-assurance/storage-and-confidentiality.md).

&nbsp;

## VPN access & the reverse proxy

The backend has no built-in TLS or authentication — the VPN is the access
boundary. Two supported topologies:

**Direct** (default): the `app` port is published on the VPN interface. Set
`ARCH_APP_BIND` / `ARCH_APP_PORT` in `.env`.

**Behind Caddy** (`proxy` profile): Caddy terminates TLS and forwards GUI, REST,
SSE, and MCP (streaming preserved). Set the hostname clients use:

```ini
COMPOSE_PROFILES=proxy
ARCH_SITE_ADDRESS=https://arch.internal      # Caddy's local CA issues an internal cert
```

For a real domain reachable by the VPN's DNS, set `ARCH_SITE_ADDRESS` to that
domain and add an email line to `docker/Caddyfile` for automatic ACME TLS. When
fronting with the proxy, restrict direct access by setting
`ARCH_APP_BIND=127.0.0.1` (or firewalling port 8000).

&nbsp;

## Connecting MCP clients

Point any MCP client at the served HTTP endpoints (no per-client backend):

```json
{
  "mcpServers": {
    "arch-repo-read":  { "url": "https://arch.internal/mcp/read" },
    "arch-repo-write": { "url": "https://arch.internal/mcp/write" }
  }
}
```

The STDIO bridges (`arch-mcp-stdio-read`, …) can also attach to the shared
backend instead of starting their own — set
`ARCH_MCP_BACKEND_URL=https://arch.internal` in the client's server entry. See
[Interfaces & MCP](../03-modeling/interfaces-and-mcp.md).

&nbsp;

## Operations

```bash
docker compose logs -f app            # follow backend logs
docker compose exec app arch-assurance status   # store + unlock state
docker compose pull && docker compose up -d      # update
docker compose down                   # stop (named volumes persist)
```

| Volume | Holds |
|---|---|
| `arch-state` | resolved workspace state, pid, logs (`/app/.arch`) |
| `arch-data` | cloned engagement/enterprise repos (`/data`) |
| `arch-assurance` | encrypted SQLCipher store (`/app/.arch-assurance`) |
| `arch-home` | credential vault (`$HOME/.config/...`) |

Health is exposed at `/health` and wired into the container `HEALTHCHECK`.

**Repository format upgrade on every restart.** Before starting the backend, the
entrypoint runs `arch-repair upgrade --commit` against the resolved workspace
roots — the guard that refuses to run against a repo a live backend is serving
always passes here, since this *is* the process about to start that backend. A
repo already on the current format sees zero writes (a true no-op), so this is
safe on every single restart, not just after `docker compose pull`. Findings
are applied, indexes rebuilt, and `.arch-repo/config.yaml` stamped
automatically. Uncommitted model edits (the normal state of an actively-used
repo) never block this — a step reads whatever is currently on disk and
carries it forward, so nothing is lost; an unrecoverable pending transaction
is the only thing besides a live backend that aborts startup, since that
signals actual inconsistency rather than ordinary in-progress work. Controlled
by:

| Variable | Default | Effect |
|---|---|---|
| `ARCH_REPAIR_UPGRADE` | `true` | Set `false` to skip the check entirely (run `arch-repair upgrade` manually instead) |

The entrypoint exports `ARCH_SETTINGS_PATH` pointing at the container's live
settings file, so the upgrade discovers the deployment's operational targets
(guidance cache, signal stores, assurance store) — not just the repositories —
and halts with the report on any non-zero exit rather than serving on stale
formats. Note the distinction from `ARCH_SETTINGS_FILE` in `.env`: that is the
**host-side** path Compose bind-mounts onto `/app/config/settings.yaml`; it is
never meaningful inside the container. See the
[upgrade guide](upgrade-guide.md#docker-upgrade-before-serving) for the exit
mapping and worked report examples, and the
[CLI reference](cli-and-backend.md#repository-maintenance) for flags and the
`--json` report contract used for scripted checks.

---

*See also: [Installation & Setup](../02-installation.md) · [Configuration Reference](configuration.md)*
