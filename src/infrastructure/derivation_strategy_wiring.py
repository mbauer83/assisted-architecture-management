"""Composition-root wiring for derivation strategies whose ``derive_fn`` needs more than
the bare ``ModelQuery``/``SourceModelSnapshot`` a strategy normally sees — currently just
``viewpoint_execution``, which needs a ``ViewpointCatalog`` and a ``RegistrySnapshot``,
both built from real repo-root paths. Those roots travel as plain data in the strategy's
own ``params["repo_roots"]`` (set at generation time), never through the shared
``ModelQuery``/``DeriveFn`` contract every other strategy also implements against.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from src.application.artifact_repository import ArtifactRepository
from src.application.derivation.types import CandidateSet, ModelQuery
from src.application.derivation.viewpoint_execution import evaluate_candidates
from src.application.runtime_catalogs import RuntimeCatalogs
from src.application.viewpoints.registry_snapshot import build_registry_snapshot
from src.config.settings import (
    viewpoints_execution_default_entity_limit_mcp,
    viewpoints_execution_max_entities,
    viewpoints_execution_timeout_seconds,
)
from src.domain.view_derivations import SourceModelSnapshot
from src.infrastructure.artifact_index import shared_artifact_index
from src.infrastructure.viewpoint_declarations import load_effective_viewpoint_catalog


@lru_cache(maxsize=1)
def _cached_runtime_catalogs() -> RuntimeCatalogs:
    from src.infrastructure.app_bootstrap import build_runtime_catalogs, get_module_registry  # noqa: PLC0415

    return build_runtime_catalogs(get_module_registry())


def _repo_roots(params: dict[str, object]) -> list[Path]:
    raw = params.get("repo_roots")
    return [Path(str(root)) for root in raw] if isinstance(raw, list) else []


def viewpoint_execution_derive(
    params: dict[str, object],
    snapshot: SourceModelSnapshot,
    query: ModelQuery,
) -> CandidateSet:
    roots = _repo_roots(params)
    read_access = ArtifactRepository(shared_artifact_index(roots))
    runtime_catalogs = _cached_runtime_catalogs()
    return evaluate_candidates(
        params,
        catalog=load_effective_viewpoint_catalog(roots),
        read_access=read_access,
        registries=build_registry_snapshot(runtime_catalogs, roots),
        max_entities=viewpoints_execution_max_entities(),
        default_limit=viewpoints_execution_default_entity_limit_mcp(),
        timeout_seconds=viewpoints_execution_timeout_seconds(),
    )
