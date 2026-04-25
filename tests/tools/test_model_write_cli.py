from __future__ import annotations

from pathlib import Path

from src.infrastructure.write.artifact_write_cli import main


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _entity_md(artifact_id: str, name: str) -> str:
    return f"""\
---
artifact-id: {artifact_id}
artifact-type: requirement
name: "{name}"
version: 0.1.0
status: active
last-updated: '2026-04-20'
---

<!-- §content -->

## {name}

## Properties

| Attribute | Value |
|---|---|
| (none) | (none) |

<!-- §display -->

### archimate

```yaml
domain: Motivation
element-type: Requirement
label: "{name}"
alias: REQ_TEST
```
"""


def test_cli_delete_entity_dry_run(tmp_path: Path, capsys) -> None:
    repo = tmp_path / "engagements" / "ENG" / "architecture-repository"
    eid = "REQ@1000000000.TestAa.delete-me"
    _write(repo / "model" / "motivation" / "requirements" / f"{eid}.md", _entity_md(eid, "Delete Me"))

    rc = main(["--repo-root", str(repo), "delete-entity", eid, "--dry-run"])
    captured = capsys.readouterr()

    assert rc == 0
    assert "Would delete entity" in captured.out


def test_cli_delete_diagram_dry_run(tmp_path: Path, capsys) -> None:
    repo = tmp_path / "engagements" / "ENG" / "architecture-repository"
    did = "diag-delete"
    _write(
        repo / "diagram-catalog" / "diagrams" / f"{did}.puml",
        f"""\
---
artifact-id: {did}
artifact-type: diagram
diagram-type: activity-bpmn
name: "Diag"
version: 0.1.0
status: active
last-updated: '2026-04-20'
---
@startuml
:x;
@enduml
""",
    )

    rc = main(["--repo-root", str(repo), "delete-diagram", did, "--dry-run"])
    captured = capsys.readouterr()

    assert rc == 0
    assert "Would delete diagram" in captured.out
