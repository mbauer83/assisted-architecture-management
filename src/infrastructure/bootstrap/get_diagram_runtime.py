"""Fetch the supported PlantUML and Graphviz runtime for this project."""

from __future__ import annotations

import argparse
import hashlib
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path

from src.infrastructure.bootstrap.get_plantuml import PLANTUML_VERSION
from src.infrastructure.bootstrap.get_plantuml import download as download_plantuml

GRAPHVIZ_VERSION = "14.1.5"
GRAPHVIZ_MIN_VERSION = "2.49.0"
GRAPHVIZ_TAR_XZ_URL = (
    "https://gitlab.com/api/v4/projects/4207231/packages/generic/"
    f"graphviz-releases/{GRAPHVIZ_VERSION}/graphviz-{GRAPHVIZ_VERSION}.tar.xz"
)
GRAPHVIZ_TAR_XZ_SHA256 = "b017378835f7ca12f1a3f1db5c338d7e7af16b284b7007ad73ccec960c1b45b3"


def _repo_root() -> Path:
    candidate = Path(__file__).resolve()
    for _ in range(6):
        candidate = candidate.parent
        if (candidate / "pyproject.toml").exists():
            return candidate
    raise SystemExit("Could not locate repository root from pyproject.toml")


def _parse_version(text: str) -> tuple[int, ...] | None:
    import re

    match = re.search(r"(\d+)\.(\d+)\.(\d+)", text)
    if match is None:
        return None
    return tuple(int(part) for part in match.groups())


def _dot_version(dot_path: Path | str) -> tuple[int, ...] | None:
    proc = subprocess.run([str(dot_path), "-V"], capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        return None
    return _parse_version((proc.stdout + proc.stderr).strip())


def _download_bytes(url: str) -> bytes:
    with urllib.request.urlopen(url) as resp:  # noqa: S310
        return resp.read()


def _sha256hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().lower()


def _ensure_graphviz_from_source(root: Path, *, force: bool) -> Path:
    tools_dir = root / "tools"
    output_dir = tools_dir / "graphviz"
    dot_name = "dot.exe" if os.name == "nt" else "dot"
    dot_path = output_dir / "bin" / dot_name
    if dot_path.exists() and not force:
        return dot_path

    archive_path = tools_dir / f"graphviz-{GRAPHVIZ_VERSION}.tar.xz"
    src_parent = tools_dir / "_graphviz-src"
    src_dir = src_parent / f"graphviz-{GRAPHVIZ_VERSION}"

    print(f"Downloading Graphviz {GRAPHVIZ_VERSION} source …")
    tar_bytes = _download_bytes(GRAPHVIZ_TAR_XZ_URL)
    actual_sha = _sha256hex(tar_bytes)
    if actual_sha != GRAPHVIZ_TAR_XZ_SHA256:
        raise SystemExit(f"Graphviz SHA-256 mismatch: expected {GRAPHVIZ_TAR_XZ_SHA256}, got {actual_sha}")

    tools_dir.mkdir(parents=True, exist_ok=True)
    archive_path.write_bytes(tar_bytes)
    shutil.rmtree(src_parent, ignore_errors=True)
    src_parent.mkdir(parents=True, exist_ok=True)

    with tarfile.open(archive_path, mode="r:xz") as tf:
        tf.extractall(src_parent)

    if not src_dir.exists():
        raise SystemExit(f"Expected extracted source directory missing: {src_dir}")

    shutil.rmtree(output_dir, ignore_errors=True)

    configure = src_dir / "configure"
    if not configure.exists():
        raise SystemExit(f"Expected configure script missing: {configure}")

    print(f"Building Graphviz {GRAPHVIZ_VERSION} into {output_dir} …")
    subprocess.run(
        [str(configure), f"--prefix={output_dir}"],
        cwd=src_dir,
        check=True,
    )
    subprocess.run(
        ["make", f"-j{max(1, os.cpu_count() or 1)}"],
        cwd=src_dir,
        check=True,
    )
    subprocess.run(["make", "install"], cwd=src_dir, check=True)

    if not dot_path.exists():
        raise SystemExit(f"Graphviz build completed but dot was not found at {dot_path}")
    return dot_path


def _install_graphviz_system() -> None:
    system = platform.system().lower()
    commands: list[list[str]] = []
    if system == "darwin" and shutil.which("brew"):
        commands = [["brew", "install", "graphviz"]]
    elif system == "linux":
        if shutil.which("apt-get"):
            commands = [["apt-get", "update"], ["apt-get", "install", "-y", "graphviz"]]
        elif shutil.which("dnf"):
            commands = [["dnf", "install", "-y", "graphviz"]]
        elif shutil.which("pacman"):
            commands = [["pacman", "-Sy", "--noconfirm", "graphviz"]]
    elif system == "windows":
        if shutil.which("winget"):
            commands = [
                [
                    "winget",
                    "install",
                    "--id",
                    "Graphviz.Graphviz",
                    "-e",
                    "--accept-source-agreements",
                    "--accept-package-agreements",
                ]
            ]
        elif shutil.which("choco"):
            commands = [["choco", "install", "graphviz", "-y"]]

    if not commands:
        raise SystemExit("No supported system package manager found for Graphviz installation")

    for cmd in commands:
        print(f"Running: {' '.join(cmd)}")
        subprocess.run(cmd, check=True)


def _check_runtime(root: Path) -> int:
    from src.application.verification.artifact_verifier_syntax import find_graphviz_dot
    from src.infrastructure.bootstrap.check_diagram_runtime import main as check_runtime

    dot = find_graphviz_dot()
    if dot is not None:
        os.environ["GRAPHVIZ_DOT"] = str(dot)
    try:
        check_runtime(["--jar", str(root / "tools" / "plantuml.jar"), "--min-graphviz", GRAPHVIZ_MIN_VERSION])
    except SystemExit as exc:
        return int(exc.code or 1)
    return 0


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="Re-download and rebuild even if present")
    parser.add_argument(
        "--graphviz-mode",
        choices=("auto", "source", "system", "none"),
        default="auto",
        help="How to provision Graphviz (default: auto)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Only verify the currently installed runtime",
    )
    args = parser.parse_args(argv)

    root = _repo_root()
    plantuml_path = root / "tools" / "plantuml.jar"

    if args.check:
        sys.exit(_check_runtime(root))

    rc = download_plantuml(PLANTUML_VERSION, plantuml_path, force=args.force)
    if rc != 0:
        sys.exit(rc)

    if args.graphviz_mode != "none":
        chosen_mode = args.graphviz_mode
        if chosen_mode == "auto":
            chosen_mode = "source" if platform.system().lower() == "linux" else "system"

        if chosen_mode == "system":
            _install_graphviz_system()
        else:
            dot_path = _ensure_graphviz_from_source(root, force=args.force)
            os.environ["GRAPHVIZ_DOT"] = str(dot_path)

    sys.exit(_check_runtime(root))


if __name__ == "__main__":
    main()
