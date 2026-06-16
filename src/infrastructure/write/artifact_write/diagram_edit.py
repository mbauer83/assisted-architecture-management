"""Diagram editing operations."""

from collections.abc import Callable
from pathlib import Path

from src.application.modeling.artifact_write import format_diagram_puml
from src.application.modeling.artifact_write_layout import optimize_puml_layout
from src.application.verification.artifact_verifier import ArtifactVerifier
from src.config.repo_paths import DIAGRAM_CATALOG, DIAGRAMS

from .boundary import assert_engagement_write_root, today_iso
from .coerce import as_optional_str_list
from .diagram_references import (
    _collect_diagram_renderer_references,
    _infer_reference_ids_from_puml,
    _merge_reference_ids,
    _prepare_diagram_puml_body,
    _prune_unknown_references,
)
from .diagram_render import _render_diagram_entities_puml, _render_diagram_png, _render_diagram_svg
from .parse_existing import parse_diagram_file
from .types import WriteResult
from .verify import verify_content_in_temp_path


def _verification_to_dict(path: Path, res) -> dict[str, object]:
    return {
        "path": str(path),
        "file_type": "diagram",
        "valid": res.valid,
        "issues": [
            {"severity": i.severity, "code": i.code, "message": i.message, "location": i.location} for i in res.issues
        ],
    }


_EDGE_LABELS_UNSET = object()


def edit_diagram(
    *,
    repo_root: Path,
    verifier: ArtifactVerifier,
    clear_repo_caches: Callable[[Path], None],
    artifact_id: str,
    puml: str | None = None,
    name: str | None = None,
    keywords: list[str] | None = ...,  # type: ignore[assignment]
    diagram_entities: dict[str, object] | None = None,
    diagram_connections: list[dict[str, object]] | None = None,
    entity_ids_used: list[str] | None = None,
    connection_ids_used: list[str] | None = None,
    view_derivations: list[dict[str, object]] | None = None,
    bindings: list[dict[str, object]] | None = None,
    replace_bindings: bool = False,
    version: str | None = None,
    status: str | None = None,
    edge_labels: dict[str, str | None] | None = _EDGE_LABELS_UNSET,  # type: ignore[assignment]
    dry_run: bool,
) -> WriteResult:
    """Edit an existing diagram file.

    If ``puml`` is provided, replaces the PUML body and re-runs auto-layout.
    Other fields (name, keywords, version, status) update frontmatter only.
    Always re-verifies and re-renders PNG on successful write.
    """
    from src.application.modeling.binding_normalize import normalize_bindings, strip_diagram_shorthand
    from src.domain.bindings import bindings_to_raw

    assert_engagement_write_root(repo_root)
    warnings: list[str] = []

    diagram_path = repo_root / DIAGRAM_CATALOG / DIAGRAMS / f"{artifact_id}.puml"
    if not diagram_path.exists():
        raise ValueError(f"Diagram '{artifact_id}' not found at {diagram_path}")

    parsed = parse_diagram_file(diagram_path)
    fm = parsed.frontmatter

    eff_name = name if name is not None else str(fm.get("name", ""))
    eff_version = version if version is not None else str(fm.get("version", "0.1.0"))
    eff_status = status if status is not None else str(fm.get("status", "draft"))
    eff_keywords = keywords if keywords is not ... else as_optional_str_list(fm.get("keywords"))
    eff_diagram_entities = diagram_entities if diagram_entities is not None else fm.get("diagram-entities")
    eff_diagram_connections = diagram_connections if diagram_connections is not None else fm.get("connections")
    diagram_type = str(fm.get("diagram-type", "archimate"))
    eff_entity_ids_used = (
        entity_ids_used if entity_ids_used is not None else as_optional_str_list(fm.get("entity-ids-used"))
    )
    eff_connection_ids_used = (
        connection_ids_used if connection_ids_used is not None else as_optional_str_list(fm.get("connection-ids-used"))
    )

    # view_derivations: caller replaces; keep existing from file if caller omits
    _raw_vd = fm.get("view_derivations")
    existing_vd = [v for v in _raw_vd if isinstance(v, dict)] if isinstance(_raw_vd, list) else []
    eff_view_derivations: list[dict[str, object]] | None = (
        view_derivations if view_derivations is not None else (existing_vd or None)
    )

    # Bindings: existing from file + new from caller, then normalize shorthand from entities
    _raw_b = fm.get("bindings")
    existing_raw_bindings = [b for b in _raw_b if isinstance(b, dict)] if isinstance(_raw_b, list) else []
    merged_raw_bindings = list(bindings or []) if replace_bindings else existing_raw_bindings + list(bindings or [])
    norm_bindings = normalize_bindings(
        eff_diagram_entities if isinstance(eff_diagram_entities, dict) else None,
        merged_raw_bindings,
    )
    clean_entities = strip_diagram_shorthand(
        eff_diagram_entities if isinstance(eff_diagram_entities, dict) else None
    )

    norm_bindings_raw = bindings_to_raw(norm_bindings)

    # Edge-label overrides: merge caller-supplied delta into existing map.
    # A None value for a key removes that key (single-key clear without full replacement).
    _raw_el = fm.get("edge-labels")
    existing_edge_labels: dict[str, str] = dict(_raw_el) if isinstance(_raw_el, dict) else {}
    if edge_labels is _EDGE_LABELS_UNSET:
        eff_edge_labels: dict[str, str] | None = existing_edge_labels or None
    else:
        merged: dict[str, str] = dict(existing_edge_labels)
        for k, v in (edge_labels or {}).items():
            if v is None:
                merged.pop(k, None)
            else:
                merged[k] = v
        eff_edge_labels = merged or None

    # Determine PUML body; inject _scope_entity_id from scoped-by binding so the
    # C4 renderer uses model-backed mode for diagrams that previously used _scope_entity_id.
    if eff_diagram_entities is not None and isinstance(eff_diagram_entities, dict) and puml is None:
        scope_eid = next(
            (b.target.entity_id for b in norm_bindings
             if b.correspondence_kind == "scoped-by" and b.subject.kind == "diagram"
             and b.target.entity_id),
            None,
        )
        render_entities: dict[str, object] = dict(eff_diagram_entities)
        if scope_eid and "_scope_entity_id" not in render_entities:
            render_entities["_scope_entity_id"] = scope_eid
        eff_diagram_conns = eff_diagram_connections if isinstance(eff_diagram_connections, list) else None
        puml_body = _render_diagram_entities_puml(
            diagram_type,
            eff_name,
            render_entities,
            eff_diagram_conns,
            repo_root,
            edge_labels=eff_edge_labels,
        )
        collected_entity_ids, collected_connection_ids = _collect_diagram_renderer_references(
            diagram_type,
            repo_root,
            render_entities,
            eff_diagram_conns,
            bindings=norm_bindings_raw,
        )
        eff_entity_ids_used = _merge_reference_ids(eff_entity_ids_used, collected_entity_ids)
        eff_connection_ids_used = _merge_reference_ids(eff_connection_ids_used, collected_connection_ids)
    elif puml is not None:
        puml_body = puml.strip("\n") + "\n"
        puml_body = _prepare_diagram_puml_body(puml_body, repo_root, diagram_type)
        # optimize_puml_layout is idempotent: it skips when [hidden] links are
        # already present, so user-provided explicit hidden chains are preserved.
        puml_body = optimize_puml_layout(puml_body)
        inferred_entity_ids, inferred_connection_ids = _infer_reference_ids_from_puml(repo_root, puml_body)
        eff_entity_ids_used = _merge_reference_ids(eff_entity_ids_used, inferred_entity_ids)
        eff_connection_ids_used = _merge_reference_ids(eff_connection_ids_used, inferred_connection_ids)
    else:
        puml_body = parsed.puml_body

    # Drop references to entities/connections that no longer exist (e.g. after a rename or
    # delete) so a stale cached reference cannot leave the diagram permanently unwritable.
    eff_entity_ids_used, eff_connection_ids_used = _prune_unknown_references(
        verifier.registry, eff_entity_ids_used, eff_connection_ids_used
    )

    content = format_diagram_puml(
        artifact_id=artifact_id,
        diagram_type=diagram_type,
        name=eff_name,
        version=eff_version,
        status=eff_status,
        last_updated=today_iso(),
        keywords=eff_keywords,
        diagram_entities=clean_entities,
        diagram_connections=eff_diagram_connections if isinstance(eff_diagram_connections, list) else None,
        entity_ids_used=eff_entity_ids_used,
        connection_ids_used=eff_connection_ids_used,
        view_derivations=eff_view_derivations,
        bindings=bindings_to_raw(norm_bindings) if norm_bindings else None,
        edge_labels=eff_edge_labels or None,
        puml_body=puml_body,
    )

    if dry_run:
        res = verify_content_in_temp_path(
            verifier=verifier,
            file_type="diagram",
            desired_name=diagram_path.name,
            content=content,
            support_repo_root=repo_root,
        )
        return WriteResult(
            wrote=False,
            path=diagram_path,
            artifact_id=artifact_id,
            content=content,
            warnings=warnings,
            verification=_verification_to_dict(diagram_path, res),
        )

    prev = diagram_path.read_text(encoding="utf-8")
    diagram_path.write_text(content, encoding="utf-8")

    res = verifier.verify_diagram_file(diagram_path)
    if not res.valid:
        diagram_path.write_text(prev, encoding="utf-8")
        return WriteResult(
            wrote=False,
            path=diagram_path,
            artifact_id=artifact_id,
            content=content,
            warnings=warnings,
            verification=_verification_to_dict(diagram_path, res),
        )

    png_path = _render_diagram_png(diagram_path, warnings)
    if png_path:
        warnings.append(f"Rendered PNG: {png_path}")
    _render_diagram_svg(diagram_path, warnings)

    clear_repo_caches(diagram_path)
    return WriteResult(
        wrote=True,
        path=diagram_path,
        artifact_id=artifact_id,
        content=None,
        warnings=warnings,
        verification=_verification_to_dict(diagram_path, res),
    )


def set_diagram_edge_label(
    *,
    repo_root: Path,
    verifier: ArtifactVerifier,
    clear_repo_caches: Callable[[Path], None],
    artifact_id: str,
    edge_key: str,
    label: str | None,
    dry_run: bool,
) -> WriteResult:
    """Set or clear a per-diagram edge-label override for a single edge.

    ``edge_key`` is ``"{src_alias}:{tgt_alias}"`` from the rendered PUML.
    ``label=None`` removes the override, reverting to the derived label.
    """
    diagram_path = repo_root / DIAGRAM_CATALOG / DIAGRAMS / f"{artifact_id}.puml"
    if not diagram_path.exists():
        raise ValueError(f"Diagram '{artifact_id}' not found at {diagram_path}")

    parsed = parse_diagram_file(diagram_path)
    raw_el = parsed.frontmatter.get("edge-labels")
    current: dict[str, str | None] = dict(raw_el) if isinstance(raw_el, dict) else {}

    if label is None:
        current.pop(edge_key, None)
    else:
        current[edge_key] = label

    return edit_diagram(
        repo_root=repo_root,
        verifier=verifier,
        clear_repo_caches=clear_repo_caches,
        artifact_id=artifact_id,
        edge_labels=current,
        dry_run=dry_run,
    )
