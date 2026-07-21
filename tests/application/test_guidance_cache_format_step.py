"""The guidance-cache format migrator (arch-repair, offline): detects sub-current cached
documents and header-patches them to the supported format, blocking on unreadable/newer ones,
preserving the rest of the document, and recommending a re-import for domain context."""

from __future__ import annotations

from pathlib import Path

from src.application.deployment_upgrade.steps.guidance_cache_format import (
    SUPPORTED_GUIDANCE_FORMAT,
    GuidanceCacheFormatStep,
)
from src.domain.operational_upgrade import UpgradeTarget
from src.infrastructure.deployment.file_targets import GuidanceCacheHandle

_V1_DOC = "guidance_format: 1\nmeta_ontologies:\n  archimate-4:\n    entity_types:\n      goal: {create_when: cw}\n"


def _handle(root: Path) -> GuidanceCacheHandle:
    target = UpgradeTarget(
        kind="guidance_cache",
        stable_id=f"guidance_cache:{root}",
        display_location=str(root),
        current_version=None,
    )
    return GuidanceCacheHandle(target=target, root=root)


def _run(root: Path) -> list:
    step = GuidanceCacheFormatStep()
    handle = _handle(root)
    findings = step.detect(handle.view())
    uow = handle.begin()
    applied = step.apply(handle.view(), uow, findings)
    uow.commit()
    return applied


class TestDetect:
    def test_v1_document_is_auto_migratable(self, tmp_path: Path) -> None:
        (tmp_path / "archimate-4.guidance.yaml").write_text(_V1_DOC, encoding="utf-8")
        findings = GuidanceCacheFormatStep().detect(_handle(tmp_path).view())
        assert len(findings) == 1
        assert findings[0].auto_migratable is True
        assert findings[0].severity == "warning"
        assert not findings[0].blocks_commit

    def test_current_document_yields_no_finding(self, tmp_path: Path) -> None:
        (tmp_path / "a.guidance.yaml").write_text(
            f"guidance_format: {SUPPORTED_GUIDANCE_FORMAT}\nmeta_ontologies: {{}}\n", encoding="utf-8"
        )
        assert GuidanceCacheFormatStep().detect(_handle(tmp_path).view()) == []

    def test_newer_document_blocks_commit(self, tmp_path: Path) -> None:
        (tmp_path / "a.guidance.yaml").write_text("guidance_format: 99\n", encoding="utf-8")
        findings = GuidanceCacheFormatStep().detect(_handle(tmp_path).view())
        assert len(findings) == 1
        assert findings[0].auto_migratable is False
        assert findings[0].blocks_commit is True
        assert "newer" in findings[0].description

    def test_headerless_document_blocks_commit(self, tmp_path: Path) -> None:
        (tmp_path / "a.guidance.yaml").write_text("meta_ontologies: {}\n", encoding="utf-8")
        findings = GuidanceCacheFormatStep().detect(_handle(tmp_path).view())
        assert len(findings) == 1
        assert findings[0].blocks_commit is True


class TestApply:
    def test_patches_header_and_preserves_body(self, tmp_path: Path) -> None:
        doc = tmp_path / "archimate-4.guidance.yaml"
        doc.write_text(_V1_DOC, encoding="utf-8")
        applied = _run(tmp_path)
        assert len(applied) == 1 and applied[0].outcome == "applied"
        text = doc.read_text(encoding="utf-8")
        assert f"guidance_format: {SUPPORTED_GUIDANCE_FORMAT}" in text
        assert "guidance_format: 1" not in text
        # Body untouched — a minimal header patch, not a re-serialization.
        assert "goal: {create_when: cw}" in text

    def test_idempotent_second_run_is_noop(self, tmp_path: Path) -> None:
        doc = tmp_path / "a.guidance.yaml"
        doc.write_text(_V1_DOC, encoding="utf-8")
        _run(tmp_path)
        applied_again = _run(tmp_path)
        assert applied_again == []

    def test_newer_document_is_not_rewritten(self, tmp_path: Path) -> None:
        doc = tmp_path / "a.guidance.yaml"
        doc.write_text("guidance_format: 99\n", encoding="utf-8")
        _run(tmp_path)
        assert doc.read_text(encoding="utf-8") == "guidance_format: 99\n"
