"""Unit tests for the configured_java_path() settings accessor.

The user-settable JRE escape hatch has two halves: this settings accessor
(diagrams.java_path) and the ARCH_JAVA environment variable honoured by the
resolver. See tests/application/verification/test_resolve_java_executable.py for
the resolver precedence tests.
"""

from __future__ import annotations

from unittest.mock import patch

from src.config.settings import configured_java_path, load_settings


class TestConfiguredJavaPath:
    def test_default_is_empty_string(self) -> None:
        with patch("src.config.settings.load_settings", return_value={"diagrams": {}}):
            assert configured_java_path() == ""

    def test_configured_value_is_returned_and_stripped(self) -> None:
        settings = {"diagrams": {"java_path": "  /opt/jdk/bin/java  "}}
        with patch("src.config.settings.load_settings", return_value=settings):
            assert configured_java_path() == "/opt/jdk/bin/java"

    def test_non_string_value_falls_back_to_empty(self) -> None:
        with patch("src.config.settings.load_settings", return_value={"diagrams": {"java_path": 123}}):
            assert configured_java_path() == ""

    def test_load_settings_includes_java_path_default(self) -> None:
        assert load_settings()["diagrams"].get("java_path") == ""
