from __future__ import annotations

from pathlib import Path

import yaml  # type: ignore[import-untyped]

_CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"
_DEFAULTS = {
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
    }
}


def load_settings() -> dict:
    path = _CONFIG_DIR / "settings.yaml"
    if not path.exists():
        return _DEFAULTS.copy()
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    backend = {**_DEFAULTS["backend"], **(data.get("backend") or {})}
    diagrams = {**_DEFAULTS["diagrams"], **(data.get("diagrams") or {})}
    return {"backend": backend, "diagrams": diagrams}


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
