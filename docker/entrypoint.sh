#!/usr/bin/env sh
# ─────────────────────────────────────────────────────────────────────────────
# Architectonic container entrypoint — fully non-interactive startup.
#
#   1. Resolve the workspace (clone/sync git repos using ARCH_GIT_* credentials).
#   2. (opt-in) Configure + unlock the confidential assurance store from env.
#   3. exec the unified backend (REST + GUI + MCP) in the foreground as PID 1.
#
# No step ever prompts: git auth and the assurance passphrase come from the
# environment, and the process has no TTY (isatty()==false), so the code paths
# that would otherwise prompt are skipped by design.
# ─────────────────────────────────────────────────────────────────────────────
set -eu

log() { printf '[entrypoint] %s\n' "$*" >&2; }

# ── 1. Workspace resolution ──────────────────────────────────────────────────
# Auto-initialize empty/uninitialized git repos on first boot — ON by default so a
# fresh deployment bootstraps cleanly. Opt out per repo with ARCH_INIT_*_IF_EMPTY set
# to a falsy value (0/false/no/off).
is_enabled() {
    case "$(printf '%s' "${1:-}" | tr '[:upper:]' '[:lower:]')" in
        0 | false | no | off | "") return 1 ;;
        *) return 0 ;;
    esac
}

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

# ── 2. Assurance (opt-in; the default deployment runs without it) ─────────────
# Reconcile the module-enabled flag with the toggle every start so the state is
# deterministic regardless of what a previous run wrote to settings.yaml.
ASSURANCE_ON="${ARCH_ENABLE_ASSURANCE:-false}"
SETTINGS_PATH="/app/config/settings.yaml"
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

    # Assert the env-selected backends into config/settings.yaml (merge: leaves
    # max_classification and other declarative keys untouched).
    arch-assurance use-backend "$store" --signals "$signals" --archive-backend "$archive" >/dev/null

    case "$store" in
        sqlcipher)
            if [ -z "${ARCH_ASSURANCE_MASTER_PASSWORD:-}" ]; then
                log "ERROR: ARCH_ENABLE_ASSURANCE=true with sqlcipher requires ARCH_ASSURANCE_MASTER_PASSWORD"
                exit 1
            fi
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

# ── 3. Start the unified backend ─────────────────────────────────────────────
log "Starting arch-backend on 0.0.0.0:${ARCH_PORT:-8000}"
# shellcheck disable=SC2086
exec arch-backend --host 0.0.0.0 ${ARCH_PORT:+--port "$ARCH_PORT"} \
    ${ARCH_READ_ONLY:+--read-only} \
    ${ARCH_ADMIN_MODE:+--admin-mode} \
    "$@"
