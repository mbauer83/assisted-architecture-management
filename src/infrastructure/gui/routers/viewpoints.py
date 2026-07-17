"""Read-only REST endpoints for execution, projection, and diagram previews."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException

from src.application.runtime_catalogs import RuntimeCatalogs
from src.application.viewpoints.artifact_projection import project_artifact_by_frontmatter
from src.application.viewpoints.derived_connection_records import derived_connection_record
from src.application.viewpoints.evaluate_viewpoint import (
    UnknownViewpointSlugError,
    ViewpointExecutionRequest,
    ViewpointExecutionTimeoutError,
    evaluate_viewpoint,
    project_viewpoint_repository,
)
from src.application.viewpoints.parameter_binding import ViewpointParameterError
from src.application.viewpoints.registry_snapshot import build_registry_snapshot
from src.config.viewpoints_settings import (
    viewpoints_derivation_max_hops,
    viewpoints_derivation_max_relationships,
    viewpoints_derivation_time_budget_seconds,
    viewpoints_execution_max_entities,
    viewpoints_execution_timeout_seconds,
)
from src.domain.relationship_reachability import DerivationLimitError, is_derived_connection_id
from src.domain.viewpoint_binding_evaluation import BindingCardinalityError
from src.domain.viewpoint_condition_validation import RegistrySnapshot
from src.domain.viewpoint_query_parsing import query_from_mapping
from src.domain.viewpoints import TargetKind
from src.infrastructure.gui.routers import state as s
from src.infrastructure.gui.routers._diagram_selection import resolve_diagram_selection
from src.infrastructure.gui.routers._viewpoint_freshness import fresh_viewpoints_runtime_catalogs_dependency

router = APIRouter()

# Fixed notation for unpersisted diagram previews. Styling overlays are applied by the
# client to the returned SVG, so this endpoint returns unstyled notation only.
_AD_HOC_DIAGRAM_TYPE = "archimate-layered"


def _parameter_error(exc: ViewpointParameterError) -> HTTPException:
    return HTTPException(400, {"code": exc.code, "path": f"parameters/{exc.parameter}", "message": str(exc)})


def _execution_error(code: str, message: str, *, path: str = "query") -> HTTPException:
    return HTTPException(400, {"code": code, "path": path, "message": message})


def _registry_snapshot(catalogs: RuntimeCatalogs, repo_roots: list[Path]) -> RegistrySnapshot:
    return build_registry_snapshot(
        catalogs,
        repo_roots,
        derivation_max_hops=viewpoints_derivation_max_hops(),
        derivation_max_relationships=viewpoints_derivation_max_relationships(),
        derivation_time_budget_seconds=viewpoints_derivation_time_budget_seconds(),
    )


def _definition_label_attribute(slug: str | None, catalogs: RuntimeCatalogs) -> str | None:
    """The saved definition's ``label_attribute`` display option, when executing by slug —
    an ad-hoc query has no persisted presentation to read one from."""
    if slug is None:
        return None
    definition = catalogs.viewpoints.get(slug)
    if definition is None or definition.presentation is None:
        return None
    value = definition.presentation.display_options.get("label_attribute")
    return value if isinstance(value, str) and value else None


@router.post("/api/viewpoints/execute")
def execute_viewpoint(
    slug: Annotated[str | None, Body()] = None,
    query: Annotated[dict[str, object] | None, Body()] = None,
    limit: Annotated[int | None, Body()] = None,
    parameters: Annotated[dict[str, object] | None, Body()] = None,
    catalogs: RuntimeCatalogs = Depends(fresh_viewpoints_runtime_catalogs_dependency),
) -> dict[str, object]:
    """Execute a viewpoint by ``slug`` (catalog definition) or ``query`` (ad-hoc, no
    presentation/styling/column parameters. Its response matches the MCP result."""
    if (slug is None) == (query is None):
        raise HTTPException(400, "exactly one of 'slug' or 'query' must be provided")

    parsed_query = query_from_mapping(query, label="query") if query is not None else None
    request = ViewpointExecutionRequest(slug=slug, query=parsed_query, limit=limit, parameters=parameters)
    repo = s.get_repo()
    registries = _registry_snapshot(catalogs, repo.repo_roots)
    max_entities = viewpoints_execution_max_entities()
    try:
        result = evaluate_viewpoint(
            request,
            catalog=catalogs.viewpoints,
            read_access=repo,
            registries=registries,
            index_generation=repo.read_model_version().generation,
            max_entities=max_entities,
            default_limit=max_entities,
            timeout_seconds=viewpoints_execution_timeout_seconds(),
        )
    except UnknownViewpointSlugError as exc:
        raise HTTPException(400, str(exc)) from exc
    except ViewpointExecutionTimeoutError as exc:
        raise HTTPException(504, {"code": "execution-timeout", "path": "query", "message": str(exc)}) from exc
    except ViewpointParameterError as exc:
        raise _parameter_error(exc) from exc
    except BindingCardinalityError as exc:
        raise _execution_error(exc.code, str(exc)) from exc
    except DerivationLimitError as exc:
        raise _execution_error("derivation-limit", str(exc)) from exc
    return asdict(result)


@router.post("/api/viewpoints/execute-projection")
def execute_viewpoint_projection(
    slug: Annotated[str | None, Body()] = None,
    query: Annotated[dict[str, object] | None, Body()] = None,
    parameters: Annotated[dict[str, object] | None, Body()] = None,
    catalogs: RuntimeCatalogs = Depends(fresh_viewpoints_runtime_catalogs_dependency),
) -> dict[str, object]:
    """Return GUI projection items with style tokens for the selected population."""
    if (slug is None) == (query is None):
        raise HTTPException(400, "exactly one of 'slug' or 'query' must be provided")
    parsed_query = query_from_mapping(query, label="query") if query is not None else None
    repo = s.get_repo()
    registries = _registry_snapshot(catalogs, repo.repo_roots)
    index_generation = repo.read_model_version().generation
    try:
        projection = project_viewpoint_repository(
            slug,
            parsed_query,
            catalog=catalogs.viewpoints,
            read_access=repo,
            registries=registries,
            parameters=parameters,
        )
    except UnknownViewpointSlugError as exc:
        raise HTTPException(400, str(exc)) from exc
    except ViewpointParameterError as exc:
        raise _parameter_error(exc) from exc
    except BindingCardinalityError as exc:
        raise _execution_error(exc.code, str(exc)) from exc
    except DerivationLimitError as exc:
        raise _execution_error("derivation-limit", str(exc)) from exc
    # Same provenance contract as /execute: consumers correlating an execution result
    # with its styled projection can verify both came from the same model snapshot.
    return {"applied": True, "index_generation": index_generation, **asdict(projection)}


@router.post("/api/viewpoints/execute-diagram")
def execute_viewpoint_diagram(
    slug: Annotated[str | None, Body()] = None,
    query: Annotated[dict[str, object] | None, Body()] = None,
    parameters: Annotated[dict[str, object] | None, Body()] = None,
    catalogs: RuntimeCatalogs = Depends(fresh_viewpoints_runtime_catalogs_dependency),
) -> dict[str, object]:
    """Render an unpersisted ArchiMate diagram for the evaluated population."""
    if (slug is None) == (query is None):
        raise HTTPException(400, "exactly one of 'slug' or 'query' must be provided")
    parsed_query = query_from_mapping(query, label="query") if query is not None else None
    repo = s.get_repo()
    repo_root = s.maybe_engagement_root()
    if repo_root is None:
        raise HTTPException(500, "Repository not initialized")
    registries = _registry_snapshot(catalogs, repo.repo_roots)
    max_entities = viewpoints_execution_max_entities()
    request = ViewpointExecutionRequest(slug=slug, query=parsed_query, limit=max_entities, parameters=parameters)
    try:
        result = evaluate_viewpoint(
            request,
            catalog=catalogs.viewpoints,
            read_access=repo,
            registries=registries,
            index_generation=repo.read_model_version().generation,
            max_entities=max_entities,
            default_limit=max_entities,
            timeout_seconds=viewpoints_execution_timeout_seconds(),
        )
    except UnknownViewpointSlugError as exc:
        raise HTTPException(400, str(exc)) from exc
    except ViewpointExecutionTimeoutError as exc:
        raise HTTPException(504, {"code": "execution-timeout", "path": "query", "message": str(exc)}) from exc
    except ViewpointParameterError as exc:
        raise _parameter_error(exc) from exc
    except BindingCardinalityError as exc:
        raise _execution_error(exc.code, str(exc)) from exc
    except DerivationLimitError as exc:
        raise _execution_error("derivation-limit", str(exc)) from exc

    from src.application.artifact_parsing import normalize_puml_alias
    from src.infrastructure.rendering.diagram_builder import generate_archimate_puml_body, render_puml_svg

    modeled_connection_ids = [cid for cid in result.connection_ids if not is_derived_connection_id(cid)]
    entities, connections, _, _ = resolve_diagram_selection(repo, list(result.entity_ids), modeled_connection_ids)
    derived_records = [
        derived_connection_record(summary) for summary in result.connections if summary.certainty is not None
    ]
    puml = generate_archimate_puml_body(
        result.slug or "viewpoint-preview",
        entities,
        [*connections, *derived_records],
        diagram_type=_AD_HOC_DIAGRAM_TYPE,
        repo_root=repo_root,
        label_attribute=_definition_label_attribute(slug, catalogs),
    )
    svg, render_warnings = render_puml_svg(puml, repo_root, _AD_HOC_DIAGRAM_TYPE)
    # The rendered SVG's node/edge ids are PlantUML aliases (`normalize_puml_alias`'d from
    # each entity's `display_alias`), never the raw artifact id — the client-side click-to-
    # select overlay needs this mapping to resolve SVG elements back to artifact ids, the
    # same way a real persisted diagram's viewer already does from its own diagram_entities.
    entity_aliases = {e.artifact_id: normalize_puml_alias(e.display_alias) for e in entities if e.display_alias}
    return {"svg": svg, "warnings": [*result.warnings, *render_warnings], "entity_aliases": entity_aliases}


@router.get("/api/diagrams/{artifact_id}/viewpoint-projection")
def get_diagram_viewpoint_projection(
    artifact_id: str,
    catalogs: RuntimeCatalogs = Depends(fresh_viewpoints_runtime_catalogs_dependency),
) -> dict[str, object]:
    """Return the optional saved viewpoint projection for one diagram or matrix."""
    repo = s.get_repo()
    diag_rec = repo.get_diagram(artifact_id)
    if diag_rec is None:
        raise HTTPException(404, f"Diagram not found: {artifact_id!r}")
    target_kind: TargetKind = "matrix" if diag_rec.diagram_type == "matrix" else "diagram"
    module = catalogs.diagram_types.find_diagram_type(diag_rec.diagram_type if target_kind == "diagram" else "matrix")
    if module is None:
        raise HTTPException(404, f"Diagram type not found: {diag_rec.diagram_type!r}")
    _, registry, _ = s.get_write_deps()
    registries = _registry_snapshot(catalogs, repo.repo_roots)
    projection = project_artifact_by_frontmatter(
        diag_rec.extra,
        target_kind=target_kind,
        target_id=diag_rec.artifact_id,
        catalog=catalogs.viewpoints,
        module=module,
        entity_type_infos=catalogs.ontology.all_entity_types(),
        default_enforcement=catalogs.viewpoint_enforcement,
        registry=registry,
        registries=registries,
    )
    if projection is None:
        return {"applied": False}
    return {"applied": True, **asdict(projection)}
