"""BDD scenarios for the MCP model writer tools.

These tests call the tool functions directly (without starting an MCP server)
so we can validate deterministic content generation and verifier-gated writes.

Updated for ArchiMate NEXT conventions:
- model/ directory (not model-entities/)
- .outgoing.md connections (not connections/ directory)
- New ID format: TYPE@epoch.random.friendly-name
- Removed: phase_produced, owner_agent, produced_by_skill, engagement, safety-relevant
- Added: keywords, last-updated
- model_add_connection (not model_create_connection)
"""

from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when

from src.common.model_verifier import ModelRegistry, ModelVerifier
from src.tools import mcp_model_server as tools


scenarios("features/model_write_tools.feature")


@pytest.fixture
def repo_root(tmp_path: Path) -> Path:
    # Minimal architecture repo skeleton with new conventions.
    root = tmp_path / "engagements" / "ENG-TEST" / "work-repositories" / "architecture-repository"
    (root / "model").mkdir(parents=True)
    (root / "diagram-catalog" / "diagrams").mkdir(parents=True)
    return root


@given("an empty engagement architecture repository")
def empty_repo(repo_root: Path) -> Path:
    return repo_root


@when("I dry-run create an entity", target_fixture="dry_run_result")
def dry_run_create_entity(repo_root: Path) -> dict[str, object]:
    return tools.model_create_entity(
        artifact_type="capability",
        name="My Capability",
        summary="A short description.",
        dry_run=True,
        repo_root=str(repo_root),
        repo_scope="engagement",
    )


@then("the dry-run result should include a valid entity verification")
def dry_run_result_valid(dry_run_result: dict[str, object]) -> None:
    verification = dry_run_result["verification"]
    assert isinstance(verification, dict)
    assert verification["file_type"] == "entity"
    assert verification["valid"] is True


@when("I attempt to add a connection referencing unknown entities", target_fixture="conn_error")
def add_connection_unknown_entities(repo_root: Path) -> Exception:
    with pytest.raises(Exception) as exc:
        tools.model_add_connection(
            connection_type="archimate-serving",
            source_entity="APP@0000000000.XXXXXX.nonexistent-source",
            target_entity="APP@0000000000.YYYYYY.nonexistent-target",
            dry_run=False,
            repo_root=str(repo_root),
            repo_scope="engagement",
        )
    return exc.value


@then("the call should fail with a helpful error")
def connection_error_helpful(conn_error: Exception) -> None:
    msg = str(conn_error)
    assert "not found" in msg.lower() or "unknown" in msg.lower() or "cannot" in msg.lower()


def _write_entity(repo_root: Path, artifact_type: str, name: str) -> dict[str, object]:
    """Create an entity using the tool and return the result dict."""
    result = tools.model_create_entity(
        artifact_type=artifact_type,
        name=name,
        summary=f"Test entity: {name}",
        dry_run=False,
        repo_root=str(repo_root),
        repo_scope="engagement",
    )
    assert result.get("wrote") is True
    return result


@given(
    "an engagement architecture repository with two entities and one connection",
    target_fixture="repo_with_entities_and_connection",
)
def repo_with_entities_and_connection(repo_root: Path) -> tuple[Path, str, str]:
    e1 = _write_entity(repo_root, "application-component", "EventStore")
    e2 = _write_entity(repo_root, "application-component", "LangGraph Orchestrator")

    e1_id = str(e1["artifact_id"])
    e2_id = str(e2["artifact_id"])

    conn = tools.model_add_connection(
        connection_type="archimate-serving",
        source_entity=e1_id,
        target_entity=e2_id,
        dry_run=False,
        repo_root=str(repo_root),
        repo_scope="engagement",
    )
    assert conn.get("wrote") is True

    # Sanity: verifier should pass across repo.
    verifier = ModelVerifier(ModelRegistry(repo_root))
    results = verifier.verify_all(repo_root)
    assert all(r.valid for r in results), [i for r in results for i in r.errors]
    return repo_root, e1_id, e2_id


@when("I create an archimate diagram with serving connection", target_fixture="diagram_result")
def create_archimate_diagram(
    repo_with_entities_and_connection: tuple[Path, str, str],
) -> dict[str, object]:
    repo_root, e1_id, e2_id = repo_with_entities_and_connection

    # Derive aliases from entity IDs: TYPE_randompart
    e1_parts = e1_id.split(".")
    e2_parts = e2_id.split(".")
    e1_alias = f"{e1_parts[0].split('@')[0]}_{e1_parts[1]}"
    e2_alias = f"{e2_parts[0].split('@')[0]}_{e2_parts[1]}"

    puml = f"""@startuml test-diagram-archimate-application
!include ../_macros.puml

$DECL_{e1_alias}()
$DECL_{e2_alias}()

{e1_alias} -[#0078A0]-> {e2_alias} : <<serving>>
@enduml
"""
    return tools.model_create_diagram(
        diagram_type="archimate-application",
        name="Test Diagram",
        puml=puml,
        artifact_id="test-diagram-archimate-application",
        dry_run=False,
        repo_root=str(repo_root),
        repo_scope="engagement",
        connection_inference="strict",
    )


@then("the diagram should verify successfully and reference the inferred ids")
def diagram_inferred_ids(
    diagram_result: dict[str, object],
    repo_with_entities_and_connection: tuple[Path, str, str],
) -> None:
    assert diagram_result.get("wrote") is True

    repo_root, e1_id, e2_id = repo_with_entities_and_connection

    # Verify the created file.
    p = Path(diagram_result["path"])
    verifier = ModelVerifier(ModelRegistry(repo_root))
    res = verifier.verify_diagram_file(p)
    assert res.valid is True, res.issues

    content = p.read_text(encoding="utf-8")
    assert "title Test Diagram" in content


def test_model_create_matrix_writes_valid_matrix(repo_root: Path) -> None:
    """Matrix creation should produce a verifiable matrix diagram file."""
    _write_entity(repo_root, "application-component", "EventStore")

    result = tools.model_create_matrix(
        name="Connection Matrix",
        purpose="Show connections between application components.",
        matrix_markdown=(
            "| Source | Target | Type |\n"
            "|---|---|---|\n"
            "| EventStore | Orchestrator | serving |\n"
        ),
        artifact_id="matrix-test-v1",
        dry_run=False,
        repo_root=str(repo_root),
        repo_scope="engagement",
    )

    assert result.get("wrote") is True
    verification = result.get("verification")
    assert isinstance(verification, dict)
    assert verification.get("valid") is True
