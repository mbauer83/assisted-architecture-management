"""Tests for WS3 — one canonical WorkspaceIndex + scoped facades."""

from __future__ import annotations

from pathlib import Path

from src.infrastructure.artifact_index.bootstrap import (
    get_shared_index,
    normalize_mounts,
    service_key,
)
from src.infrastructure.artifact_index.service import ArtifactIndex

# ── Identity: order-independent key ──────────────────────────────────────────


class TestWorkspaceIndexIdentity:
    def test_service_key_order_independent(self, tmp_path: Path) -> None:
        eng = tmp_path / "eng"
        ent = tmp_path / "ent"
        eng.mkdir()
        ent.mkdir()
        m1 = normalize_mounts([eng, ent])
        m2 = normalize_mounts([ent, eng])
        assert service_key(m1) == service_key(m2)

    def test_normalize_mounts_sorts_by_resolved_path(self, tmp_path: Path) -> None:
        zzz = tmp_path / "zzz"
        aaa = tmp_path / "aaa"
        zzz.mkdir()
        aaa.mkdir()
        mounts = normalize_mounts([zzz, aaa])
        assert mounts[0].root.name == "aaa"
        assert mounts[1].root.name == "zzz"

    def test_reversed_root_order_same_instance(self, tmp_path: Path) -> None:
        eng = tmp_path / "live_eng"
        ent = tmp_path / "live_ent"
        eng.mkdir()
        ent.mkdir()
        idx1 = get_shared_index(ArtifactIndex, [eng, ent])
        idx2 = get_shared_index(ArtifactIndex, [ent, eng])
        assert idx1 is idx2

    def test_different_mount_sets_different_instances(self, tmp_path: Path) -> None:
        a = tmp_path / "repo_a"
        b = tmp_path / "repo_b"
        c = tmp_path / "repo_c"
        a.mkdir()
        b.mkdir()
        c.mkdir()
        idx_ab = get_shared_index(ArtifactIndex, [a, b])
        idx_ac = get_shared_index(ArtifactIndex, [a, c])
        assert idx_ab is not idx_ac

    def test_single_root_identity(self, tmp_path: Path) -> None:
        r = tmp_path / "single"
        r.mkdir()
        idx1 = get_shared_index(ArtifactIndex, [r])
        idx2 = get_shared_index(ArtifactIndex, r)
        assert idx1 is idx2


# ── Scope facades ─────────────────────────────────────────────────────────────


class TestScopedFacades:
    def test_engagement_scope_for_engagement_path(self, tmp_path: Path) -> None:
        eng = tmp_path / "engagements" / "fe_proj"
        ent = tmp_path / "enterprise-repository"
        eng.mkdir(parents=True)
        ent.mkdir()
        idx = get_shared_index(ArtifactIndex, [eng, ent])
        assert idx.scope_for_path(eng / "model" / "req.md") == "engagement"

    def test_enterprise_scope_for_enterprise_path(self, tmp_path: Path) -> None:
        eng = tmp_path / "engagements" / "myproj"
        ent = tmp_path / "enterprise-repository"
        eng.mkdir(parents=True)
        ent.mkdir()
        idx = get_shared_index(ArtifactIndex, [eng, ent])
        assert idx.scope_for_path(ent / "model" / "req.md") == "enterprise"

    def test_unknown_scope_for_unrelated_path(self, tmp_path: Path) -> None:
        eng = tmp_path / "us_eng"
        eng.mkdir()
        idx = get_shared_index(ArtifactIndex, [eng])
        assert idx.scope_for_path(tmp_path / "other" / "file.md") == "unknown"

    def test_read_write_resolution_consistent_across_orderings(self, tmp_path: Path) -> None:
        eng = tmp_path / "rw_eng"
        ent = tmp_path / "rw_ent"
        eng.mkdir()
        ent.mkdir()
        idx_fwd = get_shared_index(ArtifactIndex, [eng, ent])
        idx_rev = get_shared_index(ArtifactIndex, [ent, eng])
        assert idx_fwd is idx_rev
        assert idx_fwd.find_file_by_id("NOTEXIST@0.X.slug") is None


# ── Staging isolation ─────────────────────────────────────────────────────────


class TestStagingIsolation:
    def test_staged_root_gets_isolated_index(self, tmp_path: Path) -> None:
        live = tmp_path / "si_live"
        staged = tmp_path / "si_staged"
        live.mkdir()
        staged.mkdir()
        live_idx = get_shared_index(ArtifactIndex, [live])
        staged_idx = get_shared_index(ArtifactIndex, [staged])
        assert live_idx is not staged_idx

    def test_staging_does_not_affect_live_index_repo_mounts(self, tmp_path: Path) -> None:
        live = tmp_path / "sm_live"
        staged = tmp_path / "sm_staged"
        live.mkdir()
        staged.mkdir()
        live_idx = get_shared_index(ArtifactIndex, [live])
        staged_idx = get_shared_index(ArtifactIndex, [staged])
        live_roots = {m.root for m in live_idx.repo_mounts}
        staged_roots = {m.root for m in staged_idx.repo_mounts}
        assert live_roots.isdisjoint(staged_roots)
