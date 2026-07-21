"""Operational migration: bring an already-imported guidance cache to the current format.

Guidance is imported latest-format-only; an older imported cache is migrated OFFLINE here
(``arch-repair upgrade``, system down) rather than re-imported blindly. The migration is a
minimal header patch — ``guidance_format`` bumped to the supported version in each cached
document — because the current format is a structural superset of the older type slots. New
broader-level (domain) context is never fabricated by the migrator; it arrives when the owner
re-imports the restructured guidance source, which this step recommends. A document whose
format is unreadable or NEWER than supported blocks the commit rather than being rewritten.
"""

from __future__ import annotations

import re

from src.application.deployment_upgrade.ports import (
    OperationalTargetUnitOfWork,
    OperationalTargetView,
)
from src.domain.operational_upgrade import TargetKind
from src.domain.repository_upgrade import AppliedFinding, UpgradeFinding

SUPPORTED_GUIDANCE_FORMAT = 2
_FORMAT_RE = re.compile(r"^guidance_format:[ \t]*(\d+)[ \t]*$", re.MULTILINE)
_OUTDATED_PREFIX = "guidance-format-outdated:"


class GuidanceCacheFormatStep:
    """Bumps each cached guidance document to the supported format; binds to the deployment
    guidance-cache target discovered by arch-repair (``~/.config/arch-repo/guidance-cache/`` by
    default)."""

    id = "guidance-0002-format-v2"
    version = SUPPORTED_GUIDANCE_FORMAT
    kind: TargetKind = "guidance_cache"
    description = "Guidance cache format → 2 (header patch; re-import to add domain context)"

    def detect(self, view: OperationalTargetView) -> list[UpgradeFinding]:
        findings: list[UpgradeFinding] = []
        for name in view.list_files("*.guidance.yaml"):
            content = view.read_text(name)
            if content is None:
                continue
            match = _FORMAT_RE.search(content)
            if match is None:
                findings.append(self._blocking(name, f"{name}: no readable guidance_format header"))
                continue
            current = int(match.group(1))
            if current == SUPPORTED_GUIDANCE_FORMAT:
                continue
            if current > SUPPORTED_GUIDANCE_FORMAT:
                findings.append(self._blocking(
                    name,
                    f"{name}: guidance_format {current} is newer than the supported "
                    f"{SUPPORTED_GUIDANCE_FORMAT}; wrote by a newer release",
                    instructions="Upgrade the software to a release that supports this format.",
                ))
                continue
            findings.append(UpgradeFinding(
                step_id=self.id,
                finding_id=f"{_OUTDATED_PREFIX}{name}",
                location=name,
                description=(
                    f"{name}: guidance_format {current}; the current format is "
                    f"{SUPPORTED_GUIDANCE_FORMAT}"
                ),
                severity="warning",
                auto_migratable=True,
                rewrite_summary=(
                    f"patch the guidance_format header to {SUPPORTED_GUIDANCE_FORMAT}; re-import the "
                    "guidance source to populate broader-level (domain) context"
                ),
            ))
        return findings

    def _blocking(self, name: str, description: str, *, instructions: str | None = None) -> UpgradeFinding:
        return UpgradeFinding(
            step_id=self.id,
            finding_id=f"guidance-format-unmigratable:{name}",
            location=name,
            description=description,
            severity="error",
            auto_migratable=False,
            manual_instructions=instructions or "Re-import this guidance source with arch-import-guidance.",
            blocks_commit=True,
        )

    def apply(
        self,
        view: OperationalTargetView,
        uow: OperationalTargetUnitOfWork,
        findings: list[UpgradeFinding],
    ) -> list[AppliedFinding]:
        applied: list[AppliedFinding] = []
        for finding in findings:
            if not finding.finding_id.startswith(_OUTDATED_PREFIX):
                continue
            content = view.read_text(finding.location)
            if content is None:
                continue
            patched = _FORMAT_RE.sub(f"guidance_format: {SUPPORTED_GUIDANCE_FORMAT}", content, count=1)
            uow.write_text(finding.location, patched)
            applied.append(AppliedFinding(
                finding=finding,
                outcome="applied",
                detail=(
                    f"guidance_format patched to {SUPPORTED_GUIDANCE_FORMAT}; re-import to add "
                    "domain-level context"
                ),
            ))
        return applied
