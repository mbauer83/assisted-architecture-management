import re
from collections.abc import Callable
from pathlib import Path

from src.application.modeling.artifact_write import (
    DiagramConnectionInferenceMode,
    format_diagram_puml,
    generate_diagram_id,
)
from src.application.modeling.artifact_write_layout import optimize_puml_layout
from src.application.verification.artifact_verifier import ArtifactVerifier
from src.application.verification.artifact_verifier_types import ENTITY_ID_RE
from src.application.repo_path_helpers import diagram_source_root
from src.domain.groups import UNCATEGORIZED

from ._artifact_deduplication import extract_friendly_slug, get_repository, validate_diagram_unique
from .boundary import assert_engagement_write_root
from .diagram_references import (
    _collect_diagram_renderer_references,
    _infer_reference_ids_from_puml,
    _merge_reference_ids,
    _prepare_diagram_puml_body,
)
from .diagram_render import _render_diagram_entities_puml, _render_diagram_png, _render_diagram_svg
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


def create_diagram(
    *,
    repo_root: Path,
    verifier: ArtifactVerifier,
    clear_repo_caches: Callable[[Path], None],
    diagram_type: str,
    name: str,
    puml: str,
    artifact_id: str | None,
    keywords: list[str] | None = None,
    diagram_entities: dict[str, object] | None = None,
    diagram_connections: list[dict[str, object]] | None = None,
    entity_ids_used: list[str] | None = None,
    connection_ids_used: list[str] | None = None,
    view_derivations: list[dict[str, object]] | None = None,
    bindings: list[dict[str, object]] | None = None,
    version: str,
    status: str,
    last_updated: str | None,
    connection_inference: DiagramConnectionInferenceMode = "none",
    auto_include_stereotypes: bool = True,
    dry_run: bool,
    group: str = UNCATEGORIZED,
) -> WriteResult:
    assert_engagement_write_root(repo_root)

    from src.application.modeling.binding_normalize import normalize_bindings, strip_diagram_shorthand
    from src.domain.bindings import bindings_to_raw

    effective_id = artifact_id
    warnings: list[str] = []

    from .boundary import today_iso

    last = last_updated or today_iso()

    norm_bindings = normalize_bindings(diagram_entities, bindings)
    clean_entities = strip_diagram_shorthand(diagram_entities)
    norm_bindings_raw = bindings_to_raw(norm_bindings)

    if diagram_entities is not None:
        # Inject _scope_entity_id from scoped-by binding so the C4 renderer can
        # switch to model-backed mode for diagrams that previously used _scope_entity_id.
        scope_eid = next(
            (b.target.entity_id for b in norm_bindings
             if b.correspondence_kind == "scoped-by" and b.subject.kind == "diagram"
             and b.target.entity_id),
            None,
        )
        render_entities: dict[str, object] = dict(diagram_entities)
        if scope_eid and "_scope_entity_id" not in render_entities:
            render_entities["_scope_entity_id"] = scope_eid
        puml_body = _render_diagram_entities_puml(diagram_type, name, render_entities, diagram_connections, repo_root)
        if effective_id is None:
            effective_id = generate_diagram_id(diagram_type, name)
        collected_entity_ids, collected_connection_ids = _collect_diagram_renderer_references(
            diagram_type,
            repo_root,
            render_entities,
            diagram_connections,
            bindings=norm_bindings_raw,
        )
        entity_ids_used = _merge_reference_ids(entity_ids_used, collected_entity_ids)
        connection_ids_used = _merge_reference_ids(connection_ids_used, collected_connection_ids)
    else:
        if effective_id is None:
            # Only adopt the @startuml token as the artifact-id when it is itself a
            # canonical id (i.e. round-tripping a previously-generated diagram).
            # A bare PlantUML label (e.g. "@startuml the-forces-shaping-this-system")
            # is not an identity and must not leak into the artifact-id, or it
            # produces a non-conformant id + W041. Otherwise mint a canonical id.
            m = re.search(r"@startuml\s+(\S+)", puml)
            if m and ENTITY_ID_RE.match(m.group(1).strip()):
                effective_id = m.group(1).strip()
        if effective_id is None:
            effective_id = generate_diagram_id(diagram_type, name)
        puml_body = puml.strip("\n") + "\n"
        if auto_include_stereotypes:
            puml_body = _prepare_diagram_puml_body(puml_body, repo_root, diagram_type)
        puml_body = optimize_puml_layout(puml_body)
        inferred_entity_ids, inferred_connection_ids = _infer_reference_ids_from_puml(repo_root, puml_body)
        entity_ids_used = _merge_reference_ids(entity_ids_used, inferred_entity_ids)
        connection_ids_used = _merge_reference_ids(connection_ids_used, inferred_connection_ids)

    content = format_diagram_puml(
        artifact_id=effective_id,
        diagram_type=diagram_type,
        name=name,
        version=version,
        status=status,
        last_updated=last,
        keywords=keywords,
        diagram_entities=clean_entities,
        diagram_connections=diagram_connections,
        entity_ids_used=entity_ids_used,
        connection_ids_used=connection_ids_used,
        view_derivations=view_derivations,
        bindings=bindings_to_raw(norm_bindings) if norm_bindings else None,
        puml_body=puml_body,
    )

    diag_src_root = diagram_source_root(repo_root)
    if group == UNCATEGORIZED:
        path = diag_src_root / f"{effective_id}.puml"
    else:
        path = diag_src_root / group / f"{effective_id}.puml"

    friendly_slug = extract_friendly_slug(effective_id)
    repo = get_repository(repo_root)
    try:
        validate_diagram_unique(repo, diagram_type, friendly_slug)
    except ValueError as e:
        # Report validation error in preview/dry_run
        error_msg = str(e)
        return WriteResult(
            wrote=False,
            path=path,
            artifact_id=effective_id,
            content=None,
            warnings=[error_msg],
            verification={
                "valid": False,
                "issues": [
                    {
                        "severity": "error",
                        "code": "duplicate_artifact",
                        "message": error_msg,
                        "location": None,
                    }
                ],
            },
        )

    if dry_run:
        res = verify_content_in_temp_path(
            verifier=verifier,
            file_type="diagram",
            desired_name=path.name,
            content=content,
            support_repo_root=repo_root,
        )
        return WriteResult(
            wrote=False,
            path=path,
            artifact_id=effective_id,
            content=content,
            warnings=warnings,
            verification=_verification_to_dict(path, res),
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    prev = path.read_text(encoding="utf-8") if path.exists() else None
    path.write_text(content, encoding="utf-8")

    res = verifier.verify_diagram_file(path)
    if not res.valid:
        if prev is None:
            try:
                path.unlink()
            except OSError:
                pass
        else:
            path.write_text(prev, encoding="utf-8")
        return WriteResult(
            wrote=False,
            path=path,
            artifact_id=effective_id,
            content=content,
            warnings=warnings,
            verification=_verification_to_dict(path, res),
        )

    # Render PNG + SVG after successful write
    png_path = _render_diagram_png(path, warnings)
    if png_path:
        warnings.append(f"Rendered PNG: {png_path}")
    _render_diagram_svg(path, warnings)

    clear_repo_caches(path)

    return WriteResult(
        wrote=True,
        path=path,
        artifact_id=effective_id,
        content=None,
        warnings=warnings,
        verification=_verification_to_dict(path, res),
    )
