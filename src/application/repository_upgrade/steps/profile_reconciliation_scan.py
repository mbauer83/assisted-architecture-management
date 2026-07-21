"""Reconciliation reporter for named attribute-profile conflicts (WU-R1).

Detect-only and non-destructive — mirroring ``DefaultSchemataEnsureStep``'s contract, it
never rewrites operator content. For every specialization the repo declares that binds
named profiles, it resolves the effective schema and reports each incompatible-type
conflict as a quarantined ``(entity-type, specialization)`` pair (the profiles/field/types
are named in the merge message). Proposed resolutions (rename / align-type / unbind, and
safe auto-migration) are WU-R2.

Content-version DRIFT (a shipped profile advanced past a repo customisation — what P4's
per-profile ``version`` exists for) is NOT reported here yet: no reusable profiles are
shipped, so there is no baseline to drift from. When shipped profiles land, the drift
comparison activates by giving this step the shipped registry (the same way
``known_entity_type_names`` reaches a step — an ``RepoUpgradeView`` property fed by the
module registry through the adapter).
"""

from __future__ import annotations

import yaml  # type: ignore[import-untyped]

from src.application.artifact_schema import compute_effective_attribute_schema
from src.application.repository_upgrade.ports import RepoUpgradeView, RepoUpgradeWriter
from src.domain.profile_registry import ProfileRegistry
from src.domain.repository_upgrade import AppliedFinding, ScannedSurface, UpgradeFinding
from src.domain.specializations import SpecializationCatalog, specialization_catalog_from_mapping

_SPECIALIZATIONS = ".arch-repo/specializations.yaml"


class ProfileReconciliationScanStep:
    id = "profile-reconciliation-scan"
    version = 1
    description = "Report attribute-profile conflicts (quarantined entity-type/specialization pairs)"
    scanned_surface: ScannedSurface = "profiles"

    def detect(self, view: RepoUpgradeView) -> list[UpgradeFinding]:
        specializations = _repo_specializations(view)
        if specializations is None:
            return []
        findings: list[UpgradeFinding] = []
        for entry in specializations.entries:
            if entry.concept_kind != "entity" or not entry.bound_profiles:
                continue
            _schema, conflicts = compute_effective_attribute_schema(
                view.root,
                entry.parent_type,
                [entry.slug],
                specialization_catalog=specializations,
                profile_registry=ProfileRegistry.empty(),  # repo profiles.yaml is read internally
            )
            for index, message in enumerate(conflicts):
                pair = f"{entry.parent_type}/{entry.slug}"
                findings.append(
                    UpgradeFinding(
                        step_id=self.id,
                        finding_id=f"profile-conflict:{pair}:{index}",
                        location=_SPECIALIZATIONS,
                        description=f"{pair} is quarantined by an attribute-profile conflict — {message}",
                        severity="warning",
                        auto_migratable=False,
                        manual_instructions=(
                            "Resolve the conflicting named profiles (rename the attribute, align its "
                            "type, or unbind one profile from this specialization), then re-run. Entities "
                            f"of {pair} cannot be created or edited until the conflict is cleared."
                        ),
                    )
                )
        return findings

    def apply(
        self, view: RepoUpgradeView, writer: RepoUpgradeWriter, findings: list[UpgradeFinding]
    ) -> list[AppliedFinding]:
        return []  # report-only: every finding is manual (auto_migratable=False)


def _repo_specializations(view: RepoUpgradeView) -> SpecializationCatalog | None:
    text = view.read_text(_SPECIALIZATIONS)
    if text is None:
        return None
    try:
        loaded: object = yaml.safe_load(text) or {}
    except yaml.YAMLError:
        return None  # a malformed specializations file is the specialization scan's finding, not ours
    if not isinstance(loaded, dict):
        return None
    return specialization_catalog_from_mapping(loaded, module_alias="repo")
