"""The registered-step catalog for `arch-repair upgrade`.

One process-wide registry, populated explicitly at the bottom of this module (composition-
root style, matching `_ALL_ONTOLOGY_MODULES` in `app_bootstrap.py`) rather than by
self-registration on import — no import-order fragility, and a test can build a fresh
`StepRegistry()` with any subset of steps without touching module state. `DEFAULT_REGISTRY`
is what the CLI uses by default.
"""

from __future__ import annotations

from collections.abc import Mapping

from src.application.repository_upgrade.ports import UpgradeStep
from src.application.repository_upgrade.steps.connection_metadata_scan import ConnectionMetadataScanStep
from src.application.repository_upgrade.steps.group_meta_ontology_rename import GroupMetaOntologyRenameStep
from src.application.repository_upgrade.steps.multiplicity_rename import MultiplicityRenameStep
from src.application.repository_upgrade.steps.schema_file_scan import SchemaFileScanStep
from src.application.repository_upgrade.steps.specialization_declaration_scan import (
    SpecializationDeclarationScanStep,
)
from src.application.repository_upgrade.steps.unrecognized_structure import UnrecognizedStructureScanStep
from src.application.repository_upgrade.steps.viewpoint_application_scan import ViewpointApplicationScanStep
from src.application.repository_upgrade.steps.viewpoint_declaration_scan import ViewpointDeclarationScanStep
from src.application.repository_upgrade.steps.viewpoint_incident_traversal_stamp import (
    ViewpointIncidentTraversalStampStep,
)
from src.application.repository_upgrade.steps.viewpoint_selection_mode_stamp import (
    SelectionMode,
    ViewpointSelectionModeStampStep,
)
from src.application.repository_upgrade.steps.viewpoint_style_value_upgrade import ViewpointStyleValueUpgradeStep
from src.domain.repository_upgrade import StepIdentity

FORMAT_CONTRACT_VERSION = "1"


class StepRegistry:
    def __init__(self) -> None:
        self._steps: dict[str, UpgradeStep] = {}

    def register(self, step: UpgradeStep) -> None:
        if step.id in self._steps:
            raise ValueError(f"Upgrade step id already registered: {step.id!r}")
        self._steps[step.id] = step

    def steps(self) -> tuple[UpgradeStep, ...]:
        return tuple(self._steps.values())

    def step_identities(self) -> tuple[StepIdentity, ...]:
        return tuple(StepIdentity(id=s.id, version=s.version) for s in self._steps.values())


def build_registry(selection_resolutions: Mapping[str, SelectionMode] | None = None) -> StepRegistry:
    """The full step catalog. ``selection_resolutions`` parameterizes the
    selection-mode stamp with the operator's ``--resolve-selection`` choices."""
    registry = StepRegistry()
    registry.register(MultiplicityRenameStep())
    registry.register(GroupMetaOntologyRenameStep())
    registry.register(UnrecognizedStructureScanStep())
    registry.register(SpecializationDeclarationScanStep())
    registry.register(ViewpointDeclarationScanStep())
    registry.register(ViewpointStyleValueUpgradeStep())
    registry.register(ViewpointIncidentTraversalStampStep())
    registry.register(ViewpointSelectionModeStampStep(selection_resolutions))
    registry.register(SchemaFileScanStep())
    registry.register(ConnectionMetadataScanStep())
    registry.register(ViewpointApplicationScanStep())
    return registry


DEFAULT_REGISTRY = build_registry()
