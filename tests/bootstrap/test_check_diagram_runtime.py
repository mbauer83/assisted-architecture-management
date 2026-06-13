"""Tests for check_diagram_runtime.py pure functions.

Covers _parse_version (regex matching, None on no match) and
main() early-exit paths that don't require subprocesses.
"""

from __future__ import annotations

import pytest

from src.infrastructure.bootstrap.check_diagram_runtime import _parse_version, main


class TestParseVersion:
    def test_parses_standard_version(self) -> None:
        result = _parse_version("version 2.50.0")
        assert result == (2, 50, 0)

    def test_parses_from_longer_string(self) -> None:
        result = _parse_version("Graphviz - Graph Visualization Software\ndot - graphviz version 8.1.0")
        assert result == (8, 1, 0)

    def test_parses_major_only_style(self) -> None:
        result = _parse_version("plantuml 1.2.3 (GPL)")
        assert result == (1, 2, 3)

    def test_returns_none_when_no_version(self) -> None:
        result = _parse_version("no version here")
        assert result is None

    def test_returns_none_for_empty_string(self) -> None:
        result = _parse_version("")
        assert result is None

    def test_returns_none_for_partial_version(self) -> None:
        result = _parse_version("version 1.2")
        assert result is None


class TestMainEarlyExits:
    def test_missing_jar_raises_system_exit(self, tmp_path) -> None:
        with pytest.raises(SystemExit) as exc_info:
            main(["--jar", str(tmp_path / "nonexistent.jar")])
        assert "not found" in str(exc_info.value)

    def test_invalid_min_graphviz_raises_system_exit(self, tmp_path) -> None:
        jar = tmp_path / "plantuml.jar"
        jar.write_bytes(b"fake")
        with pytest.raises(SystemExit) as exc_info:
            main(["--jar", str(jar), "--min-graphviz", "not-a-version"])
        assert "min-graphviz" in str(exc_info.value).lower()
