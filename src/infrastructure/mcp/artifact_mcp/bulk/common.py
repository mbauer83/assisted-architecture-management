"""Shared helpers for bulk MCP write/delete operations."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Literal

from src.application.verification.artifact_verifier import ArtifactRegistry, ArtifactVerifier
from src.infrastructure.artifact_index import shared_artifact_index
from src.infrastructure.mcp.artifact_mcp.edit_tools import _require_registry, _resolve

KNOWN_DELETE_OPS = frozenset(
    {"delete_entity", "delete_connection", "delete_document", "delete_diagram"}
)
KNOWN_OPS = frozenset({"create_entity", "add_connection", "edit_entity", "edit_connection"})


def resolve_ref(value: str, ref_map: dict[str, str]) -> str:
    if value.startswith("$ref:"):
        key = value[5:]
        resolved = ref_map.get(key)
        if resolved is None:
            raise ValueError(
                f"Unresolved $ref '{key}' — no create_entity item with _ref='{key}' succeeded"
            )
        return resolved
    return value


def strip_content(result: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in result.items() if key != "content"}


def resolve_root(repo_root: str | None) -> Path:
    root, _registry, _verifier = _resolve(repo_root, need_registry=False)
    return root


def local_apply_paths(repo_root: Path, paths: list[Path]) -> None:
    shared_artifact_index([repo_root]).apply_file_changes(paths)


def temp_repo_callbacks(
    repo_root: Path,
) -> tuple[Callable[[Path], None], Callable[[Path], None], set[Path], set[Path]]:
    macros_dirty: set[Path] = set()
    changed_paths: set[Path] = set()

    def clear_repo_caches(path: Path) -> None:
        changed_paths.add(path.resolve())
        local_apply_paths(repo_root, [path])

    def mark_macros_dirty(path: Path) -> None:
        macros_dirty.add(path.resolve())

    return clear_repo_caches, mark_macros_dirty, macros_dirty, changed_paths


def map_path_to_live(path_value: object, *, staged_root: Path, live_root: Path) -> object:
    if not isinstance(path_value, str):
        return path_value
    path = Path(path_value)
    try:
        rel = path.relative_to(staged_root)
    except ValueError:
        return path_value
    return str(live_root / rel)


def normalize_staged_result(
    result: dict[str, object],
    *,
    staged_root: Path,
    live_root: Path,
    dry_run: bool,
    committed: bool,
) -> dict[str, object]:
    out = dict(result)
    if "path" in out:
        out["path"] = map_path_to_live(out["path"], staged_root=staged_root, live_root=live_root)
    if dry_run or not committed:
        out["wrote"] = False
        out["dry_run"] = dry_run
    return out


def normalize_staged_verification(
    verification: dict[str, object],
    *,
    staged_root: Path,
    live_root: Path,
) -> dict[str, object]:
    out = dict(verification)
    out["repo_root"] = str(live_root)
    raw_results = out.get("results", [])
    results = raw_results if isinstance(raw_results, list) else []
    out["results"] = [
        {
            **result,
            "path": map_path_to_live(
                result.get("path"),
                staged_root=staged_root,
                live_root=live_root,
            ),
        }
        for result in results
        if isinstance(result, dict)
    ]
    return out


def _verification_payload(
    *,
    repo_root: Path,
    registry: ArtifactRegistry,
    results: list,
    executed: bool,
) -> dict[str, object]:
    invalid = [result for result in results if not result.valid]
    return {
        "valid": not invalid,
        "executed": executed,
        "counts": {
            "files": len(results),
            "valid_files": sum(1 for result in results if result.valid),
            "invalid_files": len(invalid),
            "errors": sum(len(result.errors) for result in results),
            "warnings": sum(len(result.warnings) for result in results),
        },
        "results": [
            {
                "path": str(result.path),
                "file_type": result.file_type,
                "valid": result.valid,
                "issues": [
                    {
                        "severity": issue.severity,
                        "code": issue.code,
                        "message": issue.message,
                        "location": issue.location,
                    }
                    for issue in result.issues
                ],
            }
            for result in invalid
        ],
        "repo_root": str(repo_root),
        "registry_entities": len(registry.entity_ids()),
    }


def stage_batch_verification(repo_root: Path, *, changed_paths: set[Path]) -> dict[str, object]:
    registry = ArtifactRegistry(shared_artifact_index([repo_root]))
    verifier = ArtifactVerifier(registry)
    results = verifier.verify_paths(
        repo_root,
        changed_paths=sorted(changed_paths),
        verification_scope="impacted",
        include_diagrams=True,
    )
    return _verification_payload(
        repo_root=repo_root,
        registry=registry,
        results=results,
        executed=True,
    )


def batch_verification(
    repo_root: str | None,
    *,
    dry_run: bool,
    executed: bool,
    changed_paths: list[Path] | None = None,
    verification_scope: Literal["changed", "impacted", "full"] = "full",
) -> dict[str, object]:
    if dry_run or not executed:
        return {
            "valid": True,
            "executed": False,
            "counts": {"files": 0, "valid_files": 0, "invalid_files": 0, "errors": 0, "warnings": 0},
            "results": [],
        }

    root, registry, verifier = _resolve(repo_root, need_registry=True)
    registry = _require_registry(registry)
    if changed_paths and verification_scope in {"changed", "impacted"}:
        results = verifier.verify_paths(
            root,
            changed_paths=changed_paths,
            verification_scope=verification_scope,
            include_diagrams=True,
        )
    else:
        results = verifier.verify_all(root, include_diagrams=True)
    return _verification_payload(
        repo_root=root,
        registry=registry,
        results=results,
        executed=True,
    )
