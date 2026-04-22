"""Loader for document-type schemata from .arch-repo/documents/."""
from __future__ import annotations

import json
from pathlib import Path


def load_document_schemata(repo_root: Path) -> dict[str, dict]:
    """Return {doc_type: schema_dict} for all .arch-repo/documents/*.json files."""
    schemata_dir = repo_root / ".arch-repo" / "documents"
    if not schemata_dir.exists():
        return {}
    result: dict[str, dict] = {}
    for schema_file in sorted(schemata_dir.glob("*.json")):
        try:
            data = json.loads(schema_file.read_text(encoding="utf-8"))
            result[schema_file.stem] = data
        except (json.JSONDecodeError, OSError):
            pass
    return result


def get_document_schema(repo_root: Path, doc_type: str) -> dict | None:
    return load_document_schemata(repo_root).get(doc_type)
