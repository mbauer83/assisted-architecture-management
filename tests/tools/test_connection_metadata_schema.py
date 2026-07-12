"""Tests for the `connection-metadata.{connection-type}.schema.json` convention: a
per-connection-type schema (opt-in, like `attributes.{artifact-type}.schema.json`) that
validates a connection's per-connection metadata block (the fenced YAML block under a
`### ` heading in an `.outgoing.md` file — today just `specialization`, open to future
per-connection metadata)."""

from __future__ import annotations

import json
from pathlib import Path

from src.application.artifact_schema import clear_schema_cache
from src.application.verification._verifier_rules_schema import check_connection_metadata_schema
from src.application.verification.artifact_verifier_types import VerificationResult

_FAKE_PATH = Path("/tmp/connection.md")


def _fresh_result() -> VerificationResult:
    return VerificationResult(path=_FAKE_PATH, file_type="connection")


def _write_schema(repo_root: Path, connection_type: str, schema: dict) -> None:
    schemata_dir = repo_root / ".arch-repo" / "schemata"
    schemata_dir.mkdir(parents=True, exist_ok=True)
    (schemata_dir / f"connection-metadata.{connection_type}.schema.json").write_text(
        json.dumps(schema), encoding="utf-8"
    )


def setup_function() -> None:
    clear_schema_cache()


class TestConnectionMetadataSchema:
    def test_no_schema_file_skips_validation(self, tmp_path: Path) -> None:
        result = _fresh_result()
        check_connection_metadata_schema(
            {"specialization": "anything"}, "archimate-assignment", tmp_path, result, "test"
        )
        assert result.issues == []

    def test_metadata_conforming_to_schema_is_silent(self, tmp_path: Path) -> None:
        _write_schema(
            tmp_path,
            "archimate-assignment",
            {"type": "object", "properties": {"specialization": {"type": "string"}}, "additionalProperties": True},
        )
        result = _fresh_result()
        check_connection_metadata_schema(
            {"specialization": "responsibility-assignment"}, "archimate-assignment", tmp_path, result, "test"
        )
        assert result.issues == []

    def test_metadata_violating_schema_is_w043(self, tmp_path: Path) -> None:
        _write_schema(
            tmp_path,
            "archimate-assignment",
            {"type": "object", "properties": {"priority": {"type": "integer"}}},
        )
        result = _fresh_result()
        check_connection_metadata_schema(
            {"priority": "not-an-integer"}, "archimate-assignment", tmp_path, result, "test"
        )
        assert [i.code for i in result.issues] == ["W043"]

    def test_schema_is_scoped_to_its_own_connection_type(self, tmp_path: Path) -> None:
        _write_schema(
            tmp_path,
            "archimate-assignment",
            {"type": "object", "properties": {"priority": {"type": "integer"}}},
        )
        result = _fresh_result()
        check_connection_metadata_schema(
            {"priority": "not-an-integer"}, "archimate-serving", tmp_path, result, "test"
        )
        assert result.issues == []
