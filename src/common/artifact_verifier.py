"""ERP v2.0 model verification facade with modular helper backends."""

import re
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Literal

from src.common._verifier_rules_grf import (
    check_global_artifact_reference,
)
from src.common._verifier_rules_schema import (
    check_attribute_schema,
    check_frontmatter_schema,
)
from src.common.artifact_verifier_incremental import (
    FileInventory,
    detect_changed_paths,
    expand_impacted_paths,
    git_head,
    inventory_files,
    load_incremental_state,
    load_runtime_config,
    save_incremental_state,
    serialize_result,
    state_file_path,
    verifier_engine_signature,
)
from src.common.artifact_verifier_parsing import (
    parse_frontmatter,
    parse_puml_frontmatter,
    read_file,
)
from src.common.artifact_verifier_registry import ArtifactRegistry
from src.common.artifact_verifier_rules import (
    check_artifact_id_entity,
    check_artifact_type,
    check_diagram_artifact_type,
    check_diagram_references_scoped,
    check_enum,
    check_puml_structure,
    check_required_fields,
    check_section,
)
from src.common.artifact_verifier_syntax import (
    check_puml_syntax,
    check_puml_syntax_batch,
    resolve_worker_count,
)
from src.common.artifact_verifier_types import (
    CONNECTION_TYPES,
    DIAGRAM_REQUIRED,
    ENTITY_REQUIRED,
    ENTITY_TYPES,
    OUTGOING_FILE_REQUIRED,
    VALID_STATUSES,
    IncrementalState,
    Issue,
    Severity,
    VerificationResult,
    VerifierRuntimeConfig,
    entity_id_from_path,
)
from src.common.repo_paths import ARCH_REPO, DOCS, MODEL

# Cardinality: n  |  n..m  |  n..*  |  *
_CARDINALITY_RE = re.compile(r"^\d+$|^\d+\.\.\d+$|^\d+\.\.\*$|^\*$")

# Connection header after "### ":
#   conn-type [[src_card]] → [[tgt_card] ]target_id
_CONN_HEADER_RE = re.compile(
    r"^(?P<conn_type>[a-z][a-z0-9-]+)"
    r"(?:\s+\[(?P<src_card>[^\]]+)\])?"
    r"\s+→\s+"
    r"(?:\[(?P<tgt_card>[^\]]+)\]\s+)?"
    r"(?P<target_id>\S+)$"
)

_WINDOWS_ABS_PATH_RE = re.compile(r"^[A-Za-z]:[/\\]")


def _parse_conn_header(header: str) -> tuple[str, str, str, str] | None:
    """Parse a connection header line (after '### ').

    Returns (conn_type, src_card, tgt_card, target_id) or None on failure.
    src_card / tgt_card are empty strings when absent.
    """
    m = _CONN_HEADER_RE.match(header)
    if not m:
        return None
    return (
        m.group("conn_type"),
        m.group("src_card") or "",
        m.group("tgt_card") or "",
        m.group("target_id"),
    )


class ArtifactVerifier:
    def __init__(
        self, registry: ArtifactRegistry | None = None, *, check_puml_syntax: bool = True
    ) -> None:
        self.registry = registry
        self.check_puml_syntax = check_puml_syntax

    def _repo_root_for_path(self, path: Path) -> Path | None:
        """Resolve the configured model repository root for a file path."""
        if self.registry is None:
            return None
        resolved = path.resolve()
        for root in self.registry.repo_roots:
            try:
                resolved.relative_to(root)
                return root
            except ValueError:
                continue
        return None

    def verify_entity_file(self, path: Path) -> VerificationResult:
        result = VerificationResult(path=path, file_type="entity")
        loc = str(path)
        content = read_file(path, result, loc)
        if content is None:
            return result
        fm = parse_frontmatter(content, result, loc)
        if fm is None:
            return result

        check_required_fields(fm, ENTITY_REQUIRED, result, loc)
        check_artifact_id_entity(fm, result, loc)
        check_artifact_type(fm, ENTITY_TYPES, "entity type", result, loc)
        check_enum(fm, "status", VALID_STATUSES, result, loc)
        check_section(content, "§content", required=True, result=result, loc=loc)
        check_section(content, "§display", required=True, result=result, loc=loc)

        if str(fm.get("artifact-type", "")) == "global-artifact-reference":
            check_global_artifact_reference(fm, self.registry, result, loc)

        repo_root = self._repo_root_for_path(path)
        if repo_root is not None:
            check_frontmatter_schema(fm, repo_root, "entity", result, loc)
            check_attribute_schema(content, fm, repo_root, result, loc)

        return result

    def verify_outgoing_file(self, path: Path) -> VerificationResult:
        """Verify a .outgoing.md file (new convention)."""
        result = VerificationResult(path=path, file_type="connection")
        loc = str(path)
        content = read_file(path, result, loc)
        if content is None:
            return result
        fm = parse_frontmatter(content, result, loc)
        if fm is None:
            return result

        check_required_fields(fm, OUTGOING_FILE_REQUIRED, result, loc)
        check_enum(fm, "status", VALID_STATUSES, result, loc)

        file_scope = self._scope_for_path(path)

        # Validate source-entity references an actual entity
        source = fm.get("source-entity", "")
        if self.registry is not None and source:
            all_entities = self.registry.entity_ids()
            if source not in all_entities:
                result.issues.append(
                    Issue(
                        Severity.ERROR,
                        "E120",
                        f"source-entity '{source}' not found in model",
                        loc,
                    )
                )
            elif file_scope == "enterprise" and source not in self.registry.enterprise_entity_ids():
                result.issues.append(
                    Issue(
                        Severity.ERROR,
                        "E131",
                        f"enterprise connection has non-enterprise source-entity '{source}'",
                        loc,
                    )
                )

        # Validate §connections marker is present
        if "<!-- §connections -->" not in content:
            result.issues.append(
                Issue(
                    Severity.ERROR,
                    "E121",
                    "Missing <!-- §connections --> section marker",
                    loc,
                )
            )

        # Scope-aware entity sets for target validation
        if self.registry is not None:
            allowed_entities = (
                self.registry.enterprise_entity_ids()
                if file_scope == "enterprise"
                else self.registry.entity_ids()
            )
            all_entities_for_scope = self.registry.entity_ids()
        else:
            allowed_entities = all_entities_for_scope = set()

        # Validate each connection section header
        seen_connections: set[str] = set()
        for line in content.splitlines():
            if line.startswith("### "):
                header = line[4:].strip()
                parsed = _parse_conn_header(header)
                if parsed is None:
                    result.issues.append(
                        Issue(
                            Severity.ERROR,
                            "E122",
                            f"Connection header missing ' → ' separator: '{header}'",
                            loc,
                        )
                    )
                    continue
                conn_type, src_card, tgt_card, target_id = parsed
                if conn_type not in CONNECTION_TYPES:
                    result.issues.append(
                        Issue(
                            Severity.ERROR,
                            "E123",
                            f"Unknown connection type '{conn_type}'",
                            loc,
                        )
                    )
                for card_label, card_val in (("source", src_card), ("target", tgt_card)):
                    if card_val and not _CARDINALITY_RE.match(card_val):
                        result.issues.append(
                            Issue(
                                Severity.ERROR,
                                "E125",
                                f"Invalid {card_label} cardinality '{card_val}' in '{header}' "
                                f"— expected n, n..m, n..*, or *",
                                loc,
                            )
                        )
                if self.registry is not None and target_id not in allowed_entities:
                    if target_id in all_entities_for_scope and file_scope == "enterprise":
                        result.issues.append(
                            Issue(
                                Severity.ERROR,
                                "E130",
                                (
                                    "enterprise connection references "
                                    f"non-enterprise entity '{target_id}'"
                                ),
                                loc,
                            )
                        )
                    else:
                        result.issues.append(
                            Issue(
                                Severity.ERROR,
                                "E124",
                                f"Target entity '{target_id}' not found in model",
                                loc,
                            )
                        )
                conn_key = f"{conn_type} → {target_id}"
                if conn_key in seen_connections:
                    result.issues.append(
                        Issue(
                            Severity.WARNING,
                            "W120",
                            f"Duplicate connection: '{conn_key}'",
                            loc,
                        )
                    )
                seen_connections.add(conn_key)

        repo_root = self._repo_root_for_path(path)
        if repo_root is not None:
            check_frontmatter_schema(fm, repo_root, "outgoing", result, loc)

        return result

    def verify_connection_file(self, path: Path) -> VerificationResult:
        """Verify a connection file — dispatches to outgoing or legacy format."""
        if path.name.endswith(".outgoing.md"):
            return self.verify_outgoing_file(path)
        # Legacy format — minimal validation
        result = VerificationResult(path=path, file_type="connection")
        loc = str(path)
        content = read_file(path, result, loc)
        if content is None:
            return result
        fm = parse_frontmatter(content, result, loc)
        if fm is None:
            return result
        check_enum(fm, "status", VALID_STATUSES, result, loc)
        check_section(content, "§display", required=True, result=result, loc=loc)
        return result

    def verify_diagram_file(self, path: Path) -> VerificationResult:
        return self._verify_diagram_file(path, run_syntax_check=self.check_puml_syntax)

    def _verify_diagram_file(self, path: Path, *, run_syntax_check: bool) -> VerificationResult:
        result = VerificationResult(path=path, file_type="diagram")
        loc = str(path)
        content = read_file(path, result, loc)
        if content is None:
            return result
        fm = parse_puml_frontmatter(content, result, loc)
        if fm is None:
            return result

        check_required_fields(fm, DIAGRAM_REQUIRED, result, loc)
        check_diagram_artifact_type(fm, result, loc)
        check_enum(fm, "status", VALID_STATUSES, result, loc)

        scope = self._scope_for_path(path)
        if self.registry is not None:
            check_diagram_references_scoped(fm, self.registry, scope, result, loc)
        else:
            result.issues.append(
                Issue(
                    Severity.WARNING,
                    "W002",
                    "No ArtifactRegistry provided; entity/connection reference checks skipped",
                    loc,
                )
            )

        check_puml_structure(content, fm, result, loc)

        repo_root = self._repo_root_for_path(path)
        if repo_root is not None:
            check_frontmatter_schema(fm, repo_root, "diagram", result, loc)

        if run_syntax_check:
            result.issues.extend(check_puml_syntax(path, loc))
        return result

    def verify_matrix_diagram_file(self, path: Path) -> VerificationResult:
        result = VerificationResult(path=path, file_type="diagram")
        loc = str(path)
        content = read_file(path, result, loc)
        if content is None:
            return result
        fm = parse_frontmatter(content, result, loc)
        if fm is None:
            return result

        check_required_fields(fm, DIAGRAM_REQUIRED, result, loc)
        check_diagram_artifact_type(fm, result, loc)
        check_enum(fm, "status", VALID_STATUSES, result, loc)

        scope = self._scope_for_path(path)
        if self.registry is not None:
            check_diagram_references_scoped(fm, self.registry, scope, result, loc)
        else:
            result.issues.append(
                Issue(
                    Severity.WARNING,
                    "W002",
                    "No ArtifactRegistry provided; entity/connection reference checks skipped",
                    loc,
                )
            )

        if "diagram-type" in fm and str(fm.get("diagram-type")) != "matrix":
            result.issues.append(
                Issue(
                    Severity.WARNING,
                    "W321",
                    (
                        "Markdown diagram file under diagram-catalog/diagrams "
                        "should use diagram-type: matrix"
                    ),
                    loc,
                )
            )
        if "|" not in content:
            result.issues.append(
                Issue(
                    Severity.WARNING,
                    "W322",
                    (
                        "Matrix diagram markdown has no table markup; "
                        "expected at least one matrix table"
                    ),
                    loc,
                )
            )
        return result

    def verify_all(
        self, repo_path: Path, *, include_diagrams: bool = True
    ) -> list[VerificationResult]:
        cfg = load_runtime_config()
        if cfg.mode == "incremental":
            return self._verify_all_incremental(
                repo_path, include_diagrams=include_diagrams, cfg=cfg
            )
        return self._verify_all_full(repo_path, include_diagrams=include_diagrams)

    def _verify_all_full(
        self, repo_path: Path, *, include_diagrams: bool
    ) -> list[VerificationResult]:
        inv = inventory_files(repo_path, include_diagrams=include_diagrams)
        results = self._verify_inventory_subset(inv, set(inv.ordered_paths))
        # Verify docs/ directory — not tracked by FileInventory
        docs_root = repo_path / DOCS
        if docs_root.exists():
            doc_files = sorted(docs_root.rglob("*.md"))
            worker_count = resolve_worker_count()
            results.extend(
                _verify_paths(doc_files, self.verify_document_file, workers=worker_count)
            )
        return results

    def _verify_all_incremental(
        self,
        repo_path: Path,
        *,
        include_diagrams: bool,
        cfg: VerifierRuntimeConfig,
    ) -> list[VerificationResult]:
        inv = inventory_files(repo_path, include_diagrams=include_diagrams)
        state_path = state_file_path(
            repo_path, include_diagrams=include_diagrams, state_dir=cfg.state_dir
        )
        prev = load_incremental_state(state_path)
        head = git_head(repo_path)
        engine_sig = verifier_engine_signature()

        if self._incremental_requires_full(
            prev, include_diagrams=include_diagrams, head=head, engine_sig=engine_sig
        ):
            mode = "full"
            results = self._verify_all_full(repo_path, include_diagrams=include_diagrams)
        else:
            assert prev is not None
            mode, results = self._verify_from_existing_incremental_state(
                prev,
                inv,
                repo_path=repo_path,
                include_diagrams=include_diagrams,
                cfg=cfg,
            )

        # Verify docs/ — always fresh, not tracked by incremental state
        docs_root = repo_path / DOCS
        if docs_root.exists():
            doc_files = sorted(docs_root.rglob("*.md"))
            worker_count = resolve_worker_count()
            results.extend(
                _verify_paths(doc_files, self.verify_document_file, workers=worker_count)
            )

        state = IncrementalState(
            schema_version=1,
            engine_signature=engine_sig,
            include_diagrams=include_diagrams,
            git_head=head,
            snapshots=inv.snapshots,
            results={
                inv.path_to_rel[r.path]: serialize_result(r)
                for r in results
                if r.path in inv.path_to_rel
            },
            include_registry=(self.registry is not None),
        )
        save_incremental_state(state_path, state)

        if cfg.log_mode:
            print(
                "[ArtifactVerifier] "
                f"mode={mode} include_diagrams={include_diagrams} "
                f"files={len(results)}"
            )
        return results

    def _incremental_requires_full(
        self,
        prev: IncrementalState | None,
        *,
        include_diagrams: bool,
        head: str | None,
        engine_sig: str,
    ) -> bool:
        if prev is None:
            return True
        if prev.include_diagrams != include_diagrams:
            return True
        if prev.git_head != head:
            return True
        if prev.engine_signature != engine_sig:
            return True
        # Registry availability changed — must re-verify to resolve/drop W002 warnings
        return prev.include_registry != (self.registry is not None)

    def _verify_from_existing_incremental_state(
        self,
        prev: IncrementalState,
        inv: FileInventory,
        *,
        repo_path: Path,
        include_diagrams: bool,
        cfg: VerifierRuntimeConfig,
    ) -> tuple[str, list[VerificationResult]]:
        changed, deleted = detect_changed_paths(inv, prev)
        if deleted:
            return "full", self._verify_all_full(repo_path, include_diagrams=include_diagrams)
        if not changed:
            cached = _results_from_state(prev, inv)
            if cached is not None:
                return "incremental-cached", cached
            return "full", self._verify_all_full(repo_path, include_diagrams=include_diagrams)
        if self._incremental_change_set_too_large(inv, changed, cfg):
            return "full", self._verify_all_full(repo_path, include_diagrams=include_diagrams)
        impacted = expand_impacted_paths(inv, changed)
        fresh = self._verify_inventory_subset(inv, impacted)
        return "incremental", _merge_results(prev, inv, fresh)

    def _incremental_change_set_too_large(
        self,
        inv: FileInventory,
        changed: set[str],
        cfg: VerifierRuntimeConfig,
    ) -> bool:
        total = len(inv.ordered_paths)
        changed_ratio = (len(changed) / total) if total > 0 else 1.0
        return (
            changed_ratio >= cfg.changed_ratio_threshold
            or len(changed) >= cfg.changed_count_threshold
        )

    def _verify_inventory_subset(
        self, inv: FileInventory, relpaths: set[str]
    ) -> list[VerificationResult]:
        worker_count = resolve_worker_count()
        if self.registry is not None:
            _ = self.registry.entity_ids()
            _ = self.registry.connection_ids()
        entity_files = [inv.rel_to_path[r] for r in inv.entity_relpaths if r in relpaths]
        connection_files = [inv.rel_to_path[r] for r in inv.connection_relpaths if r in relpaths]
        diagram_files = [inv.rel_to_path[r] for r in inv.diagram_puml_relpaths if r in relpaths]
        matrix_files = [inv.rel_to_path[r] for r in inv.diagram_matrix_relpaths if r in relpaths]

        out: list[VerificationResult] = []
        out.extend(_verify_paths(entity_files, self.verify_entity_file, workers=worker_count))
        out.extend(
            _verify_paths(connection_files, self.verify_connection_file, workers=worker_count)
        )

        diagram_results = _verify_paths(
            diagram_files,
            lambda path: self._verify_diagram_file(path, run_syntax_check=False),
            workers=min(worker_count, 4),
        )
        if self.check_puml_syntax and diagram_results:
            issues_by_path = check_puml_syntax_batch([r.path for r in diagram_results])
            for d in diagram_results:
                d.issues.extend(issues_by_path.get(d.path, []))
        out.extend(diagram_results)

        out.extend(
            _verify_paths(matrix_files, self.verify_matrix_diagram_file, workers=worker_count)
        )

        by_path = {r.path: r for r in out}
        return [
            by_path[inv.rel_to_path[r]]
            for r in inv.ordered_paths
            if r in relpaths and inv.rel_to_path[r] in by_path
        ]

    def verify_document_file(self, path: Path) -> VerificationResult:  # noqa: C901
        result = VerificationResult(path=path, file_type="document")
        loc = str(path)
        content = read_file(path, result, loc)
        if content is None:
            return result
        fm = parse_frontmatter(content, result, loc)
        if fm is None:
            return result

        # E153: frontmatter schema validation against .arch-repo/documents/{doc_type}.json
        doc_type = str(fm.get("doc-type", "")).strip()
        if not doc_type:
            result.issues.append(
                Issue(Severity.ERROR, "E153", "Missing required frontmatter field 'doc-type'", loc)
            )
        else:
            repo_root = self._repo_root_for_path(path) or _infer_repo_root_for_document(path)
            if repo_root is not None:
                from src.common.artifact_document_schema import get_document_schema

                schema = get_document_schema(repo_root, doc_type)
                if schema is None:
                    result.issues.append(
                        Issue(
                            Severity.ERROR,
                            "E153",
                            (
                                f"Unknown doc-type '{doc_type}': no schema at "
                                f".arch-repo/documents/{doc_type}.json"
                            ),
                            loc,
                        )
                    )
                else:
                    fm_schema = schema.get("frontmatter_schema")
                    if fm_schema:
                        from src.common.artifact_schema import validate_against_schema

                        errors = validate_against_schema(fm, fm_schema)
                        for err in errors:
                            result.issues.append(
                                Issue(
                                    Severity.ERROR,
                                    "E153",
                                    f"Document frontmatter schema violation: {err}",
                                    loc,
                                )
                            )
                    # E154: required sections
                    required_sections: list[str] = schema.get("required_sections") or []
                    if required_sections:
                        body = re.sub(r"^---\n.*?\n---\n", "", content, count=1, flags=re.DOTALL)
                        present = {
                            m.group(1).strip()
                            for m in re.finditer(r"^##\s+(.+)$", body, re.MULTILINE)
                        }
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
                    # E155: required entity-type connections
                    required_entity_types: list[str] = (
                        schema.get("required_entity_type_connections") or []
                    )
                    if required_entity_types:
                        from src.common.ontology_loader import (
                            entity_type_term_matches,
                            expand_entity_type_term,
                            format_entity_type_term,
                        )

                        linked_types = _linked_entity_types(path, content)
                        for etype in required_entity_types:
                            label = format_entity_type_term(etype)
                            if not expand_entity_type_term(etype):
                                result.issues.append(
                                    Issue(
                                        Severity.ERROR,
                                        "E155",
                                        (
                                            "Unknown required entity-type "
                                            f"connection term: {label} ({etype})"
                                        ),
                                        loc,
                                    )
                                )
                            elif not entity_type_term_matches(etype, linked_types):
                                result.issues.append(
                                    Issue(
                                        Severity.ERROR,
                                        "E155",
                                        (
                                            "Required entity-type connection "
                                            f"missing: link at least one {label}"
                                        ),
                                        loc,
                                    )
                                )

        # W155: unresolvable internal markdown links
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
                    Issue(
                        Severity.WARNING,
                        "W156",
                        f"Absolute internal link must be relative: '{file_href}'",
                        loc,
                    )
                )
                continue
            target = (path.parent / file_href).resolve()
            if not target.exists():
                result.issues.append(
                    Issue(
                        Severity.WARNING,
                        "W155",
                        f"Unresolvable internal link: '{file_href}'",
                        loc,
                    )
                )

        check_enum(fm, "status", VALID_STATUSES, result, loc)
        return result

    def _scope_for_path(self, path: Path) -> Literal["enterprise", "engagement", "unknown"]:
        if self.registry is not None:
            return self.registry.scope_for_path(path)
        from src.common.workspace_paths import infer_repo_scope

        return infer_repo_scope(path)


def _linked_entity_types(doc_path: Path, content: str) -> set[str]:
    """Return the set of artifact-type values found in entities linked from a document."""
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


def _infer_repo_root_for_document(path: Path) -> Path | None:
    """Walk up from a document path to find the repo root (parent of docs/)."""
    for parent in path.parents:
        if (parent / DOCS).exists() and (parent / ARCH_REPO).exists():
            return parent
        if (parent / DOCS).exists() and (parent / MODEL).exists():
            return parent
    return None


def _is_absolute_markdown_link(href: str) -> bool:
    return (
        href.startswith("/") or href.startswith("file://") or bool(_WINDOWS_ABS_PATH_RE.match(href))
    )


def _verify_paths(
    paths: list[Path],
    verifier_fn: Callable[[Path], VerificationResult],
    *,
    workers: int,
) -> list[VerificationResult]:
    if not paths:
        return []
    if workers <= 1:
        return [verifier_fn(path) for path in paths]
    with ThreadPoolExecutor(max_workers=workers) as executor:
        return list(executor.map(verifier_fn, paths))


def _results_from_state(
    prev: IncrementalState, inv: FileInventory
) -> list[VerificationResult] | None:
    out: list[VerificationResult] = []
    for rel in inv.ordered_paths:
        raw = prev.results.get(rel)
        if not isinstance(raw, dict):
            return None
        parsed = _deserialize_result(inv.rel_to_path[rel], raw)
        if parsed is None:
            return None
        out.append(parsed)
    return out


def _merge_results(
    prev: IncrementalState, inv: FileInventory, fresh: list[VerificationResult]
) -> list[VerificationResult]:
    by_rel = {inv.path_to_rel[r.path]: r for r in fresh}
    merged: list[VerificationResult] = []
    for rel in inv.ordered_paths:
        if rel in by_rel:
            merged.append(by_rel[rel])
            continue
        raw = prev.results.get(rel)
        if not isinstance(raw, dict):
            return fresh
        parsed = _deserialize_result(inv.rel_to_path[rel], raw)
        if parsed is None:
            return fresh
        merged.append(parsed)
    return merged


def _deserialize_result(path: Path, data: dict) -> VerificationResult | None:
    file_type = data.get("file_type")
    if file_type not in {"entity", "connection", "diagram"}:
        return None
    issues_raw = data.get("issues", [])
    if not isinstance(issues_raw, list):
        return None
    issues: list[Issue] = []
    for item in issues_raw:
        if not isinstance(item, dict):
            return None
        severity = item.get("severity")
        if severity not in {Severity.ERROR, Severity.WARNING}:
            return None
        code = item.get("code")
        message = item.get("message")
        location = item.get("location")
        if not all(isinstance(v, str) for v in [code, message, location]):
            return None
        issues.append(
            Issue(severity=severity, code=str(code), message=str(message), location=str(location))
        )
    return VerificationResult(path=path, file_type=file_type, issues=issues)


__all__ = [
    "ArtifactRegistry",
    "ArtifactVerifier",
    "Issue",
    "Severity",
    "VerificationResult",
    "entity_id_from_path",
]
