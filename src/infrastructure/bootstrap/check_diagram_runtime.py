"""Verify the local diagram toolchain versions used for PlantUML rendering."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

from src.application.verification.artifact_verifier_syntax import find_graphviz_dot


def _parse_version(text: str) -> tuple[int, ...] | None:
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", text)
    if match is None:
        return None
    return tuple(int(part) for part in match.groups())


def _run(cmd: list[str]) -> str:
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        output = (proc.stdout + proc.stderr).strip()
        raise SystemExit(output or f"Command failed: {' '.join(cmd)}")
    return (proc.stdout + proc.stderr).strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jar", default="tools/plantuml.jar", help="Path to plantuml.jar")
    parser.add_argument(
        "--min-graphviz",
        default="2.49.0",
        help="Minimum supported Graphviz version (default: 2.49.0)",
    )
    args = parser.parse_args(argv)

    jar_path = Path(args.jar)
    if not jar_path.exists():
        raise SystemExit(f"plantuml.jar not found at {jar_path}")

    min_graphviz = _parse_version(args.min_graphviz)
    if min_graphviz is None:
        raise SystemExit(f"Could not parse --min-graphviz version: {args.min_graphviz}")

    dot = find_graphviz_dot()
    if dot is None:
        raise SystemExit("Graphviz dot executable not found")
    dot_output = _run([str(dot), "-V"])
    dot_version = _parse_version(dot_output)
    if dot_version is None:
        raise SystemExit(f"Could not parse Graphviz version from: {dot_output}")
    if dot_version < min_graphviz:
        raise SystemExit(f"Graphviz {args.min_graphviz}+ required, found {'.'.join(str(p) for p in dot_version)}")

    plantuml_output = _run(["java", "-jar", str(jar_path), "-version"])
    plantuml_version = _parse_version(plantuml_output)
    if plantuml_version is None:
        raise SystemExit(f"Could not parse PlantUML version from: {plantuml_output}")

    print(f"Graphviz: {'.'.join(str(p) for p in dot_version)}")
    print(f"PlantUML: {'.'.join(str(p) for p in plantuml_version)}")
    print("Diagram runtime OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
