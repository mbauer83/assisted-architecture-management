"""
Download and SHA-256-verify plantuml.jar from Maven Central.

Maven Central provides a signed .sha256 sidecar for every artifact, making
it the most reliable source for checksum-verified downloads.

Usage
-----
    get-plantuml                      # download pinned version → tools/plantuml.jar
    get-plantuml --version 1.2025.2   # override version
    get-plantuml --output /tmp/p.jar  # custom output path
    get-plantuml --force              # re-download even if file already exists
    get-plantuml --check              # print SHA-256 of existing file, no download
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import urllib.request
from pathlib import Path

# ── Pinned release ────────────────────────────────────────────────────────────

PLANTUML_VERSION = "1.2026.2"

_MAVEN_BASE = "https://repo1.maven.org/maven2/net/sourceforge/plantuml/plantuml"

# ── Helpers ───────────────────────────────────────────────────────────────────


def _artifact_urls(version: str) -> tuple[str, str]:
    """Return (jar_url, sha256_url) for the given version."""
    base = f"{_MAVEN_BASE}/{version}/plantuml-{version}"
    return f"{base}.jar", f"{base}.jar.sha256"


def _fetch(url: str, label: str) -> bytes:
    print(f"  {label}: {url} … ", end="", flush=True)
    try:
        with urllib.request.urlopen(url) as resp:  # noqa: S310
            data = resp.read()
    except Exception as exc:
        print("FAILED")
        raise SystemExit(f"Download error: {exc}") from exc
    print(f"{len(data):,} bytes")
    return data


def _sha256hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().lower()


# ── Commands ──────────────────────────────────────────────────────────────────


def download(version: str, output: Path, *, force: bool) -> int:
    if output.exists() and not force:
        print(f"plantuml.jar already present at {output}")
        print("  (run with --force to re-download, or --check to verify)")
        return 0

    jar_url, sha_url = _artifact_urls(version)
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
        return 1

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(jar_bytes)
    print(f"OK  {output}  ({len(jar_bytes):,} bytes, SHA-256 verified)")
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
        default=PLANTUML_VERSION,
        metavar="VERSION",
        help=f"PlantUML version to download (default: {PLANTUML_VERSION})",
    )
    parser.add_argument(
        "--output",
        default="tools/plantuml.jar",
        metavar="PATH",
        help="Destination path (default: tools/plantuml.jar)",
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
    else:
        sys.exit(download(args.version, output, force=args.force))


if __name__ == "__main__":
    main()
