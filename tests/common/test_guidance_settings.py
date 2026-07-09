"""Unit tests for guidance_default_source() settings function (D2)."""

from __future__ import annotations

from unittest.mock import patch

from src.config.settings import guidance_default_source, load_settings


class TestGuidanceDefaultSource:
    def test_default_is_empty_string(self) -> None:
        with patch("src.config.settings.load_settings", return_value={"guidance": {}}):
            assert guidance_default_source() == ""

    def test_absent_guidance_section_returns_empty(self) -> None:
        with patch("src.config.settings.load_settings", return_value={}):
            assert guidance_default_source() == ""

    def test_configured_source_is_returned(self) -> None:
        settings = {"guidance": {"default_source": "https://example.invalid/guidance.yaml"}}
        with patch("src.config.settings.load_settings", return_value=settings):
            assert guidance_default_source() == "https://example.invalid/guidance.yaml"

    def test_non_string_value_falls_back_to_empty(self) -> None:
        with patch("src.config.settings.load_settings", return_value={"guidance": {"default_source": 123}}):
            assert guidance_default_source() == ""

    def test_load_settings_merges_guidance_defaults(self) -> None:
        result = load_settings()
        assert result["guidance"] == {"default_source": ""}
