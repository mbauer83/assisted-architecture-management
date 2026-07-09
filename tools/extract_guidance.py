#!/usr/bin/env python3
"""Extract ArchiMate 4 entity-type guidance text to a publishable, out-of-repo v1
guidance-cache file, then strip it from the shipped ``entities.yaml`` (D2/D3 — the
``create_when``/``never_create_when`` prose is spec-derived and license-encumbered; it must
never be committed to this repository, not even in a test fixture).

Run from the project root:
    uv run tools/extract_guidance.py [--out PATH] [--dry-run]

``--out`` must resolve outside the repository (default: a dotfolder under the user's home
directory, never the workspace). ``--dry-run`` extracts and verifies losslessness but writes
nothing.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from src.domain.guidance import GuidanceKey, guidance_overlay_from_mapping

_REPO_ROOT = Path(__file__).resolve().parent.parent
_ENTITIES_PATH = _REPO_ROOT / "src" / "ontologies" / "archimate_4" / "entities.yaml"
_META_ONTOLOGY_ALIAS = "archimate-4"
_DEFAULT_OUT = Path.home() / ".arch-guidance-extract" / "archimate-4.guidance.yaml"

# Matches entities.yaml's consistent single-line quoted-string guidance fields, e.g.:
#   create_when: "Create artifacts to model \"tangible\" assets..."
_FIELD_LINE_RE = re.compile(
    r'^([ \t]*)(create_when|never_create_when):[ \t]*"((?:[^"\\]|\\.)*)"[ \t]*$', re.MULTILINE
)


def _extract(entity_types: dict[str, Any]) -> dict[str, Any]:
    out_entity_types: dict[str, Any] = {}
    for name, info in entity_types.items():
        create_when = info.get("create_when", "")
        never_create_when = info.get("never_create_when", "")
        if not create_when and not never_create_when:
            continue
        out_entity_types[name] = {"create_when": create_when, "never_create_when": never_create_when}
    return {
        "guidance_format": 1,
        "meta_ontologies": {_META_ONTOLOGY_ALIAS: {"entity_types": out_entity_types}},
    }


def _verify_lossless(entity_types: dict[str, Any], extracted: dict[str, Any]) -> None:
    """Round-trip the extracted document through the domain parser before anything is
    stripped, and assert every non-empty entity type's guidance text survives exactly."""
    overlay = guidance_overlay_from_mapping(extracted)
    mismatches: list[str] = []
    for name, info in entity_types.items():
        create_when = info.get("create_when", "")
        never_create_when = info.get("never_create_when", "")
        if not create_when and not never_create_when:
            continue
        key = GuidanceKey(module_alias=_META_ONTOLOGY_ALIAS, concept_kind="entity", type_name=name)
        entry = overlay.get(key)
        if entry is None or entry.create_when != create_when or entry.never_create_when != never_create_when:
            mismatches.append(name)
    if mismatches:
        raise SystemExit(f"ERROR: extraction is lossy for entity types: {mismatches}")


def _assert_out_of_repo(out_path: Path) -> None:
    try:
        out_path.resolve().relative_to(_REPO_ROOT)
    except ValueError:
        return
    raise SystemExit(
        f"ERROR: --out {out_path} resolves inside the repository ({_REPO_ROOT}); the "
        "extracted guidance file must never be committed. Choose a scratch/home path."
    )


def _strip_source(text: str) -> str:
    return _FIELD_LINE_RE.sub(lambda m: f'{m.group(1)}{m.group(2)}: ""', text)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=_DEFAULT_OUT, help="Out-of-repo output path")
    parser.add_argument("--dry-run", action="store_true", help="Extract and verify only; write nothing")
    args = parser.parse_args(argv)

    _assert_out_of_repo(args.out)

    source_text = _ENTITIES_PATH.read_text(encoding="utf-8")
    entity_data = yaml.safe_load(source_text)
    entity_types: dict[str, Any] = entity_data.get("entity_types") or {}

    extracted = _extract(entity_types)
    _verify_lossless(entity_types, extracted)
    matched_count = len(extracted["meta_ontologies"][_META_ONTOLOGY_ALIAS]["entity_types"])

    if args.dry_run:
        print(f"[dry-run] would extract {matched_count} entity types' guidance to {args.out}")
        print(f"[dry-run] would strip create_when/never_create_when in {_ENTITIES_PATH}")
        return

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(yaml.safe_dump(extracted, sort_keys=False, allow_unicode=True), encoding="utf-8")
    print(f"Extracted {matched_count} entity types' guidance to {args.out}")

    stripped_text = _strip_source(source_text)
    _ENTITIES_PATH.write_text(stripped_text, encoding="utf-8")
    print(f"Stripped create_when/never_create_when in {_ENTITIES_PATH}")


if __name__ == "__main__":
    main(sys.argv[1:])
