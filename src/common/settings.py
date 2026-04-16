from __future__ import annotations

from pathlib import Path

import yaml  # type: ignore[import-untyped]

_CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"
_DEFAULTS = {"diagrams": {"archimate_type_markers": "labels"}}


def load_settings() -> dict:
    path = _CONFIG_DIR / "settings.yaml"
    if not path.exists():
        return _DEFAULTS.copy()
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    diagrams = {**_DEFAULTS["diagrams"], **(data.get("diagrams") or {})}
    return {"diagrams": diagrams}


def archimate_type_markers() -> str:
    value = load_settings()["diagrams"].get("archimate_type_markers", "labels")
    return value if value in {"labels", "icons"} else "labels"
