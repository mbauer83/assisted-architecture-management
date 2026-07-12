"""Import a hosted/local guidance-cache document into the one deployment-level
``~/.config/arch-repo/guidance-cache/`` (D2/D3/D3a). Guidance is a deployment concern, not a
per-repository-tier one — one running instance of this software pulls one guidance source,
never split per engagement/enterprise repo and never committed to either repo's git history.
Guidance is authoring help, never a governance tier: unknown keys are dropped (or, with
``--strict``, abort the import) rather than silently accepted.

Usage:
    arch-import-guidance --source <url|path> [--module ALIAS] [--dry-run] [--strict]
        [--allow-http]
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from typing import cast

import yaml  # type: ignore[import-untyped]

from src.config.settings import guidance_default_source
from src.domain.clock import utc_now_iso
from src.infrastructure.app_bootstrap import build_module_registry
from src.infrastructure.guidance_cache import guidance_cache_root
from src.infrastructure.guidance_import import (
    GuidanceImportError,
    GuidanceImportSummary,
    fetch_source,
    filter_alias_document,
    select_aliases,
    validate_schema,
)

_GUIDANCE_FORMAT_VERSION = 1


def run_import(
    *,
    source: str,
    module: str | None,
    dry_run: bool,
    strict: bool,
    allow_http: bool,
) -> list[GuidanceImportSummary]:
    raw_bytes = fetch_source(source, allow_http=allow_http)
    sha256 = hashlib.sha256(raw_bytes).hexdigest()
    data = validate_schema(yaml.safe_load(raw_bytes))
    aliases = select_aliases(data, module)

    registry = build_module_registry()
    summaries = [
        filter_alias_document(alias, alias_data, registry, strict=strict) for alias, alias_data in aliases.items()
    ]

    if dry_run:
        return summaries

    cache_root = guidance_cache_root()
    cache_root.mkdir(parents=True, exist_ok=True)
    for summary in summaries:
        _write_cache_and_sidecar(cache_root, summary, source=source, sha256=sha256)
    return summaries


def _write_cache_and_sidecar(
    cache_root: Path, summary: GuidanceImportSummary, *, source: str, sha256: str
) -> None:
    cache_file = cache_root / f"{summary.alias}.guidance.yaml"
    cache_file.write_text(str(yaml.safe_dump(summary.filtered_document, sort_keys=False)), encoding="utf-8")

    sidecar = {
        "source": source,
        "sha256": sha256,
        "guidance_format": _GUIDANCE_FORMAT_VERSION,
        "imported_at": utc_now_iso(),
        "matched_count": len(summary.matched_keys),
        "unmatched_count": len(summary.unmatched_keys),
        "unmatched_keys": list(summary.unmatched_keys),
    }
    sidecar_file = cache_root / f"{summary.alias}.guidance.meta.yaml"
    sidecar_file.write_text(str(yaml.safe_dump(sidecar, sort_keys=False)), encoding="utf-8")


def _print_summary(summary: GuidanceImportSummary, *, dry_run: bool) -> None:
    verb = "Would import" if dry_run else "Imported"
    print(f"{verb} {summary.alias}: {len(summary.matched_keys)} matched, {len(summary.unmatched_keys)} unmatched")
    for key in summary.unmatched_keys:
        print(f"  unmatched: {key}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", default=None, help="Guidance document URL or local path")
    parser.add_argument("--module", default=None, metavar="ALIAS", help="Import only this meta-ontology alias")
    parser.add_argument("--dry-run", action="store_true", help="Validate and report; write nothing")
    parser.add_argument("--strict", action="store_true", help="Fail on any unknown key instead of skipping it")
    parser.add_argument("--allow-http", action="store_true", help="Allow plain-HTTP sources (HTTPS is the default)")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    source = args.source or guidance_default_source()
    if not source:
        parser.error("--source is required (no guidance_default_source configured)")

    try:
        summaries = run_import(
            source=cast(str, source),
            module=args.module,
            dry_run=args.dry_run,
            strict=args.strict,
            allow_http=args.allow_http,
        )
    except GuidanceImportError as exc:
        parser.error(str(exc))

    for summary in summaries:
        _print_summary(summary, dry_run=args.dry_run)
    if not args.dry_run:
        print("Restart the backend for the imported guidance to take effect.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
