#!/usr/bin/env python
"""Generate THIRD-PARTY-NOTICES.md from the committed license inventories.

Reads ``licenses/{python,npm,native}.json`` (produced by check_licenses.py + the
curated native list) and renders a single top-level notices file: the project's
own license, the corresponding-source offers for every copyleft / weak-copyleft
bundled or invoked component (GPL/LGPL/EPL/MPL — the legally load-bearing part),
and the full permissive inventory per ecosystem.

Usage:
    generate-notices --write    # regenerate THIRD-PARTY-NOTICES.md
    generate-notices --check    # CI: fail if the committed file is stale
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LICENSES_DIR = REPO_ROOT / "licenses"
NOTICES_PATH = REPO_ROOT / "THIRD-PARTY-NOTICES.md"

# Corresponding-source pointers for non-native copyleft/weak-copyleft components
# (native components carry their own source_url/obligation in native.json).
_SOURCE_OFFERS: dict[str, dict[str, str]] = {
    "cvss": {
        "source_url": "https://github.com/RedHatProductSecurity/cvss",
        "obligation": (
            "LGPLv3+ (weak copyleft). Imported dynamically and unmodified, and "
            "pip-replaceable, so it is compatible with MIT redistribution; ship "
            "this notice and the upstream-source pointer above."
        ),
    },
}

_COPYLEFT_MARKERS = ("gpl", "lgpl", "epl", "mpl", "mozilla", "eclipse", "lesser general", "general public")


def _load(ecosystem: str) -> dict:
    path = LICENSES_DIR / f"{ecosystem}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _is_copyleft(license_text: str) -> bool:
    return any(m in license_text.lower() for m in _COPYLEFT_MARKERS)


def _project_license_line() -> str:
    text = (REPO_ROOT / "LICENSE").read_text(encoding="utf-8")
    return text.splitlines()[0].strip() if text.strip() else "MIT License"


def _render() -> str:
    python = _load("python")
    npm = _load("npm")
    native = _load("native")

    lines: list[str] = []
    lines.append("# Third-Party Notices")
    lines.append("")
    lines.append(
        "This product — **Architectonic** — is distributed under the "
        f"**{_project_license_line()}** (see `LICENSE`). It bundles, links, or invokes the "
        "third-party components listed below, each under its own license. This file is generated "
        "by `tools/generate_notices.py` from the committed inventories in `licenses/`; regenerate "
        "with `--write` after any dependency change. Not legal advice."
    )
    lines.append("")

    # ── Copyleft / weak-copyleft: corresponding-source offers (load-bearing) ──
    lines.append("## Copyleft and weak-copyleft components — corresponding source")
    lines.append("")
    lines.append(
        "The following components are under copyleft or weak-copyleft licenses. Each is bundled "
        "unmodified or invoked at arm's length (a separate process), so it does not affect the "
        "license of Architectonic's own code. Their complete corresponding source is available at "
        "the pointers below."
    )
    lines.append("")
    for comp in native["components"]:
        if comp.get("obligation") and _is_copyleft(comp["license"]):
            lines.append(f"### {comp['name']} — {comp['license']}")
            lines.append(f"- Version: {comp['version']}")
            lines.append(f"- Exposure: {comp['exposure']}")
            lines.append(f"- Source: {comp['source_url']}")
            lines.append(f"- Obligation: {comp['obligation']}")
            lines.append("")
    for comp in python["components"] + npm["components"]:
        if _is_copyleft(comp["license"]) and comp["name"] in _SOURCE_OFFERS:
            offer = _SOURCE_OFFERS[comp["name"]]
            lines.append(f"### {comp['name']} — {comp['license']}")
            lines.append(f"- Version: {comp['version']}")
            lines.append(f"- Source: {offer['source_url']}")
            lines.append(f"- Obligation: {offer['obligation']}")
            lines.append("")

    # ── Full permissive inventory ──
    for title, data in (
        ("Python dependencies", python),
        ("Frontend (npm) dependencies", npm),
        ("Native / system runtime components", native),
    ):
        lines.append(f"## {title} ({data['count']})")
        lines.append("")
        lines.append("| Component | Version | License |")
        lines.append("|---|---|---|")
        for comp in data["components"]:
            lines.append(f"| {comp['name']} | {comp['version'] or '—'} | {comp['license']} |")
        lines.append("")

    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="regenerate THIRD-PARTY-NOTICES.md")
    mode.add_argument("--check", action="store_true", help="CI: fail if the committed file is stale")
    args = parser.parse_args(argv)

    rendered = _render()
    if args.write:
        NOTICES_PATH.write_text(rendered, encoding="utf-8")
        print(f"wrote {NOTICES_PATH.relative_to(REPO_ROOT)}")
        return 0
    if not NOTICES_PATH.exists():
        print(f"missing {NOTICES_PATH.name} — run generate-notices --write")
        return 1
    if NOTICES_PATH.read_text(encoding="utf-8") != rendered:
        print(f"{NOTICES_PATH.name} is stale — run generate-notices --write and commit")
        return 1
    print(f"{NOTICES_PATH.name} is up to date")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
