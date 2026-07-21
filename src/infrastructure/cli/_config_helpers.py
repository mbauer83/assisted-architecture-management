"""Config-write helpers for arch-assurance CLI commands."""

from __future__ import annotations

from pathlib import Path


def _workspace_root() -> Path:
    return Path(__file__).resolve().parents[3]


def write_storage_config(
    store_backend: str,
    signals_backend: str,
    archive_backend: str | None = None,
) -> None:
    """Write storage.assurance settings to the active settings document
    (honors `ARCH_SETTINGS_PATH`; falls back to config/settings.yaml).

    archive_backend is only written when explicitly supplied so that callers
    that don't set it leave existing config untouched.
    """
    import yaml  # noqa: PLC0415

    from src.config.settings import settings_document_path  # noqa: PLC0415

    config_path = settings_document_path()
    data: dict[str, object]
    if config_path.exists():
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    else:
        data = {}
    storage: dict[str, object] = data.setdefault("storage", {})  # type: ignore[assignment]
    assurance: dict[str, object] = storage.setdefault("assurance", {})  # type: ignore[assignment]
    assurance["store_backend"] = store_backend
    assurance["signals_backend"] = signals_backend
    if archive_backend is not None:
        assurance["archive_backend"] = archive_backend
    dumped = str(yaml.dump(data, default_flow_style=False, allow_unicode=True) or "")
    config_path.write_text(dumped, encoding="utf-8")
