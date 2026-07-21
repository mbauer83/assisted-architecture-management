#!/usr/bin/env python
"""Dogfooding security refresh: generate SBOMs, acquire OSV data, submit one
typed RefreshBundle per anchor through the RefreshSecuritySignals command.

Targets:
  python — the backend's uv environment via the pinned cyclonedx-py generator
  npm    — the GUI via `npm sbom` (npm ≥ 9.5), dependency graph preserved

The script never touches a signals connector: acquisition results become a
bundle, and the command owns the run lifecycle (staging → populate → complete
→ atomic activation) against the co-located SQLCipher store. `--dry-run`
builds and reports the bundle without submitting anything.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.application.security_refresh.bundle_assembly import AcquisitionInputs  # noqa: E402
from src.application.security_refresh.command import RefreshBundle  # noqa: E402
from src.infrastructure.assurance.osv_client import OsvClient, OsvComponentQuery  # noqa: E402
from src.infrastructure.assurance.signal_ingest import assemble_bundle, submit_bundle  # noqa: E402


def _run(command: list[str], *, cwd: Path | None = None) -> str:
    completed = subprocess.run(
        command, cwd=cwd, capture_output=True, text=True, check=True, timeout=600,
    )
    return completed.stdout


def generate_python_sbom() -> tuple[dict[str, object], dict[str, str]]:
    version = _run(["uv", "run", "cyclonedx-py", "--version"]).strip()
    raw = _run(["uv", "run", "cyclonedx-py", "environment", "--output-format", "JSON"],
               cwd=REPO_ROOT)
    return json.loads(raw), {"generator": "cyclonedx-py", "generator_version": version}


def generate_npm_sbom() -> tuple[dict[str, object], dict[str, str]]:
    version = _run(["npm", "--version"]).strip()
    raw = _run(["npm", "sbom", "--sbom-format", "cyclonedx"], cwd=REPO_ROOT / "tools" / "gui")
    return json.loads(raw), {"generator": "npm sbom", "generator_version": version}


_GENERATORS = {"python": generate_python_sbom, "npm": generate_npm_sbom}


def _osv_acquire(
    queryable: Sequence[Mapping[str, str]], *, osv_base_url: str | None,
) -> AcquisitionInputs:
    """Live acquisition: query OSV for every queryable component."""
    client = OsvClient(**({"base_url": osv_base_url} if osv_base_url else {}))
    acquisition = client.query_components([
        OsvComponentQuery(component_id=q["component_id"], purl=q["purl"])
        for q in queryable
    ])
    return AcquisitionInputs(
        vulnerability_ids_by_component=acquisition.vulnerability_ids_by_component,
        vulnerabilities_by_id=acquisition.vulnerabilities_by_id,
        unmatched_components=acquisition.unmatched_components,
        failed_vulnerability_fetches=acquisition.failed_vulnerability_fetches,
    )


def build_bundle(target: str, anchor_entity_id: str, *, osv_base_url: str | None) -> RefreshBundle:
    sbom_data, generator_metadata = _GENERATORS[target]()
    return assemble_bundle(
        anchor_entity_id,
        sbom_data,
        acquire=lambda queryable: _osv_acquire(queryable, osv_base_url=osv_base_url),
        generator_metadata=generator_metadata,
        source_metadata={"vulnerability_source": "osv.dev"},
    )


def report(bundle: RefreshBundle) -> None:
    findings_by_band: dict[str, int] = {}
    unknown_severity = 0
    applicability_unknown = 0
    for finding in bundle.findings:
        band = finding.get("severity_band")
        if band:
            findings_by_band[str(band)] = findings_by_band.get(str(band), 0) + 1
        else:
            unknown_severity += 1
        if finding.get("applicability") == "unknown":
            applicability_unknown += 1
    diagnostics = bundle.diagnostics
    print(f"anchor:                {bundle.anchor_entity_id}")
    print(f"components:            {len(bundle.components)}")
    print(f"findings:              {len(bundle.findings)}")
    print(f"  by severity band:    {findings_by_band or '{}'}")
    print(f"  unknown severity:    {unknown_severity}")
    print(f"  applicability unknown: {applicability_unknown}")
    print(f"unmatched components:  {len(diagnostics.get('unmatched_components', []))}")  # type: ignore[arg-type]
    print(f"failed vuln fetches:   {len(diagnostics.get('failed_vulnerability_fetches', []))}")  # type: ignore[arg-type]
    print(f"not applicable (excl): {diagnostics.get('not_applicable_excluded', 0)}")


def submit(bundle: RefreshBundle) -> int:
    from src.infrastructure.assurance.store_factory import get_assurance_bundle  # noqa: PLC0415
    from src.infrastructure.deployment.layout import resolve_manifest  # noqa: PLC0415

    manifest = resolve_manifest()
    assurance = get_assurance_bundle(
        REPO_ROOT,
        db_path=manifest.assurance_db_path.path,
        signals_db_path=manifest.signals_db_path.path,
    )
    if not assurance.store.is_unlocked():
        try:
            assurance.store.unlock()
        except Exception as exc:  # noqa: BLE001
            print(f"cannot unlock the assurance store: {exc}", file=sys.stderr)
            print("hint: keyring key 'db-encryption-key' or ARCH_ASSURANCE_MASTER_PASSWORD",
                  file=sys.stderr)
            return 2
    run_store = assurance.refresh_run_store
    if run_store is None:
        print("refresh requires the SQLCipher store with co-located signals", file=sys.stderr)
        return 2
    result = submit_bundle(bundle, run_store=run_store)
    print(f"result: {type(result).__name__}: {result}")
    return 0 if type(result).__name__ == "RefreshActivated" else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=sorted(_GENERATORS), required=True)
    parser.add_argument("--anchor", required=True, help="architecture anchor entity id")
    parser.add_argument("--dry-run", action="store_true",
                        help="build and report the bundle; submit nothing")
    parser.add_argument("--osv-base-url", default=None)
    args = parser.parse_args()

    bundle = build_bundle(args.target, args.anchor, osv_base_url=args.osv_base_url)
    report(bundle)
    if args.dry_run:
        print("dry run — nothing submitted")
        return 0
    return submit(bundle)


if __name__ == "__main__":
    raise SystemExit(main())
