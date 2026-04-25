"""Loader for document-type schemata from .arch-repo/documents/."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from src.common.repo_paths import ARCH_DOC_SCHEMATA, ARCH_REPO


@lru_cache(maxsize=4)
def load_document_schemata(repo_root: Path) -> dict[str, dict[str, Any]]:
    """Return {doc_type: schema_dict} for all .arch-repo/documents/*.json files."""
    schemata_dir = repo_root / ARCH_REPO / ARCH_DOC_SCHEMATA
    if not schemata_dir.exists():
        return {}
    result: dict[str, dict[str, Any]] = {}
    for schema_file in sorted(schemata_dir.glob("*.json")):
        try:
            data = json.loads(schema_file.read_text(encoding="utf-8"))
            result[schema_file.stem] = data
        except (json.JSONDecodeError, OSError):
            pass
    return result


def get_document_schema(repo_root: Path, doc_type: str) -> dict[str, Any] | None:
    return load_document_schemata(repo_root).get(doc_type)


def get_document_subdirectory(schema: dict, doc_type: str) -> str:
    raw = str(schema.get("subdirectory") or doc_type).strip().replace("\\", "/")
    parts = [part for part in raw.split("/") if part and part != "."]
    if not parts or any(part == ".." for part in parts):
        raise ValueError(
            f"Invalid document subdirectory for doc-type {doc_type!r}: {raw!r}"
        )
    return "/".join(parts)
