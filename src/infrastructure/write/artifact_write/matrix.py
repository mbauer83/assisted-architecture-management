import os
import re
from collections.abc import Callable
from pathlib import Path

import yaml

from src.application.modeling.artifact_write import format_matrix_markdown, generate_diagram_id
from src.application.verification.artifact_verifier import ArtifactRegistry, ArtifactVerifier
from src.config.repo_paths import DIAGRAM_CATALOG, DIAGRAMS

from .boundary import assert_engagement_write_root, today_iso
from .types import WriteResult

_ENTITY_ID_PATTERN = re.compile(r"\b([A-Z]{2,6}@\d+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*)\b")


def _verification_to_dict(path: Path, res) -> dict[str, object]:
    return {
        "path": str(path),
        "file_type": "diagram",
        "valid": res.valid,
        "issues": [
            {"severity": i.severity, "code": i.code, "message": i.message, "location": i.location} for i in res.issues
        ],
    }


def _infer_entity_ids_from_matrix(markdown: str) -> list[str]:
    found = sorted(set(_ENTITY_ID_PATTERN.findall(markdown)))
    return found


def _read_frontmatter(path: Path) -> dict[str, object]:
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    if not content.startswith("---\n"):
        return {}
    end = content.find("\n---\n", 4)
    if end == -1:
        return {}
    try:
        parsed = yaml.safe_load(content[4:end])
    except yaml.YAMLError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _display_name_from_entity_file(path: Path, artifact_id: str) -> str:
    fm = _read_frontmatter(path)
    name = str(fm.get("name", "")).strip()
    if not name:
        return artifact_id
    return name


def _linkify_matrix_ids(
    *,
    repo_root: Path,
    registry: ArtifactRegistry,
    matrix_markdown: str,
    candidate_entity_ids: list[str],
) -> tuple[str, int]:
    """Replace plain entity IDs with relative markdown links in matrix rows."""

    diagrams_dir = repo_root / DIAGRAM_CATALOG / DIAGRAMS
    id_to_relpath: dict[str, str] = {}
    id_to_link_text: dict[str, str] = {}

    for entity_id in candidate_entity_ids:
        p = registry.find_file_by_id(entity_id)
        if p is None:
            continue
        rel = os.path.relpath(str(p), start=str(diagrams_dir)).replace("\\", "/")
        id_to_relpath[entity_id] = rel
        id_to_link_text[entity_id] = _display_name_from_entity_file(p, entity_id)

    if not id_to_relpath:
        return matrix_markdown, 0

    replaced = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal replaced
        artifact_id = match.group(1)
        target = id_to_relpath.get(artifact_id)
        if target is None:
            return artifact_id
        link_text = id_to_link_text.get(artifact_id, artifact_id)
        replaced += 1
        return f"[{link_text}]({target})"

    out_lines: list[str] = []
    for line in matrix_markdown.splitlines():
        if line.startswith("| ") and not line.startswith("|---") and "](" not in line:
            out_lines.append(_ENTITY_ID_PATTERN.sub(repl, line))
        else:
            out_lines.append(line)

    return "\n".join(out_lines), replaced


def _build_diagram_id_to_relpath(*, diagrams_dir: Path, registry: ArtifactRegistry) -> dict[str, str]:
    diagram_map: dict[str, str] = {}
    _ = registry

    if diagrams_dir.exists():
        for p in diagrams_dir.glob("*.puml"):
            if p.name.startswith("_"):
                continue
            diagram_map.setdefault(p.stem, p.name)
        for p in diagrams_dir.glob("*.md"):
            if p.name.startswith("_"):
                continue
            fm = _read_frontmatter(p)
            artifact_id = str(fm.get("artifact-id", "")).strip()
            if artifact_id:
                diagram_map.setdefault(artifact_id, p.name)
            diagram_map.setdefault(p.stem, p.name)

    return diagram_map


def _linkify_known_tokens_in_matrix_rows(
    *,
    matrix_markdown: str,
    diagram_id_to_relpath: dict[str, str],
) -> tuple[str, int]:
    """Link known diagram artifact IDs inside plain table rows."""

    if not diagram_id_to_relpath:
        return matrix_markdown, 0

    replaced = 0

    def replace_token_links(line: str, mapping: dict[str, str]) -> str:
        nonlocal replaced
        out = line
        for token in sorted(mapping.keys(), key=len, reverse=True):
            pattern = re.compile(rf"\b{re.escape(token)}\b")

            def _repl(m: re.Match[str], token_value: str = token) -> str:
                nonlocal replaced
                replaced += 1
                return f"[{token_value}]({mapping[token_value]})"

            out = pattern.sub(_repl, out)
        return out

    out_lines: list[str] = []
    for line in matrix_markdown.splitlines():
        if line.startswith("| ") and not line.startswith("|---") and "](" not in line:
            linked = replace_token_links(line, diagram_id_to_relpath)
            out_lines.append(linked)
        else:
            out_lines.append(line)

    return "\n".join(out_lines), replaced


def create_matrix(
    *,
    repo_root: Path,
    registry: ArtifactRegistry,
    verifier: ArtifactVerifier,
    clear_repo_caches: Callable[[Path], None],
    name: str,
    matrix_markdown: str,
    artifact_id: str | None,
    keywords: list[str] | None = None,
    version: str = "0.1.0",
    status: str = "draft",
    last_updated: str | None = None,
    infer_entity_ids: bool = True,
    auto_link_entity_ids: bool = True,
    entity_ids: list[str] | None = None,
    from_entity_ids: list[str] | None = None,
    to_entity_ids: list[str] | None = None,
    conn_type_configs: list[dict[str, object]] | None = None,
    combined: bool | None = None,
    dry_run: bool = True,
) -> WriteResult:
    assert_engagement_write_root(repo_root)
    effective_id = artifact_id or generate_diagram_id("matrix", name)

    last = last_updated or today_iso()

    warnings: list[str] = []
    inferred_entities: list[str] = []
    if infer_entity_ids:
        inferred_entities = _infer_entity_ids_from_matrix(matrix_markdown)

    body_markdown = matrix_markdown
    if auto_link_entity_ids:
        ids_for_links = inferred_entities if inferred_entities else _infer_entity_ids_from_matrix(matrix_markdown)
        body_markdown, replaced_count = _linkify_matrix_ids(
            repo_root=repo_root,
            registry=registry,
            matrix_markdown=matrix_markdown,
            candidate_entity_ids=ids_for_links,
        )

        diagrams_dir = repo_root / DIAGRAM_CATALOG / DIAGRAMS
        diagram_links = _build_diagram_id_to_relpath(
            diagrams_dir=diagrams_dir,
            registry=registry,
        )
        body_markdown, known_link_replacements = _linkify_known_tokens_in_matrix_rows(
            matrix_markdown=body_markdown,
            diagram_id_to_relpath=diagram_links,
        )

    content = format_matrix_markdown(
        artifact_id=effective_id,
        name=name,
        version=version,
        status=status,
        last_updated=last,
        keywords=keywords,
        matrix_markdown=body_markdown,
        entity_ids=entity_ids,
        from_entity_ids=from_entity_ids,
        to_entity_ids=to_entity_ids,
        conn_type_configs=conn_type_configs,
        combined=combined,
    )

    path = repo_root / DIAGRAM_CATALOG / DIAGRAMS / f"{effective_id}.md"

    if dry_run:
        from tempfile import TemporaryDirectory

        with TemporaryDirectory(prefix="model-write-verify-matrix-") as tmp_dir:
            tmp_path = Path(tmp_dir) / f"{artifact_id}.md"
            tmp_path.write_text(content, encoding="utf-8")
            res = verifier.verify_matrix_diagram_file(tmp_path)
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

    res = verifier.verify_matrix_diagram_file(path)
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

    clear_repo_caches(path)

    return WriteResult(
        wrote=True,
        path=path,
        artifact_id=effective_id,
        content=None,
        warnings=warnings,
        verification=_verification_to_dict(path, res),
    )
