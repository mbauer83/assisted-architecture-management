"""Security signal CLI commands for arch-assurance.

Handlers for: import-sbom, export-aibom, scan-ai-candidates.
Extracted to keep arch_assurance.py within the LoC limit.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src.infrastructure.cli._assurance_commands import _print_yaml


def _default_signals_db_path(workspace_root: Path) -> Path:
    return workspace_root / ".arch-assurance" / "security-signals.db"


def cmd_import_sbom(args: argparse.Namespace, workspace_root: Path) -> int:
    from src.infrastructure.assurance._security_connector import SQLiteSecurityConnector  # noqa: PLC0415

    db_path = Path(args.signals_db_path) if args.signals_db_path else _default_signals_db_path(workspace_root)
    sbom_file = Path(args.file)
    if not sbom_file.exists():
        print(f"Error: file not found: {sbom_file}", file=sys.stderr)
        return 1
    try:
        with sbom_file.open() as fh:
            bom_data = json.load(fh)
    except Exception as exc:  # noqa: BLE001
        print(f"Error reading BOM file: {exc}", file=sys.stderr)
        return 1

    connector = SQLiteSecurityConnector(db_path)
    result = connector.import_bom(
        bom_data,
        anchor_entity_id=args.anchor or "",
        source_file=str(sbom_file),
    )
    _print_yaml(result)
    return 1 if "error" in result else 0


def cmd_export_aibom(args: argparse.Namespace) -> int:
    from src.infrastructure.assurance._aibom_exporter import build_cyclonedx_16  # noqa: PLC0415

    if args.components_file:
        comp_path = Path(args.components_file)
        if not comp_path.exists():
            print(f"Error: components file not found: {comp_path}", file=sys.stderr)
            return 1
        try:
            with comp_path.open() as fh:
                ai_components = json.load(fh)
        except Exception as exc:  # noqa: BLE001
            print(f"Error reading components file: {exc}", file=sys.stderr)
            return 1
    else:
        ai_components = []

    bom = build_cyclonedx_16(ai_components)
    output = json.dumps(bom, indent=2)
    if args.output:
        try:
            out_path = Path(args.output)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(output)
            print(f"AI-BOM written to {args.output}")
        except OSError as exc:
            print(f"Error writing output file: {exc}", file=sys.stderr)
            return 1
    else:
        print(output)
    return 0


def cmd_scan_ai_candidates(args: argparse.Namespace) -> int:
    from src.infrastructure.assurance.ai_candidate_scanner import scan_candidates  # noqa: PLC0415

    if not args.entities_file:
        print("Error: --entities-file is required", file=sys.stderr)
        return 1
    ent_path = Path(args.entities_file)
    if not ent_path.exists():
        print(f"Error: file not found: {ent_path}", file=sys.stderr)
        return 1
    try:
        with ent_path.open() as fh:
            entities = json.load(fh)
    except Exception as exc:  # noqa: BLE001
        print(f"Error reading entities file: {exc}", file=sys.stderr)
        return 1

    candidates = scan_candidates(entities)
    _print_yaml({
        "candidates": candidates,
        "count": len(candidates),
        "note": "Heuristic suggestions only — confirm before marking.",
    })
    return 0
