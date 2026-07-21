"""`default-schemata-ensure`: missing shipped schemata are added; existing files are
never overwritten (customizations are preserved and reported)."""

from __future__ import annotations

import json
from pathlib import Path

from src.application.repository_upgrade.steps.default_schemata_ensure import DefaultSchemataEnsureStep
from src.domain.repo_default_schemata import DEFAULT_SCHEMATA
from src.infrastructure.repository_upgrade.fs_adapter import (
    FilesystemRepoUpgradeView,
    FilesystemRepoUpgradeWriter,
)

_RESOURCE_SCHEMA = "attributes.resource.schema.json"


def _repo(tmp_path: Path, *, present: dict[str, str] | None = None) -> Path:
    root = tmp_path / "repo"
    schemata = root / ".arch-repo" / "schemata"
    schemata.mkdir(parents=True)
    for name, content in (present or {}).items():
        (schemata / name).write_text(content, encoding="utf-8")
    return root


class TestDetect:
    def test_missing_files_are_auto_migratable_findings(self, tmp_path: Path) -> None:
        root = _repo(tmp_path)
        findings = DefaultSchemataEnsureStep().detect(FilesystemRepoUpgradeView(root))
        by_id = {f.finding_id: f for f in findings}
        assert f"missing-default-schema:{_RESOURCE_SCHEMA}" in by_id
        assert all(f.auto_migratable for f in findings)
        assert len(findings) == len(DEFAULT_SCHEMATA)

    def test_byte_identical_default_produces_no_finding(self, tmp_path: Path) -> None:
        content = json.dumps(DEFAULT_SCHEMATA[_RESOURCE_SCHEMA], indent=2) + "\n"
        root = _repo(tmp_path, present={_RESOURCE_SCHEMA: content})
        findings = DefaultSchemataEnsureStep().detect(FilesystemRepoUpgradeView(root))
        assert not any(_RESOURCE_SCHEMA in f.finding_id for f in findings)

    def test_customized_file_is_reported_but_never_auto_migrated(self, tmp_path: Path) -> None:
        root = _repo(tmp_path, present={_RESOURCE_SCHEMA: '{"type": "object", "custom": true}\n'})
        findings = DefaultSchemataEnsureStep().detect(FilesystemRepoUpgradeView(root))
        custom = [f for f in findings if f.finding_id == f"customized-default-schema:{_RESOURCE_SCHEMA}"]
        assert len(custom) == 1
        assert not custom[0].auto_migratable
        assert custom[0].severity == "info"

    def test_malformed_json_is_left_to_the_schema_file_scan_step(self, tmp_path: Path) -> None:
        root = _repo(tmp_path, present={_RESOURCE_SCHEMA: "{not json"})
        findings = DefaultSchemataEnsureStep().detect(FilesystemRepoUpgradeView(root))
        assert not any(_RESOURCE_SCHEMA in f.finding_id for f in findings)


class TestApply:
    def test_adds_missing_files_in_the_template_byte_format(self, tmp_path: Path) -> None:
        root = _repo(tmp_path)
        step = DefaultSchemataEnsureStep()
        view = FilesystemRepoUpgradeView(root)
        findings = [f for f in step.detect(view) if f.auto_migratable]
        outcomes = step.apply(view, FilesystemRepoUpgradeWriter(root), findings)
        assert all(o.outcome == "applied" for o in outcomes)
        written = root / ".arch-repo" / "schemata" / _RESOURCE_SCHEMA
        expected = json.dumps(DEFAULT_SCHEMATA[_RESOURCE_SCHEMA], indent=2) + "\n"
        assert written.read_text(encoding="utf-8") == expected

    def test_existing_file_is_preserved_byte_for_byte(self, tmp_path: Path) -> None:
        sentinel = '{"type": "object", "sentinel": "operator-edit"}\n'
        root = _repo(tmp_path, present={_RESOURCE_SCHEMA: sentinel})
        step = DefaultSchemataEnsureStep()
        view = FilesystemRepoUpgradeView(root)
        findings = [f for f in step.detect(view) if f.auto_migratable]
        step.apply(view, FilesystemRepoUpgradeWriter(root), findings)
        existing = root / ".arch-repo" / "schemata" / _RESOURCE_SCHEMA
        assert existing.read_text(encoding="utf-8") == sentinel

    def test_idempotent_second_run_detects_nothing_new(self, tmp_path: Path) -> None:
        root = _repo(tmp_path)
        step = DefaultSchemataEnsureStep()
        view = FilesystemRepoUpgradeView(root)
        step.apply(view, FilesystemRepoUpgradeWriter(root), [f for f in step.detect(view) if f.auto_migratable])
        assert step.detect(FilesystemRepoUpgradeView(root)) == []


class TestShippedResourcePayload:
    def test_investment_level_contract(self) -> None:
        schema = DEFAULT_SCHEMATA[_RESOURCE_SCHEMA]
        prop = schema["properties"]["investment_level"]
        assert prop["type"] == "integer"
        assert prop["minimum"] == 1
        assert prop["maximum"] == 5
        assert "1 minimal upkeep" in prop["description"]
        assert "5 primary focus" in prop["description"]
        assert schema["required"] == []
        assert schema["additionalProperties"] is True
