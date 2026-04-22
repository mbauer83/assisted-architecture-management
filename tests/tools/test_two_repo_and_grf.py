"""Behavioural tests for the two-tiered repo system and global-entity-reference (GRF).

Covers:
- ArtifactRepository loading from both engagement and enterprise repos
- is_global classification via path
- GRF creation / reuse (ensure_global_entity_reference)
- model_add_connection transparent GRF routing for global-entity targets
- Verifier rules E140 / E141 / W141 for GRF entities
- Promotion plan: excludes GRFs, builds transitive closure
- Promotion execute: rewrites GRF targets in outgoing files
- Promotion execute: replaces promoted engagement entities with GRFs
- Promotion execute: updates engagement outgoing references after replacement
- Promotion execute: handles pre-existing GRFs correctly (idempotent)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.common.artifact_query import ArtifactRepository
from src.common.artifact_verifier import ArtifactVerifier
from src.common.artifact_verifier_registry import ArtifactRegistry
from src.tools import mcp_artifact_server as mcp_tools


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _entity_md(
    artifact_id: str,
    artifact_type: str,
    name: str,
    *,
    extra_frontmatter: str = "",
) -> str:
    prefix = artifact_id.split("@")[0] if "@" in artifact_id else "ENT"
    return f"""\
---
artifact-id: {artifact_id}
artifact-type: {artifact_type}
name: "{name}"
version: 0.1.0
status: active
last-updated: '2026-04-17'{extra_frontmatter}
---

<!-- §content -->

## {name}

Test entity.

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
alias: {prefix}_{artifact_id.split('.')[1] if '.' in artifact_id else 'TEST'}
```
"""


def _grf_md(artifact_id: str, name: str, global_entity_id: str) -> str:
    rand = artifact_id.split(".")[1] if "." in artifact_id else "XXXXXX"
    return f"""\
---
artifact-id: {artifact_id}
artifact-type: global-entity-reference
name: "{name}"
version: 0.1.0
status: active
global-entity-id: {global_entity_id}
last-updated: '2026-04-17'
---

<!-- §content -->

## {name}

Engagement-repo proxy for global entity `{global_entity_id}`.

## Properties

| Attribute | Value |
|---|---|
| (none) | (none) |

<!-- §display -->

### archimate

```yaml
domain: ""
element-type: ""
label: "{name}"
alias: GRF_{rand}
```
"""


def _outgoing_md(source_entity: str, connections: list[tuple[str, str]]) -> str:
    """connections: list of (conn_type, target_id)"""
    sections = "\n".join(
        f"### {ctype} → {tid}\n" for ctype, tid in connections
    )
    return f"""\
---
source-entity: {source_entity}
version: 0.1.0
status: active
last-updated: '2026-04-17'
---

<!-- §connections -->

{sections}
"""


@pytest.fixture()
def engagement_root(tmp_path: Path) -> Path:
    root = tmp_path / "engagements" / "ENG-TEST" / "architecture-repository"
    (root / "model").mkdir(parents=True)
    (root / "diagram-catalog" / "diagrams").mkdir(parents=True)
    return root


@pytest.fixture()
def enterprise_root(tmp_path: Path) -> Path:
    root = tmp_path / "enterprise-repository"
    (root / "model").mkdir(parents=True)
    return root


# ---------------------------------------------------------------------------
# Two-repo loading
# ---------------------------------------------------------------------------

class TestTwoRepoLoading:
    def test_entities_from_both_repos_visible(
        self, engagement_root: Path, enterprise_root: Path
    ) -> None:
        _write(
            engagement_root / "model" / "motivation" / "requirements"
            / "REQ@1000000000.EngAAA.eng-req.md",
            _entity_md("REQ@1000000000.EngAAA.eng-req", "requirement", "Eng Req"),
        )
        _write(
            enterprise_root / "model" / "motivation" / "requirements"
            / "REQ@2000000000.GloAAA.global-req.md",
            _entity_md("REQ@2000000000.GloAAA.global-req", "requirement", "Global Req"),
        )

        repo = ArtifactRepository([engagement_root, enterprise_root])
        ids = {e.artifact_id for e in repo.list_entities()}
        assert "REQ@1000000000.EngAAA.eng-req" in ids
        assert "REQ@2000000000.GloAAA.global-req" in ids

    def test_is_global_via_path(
        self, engagement_root: Path, enterprise_root: Path
    ) -> None:
        eng_file = (
            engagement_root / "model" / "motivation" / "requirements"
            / "REQ@1000000000.EngAAA.eng-req.md"
        )
        ent_file = (
            enterprise_root / "model" / "motivation" / "requirements"
            / "REQ@2000000000.GloAAA.global-req.md"
        )
        _write(eng_file, _entity_md("REQ@1000000000.EngAAA.eng-req", "requirement", "E"))
        _write(ent_file, _entity_md("REQ@2000000000.GloAAA.global-req", "requirement", "G"))

        repo = ArtifactRepository([engagement_root, enterprise_root])
        eng_rec = repo.get_entity("REQ@1000000000.EngAAA.eng-req")
        ent_rec = repo.get_entity("REQ@2000000000.GloAAA.global-req")
        assert eng_rec is not None and ent_rec is not None
        assert not eng_rec.path.is_relative_to(enterprise_root)
        assert ent_rec.path.is_relative_to(enterprise_root)

    def test_registry_scope_classification(
        self, engagement_root: Path, enterprise_root: Path
    ) -> None:
        _write(
            engagement_root / "model" / "motivation" / "requirements"
            / "REQ@1000000000.EngAAA.eng-req.md",
            _entity_md("REQ@1000000000.EngAAA.eng-req", "requirement", "E"),
        )
        _write(
            enterprise_root / "model" / "motivation" / "requirements"
            / "REQ@2000000000.GloAAA.global-req.md",
            _entity_md("REQ@2000000000.GloAAA.global-req", "requirement", "G"),
        )
        registry = ArtifactRegistry([engagement_root, enterprise_root])
        assert registry.scope_of_entity("REQ@1000000000.EngAAA.eng-req") == "engagement"
        assert registry.scope_of_entity("REQ@2000000000.GloAAA.global-req") == "enterprise"


# ---------------------------------------------------------------------------
# GRF creation
# ---------------------------------------------------------------------------

class TestGrfCreation:
    def test_ensure_creates_new_grf(
        self, engagement_root: Path, enterprise_root: Path
    ) -> None:
        from src.tools.artifact_write.global_entity_reference import ensure_global_entity_reference

        repo = ArtifactRepository(engagement_root)
        result = ensure_global_entity_reference(
            engagement_repo=repo,
            engagement_root=engagement_root,
            verifier=ArtifactVerifier(None),
            clear_repo_caches=lambda _: None,
            global_entity_id="REQ@2000000000.GloAAA.global-req",
            global_entity_name="Global Req",
            dry_run=False,
        )
        assert result.wrote is True
        assert result.artifact_id.startswith("GRF@")
        assert result.path.exists()
        content = result.path.read_text()
        assert "global-entity-id: REQ@2000000000.GloAAA.global-req" in content

    def test_ensure_reuses_existing_grf(
        self, engagement_root: Path
    ) -> None:
        from src.tools.artifact_write.global_entity_reference import ensure_global_entity_reference

        global_id = "REQ@2000000000.GloAAA.global-req"
        repo = ArtifactRepository(engagement_root)

        r1 = ensure_global_entity_reference(
            engagement_repo=repo,
            engagement_root=engagement_root,
            verifier=ArtifactVerifier(None),
            clear_repo_caches=lambda _: None,
            global_entity_id=global_id,
            global_entity_name="Global Req",
            dry_run=False,
        )
        assert r1.wrote is True

        repo2 = ArtifactRepository(engagement_root)  # refresh
        r2 = ensure_global_entity_reference(
            engagement_repo=repo2,
            engagement_root=engagement_root,
            verifier=ArtifactVerifier(None),
            clear_repo_caches=lambda _: None,
            global_entity_id=global_id,
            global_entity_name="Global Req",
            dry_run=False,
        )
        assert r2.wrote is False
        assert r2.artifact_id == r1.artifact_id

    def test_build_grf_map(self, engagement_root: Path) -> None:
        from src.tools.artifact_write.global_entity_reference import build_grf_map

        grf_dir = engagement_root / "model" / "common" / "global-references"
        _write(
            grf_dir / "GRF@1000000001.AbcDef.global-req.md",
            _grf_md(
                "GRF@1000000001.AbcDef.global-req",
                "Global Req",
                "REQ@2000000000.GloAAA.global-req",
            ),
        )
        repo = ArtifactRepository(engagement_root)
        grf_map = build_grf_map(repo)
        assert grf_map["GRF@1000000001.AbcDef.global-req"] == "REQ@2000000000.GloAAA.global-req"


# ---------------------------------------------------------------------------
# Verifier GRF rules
# ---------------------------------------------------------------------------

class TestGrfVerifierRules:
    def test_grf_valid_with_enterprise_registry(
        self, engagement_root: Path, enterprise_root: Path, tmp_path: Path
    ) -> None:
        global_id = "REQ@2000000000.GloAAA.global-req"
        _write(
            enterprise_root / "model" / "motivation" / "requirements"
            / f"{global_id}.md",
            _entity_md(global_id, "requirement", "Global Req"),
        )
        grf_id = "GRF@1000000001.AbcDef.global-req"
        grf_path = engagement_root / "model" / "common" / "global-references" / f"{grf_id}.md"
        _write(grf_path, _grf_md(grf_id, "Global Req", global_id))

        registry = ArtifactRegistry([engagement_root, enterprise_root])
        verifier = ArtifactVerifier(registry)
        result = verifier.verify_entity_file(grf_path)
        errors = [i for i in result.issues if i.severity == "error"]
        assert not errors, [i.message for i in errors]

    def test_grf_e140_missing_global_entity_id(
        self, engagement_root: Path
    ) -> None:
        grf_id = "GRF@1000000001.AbcDef.bad-grf"
        grf_path = engagement_root / "model" / "common" / "global-references" / f"{grf_id}.md"
        # Write a GRF without global-entity-id
        _write(grf_path, _entity_md(grf_id, "global-entity-reference", "Bad GRF"))

        verifier = ArtifactVerifier(None)
        result = verifier.verify_entity_file(grf_path)
        codes = {i.code for i in result.issues if i.severity == "error"}
        assert "E140" in codes

    def test_grf_e141_nonexistent_global_entity(
        self, engagement_root: Path, enterprise_root: Path
    ) -> None:
        grf_id = "GRF@1000000001.AbcDef.ghost-ref"
        grf_path = engagement_root / "model" / "common" / "global-references" / f"{grf_id}.md"
        _write(
            grf_path,
            _grf_md(grf_id, "Ghost Ref", "REQ@9999999999.NoExist.nonexistent"),
        )
        # Enterprise repo has real entities but not the referenced one
        _write(
            enterprise_root / "model" / "motivation" / "requirements"
            / "REQ@2000000000.GloAAA.other.md",
            _entity_md("REQ@2000000000.GloAAA.other", "requirement", "Other"),
        )
        registry = ArtifactRegistry([engagement_root, enterprise_root])
        verifier = ArtifactVerifier(registry)
        result = verifier.verify_entity_file(grf_path)
        codes = {i.code for i in result.issues if i.severity == "error"}
        assert "E141" in codes

    def test_grf_w141_no_enterprise_repo(self, engagement_root: Path) -> None:
        grf_id = "GRF@1000000001.AbcDef.no-ent"
        grf_path = engagement_root / "model" / "common" / "global-references" / f"{grf_id}.md"
        _write(grf_path, _grf_md(grf_id, "Some Ref", "REQ@2000000000.GloAAA.unknown"))
        verifier = ArtifactVerifier(None)
        result = verifier.verify_entity_file(grf_path)
        codes = {i.code for i in result.issues if i.severity == "warning"}
        errors = {i.code for i in result.issues if i.severity == "error"}
        assert "W141" in codes
        assert "E141" not in errors


# ---------------------------------------------------------------------------
# Transparent GRF routing in model_add_connection
# ---------------------------------------------------------------------------

class TestAddConnectionGrfRouting:
    def _setup_repos(
        self, engagement_root: Path, enterprise_root: Path
    ) -> tuple[str, str]:
        """Returns (engagement_entity_id, global_entity_id)."""
        eng_id = "CAP@1000000001.EngBBB.my-cap"
        glo_id = "REQ@2000000000.GloAAA.global-req"
        _write(
            engagement_root / "model" / "strategy" / "capabilities" / f"{eng_id}.md",
            _entity_md(eng_id, "capability", "My Cap"),
        )
        _write(
            enterprise_root / "model" / "motivation" / "requirements" / f"{glo_id}.md",
            _entity_md(glo_id, "requirement", "Global Req"),
        )
        return eng_id, glo_id

    def test_connection_to_global_entity_auto_creates_grf(
        self, engagement_root: Path, enterprise_root: Path
    ) -> None:
        eng_id, glo_id = self._setup_repos(engagement_root, enterprise_root)

        result = mcp_tools.artifact_add_connection(
            source_entity=eng_id,
            connection_type="archimate-realization",
            target_entity=glo_id,
            dry_run=False,
            repo_root=str(engagement_root),
            enterprise_root=str(enterprise_root),
        )

        assert result.get("wrote") is True
        assert result.get("grf_artifact_id", "").startswith("GRF@")
        assert result.get("original_target") == glo_id

        # GRF file should exist in engagement repo
        grf_id = result["grf_artifact_id"]
        grf_dir = engagement_root / "model" / "common" / "global-references"
        grf_files = list(grf_dir.rglob("*.md"))
        assert any(grf_id in str(f) for f in grf_files)

        # Outgoing file should reference GRF, not the global entity directly
        outgoing = engagement_root / "model" / "strategy" / "capabilities" / f"{eng_id}.outgoing.md"
        assert outgoing.exists()
        content = outgoing.read_text()
        assert grf_id in content
        assert glo_id not in content

    def test_connection_to_global_entity_reuses_existing_grf(
        self, engagement_root: Path, enterprise_root: Path
    ) -> None:
        eng_id, glo_id = self._setup_repos(engagement_root, enterprise_root)

        # First connection creates GRF
        r1 = mcp_tools.artifact_add_connection(
            source_entity=eng_id, connection_type="archimate-realization",
            target_entity=glo_id, dry_run=False,
            repo_root=str(engagement_root), enterprise_root=str(enterprise_root),
        )
        grf_id_1 = r1["grf_artifact_id"]

        # Second connection (different type) should reuse the same GRF
        eng_id2 = "CAP@1000000002.EngCCC.my-cap2"
        _write(
            engagement_root / "model" / "strategy" / "capabilities" / f"{eng_id2}.md",
            _entity_md(eng_id2, "capability", "My Cap 2"),
        )
        r2 = mcp_tools.artifact_add_connection(
            source_entity=eng_id2, connection_type="archimate-serving",
            target_entity=glo_id, dry_run=False,
            repo_root=str(engagement_root), enterprise_root=str(enterprise_root),
        )
        assert r2["grf_artifact_id"] == grf_id_1  # same GRF reused

    def test_connection_between_engagement_entities_unchanged(
        self, engagement_root: Path, enterprise_root: Path
    ) -> None:
        eng_id1 = "CAP@1000000001.EngBBB.cap1"
        eng_id2 = "CAP@1000000002.EngCCC.cap2"
        _write(
            engagement_root / "model" / "strategy" / "capabilities" / f"{eng_id1}.md",
            _entity_md(eng_id1, "capability", "Cap 1"),
        )
        _write(
            engagement_root / "model" / "strategy" / "capabilities" / f"{eng_id2}.md",
            _entity_md(eng_id2, "capability", "Cap 2"),
        )
        result = mcp_tools.artifact_add_connection(
            source_entity=eng_id1, connection_type="archimate-aggregation",
            target_entity=eng_id2, dry_run=False, repo_root=str(engagement_root),
        )
        assert result.get("wrote") is True
        assert "grf_artifact_id" not in result

    def test_connection_from_global_entity_auto_creates_grf_for_source(
        self, engagement_root: Path, enterprise_root: Path
    ) -> None:
        """When source is an enterprise entity, a GRF is created and used as source."""
        eng_id, glo_id = self._setup_repos(engagement_root, enterprise_root)

        result = mcp_tools.artifact_add_connection(
            source_entity=glo_id,          # enterprise → engagement direction
            connection_type="archimate-influence",
            target_entity=eng_id,
            dry_run=False,
            repo_root=str(engagement_root),
            enterprise_root=str(enterprise_root),
        )

        assert result.get("wrote") is True
        assert result.get("grf_source_id", "").startswith("GRF@")
        assert result.get("original_source") == glo_id
        assert "grf_artifact_id" not in result  # target was engagement, no target GRF

        grf_id = result["grf_source_id"]
        grf_dir = engagement_root / "model" / "common" / "global-references"
        assert any(grf_id in str(f) for f in grf_dir.rglob("*.md"))

        # Connection stored in GRF's outgoing file, pointing to engagement entity
        grf_outgoing = next(
            f for f in grf_dir.rglob("*.outgoing.md") if grf_id in str(f)
        )
        content = grf_outgoing.read_text()
        assert eng_id in content
        assert glo_id not in content

    def test_symmetric_connection_with_global_entity_auto_creates_grf(
        self, engagement_root: Path, enterprise_root: Path
    ) -> None:
        """For a symmetric connection where target is enterprise, GRF is created for target."""
        eng_id, glo_id = self._setup_repos(engagement_root, enterprise_root)

        result = mcp_tools.artifact_add_connection(
            source_entity=eng_id,
            connection_type="archimate-association",  # symmetric
            target_entity=glo_id,
            dry_run=False,
            repo_root=str(engagement_root),
            enterprise_root=str(enterprise_root),
        )

        assert result.get("wrote") is True
        assert result.get("grf_artifact_id", "").startswith("GRF@")
        assert result.get("original_target") == glo_id

        grf_id = result["grf_artifact_id"]
        outgoing = (
            engagement_root / "model" / "strategy" / "capabilities"
            / f"{eng_id}.outgoing.md"
        )
        content = outgoing.read_text()
        assert grf_id in content
        assert glo_id not in content

    def test_connection_from_global_reuses_existing_grf(
        self, engagement_root: Path, enterprise_root: Path
    ) -> None:
        """A second connection from the same global entity reuses its existing GRF."""
        eng_id, glo_id = self._setup_repos(engagement_root, enterprise_root)
        eng_id2 = "CAP@1000000002.EngCCC.cap2"
        _write(
            engagement_root / "model" / "strategy" / "capabilities" / f"{eng_id2}.md",
            _entity_md(eng_id2, "capability", "Cap 2"),
        )

        r1 = mcp_tools.artifact_add_connection(
            source_entity=glo_id, connection_type="archimate-influence",
            target_entity=eng_id, dry_run=False,
            repo_root=str(engagement_root), enterprise_root=str(enterprise_root),
        )
        grf_id_1 = r1["grf_source_id"]

        r2 = mcp_tools.artifact_add_connection(
            source_entity=glo_id, connection_type="archimate-influence",
            target_entity=eng_id2, dry_run=False,
            repo_root=str(engagement_root), enterprise_root=str(enterprise_root),
        )
        assert r2["grf_source_id"] == grf_id_1


# ---------------------------------------------------------------------------
# Promotion: plan excludes GRFs
# ---------------------------------------------------------------------------

class TestPromotionPlan:
    def test_plan_excludes_grf_entities(
        self, engagement_root: Path, enterprise_root: Path
    ) -> None:
        from src.tools.artifact_write.promote_to_enterprise import plan_promotion

        eng_id = "CAP@1000000001.EngBBB.my-cap"
        grf_id = "GRF@1000000002.GrfCCC.grf-ref"
        glo_id = "REQ@2000000000.GloAAA.global-req"

        _write(
            engagement_root / "model" / "strategy" / "capabilities" / f"{eng_id}.md",
            _entity_md(eng_id, "capability", "My Cap"),
        )
        _write(
            engagement_root / "model" / "common" / "global-references" / f"{grf_id}.md",
            _grf_md(grf_id, "Global Req Ref", glo_id),
        )
        _write(
            enterprise_root / "model" / "motivation" / "requirements" / f"{glo_id}.md",
            _entity_md(glo_id, "requirement", "Global Req"),
        )
        # Connection from engagement entity to GRF
        _write(
            engagement_root / "model" / "strategy" / "capabilities" / f"{eng_id}.outgoing.md",
            _outgoing_md(eng_id, [("archimate-realization", grf_id)]),
        )

        registry = ArtifactRegistry([engagement_root, enterprise_root])
        repo = ArtifactRepository([engagement_root, enterprise_root])
        plan = plan_promotion(eng_id, registry, repo)

        assert eng_id in plan.entities_to_add
        assert grf_id not in plan.entities_to_add
        assert grf_id not in plan.already_in_enterprise

    def test_plan_exclude_params(
        self, engagement_root: Path, enterprise_root: Path
    ) -> None:
        from src.tools.artifact_write.promote_to_enterprise import plan_promotion

        eng_id1 = "CAP@1000000001.EngBBB.cap1"
        eng_id2 = "CAP@1000000002.EngCCC.cap2"
        for eid, name in [(eng_id1, "Cap 1"), (eng_id2, "Cap 2")]:
            _write(
                engagement_root / "model" / "strategy" / "capabilities" / f"{eid}.md",
                _entity_md(eid, "capability", name),
            )
        _write(
            engagement_root / "model" / "strategy" / "capabilities" / f"{eng_id1}.outgoing.md",
            _outgoing_md(eng_id1, [("archimate-aggregation", eng_id2)]),
        )

        registry = ArtifactRegistry([engagement_root, enterprise_root])
        repo = ArtifactRepository([engagement_root, enterprise_root])
        plan = plan_promotion(
            eng_id1, registry, repo,
            exclude_entity_ids={eng_id2},
        )
        assert eng_id1 in plan.entities_to_add
        assert eng_id2 not in plan.entities_to_add


# ---------------------------------------------------------------------------
# Promotion execute: outgoing rewrite
# ---------------------------------------------------------------------------

class TestPromotionExecuteOutgoingRewrite:
    def test_grf_targets_rewritten_to_enterprise_ids(
        self, engagement_root: Path, enterprise_root: Path
    ) -> None:
        from src.tools.artifact_write.promote_execute import make_target_resolver, _rewrite_outgoing
        from src.tools.artifact_write.promote_to_enterprise import PromotionResult, PromotionPlan

        grf_id = "GRF@1000000002.GrfCCC.grf-ref"
        glo_id = "REQ@2000000000.GloAAA.global-req"
        eng_id = "CAP@1000000001.EngBBB.my-cap"

        content = _outgoing_md(eng_id, [
            ("archimate-realization", grf_id),
            ("archimate-serving", glo_id),  # already enterprise
        ])

        plan = PromotionPlan(
            root_entity=eng_id, entities_to_add=[eng_id], conflicts=[],
            connection_ids=[], already_in_enterprise=[], warnings=[],
        )
        result = PromotionResult(plan=plan, executed=False)

        resolver = make_target_resolver(
            grf_map={grf_id: glo_id},
            promoted_ids={eng_id},
            enterprise_ids={glo_id},
        )
        rewritten = _rewrite_outgoing(content, resolve_target=resolver, result=result)

        assert grf_id not in rewritten
        assert glo_id in rewritten
        assert "archimate-realization" in rewritten
        assert "archimate-serving" in rewritten

    def test_stranded_targets_dropped_with_warning(
        self, engagement_root: Path, enterprise_root: Path
    ) -> None:
        from src.tools.artifact_write.promote_execute import make_target_resolver, _rewrite_outgoing
        from src.tools.artifact_write.promote_to_enterprise import PromotionResult, PromotionPlan

        eng_id = "CAP@1000000001.EngBBB.my-cap"
        other_eng = "CAP@1000000003.EngDDD.other"

        content = _outgoing_md(eng_id, [
            ("archimate-serving", other_eng),
        ])
        plan = PromotionPlan(
            root_entity=eng_id, entities_to_add=[eng_id], conflicts=[],
            connection_ids=[], already_in_enterprise=[], warnings=[],
        )
        result = PromotionResult(plan=plan, executed=False)
        resolver = make_target_resolver({}, promoted_ids={eng_id}, enterprise_ids=set())
        rewritten = _rewrite_outgoing(content, resolve_target=resolver, result=result)

        assert other_eng not in rewritten
        assert any(other_eng in w for w in result.plan.warnings)


# ---------------------------------------------------------------------------
# Promotion execute: full round-trip (enterprise copy + engagement GRF replacement)
# ---------------------------------------------------------------------------

class TestPromotionExecuteFullRoundTrip:
    def _setup(
        self, engagement_root: Path, enterprise_root: Path
    ) -> tuple[str, str, str]:
        """Create eng entity with GRF connection. Returns (eng_id, grf_id, glo_id)."""
        eng_id = "CAP@1000000001.EngBBB.my-cap"
        grf_id = "GRF@1000000002.GrfCCC.grf-ref"
        glo_id = "REQ@2000000000.GloAAA.global-req"

        _write(
            engagement_root / "model" / "strategy" / "capabilities" / f"{eng_id}.md",
            _entity_md(eng_id, "capability", "My Cap"),
        )
        _write(
            engagement_root / "model" / "common" / "global-references" / f"{grf_id}.md",
            _grf_md(grf_id, "Global Req Ref", glo_id),
        )
        _write(
            engagement_root / "model" / "strategy" / "capabilities" / f"{eng_id}.outgoing.md",
            _outgoing_md(eng_id, [("archimate-realization", grf_id)]),
        )
        _write(
            enterprise_root / "model" / "motivation" / "requirements" / f"{glo_id}.md",
            _entity_md(glo_id, "requirement", "Global Req"),
        )
        return eng_id, grf_id, glo_id

    def test_entity_copied_to_enterprise(
        self, engagement_root: Path, enterprise_root: Path
    ) -> None:
        from src.tools.artifact_write.promote_to_enterprise import plan_promotion
        from src.tools.artifact_write.promote_execute import execute_promotion

        eng_id, grf_id, glo_id = self._setup(engagement_root, enterprise_root)
        registry = ArtifactRegistry([engagement_root, enterprise_root])
        repo = ArtifactRepository([engagement_root, enterprise_root])
        verifier = ArtifactVerifier(registry)

        plan = plan_promotion(eng_id, registry, repo)
        result = execute_promotion(plan, engagement_root, enterprise_root, verifier, registry)

        assert result.executed, result.verification_errors
        ent_file = enterprise_root / "model" / "strategy" / "capabilities" / f"{eng_id}.md"
        assert ent_file.exists()

    def test_grf_target_rewritten_in_enterprise_outgoing(
        self, engagement_root: Path, enterprise_root: Path
    ) -> None:
        from src.tools.artifact_write.promote_to_enterprise import plan_promotion
        from src.tools.artifact_write.promote_execute import execute_promotion

        eng_id, grf_id, glo_id = self._setup(engagement_root, enterprise_root)
        registry = ArtifactRegistry([engagement_root, enterprise_root])
        repo = ArtifactRepository([engagement_root, enterprise_root])
        verifier = ArtifactVerifier(registry)

        plan = plan_promotion(eng_id, registry, repo)
        result = execute_promotion(plan, engagement_root, enterprise_root, verifier, registry)

        assert result.executed, result.verification_errors
        ent_outgoing = (
            enterprise_root / "model" / "strategy" / "capabilities"
            / f"{eng_id}.outgoing.md"
        )
        assert ent_outgoing.exists()
        content = ent_outgoing.read_text()
        assert grf_id not in content, "GRF should be rewritten to enterprise entity"
        assert glo_id in content, "Real enterprise entity should appear in outgoing"

    def test_promoted_engagement_entity_replaced_by_grf(
        self, engagement_root: Path, enterprise_root: Path
    ) -> None:
        from src.tools.artifact_write.promote_to_enterprise import plan_promotion
        from src.tools.artifact_write.promote_execute import execute_promotion

        eng_id, grf_id, glo_id = self._setup(engagement_root, enterprise_root)
        orig_eng_file = (
            engagement_root / "model" / "strategy" / "capabilities" / f"{eng_id}.md"
        )
        registry = ArtifactRegistry([engagement_root, enterprise_root])
        repo = ArtifactRepository([engagement_root, enterprise_root])
        verifier = ArtifactVerifier(registry)

        plan = plan_promotion(eng_id, registry, repo)
        result = execute_promotion(plan, engagement_root, enterprise_root, verifier, registry)

        assert result.executed, result.verification_errors
        # Original engagement entity file removed
        assert not orig_eng_file.exists(), "Original engagement entity should be replaced by GRF"
        # A new GRF for the promoted entity should exist
        grf_dir = engagement_root / "model" / "common" / "global-references"
        new_grfs = [
            f for f in grf_dir.rglob("GRF@*.md")
            if eng_id in f.read_text()
        ]
        assert new_grfs, "A GRF pointing to the promoted entity should be created"

    def test_outgoing_references_updated_after_replacement(
        self, engagement_root: Path, enterprise_root: Path
    ) -> None:
        from src.tools.artifact_write.promote_to_enterprise import plan_promotion
        from src.tools.artifact_write.promote_execute import execute_promotion

        eng_id, grf_id, glo_id = self._setup(engagement_root, enterprise_root)

        # Add a second engagement entity that connects TO eng_id
        other_eng = "CAP@1000000099.EngEEE.other-cap"
        _write(
            engagement_root / "model" / "strategy" / "capabilities" / f"{other_eng}.md",
            _entity_md(other_eng, "capability", "Other Cap"),
        )
        # Use archimate-influence (not in PROMOTION_TRAVERSAL_TYPES) so other_eng
        # is NOT pulled into the promotion closure
        _write(
            engagement_root / "model" / "strategy" / "capabilities" / f"{other_eng}.outgoing.md",
            _outgoing_md(other_eng, [("archimate-influence", eng_id)]),
        )

        registry = ArtifactRegistry([engagement_root, enterprise_root])
        repo = ArtifactRepository([engagement_root, enterprise_root])
        verifier = ArtifactVerifier(registry)

        plan = plan_promotion(eng_id, registry, repo)
        result = execute_promotion(plan, engagement_root, enterprise_root, verifier, registry)

        assert result.executed, result.verification_errors
        # The other engagement entity's outgoing should now reference the new GRF
        other_outgoing = (
            engagement_root / "model" / "strategy" / "capabilities"
            / f"{other_eng}.outgoing.md"
        )
        content = other_outgoing.read_text()
        assert eng_id not in content, "Old entity ID should be replaced in cross-references"
        assert "GRF@" in content, "Reference should point to new GRF"
