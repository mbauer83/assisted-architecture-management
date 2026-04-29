"""Diagram editing operations."""

from collections.abc import Callable
from pathlib import Path

from src.application.modeling.artifact_write import format_diagram_puml
from src.application.modeling.artifact_write_layout import optimize_puml_layout
from src.application.verification.artifact_verifier import ArtifactVerifier
from src.config.repo_paths import DIAGRAM_CATALOG, DIAGRAMS

from .boundary import assert_engagement_write_root, today_iso
from .coerce import as_optional_str_list
from .diagram import _prepare_archimate_puml_body, _render_diagram_png, _render_diagram_svg
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


def edit_diagram(
    *,
    repo_root: Path,
    verifier: ArtifactVerifier,
    clear_repo_caches: Callable[[Path], None],
    artifact_id: str,
    puml: str | None = None,
    name: str | None = None,
    keywords: list[str] | None = ...,  # type: ignore[assignment]
    entity_ids_used: list[str] | None = None,
    connection_ids_used: list[str] | None = None,
    version: str | None = None,
    status: str | None = None,
    dry_run: bool,
) -> WriteResult:
    """Edit an existing diagram file.

    If ``puml`` is provided, replaces the PUML body and re-runs auto-layout.
    Other fields (name, keywords, version, status) update frontmatter only.
    Always re-verifies and re-renders PNG on successful write.
    """
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
    diagram_type = str(fm.get("diagram-type", "archimate"))

    # Determine PUML body
    if puml is not None:
        puml_body = puml.strip("\n") + "\n"
        puml_body = _prepare_archimate_puml_body(puml_body, repo_root, diagram_type)
        # optimize_puml_layout is idempotent: it skips when [hidden] links are
        # already present, so user-provided explicit hidden chains are preserved.
        puml_body = optimize_puml_layout(puml_body)
    else:
        puml_body = parsed.puml_body

    content = format_diagram_puml(
        artifact_id=artifact_id,
        diagram_type=diagram_type,
        name=eff_name,
        version=eff_version,
        status=eff_status,
        last_updated=today_iso(),
        keywords=eff_keywords,
        entity_ids_used=entity_ids_used
        if entity_ids_used is not None
        else as_optional_str_list(fm.get("entity-ids-used")),
        connection_ids_used=(
            connection_ids_used
            if connection_ids_used is not None
            else as_optional_str_list(fm.get("connection-ids-used"))
        ),
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
