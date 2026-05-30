"""Scaffold a new engagement repository with baseline schemata and document types."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from src.application.artifact_document_schema import get_document_subdirectory
from src.config.repo_paths import ARCH_DOC_SCHEMATA, ARCH_REPO, DIAGRAM_CATALOG, DIAGRAMS, DOCS, MODEL, RENDERED

INITIAL_COMMIT_MESSAGE = "Initialize engagement architecture repository"

DEFAULT_DOCUMENT_SCHEMAS: dict[str, dict] = {
    "adr": {
        "abbreviation": "ADR",
        "name": "Architecture Decision Record",
        "subdirectory": "adr",
        "frontmatter_schema": {
            "type": "object",
            "required": ["title", "status"],
            "properties": {
                "title": {"type": "string"},
                "status": {"type": "string", "enum": ["draft", "accepted", "rejected", "superseded"]},
                "deciders": {"type": "array", "items": {"type": "string"}},
                "date": {"type": "string"},
            },
        },
        "required_sections": ["Context", "Decision", "Consequences"],
        "suggested_entity_type_connections": ["@all"],
    },
    "spec": {
        "abbreviation": "SPC",
        "name": "Specification",
        "frontmatter_schema": {
            "type": "object",
            "required": ["title", "status"],
            "properties": {
                "title": {"type": "string"},
                "status": {"type": "string", "enum": ["draft", "accepted", "rejected", "superseded"]},
                "keywords": {"type": "array", "items": {"type": "string"}},
            },
        },
        "required_sections": ["Scope", "Summary", "Specification"],
    },
    "standard": {
        "abbreviation": "STD",
        "name": "Standard",
        "frontmatter_schema": {
            "type": "object",
            "required": ["title", "status", "applies_to"],
            "properties": {
                "title": {"type": "string"},
                "status": {"type": "string", "enum": ["draft", "accepted", "rejected", "superseded"]},
                "applies_to": {"type": "array", "items": {"type": "string"}},
            },
        },
        "required_sections": ["Scope", "Motivation", "Summary", "Specification"],
        "required_entity_type_connections": ["requirement"],
        "suggested_entity_type_connections": ["principle", "goal"],
    },
}

DEFAULT_SCHEMATA: dict[str, dict] = {
    "attributes.capability.schema.json": {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "attributes.capability.schema.json",
        "title": "Capability Attribute Schema",
        "description": "Attribute schema for Properties table in Capability entities.",
        "type": "object",
        "required": ["Maturity"],
        "properties": {
            "Maturity": {
                "type": "string",
                "enum": ["Initial", "Developing", "Defined", "Managed", "Optimising"],
            },
            "Realizes": {"type": "string"},
        },
        "additionalProperties": True,
    },
    "attributes.driver.schema.json": {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "attributes.driver.schema.json",
        "title": "Driver Attribute Schema",
        "description": "Attribute schema for Properties table in Driver entities.",
        "type": "object",
        "required": ["Category", "Source"],
        "properties": {
            "Category": {
                "type": "string",
                "enum": [
                    "External Trend",
                    "Internal Challenge",
                    "Organizational",
                    "Organizational Constraint",
                    "Organizational Trend",
                    "Technical Trend",
                    "Technological",
                    "Technology Trend",
                ],
            },
            "Source": {"type": "string"},
        },
        "additionalProperties": True,
    },
    "attributes.goal.schema.json": {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "attributes.goal.schema.json",
        "title": "Goal Attribute Schema",
        "description": "Attribute schema for Properties table in Goal entities.",
        "type": "object",
        "required": ["Priority", "Measurability"],
        "properties": {
            "Priority": {"type": "string", "enum": ["Must", "Should", "Could", "Won't"]},
            "Measurability": {"type": "string"},
        },
        "additionalProperties": True,
    },
    "attributes.principle.schema.json": {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "attributes.principle.schema.json",
        "title": "Principle Attribute Schema",
        "description": "Attribute schema for Properties table in Principle entities.",
        "type": "object",
        "required": ["Priority", "Rationale"],
        "properties": {
            "Priority": {"type": "string", "enum": ["Must", "Should", "Could", "Won't"]},
            "Rationale": {"type": "string"},
        },
        "additionalProperties": True,
    },
    "attributes.requirement.schema.json": {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "attributes.requirement.schema.json",
        "title": "Requirement Attribute Schema",
        "description": "Attribute schema for Properties table in Requirement entities.",
        "type": "object",
        "required": ["Priority", "Category"],
        "properties": {
            "Priority": {"type": "string", "enum": ["Must", "Should", "Could", "Won't", "Never"]},
            "Category": {"type": "string"},
            "Children": {"type": "string"},
        },
        "additionalProperties": True,
    },
    "attributes.stakeholder.schema.json": {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "attributes.stakeholder.schema.json",
        "title": "Stakeholder Attribute Schema",
        "description": "Attribute schema for Properties table in Stakeholder entities.",
        "type": "object",
        "required": ["Category", "Concerns"],
        "properties": {
            "Category": {"type": "string"},
            "Concerns": {"type": "string"},
        },
        "additionalProperties": True,
    },
    "frontmatter.diagram.schema.json": {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "frontmatter.diagram.schema.json",
        "title": "Diagram Frontmatter Schema",
        "description": "JSON Schema for diagram file frontmatter. Extends tool-required base fields.",
        "type": "object",
        "required": ["artifact-id", "artifact-type", "name", "diagram-type", "version", "status", "last-updated"],
        "properties": {
            "artifact-id": {"type": "string", "pattern": "^[A-Z]{2,6}@\\d+\\.[A-Za-z0-9_-]+\\..+$"},
            "artifact-type": {"type": "string", "enum": ["diagram"]},
            "name": {"type": "string", "minLength": 1},
            "diagram-type": {"type": "string"},
            "version": {"type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$"},
            "status": {"type": "string", "enum": ["draft", "active", "deprecated"]},
            "keywords": {"type": "array", "items": {"type": "string"}},
            "last-updated": {"type": "string"},
        },
        "additionalProperties": True,
    },
    "frontmatter.entity.schema.json": {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "frontmatter.entity.schema.json",
        "title": "Entity Frontmatter Schema",
        "description": (
            "JSON Schema for entity file frontmatter. Extends the tool-required base fields; "
            "tool-required fields cannot be removed or overridden."
        ),
        "type": "object",
        "required": ["artifact-id", "artifact-type", "name", "version", "status", "last-updated"],
        "properties": {
            "artifact-id": {"type": "string", "pattern": "^[A-Z]{2,6}@\\d+\\.[A-Za-z0-9_-]+\\..+$"},
            "artifact-type": {"type": "string"},
            "name": {"type": "string", "minLength": 1},
            "version": {"type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$"},
            "status": {"type": "string", "enum": ["draft", "active", "deprecated"]},
            "keywords": {"type": "array", "items": {"type": "string"}},
            "last-updated": {"type": "string"},
        },
        "additionalProperties": True,
    },
    "frontmatter.outgoing.schema.json": {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "frontmatter.outgoing.schema.json",
        "title": "Outgoing Connections File Frontmatter Schema",
        "description": "JSON Schema for .outgoing.md file frontmatter. Extends tool-required base fields.",
        "type": "object",
        "required": ["source-entity", "version", "status", "last-updated"],
        "properties": {
            "source-entity": {"type": "string", "pattern": "^[A-Z]{2,6}@\\d+\\.[A-Za-z0-9_-]+\\..+$"},
            "version": {"type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$"},
            "status": {"type": "string", "enum": ["draft", "active", "deprecated"]},
            "last-updated": {"type": "string"},
        },
        "additionalProperties": True,
    },
}


def _write_json_if_missing(path: Path, payload: dict) -> None:
    if path.exists():
        return
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _run_git(args: list[str], cwd: Path) -> None:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise SystemExit(f"ERROR: git {' '.join(args)} failed for {cwd}\n{result.stderr.strip()}")


def _git_output(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
    )


def _has_commits(path: Path) -> bool:
    return _git_output(["rev-parse", "--verify", "HEAD"], cwd=path).returncode == 0


def _ensure_git_repo(path: Path, *, git_url: str | None, branch: str) -> None:
    git_dir = path / ".git"
    if not git_dir.exists():
        _run_git(["init", "-b", branch], cwd=path)
    if git_url is None:
        return

    result = _git_output(["remote", "get-url", "origin"], cwd=path)
    if result.returncode != 0:
        _run_git(["remote", "add", "origin", git_url], cwd=path)
        return
    current = result.stdout.strip()
    if current != git_url:
        raise SystemExit(f"ERROR: {path} already has origin={current!r}, expected {git_url!r}")
def _commit_initial_scaffold(path: Path, *, commit_author_name: str, commit_author_email: str) -> None:
    if _has_commits(path):
        return
    _run_git(["add", "-A"], cwd=path)
    result = _git_output(
        [
            "-c",
            f"user.name={commit_author_name}",
            "-c",
            f"user.email={commit_author_email}",
            "commit",
            "-m",
            INITIAL_COMMIT_MESSAGE,
        ],
        cwd=path,
    )
    if result.returncode != 0:
        raise SystemExit(f"ERROR: git commit failed for {path}\n{result.stderr.strip()}")


def create_engagement_repo(
    path: Path,
    *,
    git_url: str | None = None,
    branch: str = "main",
    commit_author_name: str = "arch-switch-engagement",
    commit_author_email: str = "arch-switch-engagement@local.invalid",
) -> Path:
    if path.exists() and not path.is_dir():
        raise SystemExit(f"ERROR: engagement path exists but is not a directory: {path}")
    if path.exists() and any(path.iterdir()) and not (path / MODEL).is_dir():
        raise SystemExit(f"ERROR: engagement path exists but does not look like an architecture repository: {path}")

    path.mkdir(parents=True, exist_ok=True)
    (path / MODEL).mkdir(parents=True, exist_ok=True)
    (path / DOCS).mkdir(parents=True, exist_ok=True)
    (path / DIAGRAM_CATALOG / DIAGRAMS).mkdir(parents=True, exist_ok=True)
    (path / DIAGRAM_CATALOG / RENDERED).mkdir(parents=True, exist_ok=True)
    documents_dir = path / ARCH_REPO / ARCH_DOC_SCHEMATA
    schemata_dir = path / ARCH_REPO / "schemata"
    documents_dir.mkdir(parents=True, exist_ok=True)
    schemata_dir.mkdir(parents=True, exist_ok=True)

    for doc_type, schema in DEFAULT_DOCUMENT_SCHEMAS.items():
        _write_json_if_missing(documents_dir / f"{doc_type}.json", schema)
        (path / DOCS / get_document_subdirectory(schema, doc_type)).mkdir(parents=True, exist_ok=True)
    for filename, schema in DEFAULT_SCHEMATA.items():
        _write_json_if_missing(schemata_dir / filename, schema)

    _ensure_git_repo(path, git_url=git_url, branch=branch)
    _commit_initial_scaffold(
        path,
        commit_author_name=commit_author_name,
        commit_author_email=commit_author_email,
    )
    return path.resolve()
