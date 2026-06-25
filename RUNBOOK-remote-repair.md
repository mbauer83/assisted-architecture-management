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

## Git authentication (for the push in step 5b)
**This deployment authenticates via the compose `env_file:`.** `docker compose run app` loads that same
`env_file:` automatically, so the step-5b command below needs **no extra auth flags** — `arch-repair`
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
> append it to the step-5b `docker compose run`: `-e ARCH_GIT_HTTPS_TOKEN=…`, or
> `--git-token-file /run/secrets/git_token`, or `-e ARCH_GIT_HTTPS_USERNAME=… -e ARCH_GIT_HTTPS_PASSWORD=…`,
> or `-e ARCH_GIT_SSH_PASSWORD=…`. Not needed for this deployment.

---

## Steps (run in order)

```sh
# Helper: run a command in a one-off container while the service is quiesced.
# -T disables TTY allocation so binary stdout (the tar in step 1) is not corrupted and
# the commands stay non-interactive. The one-off container mounts the same arch-data
# volume but overrides the entrypoint, so arch-init does NOT run here.
R() { docker compose run --rm -T --no-deps --entrypoint sh app -lc "$1"; }

# ORDER MATTERS: `arch-repair` (step 5b) ships *in the updated image* — it does NOT exist on the
# currently-running old image. So you must build/pull the new image (step 4) BEFORE the repair.
# Building/pulling only prepares the image; it does not start the service. The service stays stopped
# through the whole repair, so arch-init (which ABORTS on a dirty tree or a non-'main' branch, and
# never resets or discards data) only runs at the final start (step 6) — by which point the repair
# has committed a clean tree back on 'main'. Cardinal rule: FINISH the repair before step 6.

# 0. QUIESCE FIRST — stop the service so git-sync (60s) and GUI/MCP writes cannot race the repair.
docker compose stop app

# 0b. Confirm the engagement repo path matches arch-workspace.server.yaml (default /data/engagement;
#     an operator may have customised it). Adjust the paths below if your config differs.
R 'ls -d /data/*'

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

# 4. DEPLOY THE UPDATED IMAGE NOW — REQUIRED before the repair, because `arch-repair` lives in this
#    image. This only builds/pulls the image; it does NOT start the service (so nothing can abort on the
#    dirty tree yet). First ensure the latest commits are pushed to the project remote, then on the host:
#      Source checkout on host:
git pull                      # fetch the latest application source into the deployment checkout
docker compose build app      # build the new image — it now contains `arch-repair`
#      Registry-based deploy — use INSTEAD of the build line above:
#      docker compose pull app
#    (Every `docker compose run`/`up` below now uses this new image.)

# 5a. INSPECT on the ORIGINAL production branch. Nothing here is irreversible.
R 'cd /data/engagement &&
   git diff --check &&
   test -f "projects/autocam/model/application/application-component/APP@1782278054.OPaZCl.cps.md" &&
   ! grep -rq --exclude-dir=.git "APP@1782278054.OPaZCl.cam-projects-cps" . &&
   echo "=== working-tree change set — review before step 5b ===" &&
   git status --short'
#     >>> OPERATOR: proceed to 5b only if the change list is exactly as expected. <<<

# 5b. Guarded, resumable repair (now available from the step-4 image). Verifies the upstream is
#     origin/<prod-branch>, commits the staged fix onto repair/cps-rename, pushes it, then
#     fast-forward-only merges it into the production branch and pushes that (ff-only: aborts instead
#     of clobbering a diverged production branch). Resumable — rerun after any interruption (state in
#     .git/arch-repair-state.json). Auth: `docker compose run` loads the deployment's env_file
#     automatically, so no auth flag is needed (see "Git authentication" above for the fallback).
#     Author identity: the commit uses ARCH_GIT_AUTHOR_NAME/_EMAIL from the env_file (default
#     "Architecture Repository Service" if unset) — see "Git author identity" below to set it first.
docker compose run --rm -T --no-deps --entrypoint arch-repair app \
  --repo-root /data/engagement \
  --repair-branch repair/cps-rename \
  --message 'fix(model): repair CPS slug references after rename (CFCS, MIRA diagrams)' \
  --confirm
#     >>> MUST print "Repair complete: repair/cps-rename → main" before you continue. If it failed
#         partway (auth, ff-only on a diverged production branch, etc.) HEAD may still be on
#         repair/cps-rename — DO NOT start the service yet (arch-init would abort). Fix the cause and
#         rerun the SAME command (it is resumable) until it prints "Repair complete". An ff-only
#         abort means production diverged: re-fetch and reconcile, then rerun. <<<

# 5c. Pre-start gate — assert the tree is clean and NOT on the repair branch, so the step-6 start
#     cannot abort (arch-init refuses a dirty tree or a non-'main' branch).
R 'cd /data/engagement &&
   test -z "$(git status --porcelain)" &&
   case "$(git rev-parse --abbrev-ref HEAD)" in
     repair/*) echo "ABORT: still on the repair branch — rerun step 5b until complete"; exit 1;;
     *) echo "OK: clean, on $(git rev-parse --abbrev-ref HEAD) — safe to start";;
   esac'

# 6. Start the service on the step-4 image (volumes persist — NEVER pass -v). The container was stopped
#    in step 0; starting it now runs the WS1–WS14 code, re-runs arch-init over the clean repaired tree,
#    and rebuilds the in-memory index from /data, so the served index ≡ disk at first request (WS9).
docker compose up -d app

# 7. Verify the system is actually RUNNING and serving the repaired data (no MCP needed).
#    7a. Wait for the app to report healthy (the compose healthcheck curls /health). A healthy app
#        also proves the index built cleanly — WS9 aborts startup on a duplicate/inconsistent index.
until [ "$(docker inspect -f '{{.State.Health.Status}}' "$(docker compose ps -q app)")" = healthy ]; do
  sleep 3; done
docker compose exec -T app curl -fsS http://localhost:8000/health && echo " <- app healthy"
#    7b. On-disk: no stale refs remain, entity file present.
docker compose exec -T app sh -lc '
  cd /data/engagement &&
  ! grep -rq --exclude-dir=.git "cam-projects-cps" . &&
  test -f projects/autocam/model/application/application-component/APP@1782278054.OPaZCl.cps.md &&
  echo "OK: no stale refs, entity file present"'
#    7c. Served data: the repaired entity is served through the running REST API (HTTP 200 + JSON).
#        Query by the rename-stable SHORT id — read_artifact resolves short/long/stale-slug forms, so
#        this stays correct even if the slug changes again.
docker compose exec -T app curl -fsS \
  'http://localhost:8000/api/entity?id=APP@1782278054.OPaZCl' >/dev/null && echo "OK: entity served"

rm -f orig-branch.txt   # clear the durable marker only after a clean, verified completion
```

## Git author identity (set before step 5b)
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
- **Safety of restart:** arch-init never resets or discards the working tree — it either accepts a
  clean (or explicitly-allowed-dirty) checkout or aborts startup. The step-5c gate plus "commit before
  start" mean the step-6 start can only ever serve the fully-repaired, committed state.
- If anything looks wrong: restore `eng-backup.tgz` (or just redo steps 3 + 5a–5b) — recovery is cheap.
- **If you genuinely cannot deploy the updated image** (no source build and no registry image carrying
  WS14 yet): there is no `arch-repair` to run. Either publish the image first, or perform the commit/push
  by hand inside the `R` shell (`git switch -c …`, `add -A`, `commit`, `push`, ff-only merge) — but then
  *you* must wire git credentials (the env_file token alone won't authenticate a bare `git push` without
  the askpass helper arch-repair sets up). Deploying the image (step 4) is the supported path.
- **Enterprise repo:** this repair scopes to `/data/engagement`. If the enterprise repo also carries the
  stale slug (e.g. the entity was promoted), scan and repeat the same procedure against it:
  `R 'grep -rq --exclude-dir=.git "cam-projects-cps" /data/enterprise && echo FOUND || echo clean'`,
  then rerun steps 3 + 5a–5b with `--repo-root /data/enterprise` and a fresh `--repair-branch`.
- **Cleanup (optional):** the merged `repair/cps-rename` branch remains locally and on origin; delete it
  once production is confirmed good: `R 'cd /data/engagement && git branch -D repair/cps-rename'` and
  `git push origin --delete repair/cps-rename` (with auth as in step 5b).
- Once the WS1–WS14 code is running (step 6), any **residual** stale slug is non-fatal — it resolves by
  short id — so this data repair is belt-and-braces, not load-bearing, going forward.
- Independent post-check from a workstation with the read MCP (optional): `artifact_verify` on
  `ARC@1782278684.yUXoze` and `ARC@1782365608.c3xIZY` → expect no `E301`/`E302`.
