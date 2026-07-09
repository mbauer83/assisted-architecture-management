"""Tests for connection cardinalities (feature i) and modeling guidance tool (feature iii).

Also covers the removal of element_category from EntityTypeInfo (feature ii).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import cast

import pytest

from src.application.modeling.artifact_write_formatting import format_outgoing_markdown
from src.application.verification.artifact_verifier import ArtifactVerifier
from src.application.verification.artifact_verifier_registry import ArtifactRegistry
from src.infrastructure.artifact_index import shared_artifact_index
from src.infrastructure.write.artifact_write.parse_existing import parse_outgoing_file
from src.infrastructure.write.artifact_write.type_guidance import get_type_guidance

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _all_entity_types() -> dict:
    # Use the same cached registry get_type_guidance reads (get_module_registry), not a fresh
    # build_module_registry(): a freshly built registry can reflect a different optional-module
    # (confidential_store) capability state than the cached one, making the count comparison
    # order-dependent under xdist. Comparing like-for-like keeps the assertion stable.
    from src.infrastructure.app_bootstrap import get_module_registry  # noqa: PLC0415

    return {str(k): v for k, v in get_module_registry().all_entity_types().items()}


@lru_cache(maxsize=1)
def _catalogs():
    from src.infrastructure.app_bootstrap import build_runtime_catalogs, get_module_registry  # noqa: PLC0415

    return build_runtime_catalogs(get_module_registry())


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _entity(artifact_id: str, artifact_type: str = "requirement") -> str:
    prefix = artifact_id.split("@")[0]
    rand = artifact_id.split(".")[1] if "." in artifact_id else "XXXXXX"
    return f"""\
---
artifact-id: {artifact_id}
artifact-type: {artifact_type}
name: "Test Entity"
version: 0.1.0
status: draft
last-updated: '2026-04-17'
---

<!-- §content -->

## Test Entity

<!-- §display -->

### archimate

```yaml
domain: Motivation
element-type: Requirement
label: "Test Entity"
alias: {prefix}_{rand}
```
"""


def _outgoing(source: str, header_lines: list[str]) -> str:
    sections = "\n".join(f"{h}\n" for h in header_lines)
    return f"""\
---
source-entity: {source}
version: 0.1.0
status: draft
last-updated: '2026-04-17'
---

<!-- §connections -->

{sections}
"""


def _guidance_entries(result: dict[str, object]) -> list[dict[str, object]]:
    entries = result["entity_types"]
    assert isinstance(entries, list)
    return [cast(dict[str, object], entry) for entry in entries]


def _guidance_total(result: dict[str, object]) -> int:
    total = result["total"]
    assert isinstance(total, int)
    return total


def _diagram_own_types(result: dict[str, object]) -> list[dict[str, object]]:
    diagram_guidance = cast(dict[str, object], result["diagram_type_guidance"])
    own_types = diagram_guidance["own_entity_types"]
    assert isinstance(own_types, list)
    return [cast(dict[str, object], entry) for entry in own_types]


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "architecture-repository"
    (root / "model" / "motivation" / "requirement").mkdir(parents=True)
    (root / "diagram-catalog" / "diagrams").mkdir(parents=True)
    return root


def _setup_two_entities(repo: Path) -> tuple[str, str]:
    src = "REQ@1000000010.SrcAaa.src"
    tgt = "REQ@1000000011.TgtBbb.tgt"
    _write(repo / "model/motivation/requirements" / f"{src}.md", _entity(src))
    _write(repo / "model/motivation/requirements" / f"{tgt}.md", _entity(tgt))
    return src, tgt


# ===========================================================================
# Feature i: Cardinality support
# ===========================================================================


class TestFormatOutgoingWithCardinality:
    """Unit tests for the formatter — no file I/O."""

    def test_no_cardinality_unchanged(self) -> None:
        content = format_outgoing_markdown(
            source_entity="REQ@1.A.src",
            version="0.1.0",
            status="draft",
            last_updated="2026-04-17",
            connections=[{"connection_type": "archimate-realization", "target_entity": "REQ@2.B.tgt"}],
        )
        assert "### archimate-realization → REQ@2.B.tgt" in content

    def test_src_cardinality_only(self) -> None:
        content = format_outgoing_markdown(
            source_entity="REQ@1.A.src",
            version="0.1.0",
            status="draft",
            last_updated="2026-04-17",
            connections=[
                {
                    "connection_type": "archimate-realization",
                    "target_entity": "REQ@2.B.tgt",
                    "src_cardinality": "1",
                }
            ],
        )
        assert "### archimate-realization [1] → REQ@2.B.tgt" in content

    def test_tgt_cardinality_only(self) -> None:
        content = format_outgoing_markdown(
            source_entity="REQ@1.A.src",
            version="0.1.0",
            status="draft",
            last_updated="2026-04-17",
            connections=[
                {
                    "connection_type": "archimate-realization",
                    "target_entity": "REQ@2.B.tgt",
                    "tgt_cardinality": "0..*",
                }
            ],
        )
        assert "### archimate-realization → [0..*] REQ@2.B.tgt" in content

    def test_both_cardinalities(self) -> None:
        content = format_outgoing_markdown(
            source_entity="REQ@1.A.src",
            version="0.1.0",
            status="draft",
            last_updated="2026-04-17",
            connections=[
                {
                    "connection_type": "archimate-realization",
                    "target_entity": "REQ@2.B.tgt",
                    "src_cardinality": "1",
                    "tgt_cardinality": "0..*",
                }
            ],
        )
        assert "### archimate-realization [1] → [0..*] REQ@2.B.tgt" in content

    def test_wildcard_src_cardinality(self) -> None:
        content = format_outgoing_markdown(
            source_entity="REQ@1.A.src",
            version="0.1.0",
            status="draft",
            last_updated="2026-04-17",
            connections=[
                {
                    "connection_type": "archimate-association",
                    "target_entity": "REQ@2.B.tgt",
                    "src_cardinality": "*",
                }
            ],
        )
        assert "### archimate-association [*] → REQ@2.B.tgt" in content

    def test_range_cardinality(self) -> None:
        content = format_outgoing_markdown(
            source_entity="REQ@1.A.src",
            version="0.1.0",
            status="draft",
            last_updated="2026-04-17",
            connections=[
                {
                    "connection_type": "archimate-realization",
                    "target_entity": "REQ@2.B.tgt",
                    "src_cardinality": "1..5",
                    "tgt_cardinality": "1..*",
                }
            ],
        )
        assert "### archimate-realization [1..5] → [1..*] REQ@2.B.tgt" in content


class TestParseOutgoingWithCardinality:
    """Round-trip parsing of cardinalities from .outgoing.md files."""

    def test_parse_no_cardinality(self, tmp_path: Path) -> None:
        path = tmp_path / "REQ@1.A.src.outgoing.md"
        path.write_text(
            _outgoing("REQ@1.A.src", ["### archimate-realization → REQ@2.B.tgt"]),
            encoding="utf-8",
        )
        parsed = parse_outgoing_file(path)
        assert len(parsed.connections) == 1
        conn = parsed.connections[0]
        assert conn["connection_type"] == "archimate-realization"
        assert conn["target_entity"] == "REQ@2.B.tgt"
        assert "src_cardinality" not in conn
        assert "tgt_cardinality" not in conn

    def test_parse_src_cardinality(self, tmp_path: Path) -> None:
        path = tmp_path / "REQ@1.A.src.outgoing.md"
        path.write_text(
            _outgoing("REQ@1.A.src", ["### archimate-realization [1] → REQ@2.B.tgt"]),
            encoding="utf-8",
        )
        parsed = parse_outgoing_file(path)
        conn = parsed.connections[0]
        assert conn["connection_type"] == "archimate-realization"
        assert conn["target_entity"] == "REQ@2.B.tgt"
        assert conn.get("src_cardinality") == "1"
        assert "tgt_cardinality" not in conn

    def test_parse_tgt_cardinality(self, tmp_path: Path) -> None:
        path = tmp_path / "REQ@1.A.src.outgoing.md"
        path.write_text(
            _outgoing("REQ@1.A.src", ["### archimate-realization → [0..*] REQ@2.B.tgt"]),
            encoding="utf-8",
        )
        parsed = parse_outgoing_file(path)
        conn = parsed.connections[0]
        assert conn["target_entity"] == "REQ@2.B.tgt"
        assert "src_cardinality" not in conn
        assert conn.get("tgt_cardinality") == "0..*"

    def test_parse_both_cardinalities(self, tmp_path: Path) -> None:
        path = tmp_path / "REQ@1.A.src.outgoing.md"
        path.write_text(
            _outgoing("REQ@1.A.src", ["### archimate-realization [1] → [0..*] REQ@2.B.tgt"]),
            encoding="utf-8",
        )
        parsed = parse_outgoing_file(path)
        conn = parsed.connections[0]
        assert conn.get("src_cardinality") == "1"
        assert conn.get("tgt_cardinality") == "0..*"

    def test_roundtrip_preserves_cardinalities(self, tmp_path: Path) -> None:
        """Parse → format → parse round-trip preserves both cardinalities."""
        path = tmp_path / "REQ@1.A.src.outgoing.md"
        path.write_text(
            _outgoing("REQ@1.A.src", ["### archimate-realization [1..3] → [1..*] REQ@2.B.tgt"]),
            encoding="utf-8",
        )
        parsed = parse_outgoing_file(path)
        reformatted = format_outgoing_markdown(
            source_entity="REQ@1.A.src",
            version="0.1.0",
            status="draft",
            last_updated="2026-04-17",
            connections=parsed.connections,
        )
        path2 = tmp_path / "roundtrip.outgoing.md"
        path2.write_text(reformatted, encoding="utf-8")
        parsed2 = parse_outgoing_file(path2)
        assert parsed2.connections[0].get("src_cardinality") == "1..3"
        assert parsed2.connections[0].get("tgt_cardinality") == "1..*"


class TestVerifierCardinality:
    """Tests for verifier's cardinality validation rules."""

    def test_valid_cardinality_passes_verification(self, repo: Path) -> None:
        src, tgt = _setup_two_entities(repo)
        out_path = repo / "model/motivation/requirements" / f"{src}.outgoing.md"
        _write(out_path, _outgoing(src, [f"### archimate-aggregation [1] → [0..*] {tgt}"]))
        registry = ArtifactRegistry(shared_artifact_index(repo))
        verifier = ArtifactVerifier(registry, catalogs=_catalogs())
        result = verifier.verify_outgoing_file(out_path)
        assert result.valid, [i.message for i in result.issues]

    def test_all_cardinality_formats_valid(self, repo: Path) -> None:
        src, tgt = _setup_two_entities(repo)
        for card in ["1", "0", "0..1", "1..5", "*", "1..*", "0..*"]:
            out_path = repo / "model/motivation/requirements" / f"{src}.outgoing.md"
            _write(out_path, _outgoing(src, [f"### archimate-association [{card}] → {tgt}"]))
            registry = ArtifactRegistry(shared_artifact_index(repo))
            verifier = ArtifactVerifier(registry, catalogs=_catalogs())
            result = verifier.verify_outgoing_file(out_path)
            assert result.valid, f"Cardinality '{card}' failed: {[i.message for i in result.issues]}"

    def test_invalid_cardinality_rejected(self, repo: Path) -> None:
        src, tgt = _setup_two_entities(repo)
        out_path = repo / "model/motivation/requirements" / f"{src}.outgoing.md"
        _write(out_path, _outgoing(src, [f"### archimate-realization [1:n] → {tgt}"]))
        registry = ArtifactRegistry(shared_artifact_index(repo))
        verifier = ArtifactVerifier(registry, catalogs=_catalogs())
        result = verifier.verify_outgoing_file(out_path)
        assert not result.valid
        assert any(i.code == "E125" for i in result.issues)

    def test_invalid_tgt_cardinality_rejected(self, repo: Path) -> None:
        src, tgt = _setup_two_entities(repo)
        out_path = repo / "model/motivation/requirements" / f"{src}.outgoing.md"
        _write(out_path, _outgoing(src, [f"### archimate-realization → [many] {tgt}"]))
        registry = ArtifactRegistry(shared_artifact_index(repo))
        verifier = ArtifactVerifier(registry, catalogs=_catalogs())
        result = verifier.verify_outgoing_file(out_path)
        assert not result.valid
        assert any(i.code == "E125" for i in result.issues)


class TestAddConnectionWithCardinality:
    """Integration tests: add_connection writes and verifies cardinalities."""

    def test_add_connection_with_src_cardinality(self, repo: Path) -> None:
        from src.infrastructure.write.artifact_write.connection import add_connection

        src, tgt = _setup_two_entities(repo)
        registry = ArtifactRegistry(shared_artifact_index(repo))
        verifier = ArtifactVerifier(registry, catalogs=_catalogs())

        def clear(_: Path) -> None:
            pass

        result = add_connection(
            repo_root=repo,
            registry=registry,
            verifier=verifier,
            clear_repo_caches=clear,
            source_entity=src,
            connection_type="archimate-influence",
            target_entity=tgt,
            description=None,
            version="0.1.0",
            status="draft",
            last_updated="2026-04-17",
            dry_run=False,
            src_cardinality="1",
        )
        assert result.wrote
        out_path = repo / "model/motivation/requirements" / f"{src}.outgoing.md"
        content = out_path.read_text()
        assert "### archimate-influence [1] →" in content

    def test_add_connection_with_both_cardinalities(self, repo: Path) -> None:
        from src.infrastructure.write.artifact_write.connection import add_connection

        src, tgt = _setup_two_entities(repo)
        registry = ArtifactRegistry(shared_artifact_index(repo))
        verifier = ArtifactVerifier(registry, catalogs=_catalogs())

        def clear(_: Path) -> None:
            pass

        result = add_connection(
            repo_root=repo,
            registry=registry,
            verifier=verifier,
            clear_repo_caches=clear,
            source_entity=src,
            connection_type="archimate-association",
            target_entity=tgt,
            description=None,
            version="0.1.0",
            status="draft",
            last_updated="2026-04-17",
            dry_run=False,
            src_cardinality="1",
            tgt_cardinality="0..*",
        )
        assert result.wrote
        out_path = repo / "model/motivation/requirements" / f"{src}.outgoing.md"
        content = out_path.read_text()
        assert "### archimate-association [1] → [0..*]" in content


# ===========================================================================
# Feature i (extended): API body cardinality validation (Pydantic)
# ===========================================================================


class TestConnectionBodyCardinality:
    """Pydantic-level validation of cardinality fields on Add/Edit request bodies."""

    def test_add_body_accepts_valid_formats(self) -> None:
        from src.infrastructure.gui.routers.connections import AddConnectionBody

        for card in ["1", "0", "0..1", "1..5", "100..200", "*", "1..*", "0..*"]:
            body = AddConnectionBody(
                source_entity="A",
                connection_type="archimate-realization",
                target_entity="B",
                src_cardinality=card,
            )
            assert body.src_cardinality == card

            body = AddConnectionBody(
                source_entity="A",
                connection_type="archimate-realization",
                target_entity="B",
                tgt_cardinality=card,
            )
            assert body.tgt_cardinality == card

    def test_add_body_rejects_invalid_formats(self) -> None:
        from pydantic import ValidationError

        from src.infrastructure.gui.routers.connections import AddConnectionBody

        for bad in ["1:n", "many", "1-5", "n", "one", "1..n", "*..1", "1..2..3"]:
            with pytest.raises(ValidationError, match="Invalid cardinality"):
                AddConnectionBody(
                    source_entity="A",
                    connection_type="archimate-realization",
                    target_entity="B",
                    src_cardinality=bad,
                )
            with pytest.raises(ValidationError, match="Invalid cardinality"):
                AddConnectionBody(
                    source_entity="A",
                    connection_type="archimate-realization",
                    target_entity="B",
                    tgt_cardinality=bad,
                )

    def test_add_body_accepts_none(self) -> None:
        from src.infrastructure.gui.routers.connections import AddConnectionBody

        body = AddConnectionBody(
            source_entity="A",
            connection_type="archimate-realization",
            target_entity="B",
        )
        assert body.src_cardinality is None
        assert body.tgt_cardinality is None

    def test_edit_body_accepts_valid_formats(self) -> None:
        from src.infrastructure.gui.routers.connections import EditConnectionBody

        body = EditConnectionBody(
            source_entity="A",
            connection_type="archimate-realization",
            target_entity="B",
            src_cardinality="1..*",
            tgt_cardinality="0..1",
        )
        assert body.src_cardinality == "1..*"
        assert body.tgt_cardinality == "0..1"

    def test_edit_body_rejects_invalid_formats(self) -> None:
        from pydantic import ValidationError

        from src.infrastructure.gui.routers.connections import EditConnectionBody

        with pytest.raises(ValidationError, match="Invalid cardinality"):
            EditConnectionBody(
                source_entity="A",
                connection_type="archimate-realization",
                target_entity="B",
                src_cardinality="1:n",
            )
        with pytest.raises(ValidationError, match="Invalid cardinality"):
            EditConnectionBody(
                source_entity="A",
                connection_type="archimate-realization",
                target_entity="B",
                tgt_cardinality="many",
            )

    def test_edit_body_accepts_none_to_clear(self) -> None:
        """None is valid for edit — it signals 'remove this cardinality'."""
        from src.infrastructure.gui.routers.connections import EditConnectionBody

        body = EditConnectionBody(
            source_entity="A",
            connection_type="archimate-realization",
            target_entity="B",
            src_cardinality=None,
            tgt_cardinality=None,
        )
        assert body.src_cardinality is None
        assert body.tgt_cardinality is None


# ===========================================================================
# Feature ii: element_category removed from EntityTypeInfo
# ===========================================================================


class TestElementCategoryRemoved:
    def test_entity_type_info_has_no_element_category(self) -> None:
        info = _all_entity_types()["requirement"]
        assert not hasattr(info, "element_category"), "element_category should have been removed from EntityTypeInfo"

    def test_entity_type_info_still_has_classes(self) -> None:
        info = _all_entity_types()["requirement"]
        assert hasattr(info, "classes")
        assert "motivation-element" in info.classes

    def test_category_map_not_exported(self) -> None:
        import src.domain.ontology_catalog as ol

        assert not hasattr(ol, "CATEGORY_MAP"), "CATEGORY_MAP should have been removed from the ontology catalog"


# ===========================================================================
# Feature iii: artifact_authoring_guidance MCP tool
# ===========================================================================


class TestGetTypeGuidance:
    def test_all_manually_creatable_types_returned_when_no_filter(self) -> None:
        # Internal types (promotion-created only, e.g. global-artifact-reference) are excluded:
        # guidance must never offer a type the create path rejects.
        result = get_type_guidance()
        creatable = [name for name, info in _all_entity_types().items() if not info.internal]
        assert _guidance_total(result) == len(creatable)
        assert isinstance(result["entity_types"], list)

    def test_all_types_include_domain(self) -> None:
        result = get_type_guidance()
        for entry in _guidance_entries(result):
            assert "domain" in entry

    def test_filter_by_entity_type_names(self) -> None:
        result = get_type_guidance(filter=["requirement", "goal"])
        assert _guidance_total(result) == 2
        names = {cast(str, e["name"]) for e in _guidance_entries(result)}
        assert names == {"requirement", "goal"}

    def test_filter_by_entity_type_includes_domain(self) -> None:
        result = get_type_guidance(filter=["requirement"])
        entry = _guidance_entries(result)[0]
        assert "domain" in entry
        assert entry["domain"] == "motivation"

    def test_filter_by_domain_name(self) -> None:
        result = get_type_guidance(filter=["Motivation"])
        assert _guidance_total(result) > 0
        for entry in _guidance_entries(result):
            assert "domain" not in entry  # omitted when filtering by domain

    def test_filter_by_domain_dir_name(self) -> None:
        result = get_type_guidance(filter=["motivation"])
        assert _guidance_total(result) > 0

    def test_filter_by_domain_case_insensitive(self) -> None:
        r1 = get_type_guidance(filter=["MOTIVATION"])
        r2 = get_type_guidance(filter=["Motivation"])
        assert _guidance_total(r1) == _guidance_total(r2)

    def test_unknown_filter_returns_error(self) -> None:
        result = get_type_guidance(filter=["nonexistent-thing"])
        assert "error" in result

    def test_each_entry_has_required_fields(self) -> None:
        result = get_type_guidance(filter=["requirement"])
        entry = _guidance_entries(result)[0]
        for field in ("name", "prefix", "classes", "create_when", "never_create_when", "permitted_connections"):
            assert field in entry, f"Missing field: {field}"

    def test_permitted_connections_structure(self) -> None:
        result = get_type_guidance(filter=["requirement"])
        conns = cast(dict[str, list[object]], _guidance_entries(result)[0]["permitted_connections"])
        assert isinstance(conns, dict)
        for key in ("outgoing", "incoming", "symmetric"):
            assert key in conns

    def test_permitted_connections_non_empty(self) -> None:
        result = get_type_guidance(filter=["requirement"])
        conns = cast(dict[str, list[object]], _guidance_entries(result)[0]["permitted_connections"])
        total = sum(len(v) for v in conns.values())
        assert total > 0, "requirement should have at least some permitted connections"

    def test_create_when_and_never_create_when_are_strings(self) -> None:
        result = get_type_guidance(filter=["capability"])
        entry = _guidance_entries(result)[0]
        assert isinstance(entry["create_when"], str)
        assert isinstance(entry["never_create_when"], str)
        assert len(entry["create_when"]) > 0

    def test_multiple_domains_filter(self) -> None:
        r_mot = get_type_guidance(filter=["Motivation"])
        r_str = get_type_guidance(filter=["Strategy"])
        r_both = get_type_guidance(filter=["Motivation", "Strategy"])
        assert _guidance_total(r_both) == _guidance_total(r_mot) + _guidance_total(r_str)

    def test_mcp_tool_function_reachable(self) -> None:
        from src.infrastructure.mcp.artifact_mcp.write.entity import artifact_authoring_guidance

        result = artifact_authoring_guidance(filter=["stakeholder"])
        assert _guidance_total(result) == 1
        assert _guidance_entries(result)[0]["name"] == "stakeholder"

    def test_activity_guidance_exposes_structured_mapping_sources(self) -> None:
        result = get_type_guidance(diagram_type="activity")

        own_types = _diagram_own_types(result)
        swimlane = next(entry for entry in own_types if entry["entity_type"] == "swimlane")
        mappings = cast(dict[str, object], swimlane["permitted_mappings"])

        assert mappings["entity_types"] == ["role", "business-actor", "application-component"]
        sources = cast(list[dict[str, object]], mappings["sources"])
        assert sources[0]["ontology"] == "archimate_next"
        assert sources[0]["entity_type"] == "role"

    def test_archimate_guidance_exposes_connection_annotation_notes(self) -> None:
        result = get_type_guidance(diagram_type="archimate-technology")

        diagram_guidance = cast(dict[str, object], result["diagram_type_guidance"])
        notes = cast(list[str], diagram_guidance["puml_notes"])

        assert any("hidden by default" in note for note in notes)
        assert any("diagram_connections" in note for note in notes)
        assert any("include_description" in note for note in notes)

    # ---- Disabled module guidance ------------------------------------------

    def test_disabled_sysml_domain_filter_returns_error(self) -> None:
        result = get_type_guidance(filter=["sysml"])
        assert "error" in result
        assert result["unknown"] == ["sysml"]

    def test_disabled_sysml_entity_type_filter_returns_error(self) -> None:
        result = get_type_guidance(filter=["part-definition"])
        assert "error" in result
        assert result["unknown"] == ["part-definition"]

    # ---- Sequence diagram module allowed_bindings --------------------------

    def test_sequence_guidance_has_allowed_bindings(self) -> None:
        result = get_type_guidance(diagram_type="sequence")
        guidance = cast(dict[str, object], result["diagram_type_guidance"])
        assert "allowed_bindings" in guidance

    def test_sequence_allowed_bindings_has_lifeline_and_message(self) -> None:
        result = get_type_guidance(diagram_type="sequence")
        guidance = cast(dict[str, object], result["diagram_type_guidance"])
        ab = cast(dict[str, object], guidance["allowed_bindings"])
        entity_ab = cast(dict[str, object], ab.get("entity", {}))
        assert "lifeline" in entity_ab, "allowed_bindings.entity must have 'lifeline' entry"
        assert "message" in entity_ab, "allowed_bindings.entity must have 'message' entry"

    def test_sequence_lifeline_correspondence_kinds(self) -> None:
        result = get_type_guidance(diagram_type="sequence")
        guidance = cast(dict[str, object], result["diagram_type_guidance"])
        ab = cast(dict[str, object], guidance["allowed_bindings"])
        lifeline = cast(dict[str, object], cast(dict[str, object], ab["entity"])["lifeline"])
        kinds = cast(list[str], lifeline["correspondence_kinds"])
        assert "represents" in kinds
        assert lifeline["default_correspondence_kind"] == "represents"
        assert "entity-id" in cast(list[str], lifeline["target_forms"])

    def test_sequence_message_correspondence_kinds(self) -> None:
        result = get_type_guidance(diagram_type="sequence")
        guidance = cast(dict[str, object], result["diagram_type_guidance"])
        ab = cast(dict[str, object], guidance["allowed_bindings"])
        message = cast(dict[str, object], cast(dict[str, object], ab["entity"])["message"])
        kinds = cast(list[str], message["correspondence_kinds"])
        assert "represents" in kinds
        assert "abstracts" in kinds
        assert "connection-id" in cast(list[str], message["target_forms"])
