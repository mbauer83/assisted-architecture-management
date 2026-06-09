"""Cascade delete for model-project groups.

Two-stage: _cascade_preflight (dry_run=True) → impact report only.
           _cascade_apply   (dry_run=False) → applies, verifies, rolls back on error.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from src.application.repo_path_helpers import all_model_roots, diagram_source_root, docs_root
from src.infrastructure.write.artifact_write._cascade_helpers import (
    conn_row_touches,
    conn_touches,
    find_broken_links,
    is_puml_customised,
    read_connection_targets,
    read_diagram_frontmatter,
    read_frontmatter_id_name,
    read_source_entity_id,
    remove_from_groups_yaml,
    rollback_cascade,
)

# ---------------------------------------------------------------------------
# Preflight
# ---------------------------------------------------------------------------


def _cascade_preflight(repo_root: Path, project_slug: str) -> dict:
    """Compute full impact of deleting a model-project — no mutations."""
    project_dir = repo_root / "projects" / project_slug / "model"

    owned_entities: list[dict] = []
    owned_connections: list[dict] = []
    owned_entity_ids: set[str] = set()
    owned_paths: set[Path] = set()

    if project_dir.exists():
        for f in sorted(project_dir.rglob("*.md")):
            if f.name.endswith(".outgoing.md"):
                owned_connections.append({"path": str(f.relative_to(repo_root))})
                continue
            fm = read_frontmatter_id_name(f)
            if fm:
                eid, name = fm
                owned_entity_ids.add(eid)
                owned_paths.add(f)
                owned_entities.append({"id": eid, "name": name, "path": str(f.relative_to(repo_root))})

    # Foreign connections (source outside project, target inside)
    foreign_connections: list[dict] = []
    for model_root in all_model_roots(repo_root):
        for f in sorted(model_root.rglob("*.outgoing.md")):
            src_id = read_source_entity_id(f)
            if src_id and src_id in owned_entity_ids:
                continue
            for tgt_id in read_connection_targets(f):
                if tgt_id in owned_entity_ids:
                    foreign_connections.append(
                        {"path": str(f.relative_to(repo_root)), "source": src_id or "?", "target": tgt_id}
                    )
                    break

    # Foreign diagrams referencing owned entities
    foreign_diagrams: list[dict] = []
    src_root = diagram_source_root(repo_root)
    if src_root.exists():
        for f in sorted(src_root.rglob("*.puml")):
            fm = read_diagram_frontmatter(f)
            if fm is None:
                continue
            ids_used = fm.get("entity-ids-used")
            if not isinstance(ids_used, list):
                continue
            entities_removed = [eid for eid in ids_used if eid in owned_entity_ids]
            if not entities_removed:
                continue
            conn_ids_used = fm.get("connection-ids-used")
            conns_removed = [
                cid for cid in (conn_ids_used if isinstance(conn_ids_used, list) else [])
                if conn_touches(cid, owned_entity_ids)
            ]
            has_de = isinstance(fm.get("diagram-entities"), dict)
            foreign_diagrams.append({
                "id": str(fm.get("artifact-id", "")),
                "name": str(fm.get("name", f.stem)),
                "path": str(f.relative_to(repo_root)),
                "entities_removed": entities_removed,
                "connections_removed": conns_removed,
                "puml_customised": is_puml_customised(f, fm) if has_de else True,
            })

    # Blocking documents
    docs_blocking: list[dict] = []
    docs_dir = docs_root(repo_root)
    if docs_dir.exists():
        for f in sorted(docs_dir.rglob("*.md")):
            broken = find_broken_links(f, owned_paths, repo_root)
            if broken:
                fm_doc = read_frontmatter_id_name(f)
                docs_blocking.append({
                    "id": fm_doc[0] if fm_doc else "",
                    "title": fm_doc[1] if fm_doc else f.stem,
                    "path": str(f.relative_to(repo_root)),
                    "broken_links": broken,
                })

    return {
        "project": project_slug,
        "dry_run": True,
        "owned": {"entities": owned_entities, "connections": owned_connections},
        "foreign": {
            "connections": foreign_connections,
            "diagrams": foreign_diagrams,
            "documents_blocking": docs_blocking,
        },
        "apply_blocked_by": [d["path"] for d in docs_blocking],
    }


# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------


def _cascade_apply(repo_root: Path, project_slug: str, preflight: dict) -> dict:
    """Execute the cascade delete. Caller must ensure apply_blocked_by is empty."""
    from src.application.modeling.artifact_write_formatting import format_diagram_puml  # noqa: PLC0415
    from src.infrastructure.write.artifact_write.boundary import today_iso  # noqa: PLC0415
    from src.infrastructure.write.artifact_write.diagram_render import _render_diagram_entities_puml  # noqa: PLC0415
    from src.infrastructure.write.artifact_write.parse_existing import parse_diagram_file  # noqa: PLC0415

    backups: list[tuple[Path, bytes | None]] = []
    staged: list[str] = []
    warnings: list[str] = []

    def _git(args: list[str]) -> None:
        subprocess.run(["git", *args], cwd=repo_root, capture_output=True, text=True, check=False)

    def _rm(path: Path) -> None:
        backups.append((path, path.read_bytes() if path.exists() else None))
        rel = str(path.relative_to(repo_root))
        _git(["rm", "-f", rel])
        staged.append(rel)

    try:
        for rec in preflight["owned"]["entities"]:
            _rm(repo_root / rec["path"])
        for rec in preflight["owned"]["connections"]:
            p = repo_root / rec["path"]
            if p.exists():
                _rm(p)

        done: set[str] = set()
        for rec in preflight["foreign"]["connections"]:
            pth = rec["path"]
            if pth not in done:
                done.add(pth)
                p = repo_root / pth
                if p.exists():
                    _rm(p)

        for drec in preflight["foreign"]["diagrams"]:
            diagram_path = repo_root / drec["path"]
            if not diagram_path.exists():
                continue
            parsed = parse_diagram_file(diagram_path)
            fm = parsed.frontmatter
            remove_eids = set(drec["entities_removed"])
            remove_cids = set(drec["connections_removed"])
            raw_eids = fm.get("entity-ids-used")
            raw_cids = fm.get("connection-ids-used")
            new_eids = [e for e in (raw_eids if isinstance(raw_eids, list) else []) if e not in remove_eids]
            new_cids = [c for c in (raw_cids if isinstance(raw_cids, list) else []) if c not in remove_cids]
            de = fm.get("diagram-entities")
            new_de: dict | None = None
            new_dc: list | None = None
            if isinstance(de, dict):
                new_de = {k: v for k, v in de.items() if k not in remove_eids and not k.startswith("_")}
                dc = fm.get("connections")
                if isinstance(dc, list):
                    new_dc = [c for c in dc if not conn_row_touches(c, remove_eids)]
                if drec["puml_customised"]:
                    warnings.append(
                        f"PUML body of diagram '{drec['name']}' was regenerated; "
                        "any manual customisations have been replaced."
                    )
                new_body = _render_diagram_entities_puml(
                    str(fm.get("diagram-type", "archimate")), str(fm.get("name", "")),
                    new_de, new_dc, repo_root,
                )
            else:
                new_body = parsed.puml_body
            content = format_diagram_puml(
                artifact_id=str(fm.get("artifact-id", "")),
                diagram_type=str(fm.get("diagram-type", "archimate")),
                name=str(fm.get("name", "")), version=str(fm.get("version", "0.1.0")),
                status=str(fm.get("status", "draft")), last_updated=today_iso(),
                entity_ids_used=new_eids or None, connection_ids_used=new_cids or None,
                diagram_entities=new_de, diagram_connections=new_dc, puml_body=new_body,
            )
            backups.append((diagram_path, diagram_path.read_bytes()))
            diagram_path.write_text(content, encoding="utf-8")
            rel = str(diagram_path.relative_to(repo_root))
            _git(["add", rel])
            staged.append(rel)

        remove_from_groups_yaml(repo_root, project_slug)
        arch_groups = repo_root / ".arch-repo" / "groups.yaml"
        if arch_groups.exists():
            _git(["add", str(arch_groups.relative_to(repo_root))])
            staged.append(str(arch_groups.relative_to(repo_root)))

        from src.application.verification.artifact_verifier import ArtifactVerifier  # noqa: PLC0415
        from src.application.verification.artifact_verifier_registry import ArtifactRegistry  # noqa: PLC0415
        from src.infrastructure.app_bootstrap import build_runtime_catalogs, get_module_registry  # noqa: PLC0415
        from src.infrastructure.artifact_index import shared_artifact_index  # noqa: PLC0415

        reg = ArtifactRegistry(shared_artifact_index(repo_root))
        _verifier = ArtifactVerifier(reg, catalogs=build_runtime_catalogs(get_module_registry()))
        errors = [
            f"{i.code}: {i.message} ({i.location})"
            for r in _verifier.verify_all(repo_root, include_diagrams=False)
            for i in r.issues if i.severity == "error"
        ]
        if errors:
            rollback_cascade(backups, repo_root)
            return {"project": project_slug, "dry_run": False, "applied": False, "errors": errors, "warnings": warnings}

    except Exception as exc:  # noqa: BLE001
        rollback_cascade(backups, repo_root)
        return {"project": project_slug, "dry_run": False, "applied": False, "errors": [str(exc)], "warnings": warnings}

    return {
        "project": project_slug, "dry_run": False, "applied": True,
        "staged_paths": staged, "warnings": warnings,
        "owned_deleted": len(preflight["owned"]["entities"]) + len(preflight["owned"]["connections"]),
        "foreign_connections_deleted": len(preflight["foreign"]["connections"]),
        "diagrams_updated": len(preflight["foreign"]["diagrams"]),
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def cascade_delete_model_project(
    repo_root: Path, project_slug: str, confirm: str, dry_run: bool,
) -> dict:
    """Entry point: preflight (dry_run=True) or apply (dry_run=False)."""
    if confirm != project_slug:
        raise ValueError(
            f"Model-project delete requires confirm={project_slug!r} (typed slug). Got {confirm!r}."
        )
    preflight = _cascade_preflight(repo_root, project_slug)
    if dry_run:
        return preflight
    if preflight["apply_blocked_by"]:
        return {
            **preflight, "dry_run": False, "applied": False,
            "errors": [
                f"Apply blocked: {len(preflight['apply_blocked_by'])} document(s) have links to "
                "entities in this project. Resolve them first."
            ],
        }
    return _cascade_apply(repo_root, project_slug, preflight)
