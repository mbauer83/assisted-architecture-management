import os
import tempfile
from pathlib import Path
from typing import Literal

from src.application.verification.artifact_verifier import ArtifactVerifier, VerificationResult
from src.config.repo_paths import ARCH_REPO, DIAGRAM_CATALOG, DIAGRAMS, DOCS, MODEL


def verify_content_in_temp_path(
    *,
    verifier: ArtifactVerifier,
    file_type: Literal["entity", "connection", "diagram", "document"],
    desired_name: str,
    content: str,
    support_repo_root: Path | None = None,
) -> VerificationResult:
    """Verify *content* by writing it to a temp location.

    For diagrams, create a minimal diagram-catalog structure so relative includes
    (../_macros.puml) can resolve during PlantUML checks.
    """

    tmp_root = Path(tempfile.mkdtemp(prefix=f"model-write-verify-{file_type}-"))

    if file_type == "diagram":
        cat = tmp_root / DIAGRAM_CATALOG
        diagrams = cat / DIAGRAMS
        diagrams.mkdir(parents=True, exist_ok=True)

        if support_repo_root is not None:
            for support in (
                "_macros.puml",
                "_archimate-stereotypes.puml",
                "_archimate-glyphs.puml",
            ):
                src = support_repo_root / DIAGRAM_CATALOG / support
                if src.exists():
                    (cat / support).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

        tmp_path = diagrams / desired_name
    elif file_type == "document":
        desired_relpath = Path(desired_name)
        if support_repo_root is not None:
            arch_repo = support_repo_root / ARCH_REPO
            if arch_repo.exists():
                os.symlink(arch_repo, tmp_root / ARCH_REPO, target_is_directory=True)
            model_root = support_repo_root / MODEL
            if model_root.exists():
                os.symlink(model_root, tmp_root / MODEL, target_is_directory=True)

            source_docs_root = support_repo_root / DOCS
            mirrored_docs_root = tmp_root / DOCS
            mirrored_docs_root.mkdir(parents=True, exist_ok=True)
            if source_docs_root.exists():
                for existing in source_docs_root.rglob("*"):
                    rel = existing.relative_to(source_docs_root)
                    target = mirrored_docs_root / rel
                    if existing.is_dir():
                        target.mkdir(parents=True, exist_ok=True)
                    elif rel != desired_relpath:
                        target.parent.mkdir(parents=True, exist_ok=True)
                        os.symlink(existing, target)
        tmp_path = tmp_root / DOCS / desired_name
        tmp_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        tmp_path = tmp_root / desired_name

    tmp_path.write_text(content, encoding="utf-8")

    if file_type == "entity":
        return verifier.verify_entity_file(tmp_path)
    if file_type == "connection":
        return verifier.verify_connection_file(tmp_path)
    if file_type == "document":
        return verifier.verify_document_file(tmp_path)
    return verifier.verify_diagram_file(tmp_path)
