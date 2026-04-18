"""Behavioural tests for ModelVerifier rules.

Covers verify_entity_file, verify_outgoing_file, and verify_all for both
single-repo and two-repo setups.  GRF-specific verifier rules are in
test_two_repo_and_grf.py; this file covers the non-GRF verification paths.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.common.model_verifier import ModelVerifier
from src.common.model_verifier_registry import ModelRegistry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _entity(
    artifact_id: str,
    artifact_type: str = "requirement",
    name: str = "Test Entity",
    *,
    extra_fm: str = "",
    no_content_section: bool = False,
    no_display_section: bool = False,
) -> str:
    prefix = artifact_id.split("@")[0]
    rand = artifact_id.split(".")[1] if "." in artifact_id else "XXXXXX"
    content_marker = "" if no_content_section else "<!-- §content -->"
    display_marker = "" if no_display_section else "<!-- §display -->"
    return f"""\
---
artifact-id: {artifact_id}
artifact-type: {artifact_type}
name: "{name}"
version: 0.1.0
status: draft
last-updated: '2026-04-17'{extra_fm}
---

{content_marker}

## {name}

{display_marker}

### archimate

```yaml
domain: Motivation
element-type: Requirement
label: "{name}"
alias: {prefix}_{rand}
```
"""


def _outgoing(source: str, connections: list[tuple[str, str]]) -> str:
    sections = "\n".join(f"### {ct} → {tgt}\n" for ct, tgt in connections)
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


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "engagements" / "ENG-T" / "architecture-repository"
    (root / "model").mkdir(parents=True)
    (root / "diagram-catalog" / "diagrams").mkdir(parents=True)
    return root


# ---------------------------------------------------------------------------
# verify_entity_file
# ---------------------------------------------------------------------------

class TestVerifyEntityFile:
    def test_valid_entity_passes(self, repo: Path) -> None:
        eid = "REQ@1000000000.AbcDef.my-req"
        path = repo / "model" / "motivation" / "requirements" / f"{eid}.md"
        _write(path, _entity(eid))
        result = ModelVerifier().verify_entity_file(path)
        assert result.valid, [i.message for i in result.issues]

    def test_missing_artifact_id_field(self, repo: Path) -> None:
        path = repo / "model" / "motivation" / "requirements" / "REQ@1000000001.XxXxXx.bad.md"
        _write(path, """\
---
artifact-type: requirement
name: "Bad"
version: 0.1.0
status: draft
last-updated: '2026-04-17'
---
<!-- §content -->
## Bad
<!-- §display -->
### archimate
```yaml
domain: Motivation
element-type: Requirement
label: "Bad"
alias: REQ_XxXxXx
```
""")
        result = ModelVerifier().verify_entity_file(path)
        assert not result.valid
        codes = {i.code for i in result.issues if i.severity == "error"}
        assert "E021" in codes  # missing required field

    def test_invalid_artifact_type(self, repo: Path) -> None:
        eid = "REQ@1000000002.AbcDef.bad-type"
        path = repo / "model" / "motivation" / "requirements" / f"{eid}.md"
        content = _entity(eid, artifact_type="not-a-real-type")
        _write(path, content)
        result = ModelVerifier().verify_entity_file(path)
        assert not result.valid
        assert any(i.code == "E102" for i in result.issues)

    def test_missing_content_section(self, repo: Path) -> None:
        eid = "REQ@1000000003.AbcDef.no-content"
        path = repo / "model" / "motivation" / "requirements" / f"{eid}.md"
        _write(path, _entity(eid, no_content_section=True))
        result = ModelVerifier().verify_entity_file(path)
        assert not result.valid
        assert any(i.code == "E031" for i in result.issues)

    def test_artifact_id_mismatch(self, repo: Path) -> None:
        eid = "REQ@1000000004.AbcDef.correct-name"
        wrong_id = "REQ@1000000004.AbcDef.wrong-name"
        path = repo / "model" / "motivation" / "requirements" / f"{eid}.md"
        _write(path, _entity(wrong_id))  # frontmatter id ≠ filename
        result = ModelVerifier().verify_entity_file(path)
        assert not result.valid
        assert any(i.code == "E104" for i in result.issues)

    def test_invalid_status_value(self, repo: Path) -> None:
        eid = "REQ@1000000005.AbcDef.bad-status"
        path = repo / "model" / "motivation" / "requirements" / f"{eid}.md"
        _write(path, _entity(eid, extra_fm="\nbad-status: yes").replace(
            "status: draft", "status: invalid-value"
        ))
        result = ModelVerifier().verify_entity_file(path)
        assert not result.valid
        assert any(i.code == "E022" for i in result.issues)


# ---------------------------------------------------------------------------
# verify_outgoing_file
# ---------------------------------------------------------------------------

class TestVerifyOutgoingFile:
    def _setup_entities(self, repo: Path, *eids_and_types) -> None:
        for eid, etype in eids_and_types:
            from src.common.ontology_loader import ENTITY_TYPES
            info = ENTITY_TYPES[etype]
            path = repo / "model" / info.domain_dir / info.subdir / f"{eid}.md"
            _write(path, _entity(eid, etype))

    def test_valid_outgoing_passes(self, repo: Path) -> None:
        src = "REQ@1000000000.SrcAaa.src"
        tgt = "REQ@1000000001.TgtBbb.tgt"
        self._setup_entities(repo, (src, "requirement"), (tgt, "requirement"))
        out_path = repo / "model" / "motivation" / "requirements" / f"{src}.outgoing.md"
        _write(out_path, _outgoing(src, [("archimate-association", tgt)]))
        registry = ModelRegistry(repo)
        result = ModelVerifier(registry).verify_outgoing_file(out_path)
        assert result.valid, [i.message for i in result.issues]

    def test_unknown_source_entity(self, repo: Path) -> None:
        tgt = "REQ@1000000001.TgtBbb.tgt"
        self._setup_entities(repo, (tgt, "requirement"))
        ghost_src = "REQ@9999999999.GhostX.ghost"
        out_path = repo / "model" / "motivation" / "requirements" / f"{ghost_src}.outgoing.md"
        _write(out_path, _outgoing(ghost_src, [("archimate-association", tgt)]))
        registry = ModelRegistry(repo)
        result = ModelVerifier(registry).verify_outgoing_file(out_path)
        assert not result.valid
        assert any(i.code == "E120" for i in result.issues)

    def test_unknown_target_entity(self, repo: Path) -> None:
        src = "REQ@1000000000.SrcAaa.src"
        self._setup_entities(repo, (src, "requirement"))
        out_path = repo / "model" / "motivation" / "requirements" / f"{src}.outgoing.md"
        _write(out_path, _outgoing(src, [("archimate-association", "REQ@9999999999.GhostX.ghost")]))
        registry = ModelRegistry(repo)
        result = ModelVerifier(registry).verify_outgoing_file(out_path)
        assert not result.valid
        assert any(i.code == "E124" for i in result.issues)

    def test_unknown_connection_type(self, repo: Path) -> None:
        src = "REQ@1000000000.SrcAaa.src"
        tgt = "REQ@1000000001.TgtBbb.tgt"
        self._setup_entities(repo, (src, "requirement"), (tgt, "requirement"))
        out_path = repo / "model" / "motivation" / "requirements" / f"{src}.outgoing.md"
        _write(out_path, _outgoing(src, [("not-a-real-connection-type", tgt)]))
        registry = ModelRegistry(repo)
        result = ModelVerifier(registry).verify_outgoing_file(out_path)
        assert not result.valid
        assert any(i.code == "E123" for i in result.issues)

    def test_missing_connections_section_marker(self, repo: Path) -> None:
        src = "REQ@1000000000.SrcAaa.src"
        tgt = "REQ@1000000001.TgtBbb.tgt"
        self._setup_entities(repo, (src, "requirement"), (tgt, "requirement"))
        out_path = repo / "model" / "motivation" / "requirements" / f"{src}.outgoing.md"
        content = _outgoing(src, [("archimate-association", tgt)]).replace("<!-- §connections -->", "")
        _write(out_path, content)
        registry = ModelRegistry(repo)
        result = ModelVerifier(registry).verify_outgoing_file(out_path)
        assert not result.valid
        assert any(i.code == "E121" for i in result.issues)

    def test_enterprise_outgoing_cannot_target_engagement_entity(
        self, tmp_path: Path
    ) -> None:
        eng_root = tmp_path / "engagements" / "ENG-T" / "architecture-repository"
        ent_root = tmp_path / "enterprise-repository"
        (eng_root / "model").mkdir(parents=True)
        (ent_root / "model").mkdir(parents=True)

        eng_id = "REQ@1000000000.EngAaa.eng-req"
        ent_id = "REQ@2000000000.EntBbb.ent-req"
        _write(
            eng_root / "model" / "motivation" / "requirements" / f"{eng_id}.md",
            _entity(eng_id),
        )
        _write(
            ent_root / "model" / "motivation" / "requirements" / f"{ent_id}.md",
            _entity(ent_id),
        )
        # Enterprise outgoing targeting engagement entity → error
        out_path = ent_root / "model" / "motivation" / "requirements" / f"{ent_id}.outgoing.md"
        _write(out_path, _outgoing(ent_id, [("archimate-association", eng_id)]))
        registry = ModelRegistry([eng_root, ent_root])
        result = ModelVerifier(registry).verify_outgoing_file(out_path)
        assert not result.valid
        assert any(i.code == "E130" for i in result.issues)


# ---------------------------------------------------------------------------
# verify_all
# ---------------------------------------------------------------------------

class TestVerifyAll:
    def test_verify_all_passes_clean_repo(self, repo: Path) -> None:
        eid = "REQ@1000000000.AbcDef.clean"
        _write(
            repo / "model" / "motivation" / "requirements" / f"{eid}.md",
            _entity(eid),
        )
        registry = ModelRegistry(repo)
        results = ModelVerifier(registry).verify_all(repo, include_diagrams=False)
        assert all(r.valid for r in results), [
            f"{r.path.name}: {[i.message for i in r.issues]}" for r in results if not r.valid
        ]

    def test_verify_all_finds_errors_in_bad_entity(self, repo: Path) -> None:
        eid = "REQ@1000000000.AbcDef.bad"
        path = repo / "model" / "motivation" / "requirements" / f"{eid}.md"
        _write(path, _entity(eid, no_content_section=True))
        registry = ModelRegistry(repo)
        results = ModelVerifier(registry).verify_all(repo, include_diagrams=False)
        assert any(not r.valid for r in results)

    def test_verify_all_two_repos(self, tmp_path: Path) -> None:
        eng_root = tmp_path / "engagements" / "ENG-T" / "architecture-repository"
        ent_root = tmp_path / "enterprise-repository"
        (eng_root / "model").mkdir(parents=True)
        (ent_root / "model").mkdir(parents=True)

        eng_id = "REQ@1000000000.EngAaa.eng"
        ent_id = "REQ@2000000000.EntBbb.ent"
        _write(eng_root / "model" / "motivation" / "requirements" / f"{eng_id}.md", _entity(eng_id))
        _write(ent_root / "model" / "motivation" / "requirements" / f"{ent_id}.md", _entity(ent_id))

        registry = ModelRegistry([eng_root, ent_root])
        # verify_all for each root independently
        for root in (eng_root, ent_root):
            results = ModelVerifier(registry).verify_all(root, include_diagrams=False)
            assert all(r.valid for r in results), [
                i.message for r in results for i in r.issues if i.severity == "error"
            ]
