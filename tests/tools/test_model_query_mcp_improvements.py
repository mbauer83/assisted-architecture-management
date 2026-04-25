"""Tests for model query MCP improvements.

Updated for ArchiMate NEXT conventions:
- model/ directory (not model-entities/)
- New ID format: TYPE@epoch.random.friendly-name
- New frontmatter: removed engagement, phase-produced, owner-agent, safety-relevant
- Standard YAML frontmatter for diagrams (not comment-style)
"""

from pathlib import Path

from src.application.artifact_query import ArtifactRepository
from src.infrastructure.artifact_index import shared_artifact_index
from src.infrastructure.mcp import mcp_artifact_server


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _build_repo(root: Path) -> Path:
    _write(
        root / "model" / "application" / "components" / "APP@1712870400.kRZYOA.event-store.md",
        """---
artifact-id: APP@1712870400.kRZYOA.event-store
artifact-type: application-component
name: "Event Store"
version: 0.1.0
status: draft
keywords: [events, storage]
last-updated: '2026-04-14'
---

<!-- §content -->

## Event Store

Stores event streams.

## Properties

| Attribute | Value |
|---|---|
| (none) | (none) |

<!-- §display -->

### archimate

```yaml
domain: Application
element-type: ApplicationComponent
label: "Event Store"
alias: APP_kRZYOA
```
""",
    )
    _write(
        root / "diagram-catalog" / "diagrams" / "DIA@1712870400.DFgOaO.event-activity-overview.puml",
        """---
artifact-id: DIA@1712870400.DFgOaO.event-activity-overview
artifact-type: diagram
name: "Event Activity Overview"
diagram-type: activity-bpmn
version: 0.1.0
status: draft
last-updated: '2026-04-14'
---
@startuml
title Event Activity Overview
@enduml
""",
    )
    return root


def test_model_repository_search_priority_and_counts(tmp_path: Path) -> None:
    repo_root = _build_repo(tmp_path / "repo")
    repo = ArtifactRepository(shared_artifact_index(repo_root))

    strict = repo.search_artifacts(
        "event",
        prefer_record_type="diagram",
        strict_record_type=True,
        include_connections=False,
        include_diagrams=True,
    )
    assert strict.hits
    assert all(hit.record_type == "diagram" for hit in strict.hits)

    preferred = repo.search_artifacts(
        "event",
        prefer_record_type="diagram",
        strict_record_type=False,
        include_connections=False,
        include_diagrams=True,
    )
    assert preferred.hits
    assert preferred.hits[0].record_type == "diagram"

    counts = repo.count_artifacts_by("diagram_type", include_connections=False, include_diagrams=True)
    assert counts["activity-bpmn"] == 1


def test_model_query_mcp_projection_and_aggregate_tool(tmp_path: Path) -> None:
    repo_root = _build_repo(tmp_path / "repo")
    tool_map = mcp_artifact_server.mcp_read._tool_manager._tools

    listed = tool_map["artifact_query_list_artifacts"].fn(
        repo_root=str(repo_root),
        repo_scope="engagement",
        include_record_types=["entities"],
        fields=["artifact_id", "path"],
    )
    assert listed
    assert set(listed[0].keys()) == {"artifact_id", "path"}

    searched = tool_map["artifact_query_search_artifacts"].fn(
        "event",
        repo_root=str(repo_root),
        repo_scope="engagement",
        fields=["artifact_id", "record_type", "score"],
        include_record_types=["entities", "diagrams", "documents"],
        prefer_record_type="diagram",
    )
    assert searched["hits"]
    assert set(searched["hits"][0].keys()) <= {"artifact_id", "record_type", "score"}

    grouped = tool_map["artifact_query_stats"].fn(
        group_by="diagram_type",
        repo_root=str(repo_root),
        repo_scope="engagement",
    )
    assert grouped["counts"]["activity-bpmn"] == 1
