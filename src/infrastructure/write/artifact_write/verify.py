import os
import tempfile
from pathlib import Path
from typing import Literal

from src.application.verification.artifact_verifier import ArtifactVerifier, VerificationResult
from src.config.repo_paths import ARCH_REPO, DIAGRAM_CATALOG, DIAGRAMS, DOCS, MODEL


def _diagram_temp_path(tmp_root: Path, desired_name: str, support_repo_root: Path | None) -> Path:
    """Lay out a minimal diagram-catalog so relative includes resolve during PlantUML checks."""
    cat = tmp_root / DIAGRAM_CATALOG
    diagrams = cat / DIAGRAMS
    diagrams.mkdir(parents=True, exist_ok=True)
    if support_repo_root is not None:
        for support in ("_archimate-stereotypes.puml", "_archimate-glyphs.puml"):
            src = support_repo_root / DIAGRAM_CATALOG / support
            if src.exists():
                (cat / support).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return diagrams / desired_name


def _mirror_doc_entry(existing: Path, source_root: Path, mirror_root: Path, skip_rel: Path) -> None:
    """Recreate one docs-tree entry under *mirror_root*: dirs as real dirs, files as symlinks."""
    rel = existing.relative_to(source_root)
    target = mirror_root / rel
    if existing.is_dir():
        target.mkdir(parents=True, exist_ok=True)
    elif rel != skip_rel:
        target.parent.mkdir(parents=True, exist_ok=True)
        os.symlink(existing, target)


def _document_temp_path(tmp_root: Path, desired_name: str, support_repo_root: Path | None) -> Path:
    """Mirror the docs tree (symlinks) around the document under test so cross-doc checks resolve."""
    tmp_path = tmp_root / DOCS / desired_name
    if support_repo_root is None:
        tmp_path.parent.mkdir(parents=True, exist_ok=True)
        return tmp_path

    for top in (ARCH_REPO, MODEL):
        src = support_repo_root / top
        if src.exists():
            os.symlink(src, tmp_root / top, target_is_directory=True)

    source_docs_root = support_repo_root / DOCS
    mirrored_docs_root = tmp_root / DOCS
    mirrored_docs_root.mkdir(parents=True, exist_ok=True)
    skip_rel = Path(desired_name)
    for existing in source_docs_root.rglob("*") if source_docs_root.exists() else []:
        _mirror_doc_entry(existing, source_docs_root, mirrored_docs_root, skip_rel)
    tmp_path.parent.mkdir(parents=True, exist_ok=True)
    return tmp_path


def verify_content_in_temp_path(
    *,
    verifier: ArtifactVerifier,
    file_type: Literal["entity", "connection", "diagram", "document"],
    desired_name: str,
    content: str,
    support_repo_root: Path | None = None,
) -> VerificationResult:
    """Verify *content* by writing it to a temp location laid out for its file type."""
    tmp_root = Path(tempfile.mkdtemp(prefix=f"model-write-verify-{file_type}-"))
    if file_type == "diagram":
        tmp_path = _diagram_temp_path(tmp_root, desired_name, support_repo_root)
    elif file_type == "document":
        tmp_path = _document_temp_path(tmp_root, desired_name, support_repo_root)
    else:
        tmp_path = tmp_root / desired_name

    tmp_path.write_text(content, encoding="utf-8")

    dispatch = {
        "entity": verifier.verify_entity_file,
        "connection": verifier.verify_connection_file,
        "document": verifier.verify_document_file,
        "diagram": verifier.verify_diagram_file,
    }
    return dispatch[file_type](tmp_path)


def collect_verification_errors(repo_root: Path, *, include_diagrams: bool = False) -> list[str]:
    """Build a verifier for *repo_root* and return formatted ``CODE: message (location)`` error strings."""
    from src.application.verification.artifact_verifier_registry import ArtifactRegistry  # noqa: PLC0415
    from src.infrastructure.app_bootstrap import build_runtime_catalogs, get_module_registry  # noqa: PLC0415
    from src.infrastructure.artifact_index import shared_artifact_index  # noqa: PLC0415

    registry = ArtifactRegistry(shared_artifact_index(repo_root))
    verifier = ArtifactVerifier(registry, catalogs=build_runtime_catalogs(get_module_registry()))
    return [
        f"{i.code}: {i.message} ({i.location})"
        for r in verifier.verify_all(repo_root, include_diagrams=include_diagrams)
        for i in r.issues
        if i.severity == "error"
    ]
