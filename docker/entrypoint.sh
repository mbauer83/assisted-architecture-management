#!/usr/bin/env sh
# ─────────────────────────────────────────────────────────────────────────────
# Architectonic container entrypoint — fully non-interactive startup.
#
#   1. Resolve configuration + target locations (workspace, settings document)
#      without opening any store.
#   2. Obtain credentials non-interactively (env-provided passphrase/vault).
#   3-5. Discover, preflight, and migrate every existing persisted target
#      (repositories AND operational stores/caches) via `arch-repair upgrade`,
#      then verify by exit state.
#   6. Initialize absent optional stores at current version (not a migration).
#   7. Only then start ordinary connectors: exec the unified backend as PID 1.
#
# No step ever prompts: git auth and the assurance passphrase come from the
# environment, and the process has no TTY (isatty()==false), so the code paths
# that would otherwise prompt are skipped by design. Startup deliberately has
# no --exclude-target mechanism: excluding a configured active target while
# the software will immediately use it is a contradiction.
# ─────────────────────────────────────────────────────────────────────────────
set -eu

log() { printf '[entrypoint] %s\n' "$*" >&2; }

is_enabled() {
    case "$(printf '%s' "${1:-}" | tr '[:upper:]' '[:lower:]')" in
        0 | false | no | off | "") return 1 ;;
        *) return 0 ;;
    esac
}

# ── 1. Configuration + target locations (no store is opened here) ────────────
WORKSPACE_CONFIG="${ARCH_WORKSPACE_CONFIG:-/app/arch-workspace.yaml}"
if [ -f "$WORKSPACE_CONFIG" ]; then
    log "Resolving workspace from $WORKSPACE_CONFIG"
    init_args=""
    is_enabled "${ARCH_INIT_ENGAGEMENT_IF_EMPTY:-true}" && init_args="$init_args --initialize-engagement-repo-if-empty"
    is_enabled "${ARCH_INIT_ENTERPRISE_IF_EMPTY:-true}" && init_args="$init_args --initialize-enterprise-repo-if-empty"
    log "Workspace init flags:${init_args:- (none)}"
    # shellcheck disable=SC2086
    arch-init --config "$WORKSPACE_CONFIG" $init_args
else
    log "No workspace config at $WORKSPACE_CONFIG — relying on ARCH_REPO_ROOT/ARCH_ENTERPRISE_ROOT"
fi

# The container's live settings document is the deployment identity. Upgrade
# discovery and the runtime read the SAME document through ARCH_SETTINGS_PATH,
# so both resolve byte-identical canonical store/cache paths. (Distinct from
# ARCH_SETTINGS_FILE, which is a host-side Compose bind-mount source.)
SETTINGS_PATH="/app/config/settings.yaml"
export ARCH_SETTINGS_PATH="$SETTINGS_PATH"

# Reconcile the module-enabled flag with the toggle every start so the state is
# deterministic regardless of what a previous run wrote to settings.yaml.
ASSURANCE_ON="${ARCH_ENABLE_ASSURANCE:-false}"
if [ -f "$SETTINGS_PATH" ]; then
    ARCH_ASSURANCE_ON="$ASSURANCE_ON" \
    ARCH_MAX_CLASSIFICATION="${ARCH_MAX_CLASSIFICATION:-}" \
    python - "$SETTINGS_PATH" <<'PY'
import os, sys, yaml
path = sys.argv[1]
data = yaml.safe_load(open(path, encoding="utf-8").read()) or {}
data.setdefault("modules", {}).setdefault("assurance", {})["enabled"] = (
    os.environ["ARCH_ASSURANCE_ON"] == "true"
)
tlp = os.environ.get("ARCH_MAX_CLASSIFICATION", "")
if tlp:
    data.setdefault("storage", {}).setdefault("assurance", {})["max_classification"] = tlp
with open(path, "w", encoding="utf-8") as fh:
    yaml.safe_dump(data, fh, default_flow_style=False, allow_unicode=True)
PY
fi

if [ "$ASSURANCE_ON" = "true" ]; then
    store="${ARCH_ASSURANCE_STORE_BACKEND:-sqlcipher}"
    signals="${ARCH_ASSURANCE_SIGNALS_BACKEND:-sqlcipher-colocated}"
    archive="${ARCH_ASSURANCE_ARCHIVE_BACKEND:-standard}"
    log "Assurance enabled — store=$store signals=$signals archive=$archive"
    # Assert the env-selected backends into the settings document (merge: leaves
    # max_classification and other declarative keys untouched).
    arch-assurance use-backend "$store" --signals "$signals" --archive-backend "$archive" >/dev/null
fi

# ── 2. Credentials (non-interactive; never logged) ───────────────────────────
if [ "$ASSURANCE_ON" = "true" ] && [ "${ARCH_ASSURANCE_STORE_BACKEND:-sqlcipher}" = "sqlcipher" ] \
    && [ -z "${ARCH_ASSURANCE_MASTER_PASSWORD:-}" ]; then
    log "ERROR: ARCH_ENABLE_ASSURANCE=true with sqlcipher requires ARCH_ASSURANCE_MASTER_PASSWORD"
    exit 1
fi

# ── 3–5. Discover + preflight + migrate every existing target, then verify ───
# Runs before the backend starts, so the guard's "no backend may be serving the
# target repo" check always passes in this single-container deployment, and a
# deployment that is already current is a true no-op (no writes) — safe on every
# restart. Opt out with ARCH_REPAIR_UPGRADE=false (e.g. to defer to a manually
# run `arch-repair upgrade`). Exit-state mapping (readiness reads the report
# state): 0 → proceed; 1 repository step errors, 3 unresolved blocking
# migration, 20 partial apply, 21 infrastructure failure → halt with the report.
if is_enabled "${ARCH_REPAIR_UPGRADE:-true}"; then
    upgrade_roots=""
    if [ -f "$WORKSPACE_CONFIG" ]; then
        upgrade_roots="--workspace $(dirname "$WORKSPACE_CONFIG")"
    else
        [ -n "${ARCH_REPO_ROOT:-}" ] && upgrade_roots="$upgrade_roots --repo-root $ARCH_REPO_ROOT"
        [ -n "${ARCH_ENTERPRISE_ROOT:-}" ] && upgrade_roots="$upgrade_roots --repo-root $ARCH_ENTERPRISE_ROOT"
    fi
    upgrade_args="--commit --settings $SETTINGS_PATH $upgrade_roots"
    log "Upgrading persisted formats (arch-repair upgrade $upgrade_args)"
    rc=0
    # shellcheck disable=SC2086
    arch-repair upgrade $upgrade_args || rc=$?
    case "$rc" in
        0) log "Persisted formats current — proceeding" ;;
        1) log "HALT: repository upgrade steps reported errors (exit 1) — see report above"; exit 1 ;;
        3) log "HALT: unresolved blocking migration (exit 3) — nothing was written; resolve the listed choices"; exit 3 ;;
        20) log "HALT: partial apply (exit 20) — some targets committed; re-run to resume, see report"; exit 20 ;;
        21) log "HALT: infrastructure failure before any commit (exit 21) — see report"; exit 21 ;;
        *) log "HALT: arch-repair upgrade exited $rc"; exit "$rc" ;;
    esac
else
    log "Persisted-format upgrade skipped (ARCH_REPAIR_UPGRADE=false)"
fi

# ── 6. Initialize absent optional stores at current version (not a migration) ─
if [ "$ASSURANCE_ON" = "true" ]; then
    store="${ARCH_ASSURANCE_STORE_BACKEND:-sqlcipher}"
    signals="${ARCH_ASSURANCE_SIGNALS_BACKEND:-sqlcipher-colocated}"
    archive="${ARCH_ASSURANCE_ARCHIVE_BACKEND:-standard}"
    case "$store" in
        sqlcipher)
            st="$(arch-assurance status 2>/dev/null | awk '/^status:/ {print $2}')"
            if [ "$st" = "not_initialised" ] || [ -z "$st" ]; then
                log "Initialising SQLCipher assurance store"
                arch-assurance init --backend sqlcipher --signals "$signals" --archive-backend "$archive"
            fi
            # Idempotent: verifies the key and sets the persistent auto-unlock gate.
            if arch-assurance unlock; then
                log "Assurance store unlocked (auto-unlock active for future restarts)"
            else
                log "WARNING: assurance unlock failed — store stays locked (fail-closed)"
            fi
            ;;
        private-git | pocketbase)
            log "NOTE: store '$store' requires a one-time bootstrap — see docs/reference/docker-compose.md"
            ;;
        *)
            log "WARNING: unknown assurance store backend '$store'"
            ;;
    esac
fi

# ── 7. Start the unified backend ─────────────────────────────────────────────
log "Starting arch-backend on 0.0.0.0:${ARCH_PORT:-8000}"
# shellcheck disable=SC2086
exec arch-backend --host 0.0.0.0 ${ARCH_PORT:+--port "$ARCH_PORT"} \
    ${ARCH_READ_ONLY:+--read-only} \
    ${ARCH_ADMIN_MODE:+--admin-mode} \
    "$@"
