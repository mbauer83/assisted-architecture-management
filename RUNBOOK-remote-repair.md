# RUNBOOK — Repair the remote Docker-Compose instance (host CLI)

Repairs the CPS stale-slug references on the remote, from the **host** shell only (no MCP, no Claude).
Run from the deployment directory containing `docker-compose.yml`. Everything is keyed off the compose
**service `app`** — no image/repo/volume name assumption.

## Facts that shape this
- The artifact index is **in-memory only** (rebuilt from `/data` on every start) — recreating the
  container *is* the index repair; **no volume needs discarding**.
- `arch-data` (repos, with the uncommitted rename), `arch-home` (credentials), `arch-assurance`
  (encrypted store) are **irreplaceable**.

> ⚠ **NEVER** `docker compose down -v` or `docker volume rm`. "Rebuild" = rebuild the *image* /
> recreate the *container*, never wipe a data volume.

## Host requirements
Only **Docker + Compose v2**. (Plus `git` *if* the host builds the image from source — else use
`docker compose pull`.) All text tools run **inside** the container; the host userland is irrelevant.

## Affected artifacts
- Entity CPS `APP@1782278054.OPaZCl` (current file `…OPaZCl.cps.md`; stale refs say `…cam-projects-cps`).
- Diagrams `ARC@1782278684.yUXoze` (CFCS) and `ARC@1782365608.c3xIZY` (MIRA).

## Git authentication (for the push in step 4b)
**This deployment authenticates via the compose `env_file:`.** `docker compose run app` loads that same
`env_file:` automatically, so the step-4b command below needs **no extra auth flags** — `arch-repair`
reuses the image's resolver (the same one git-sync already uses) and picks the credentials straight out
of the inherited env. The resolver reads, in order:

| Mode | Env var(s) in the env file |
|------|-----------|
| Token in a secret file | `ARCH_GIT_HTTPS_TOKEN_FILE` (path to a mounted file holding the PAT) |
| Inline token (PAT) | `ARCH_GIT_HTTPS_TOKEN` (used as the password; defaults the username) |
| Explicit user + password/token | `ARCH_GIT_HTTPS_USERNAME` + `ARCH_GIT_HTTPS_PASSWORD` |
| SSH key passphrase | `ARCH_GIT_SSH_PASSWORD` |

Sanity-check that the env file is being loaded before you push (optional):
```sh
R 'env | grep -E "ARCH_GIT_(HTTPS|SSH)" | sed "s/=.*/=<set>/"'   # shows which auth vars are present
```

> Fallback only — if a credential is *not* in the env file (e.g. you keep it out of the deployment),
> append it to the step-4b `docker compose run`: `-e ARCH_GIT_HTTPS_TOKEN=…`, or
> `--git-token-file /run/secrets/git_token`, or `-e ARCH_GIT_HTTPS_USERNAME=… -e ARCH_GIT_HTTPS_PASSWORD=…`,
> or `-e ARCH_GIT_SSH_PASSWORD=…`. Not needed for this deployment.

---

## Steps (run in order)

```sh
# Helper: run a command in a one-off container while the service is quiesced.
R() { docker compose run --rm --no-deps --entrypoint sh app -lc "$1"; }

# 0. QUIESCE FIRST — stop the service so git-sync (60s) and GUI/MCP writes cannot race the repair.
docker compose stop app

# 1. Insurance backup of the quiesced repo (recovery is cheap; you can also just redo the repair).
R 'tar cz -C /data/engagement .' > eng-backup.tgz

# 2. Record the ORIGINAL production branch ONCE (durable host file); abort if it looks like repair/*.
[ -f orig-branch.txt ] || R 'cd /data/engagement && git rev-parse --abbrev-ref HEAD' > orig-branch.txt
case "$(cat orig-branch.txt)" in repair/*) echo "ABORT: orig-branch.txt is a repair branch"; exit 1;; esac

# 3. Rewrite the stale slug across the WHOLE engagement repo (covers projects/autocam/... AND the
#    diagram catalog; the old id is a unique substring, so connection ids are fixed too).
R 'cd /data/engagement &&
   grep -rl --exclude-dir=.git "APP@1782278054.OPaZCl.cam-projects-cps" . |
   xargs -r sed -i "s/APP@1782278054\.OPaZCl\.cam-projects-cps/APP@1782278054.OPaZCl.cps/g"'

# 4a. INSPECT on the ORIGINAL production branch. Nothing here is irreversible.
R 'cd /data/engagement &&
   git diff --check &&
   test -f "projects/autocam/model/application/application-component/APP@1782278054.OPaZCl.cps.md" &&
   ! grep -rq --exclude-dir=.git "APP@1782278054.OPaZCl.cam-projects-cps" . &&
   echo "=== working-tree change set — review before step 4b ===" &&
   git status --short'
#     >>> OPERATOR: proceed to 4b only if the change list is exactly as expected. <<<

# 4b. Guarded, resumable repair. Verifies the upstream is origin/<prod-branch>, commits the staged
#     fix onto repair/cps-rename, pushes it, then fast-forward-only merges it into the production
#     branch and pushes that (ff-only: aborts instead of clobbering a diverged production branch).
#     Resumable — rerun the same command after any interruption (state in .git/arch-repair-state.json).
#     Auth: `docker compose run` loads the deployment's env_file automatically, so no auth flag is
#     needed here (see "Git authentication" above for the fallback if a credential is kept out of it).
#     Author identity: the commit uses ARCH_GIT_AUTHOR_NAME/_EMAIL from the env_file (default
#     "Architecture Repository Service" if unset) — see "Git author identity" below to set it first.
docker compose run --rm --no-deps --entrypoint arch-repair app \
  --repo-root /data/engagement \
  --repair-branch repair/cps-rename \
  --message 'fix(model): repair CPS slug references after rename (CFCS, MIRA diagrams)' \
  --confirm

# 5. Deploy + bring the service back (volumes persist — NEVER pass -v). Recreating rebuilds the
#    in-memory index from the now-correct /data. (Registry deploy: `docker compose pull` instead of build.)
git pull
docker compose build app
docker compose up -d app

# 6. Verify (no MCP): no stale refs remain, entity file present.
docker compose exec app sh -lc '
  cd /data/engagement &&
  ! grep -rq --exclude-dir=.git "cam-projects-cps" . &&
  test -f projects/autocam/model/application/application-component/APP@1782278054.OPaZCl.cps.md &&
  echo "OK: no stale refs, entity file present"'

rm -f orig-branch.txt   # clear the durable marker only after a clean, verified completion
```

## Git author identity (set before step 4b)
The repair commit and all normal `save_changes` commits take their identity from **environment
variables**, applied as `git -c user.name=… -c user.email=…` — the container's `git config` is **not**
consulted, so `git config --global` has no effect here. Set these in the deployment's `env_file` (the
same file used for auth) so the commit is attributable:

```
ARCH_GIT_AUTHOR_NAME=Your Service Or Person Name
ARCH_GIT_AUTHOR_EMAIL=you@example.com
```

This identity is the **committer** (and the author of the repair commit). If you leave it unset, the
commit still succeeds using the built-in default `Architecture Repository Service
<arch-service@localhost>` — functional, but unattributed. To override just this one repair without
editing the env file, pass it inline: `docker compose run … -e ARCH_GIT_AUTHOR_NAME=… -e
ARCH_GIT_AUTHOR_EMAIL=… --entrypoint arch-repair app …`. (A normal `save_changes` can additionally
carry a distinct per-request **author** while keeping this env identity as committer.)

## Notes
- If anything looks wrong: restore `eng-backup.tgz` (or just redo steps 3–4) — recovery is cheap.
- After the code fix (`PLAN-rename-stale-index-fix.md`) ships, stale slug refs are **non-fatal** (they
  resolve by short id), so this manual repair becomes optional cosmetic cleanup.
- Independent post-check from a workstation with the read MCP (optional): `artifact_verify` on
  `ARC@1782278684.yUXoze` and `ARC@1782365608.c3xIZY` → expect no `E301`/`E302`.
