"""
Download and verify plantuml.jar.

Primary source: Maven Central (SHA-256 verified via sidecar file).
Fallback source: GitHub Releases (no SHA-256 sidecar; size is reported).

Usage
-----
    get-plantuml                      # download pinned version → plantuml.jar
    get-plantuml --latest             # query GitHub API for newest release, then download
    get-plantuml --version 1.2026.3   # override version
    get-plantuml --output /tmp/p.jar  # custom output path
    get-plantuml --force              # re-download even if file already exists
    get-plantuml --check              # print SHA-256 of existing file, no download
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

# ── Pinned release ────────────────────────────────────────────────────────────

PLANTUML_VERSION = "1.2026.3"

_MAVEN_BASE = "https://repo1.maven.org/maven2/net/sourceforge/plantuml/plantuml"
_GITHUB_API_LATEST = "https://api.github.com/repos/plantuml/plantuml/releases/latest"
_GITHUB_DOWNLOAD = "https://github.com/plantuml/plantuml/releases/download/v{version}/plantuml-{version}.jar"

# ── Helpers ───────────────────────────────────────────────────────────────────


def _fetch(url: str, label: str) -> bytes:  # pragma: no cover — network download, not testable in unit tests
    print(f"  {label}: {url} … ", end="", flush=True)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "get-plantuml/1.0"})
        with urllib.request.urlopen(req) as resp:  # noqa: S310
            data = resp.read()
    except Exception as exc:
        print("FAILED")
        raise SystemExit(f"Download error: {exc}") from exc
    print(f"{len(data):,} bytes")
    return data


def _head_ok(url: str) -> bool:  # pragma: no cover — network HEAD request, not testable in unit tests
    """Return True if url responds with 2xx."""
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "get-plantuml/1.0"})
        with urllib.request.urlopen(req) as resp:  # noqa: S310
            return resp.status < 300
    except Exception:
        return False


def _sha256hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().lower()


def _latest_github_version() -> str:  # pragma: no cover — network GitHub API, not testable in unit tests
    print(f"  querying: {_GITHUB_API_LATEST} … ", end="", flush=True)
    try:
        req = urllib.request.Request(_GITHUB_API_LATEST, headers={"User-Agent": "get-plantuml/1.0"})
        with urllib.request.urlopen(req) as resp:  # noqa: S310
            data = json.loads(resp.read())
        tag = data["tag_name"].lstrip("v")
        print(tag)
        return tag
    except Exception as exc:
        print("FAILED")
        raise SystemExit(f"GitHub API error: {exc}") from exc


# ── Download strategies ───────────────────────────────────────────────────────


def _download_maven(version: str, output: Path) -> bool:  # pragma: no cover
    """Try Maven Central. Returns True on success, False if version not found there."""
    base = f"{_MAVEN_BASE}/{version}/plantuml-{version}"
    jar_url = f"{base}.jar"
    sha_url = f"{base}.jar.sha256"

    if not _head_ok(sha_url):
        print(f"  PlantUML {version} not yet on Maven Central — trying GitHub Releases")
        return False

    print(f"Downloading PlantUML {version} from Maven Central:")
    jar_bytes = _fetch(jar_url, "jar")
    sha_bytes = _fetch(sha_url, "sha256")

    expected = sha_bytes.decode().strip().split()[0].lower()
    actual = _sha256hex(jar_bytes)
    if actual != expected:
        print()
        print("ERROR: SHA-256 mismatch — aborting, file not written")
        print(f"  expected : {expected}")
        print(f"  actual   : {actual}")
        raise SystemExit(1)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(jar_bytes)
    print(f"OK  {output}  ({len(jar_bytes):,} bytes, SHA-256 verified)")
    return True


def _download_github(version: str, output: Path) -> None:  # pragma: no cover
    """Download from GitHub Releases (no SHA-256 sidecar)."""
    jar_url = _GITHUB_DOWNLOAD.format(version=version)
    print(f"Downloading PlantUML {version} from GitHub Releases:")
    jar_bytes = _fetch(jar_url, "jar")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(jar_bytes)
    digest = _sha256hex(jar_bytes)
    print(f"OK  {output}  ({len(jar_bytes):,} bytes)")
    print(f"  SHA-256: {digest}  (no Maven Central sidecar to verify against)")


# ── Commands ──────────────────────────────────────────────────────────────────


def download(version: str, output: Path, *, force: bool) -> int:
    if output.exists() and not force:
        print(f"plantuml.jar already present at {output}")
        print("  (run with --force to re-download, or --check to verify)")
        return 0

    if not _download_maven(version, output):
        _download_github(version, output)
    return 0


def check(output: Path) -> int:
    if not output.exists():
        print(f"File not found: {output}")
        return 1
    digest = _sha256hex(output.read_bytes())
    print(f"{output}")
    print(f"  SHA-256: {digest}")
    return 0


# ── Entry point ───────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version",
        default=None,
        metavar="VERSION",
        help=f"PlantUML version to download (default: {PLANTUML_VERSION})",
    )
    parser.add_argument(
        "--latest",
        action="store_true",
        help="Query GitHub API for the newest release and download that version",
    )
    parser.add_argument(
        "--output",
        default="plantuml.jar",
        metavar="PATH",
        help="Destination path (default: plantuml.jar)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download even if the file already exists",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Print SHA-256 of the existing file without downloading",
    )
    args = parser.parse_args(argv)
    output = Path(args.output)

    if args.check:
        sys.exit(check(output))

    if args.latest:
        version = _latest_github_version()
    elif args.version:
        version = args.version
    else:
        version = PLANTUML_VERSION

    sys.exit(download(version, output, force=args.force))


if __name__ == "__main__":
    main()
