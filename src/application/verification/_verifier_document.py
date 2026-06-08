"""Verification logic for document (docs/) files."""

from __future__ import annotations

import re
from pathlib import Path

from src.application.runtime_catalogs import RuntimeCatalogs
from src.application.verification.artifact_verifier_parsing import parse_frontmatter, read_file
from src.application.verification.artifact_verifier_registry import ArtifactRegistry
from src.application.verification.artifact_verifier_rules import check_enum
from src.application.verification.artifact_verifier_types import (
    VALID_STATUSES,
    Issue,
    Severity,
    VerificationResult,
)
from src.domain.repo_layout import ARCH_REPO, DOCS, MODEL

_WINDOWS_ABS_PATH_RE = re.compile(r"^[A-Za-z]:[/\\]")


def _is_absolute_markdown_link(href: str) -> bool:
    return href.startswith("/") or href.startswith("file://") or bool(_WINDOWS_ABS_PATH_RE.match(href))


def _infer_repo_root_for_document(path: Path) -> Path | None:
    for parent in path.parents:
        if (parent / DOCS).exists() and (parent / ARCH_REPO).exists():
            return parent
        if (parent / DOCS).exists() and (parent / MODEL).exists():
            return parent
    return None


def _doc_repo_root(path: Path, registry: ArtifactRegistry | None) -> Path | None:
    if registry is not None:
        resolved = path.resolve()
        for root in registry.repo_roots:
            try:
                resolved.relative_to(root)
                return root
            except ValueError:
                continue
    return _infer_repo_root_for_document(path)


def _linked_entity_types(doc_path: Path, content: str) -> set[str]:
    types: set[str] = set()
    for m in re.finditer(r"\[([^\]]+)\]\(([^)]+)\)", content):
        href = m.group(2)
        if href.startswith("http") or href.startswith("#"):
            continue
        anchor_idx = href.find("#")
        file_href = href[:anchor_idx] if anchor_idx >= 0 else href
        if not file_href.endswith(".md"):
            continue
        target = (doc_path.parent / file_href).resolve()
        if not target.is_file():
            continue
        try:
            target_content = target.read_text(encoding="utf-8")
        except OSError:
            continue
        fm = parse_frontmatter(
            target_content, VerificationResult(path=target, file_type="entity"), str(target)
        )
        if fm:
            etype = fm.get("artifact-type", "")
            if etype:
                types.add(str(etype))
    return types


def verify_document(  # noqa: C901
    path: Path,
    *,
    registry: ArtifactRegistry | None,
    catalogs: RuntimeCatalogs,
) -> VerificationResult:
    """Verify a document file under docs/."""
    result = VerificationResult(path=path, file_type="document")
    loc = str(path)
    content = read_file(path, result, loc)
    if content is None:
        return result
    fm = parse_frontmatter(content, result, loc)
    if fm is None:
        return result

    doc_type = str(fm.get("doc-type", "")).strip()
    doc_type_status_enum: frozenset[str] | None = None
    if not doc_type:
        result.issues.append(Issue(Severity.ERROR, "E153", "Missing required frontmatter field 'doc-type'", loc))
    else:
        repo_root = _doc_repo_root(path, registry)
        if repo_root is not None:
            from src.application.artifact_document_schema import get_document_schema  # noqa: PLC0415

            schema = get_document_schema(repo_root, doc_type)
            if schema is None:
                result.issues.append(
                    Issue(
                        Severity.ERROR,
                        "E153",
                        f"Unknown doc-type '{doc_type}': no schema at .arch-repo/documents/{doc_type}.json",
                        loc,
                    )
                )
            else:
                fm_schema = schema.get("frontmatter_schema")
                if fm_schema:
                    from src.application.artifact_schema import validate_against_schema  # noqa: PLC0415

                    errors = validate_against_schema(fm, fm_schema)
                    for err in errors:
                        result.issues.append(
                            Issue(Severity.ERROR, "E153", f"Document frontmatter schema violation: {err}", loc)
                        )
                    status_enum = fm_schema.get("properties", {}).get("status", {}).get("enum")
                    if status_enum:
                        doc_type_status_enum = frozenset(str(v) for v in status_enum)
                required_sections: list[str] = schema.get("required_sections") or []
                if required_sections:
                    body = re.sub(r"^---\n.*?\n---\n", "", content, count=1, flags=re.DOTALL)
                    present = {m.group(1).strip() for m in re.finditer(r"^##\s+(.+)$", body, re.MULTILINE)}
                    for section in required_sections:
                        if section not in present:
                            result.issues.append(
                                Issue(
                                    Severity.ERROR,
                                    "E154",
                                    f"Required section '## {section}' missing from document",
                                    loc,
                                )
                            )
                required_entity_types: list[str] = schema.get("required_entity_type_connections") or []
                if required_entity_types:
                    _oc = catalogs.ontology
                    linked_types = _linked_entity_types(path, content)
                    for etype in required_entity_types:
                        label = _oc.format_entity_type_term(etype)
                        if not _oc.expand_entity_type_term(etype):
                            result.issues.append(
                                Issue(
                                    Severity.ERROR,
                                    "E155",
                                    f"Unknown required entity-type connection term: {label} ({etype})",
                                    loc,
                                )
                            )
                        elif not _oc.entity_type_term_matches(etype, linked_types):
                            result.issues.append(
                                Issue(
                                    Severity.ERROR,
                                    "E155",
                                    f"Required entity-type connection missing: link at least one {label}",
                                    loc,
                                )
                            )

    for m in re.finditer(r"\[([^\]]+)\]\(([^)]+)\)", content):
        href = m.group(2)
        if href.startswith("http://") or href.startswith("https://") or href.startswith("#"):
            continue
        anchor_idx = href.find("#")
        file_href = href[:anchor_idx] if anchor_idx >= 0 else href
        if not file_href or not file_href.endswith(".md"):
            continue
        if _is_absolute_markdown_link(file_href):
            result.issues.append(
                Issue(Severity.WARNING, "W156", f"Absolute internal link must be relative: '{file_href}'", loc)
            )
            continue
        target = (path.parent / file_href).resolve()
        if not target.exists():
            result.issues.append(
                Issue(Severity.WARNING, "W155", f"Unresolvable internal link: '{file_href}'", loc)
            )

    check_enum(fm, "status", doc_type_status_enum or VALID_STATUSES, result, loc)
    return result
