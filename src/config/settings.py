from __future__ import annotations

from pathlib import Path

import yaml  # type: ignore[import-untyped]

from src.domain.classification import TLP_ORDER
from src.domain.viewpoints import EnforcementSetting

_CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"
_DEFAULT_ENGAGEMENT: dict[str, object] = {}
_DEFAULTS: dict[str, dict[str, object]] = {
    "backend": {
        "port": 8000,
        "log_path": ".arch/backend.log",
        "min_log_level": "INFO",
    },
    "diagrams": {
        "archimate_type_markers": "labels",
        "sprite_scale": 1.5,
        "render_dpi": 150,
        "plantuml_limit_size": 16384,
    },
    "repo_init": {
        "default_branch": "main",
        "commit_author_name": "arch-switch-engagement",
        "commit_author_email": "arch-switch-engagement@local.invalid",
        "engagement": _DEFAULT_ENGAGEMENT,
    },
    "storage": {
        "assurance": {
            "store_backend": "sqlcipher",
            "signals_backend": "sqlcipher-colocated",
            "archive_backend": "standard",
            "max_classification": "TLP:AMBER",
        },
        "read_model": {},
    },
    "validation": {
        "datatype_type_references_blocking": True,
        "viewpoint_enforcement": "warn",
    },
    "guidance": {
        "default_source": "",
    },
    "viewpoints": {
        "execution_max_entities": 500,
        "execution_default_entity_limit_mcp": 200,
        "execution_timeout_seconds": 10,
    },
    "exchange": {
        "max_document_bytes": 10_000_000,
    },
}

_VALID_STORE_BACKENDS = frozenset({"sqlcipher", "pocketbase", "private-git"})
_VALID_SIGNALS_BACKENDS = frozenset({"sqlcipher-colocated", "sqlite", "encrypted"})
_VALID_ARCHIVE_BACKENDS = frozenset({"standard", "worm", "s3-worm", "azure-blob-worm"})
_VALID_TLP_LEVELS = frozenset(TLP_ORDER)

_SettingsSection = dict[str, object]


def load_settings() -> dict:
    path = _CONFIG_DIR / "settings.yaml"
    if not path.exists():
        return _DEFAULTS.copy()
    data: dict[str, object] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    backend_raw = data.get("backend")
    diagrams_raw = data.get("diagrams")
    repo_init_raw = data.get("repo_init")
    backend_section: _SettingsSection = backend_raw if isinstance(backend_raw, dict) else {}
    diagrams_section: _SettingsSection = diagrams_raw if isinstance(diagrams_raw, dict) else {}
    repo_init_section: _SettingsSection = repo_init_raw if isinstance(repo_init_raw, dict) else {}
    repo_init_engagement_raw = repo_init_section.get("engagement")
    repo_init_engagement_section: _SettingsSection = (
        repo_init_engagement_raw if isinstance(repo_init_engagement_raw, dict) else {}
    )
    backend = {**_DEFAULTS["backend"], **backend_section}
    diagrams = {**_DEFAULTS["diagrams"], **diagrams_section}
    repo_init = {
        **_DEFAULTS["repo_init"],
        **repo_init_section,
        "engagement": {
            **_DEFAULT_ENGAGEMENT,
            **repo_init_engagement_section,
        },
    }
    modules_raw = data.get("modules")
    modules_section: _SettingsSection = modules_raw if isinstance(modules_raw, dict) else {}

    storage_raw = data.get("storage")
    storage_section: _SettingsSection = storage_raw if isinstance(storage_raw, dict) else {}
    storage_assurance_raw = storage_section.get("assurance")
    storage_assurance: _SettingsSection = (
        storage_assurance_raw if isinstance(storage_assurance_raw, dict) else {}
    )
    storage_read_model_raw = storage_section.get("read_model")
    storage_read_model: _SettingsSection = (
        storage_read_model_raw if isinstance(storage_read_model_raw, dict) else {}
    )
    default_storage: dict[str, object] = _DEFAULTS["storage"]  # type: ignore[assignment]
    default_assurance: dict[str, object] = default_storage["assurance"]  # type: ignore[assignment]
    storage: dict[str, object] = {
        "assurance": {**default_assurance, **storage_assurance},
        "read_model": {**storage_read_model},
    }
    validation_raw = data.get("validation")
    validation_section: _SettingsSection = validation_raw if isinstance(validation_raw, dict) else {}
    validation = {**_DEFAULTS["validation"], **validation_section}

    guidance_raw = data.get("guidance")
    guidance_section: _SettingsSection = guidance_raw if isinstance(guidance_raw, dict) else {}
    guidance = {**_DEFAULTS["guidance"], **guidance_section}

    viewpoints_raw = data.get("viewpoints")
    viewpoints_section: _SettingsSection = viewpoints_raw if isinstance(viewpoints_raw, dict) else {}
    viewpoints = {**_DEFAULTS["viewpoints"], **viewpoints_section}

    exchange_raw = data.get("exchange")
    exchange_section: _SettingsSection = exchange_raw if isinstance(exchange_raw, dict) else {}
    exchange = {**_DEFAULTS["exchange"], **exchange_section}

    return {
        "backend": backend,
        "diagrams": diagrams,
        "repo_init": repo_init,
        "modules": modules_section,
        "storage": storage,
        "validation": validation,
        "guidance": guidance,
        "viewpoints": viewpoints,
        "exchange": exchange,
    }


def module_overrides() -> dict[str, dict[str, object]]:
    """Return the ``modules:`` section from settings.yaml as {name: override-dict}.

    Only ``enabled`` is a supported YAML override key. Absent modules default to
    the module's own manifest values (enabled=True, requires=[]).
    """
    raw = load_settings().get("modules", {})
    if not isinstance(raw, dict):
        return {}
    out: dict[str, dict[str, object]] = {}
    for name, entry in raw.items():
        if not isinstance(entry, dict):
            continue
        parsed: dict[str, object] = {}
        if "enabled" in entry:
            parsed["enabled"] = bool(entry["enabled"])
        out[str(name)] = parsed
    return out


def backend_port() -> int:
    value = load_settings()["backend"].get("port", 8000)
    try:
        return max(1, min(65535, int(value)))
    except (TypeError, ValueError):
        return 8000


def backend_log_path() -> str:
    value = load_settings()["backend"].get("log_path", ".arch/backend.log")
    if not isinstance(value, str) or not value.strip():
        return ".arch/backend.log"
    return value.strip()


def backend_min_log_level() -> str:
    value = load_settings()["backend"].get("min_log_level", "INFO")
    if not isinstance(value, str):
        return "INFO"
    normalized = value.strip().upper()
    if normalized == "WARN":
        return "WARNING"
    if normalized in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        return normalized
    return "INFO"


def archimate_type_markers() -> str:
    value = load_settings()["diagrams"].get("archimate_type_markers", "labels")
    return value if value in {"labels", "icons"} else "labels"


def sprite_scale() -> float:
    value = load_settings()["diagrams"].get("sprite_scale", 1.5)
    try:
        return max(0.5, float(value))
    except (TypeError, ValueError):
        return 1.5


def render_dpi() -> int:
    value = load_settings()["diagrams"].get("render_dpi", 150)
    try:
        return max(72, int(value))
    except (TypeError, ValueError):
        return 150


def plantuml_limit_size() -> int:
    value = load_settings()["diagrams"].get("plantuml_limit_size", 16384)
    try:
        return max(4096, int(value))
    except (TypeError, ValueError):
        return 16384


def datatype_type_references_blocking() -> bool:
    """Whether E332/E334/E335/E336 reject writes instead of remaining advisory."""
    value = load_settings()["validation"].get("datatype_type_references_blocking", True)
    return value if isinstance(value, bool) else True


def viewpoint_enforcement_setting() -> EnforcementSetting:
    """Default viewpoint-application enforcement (W180/W181), overridable per-application."""
    value = str(load_settings()["validation"].get("viewpoint_enforcement", "warn"))
    if value not in ("off", "warn", "ghost"):
        return "warn"
    return value


def _viewpoints_value(key: str) -> object:
    viewpoints = load_settings().get("viewpoints", {})
    if not isinstance(viewpoints, dict):
        return _DEFAULTS["viewpoints"][key]  # type: ignore[index]
    return viewpoints.get(key, _DEFAULTS["viewpoints"][key])  # type: ignore[index]


def viewpoints_execution_max_entities() -> int:
    """Hard cap on entities in a viewpoint execution result, all transports (companion
    plan §7.1). GUI/REST default to this cap; MCP defaults lower (see below)."""
    value = _viewpoints_value("execution_max_entities")
    try:
        return max(1, int(value))  # type: ignore[call-overload]
    except (TypeError, ValueError):
        return 500


def viewpoints_execution_default_entity_limit_mcp() -> int:
    """MCP ``execute`` action default entity limit when no ``limit`` argument is given —
    smaller than the hard cap to protect agent context windows."""
    value = _viewpoints_value("execution_default_entity_limit_mcp")
    try:
        return max(1, int(value))  # type: ignore[call-overload]
    except (TypeError, ValueError):
        return 200


def viewpoints_execution_timeout_seconds() -> float:
    """Wall-clock budget for one viewpoint execution before it fails as a typed timeout
    error rather than returning a partial result."""
    value = _viewpoints_value("execution_timeout_seconds")
    try:
        return max(0.1, float(value))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 10.0


def exchange_max_document_bytes() -> int:
    """Hard size cap on an incoming C19C model-exchange document (parent plan §4.5) —
    rejected before any parsing is attempted, independent of the parser's own
    entity-expansion defenses."""
    value = load_settings()["exchange"]["max_document_bytes"]
    try:
        return max(1, int(value))  # type: ignore[call-overload]
    except (TypeError, ValueError):
        return 10_000_000


def guidance_default_source() -> str:
    """Preconfigured ``--source`` default for ``arch-import-guidance`` (D2). Operational
    default only — never a governance/customization surface."""
    guidance = load_settings().get("guidance", {})
    if not isinstance(guidance, dict):
        return ""
    value = guidance.get("default_source", "")
    return value if isinstance(value, str) else ""


def _repo_init_value(key: str, repo_kind: str | None = None) -> object:
    repo_init = load_settings().get("repo_init", {})
    if not isinstance(repo_init, dict):
        repo_init = {}
    if repo_kind:
        scoped = repo_init.get(repo_kind)
        if isinstance(scoped, dict) and key in scoped:
            return scoped.get(key)
    return repo_init.get(key)


def repo_init_default_branch(repo_kind: str | None = None) -> str:
    value = _repo_init_value("default_branch", repo_kind)
    if not isinstance(value, str) or not value.strip():
        return "main"
    return value.strip()


def repo_init_commit_author_name(repo_kind: str | None = None) -> str:
    value = _repo_init_value("commit_author_name", repo_kind)
    if not isinstance(value, str) or not value.strip():
        return "arch-switch-engagement"
    return value.strip()


def repo_init_commit_author_email(repo_kind: str | None = None) -> str:
    value = _repo_init_value("commit_author_email", repo_kind)
    if not isinstance(value, str) or not value.strip():
        return "arch-switch-engagement@local.invalid"
    return value.strip()


# ── Storage settings ──────────────────────────────────────────────────────────


def _storage_assurance_value(key: str) -> object:
    storage = load_settings().get("storage", {})
    if not isinstance(storage, dict):
        return _DEFAULTS["storage"]["assurance"][key]  # type: ignore[index]
    assurance = storage.get("assurance", {})
    if not isinstance(assurance, dict):
        return _DEFAULTS["storage"]["assurance"][key]  # type: ignore[index]
    return assurance.get(key, _DEFAULTS["storage"]["assurance"][key])  # type: ignore[index]


def storage_assurance_store_backend() -> str:
    """Return the active assurance store backend name.

    Fails closed (raises ValueError) for unknown backends so misconfiguration
    surfaces at startup rather than at first use.
    """
    value = _storage_assurance_value("store_backend")
    candidate = str(value).strip() if isinstance(value, str) else "sqlcipher"
    if candidate not in _VALID_STORE_BACKENDS:
        raise ValueError(
            f"Unknown storage.assurance.store_backend: {candidate!r}. "
            f"Supported: {sorted(_VALID_STORE_BACKENDS)}"
        )
    return candidate


def storage_assurance_signals_backend() -> str:
    """Return the active signals backend name. Fails closed on unknown values."""
    value = _storage_assurance_value("signals_backend")
    candidate = str(value).strip() if isinstance(value, str) else "sqlcipher-colocated"
    if candidate not in _VALID_SIGNALS_BACKENDS:
        raise ValueError(
            f"Unknown storage.assurance.signals_backend: {candidate!r}. "
            f"Supported: {sorted(_VALID_SIGNALS_BACKENDS)}"
        )
    return candidate


def storage_assurance_archive_backend() -> str:
    """Return the active archive backend name. Fails closed on unknown values.

    'standard'        — append-only hash-chained log (SQLCipherAssuranceArchive).
    'worm'            — extends standard with DEK encryption, legal holds,
                        crypto-shredding, RFC 3161; requires store_backend 'sqlcipher'.
    's3-worm'         — S3 Object Lock WORM; independent of store_backend.
    'azure-blob-worm' — Azure Blob immutability-policy WORM; independent of
                        store_backend.
    """
    value = _storage_assurance_value("archive_backend")
    candidate = str(value).strip() if isinstance(value, str) else "standard"
    if candidate not in _VALID_ARCHIVE_BACKENDS:
        raise ValueError(
            f"Unknown storage.assurance.archive_backend: {candidate!r}. "
            f"Supported: {sorted(_VALID_ARCHIVE_BACKENDS)}"
        )
    return candidate


def storage_assurance_max_classification() -> str:
    """Return the TLP max-classification ceiling for MCP exposure control.

    Artifacts with a TLP level *above* this ceiling are withheld at the
    arch-assurance-read boundary. Defaults to TLP:AMBER.
    """
    value = _storage_assurance_value("max_classification")
    candidate = str(value).strip().upper() if isinstance(value, str) else "TLP:AMBER"
    if candidate not in _VALID_TLP_LEVELS:
        return "TLP:AMBER"
    return candidate


def storage_read_model_seam() -> dict[str, object]:
    """Return the storage.read_model seam dict (reserved for future FTS-backend toggle)."""
    storage = load_settings().get("storage", {})
    if not isinstance(storage, dict):
        return {}
    read_model = storage.get("read_model", {})
    return dict(read_model) if isinstance(read_model, dict) else {}
