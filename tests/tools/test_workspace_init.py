"""Tests for workspace_init: config parsing, state file, load_init_state."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.infrastructure.workspace.workspace_init import _parse_config, _resolve_repo, _write_state, load_init_state


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    return tmp_path / "workspace"


def _minimal_repo(path: Path) -> Path:
    (path / "model").mkdir(parents=True)
    return path


class TestParseConfig:
    def test_valid_local_config(self, tmp_path: Path) -> None:
        cfg = {"engagement": {"local": "eng"}, "enterprise": {"local": "ent"}}
        import yaml
        f = tmp_path / "arch-workspace.yaml"
        f.write_text(yaml.safe_dump(cfg))
        result = _parse_config(f)
        assert result["engagement"]["local"] == "eng"

    def test_missing_enterprise_key_raises(self, tmp_path: Path) -> None:
        import yaml
        f = tmp_path / "arch-workspace.yaml"
        f.write_text(yaml.safe_dump({"engagement": {"local": "eng"}}))
        with pytest.raises(SystemExit, match="enterprise"):
            _parse_config(f)

    def test_missing_engagement_key_raises(self, tmp_path: Path) -> None:
        import yaml
        f = tmp_path / "arch-workspace.yaml"
        f.write_text(yaml.safe_dump({"enterprise": {"local": "ent"}}))
        with pytest.raises(SystemExit, match="engagement"):
            _parse_config(f)


class TestResolveRepo:
    def test_local_path_resolved(self, tmp_path: Path) -> None:
        repo = _minimal_repo(tmp_path / "my-repo")
        result = _resolve_repo("test", {"local": str(repo)}, tmp_path)
        assert result == repo.resolve()

    def test_local_relative_path(self, tmp_path: Path) -> None:
        repo = _minimal_repo(tmp_path / "relative-repo")
        result = _resolve_repo("test", {"local": "relative-repo"}, tmp_path)
        assert result == repo.resolve()

    def test_nonexistent_local_raises(self, tmp_path: Path) -> None:
        with pytest.raises(SystemExit, match="does not exist"):
            _resolve_repo("test", {"local": "ghost"}, tmp_path)

    def test_local_without_model_dir_raises(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty-repo"
        empty.mkdir()
        with pytest.raises(SystemExit, match="model/"):
            _resolve_repo("test", {"local": str(empty)}, tmp_path)

    def test_missing_spec_raises(self, tmp_path: Path) -> None:
        with pytest.raises(SystemExit, match="local.*git"):
            _resolve_repo("test", {}, tmp_path)


class TestWriteAndLoadState:
    def test_write_then_load(self, tmp_path: Path) -> None:
        eng = tmp_path / "eng"
        ent = tmp_path / "ent"
        eng.mkdir()
        ent.mkdir()
        state_path = _write_state(tmp_path, eng, ent)
        assert state_path.exists()

        loaded = load_init_state(tmp_path)
        assert loaded is not None
        assert loaded["engagement_root"] == str(eng)
        assert loaded["enterprise_root"] == str(ent)

    def test_load_walks_up(self, tmp_path: Path) -> None:
        eng = tmp_path / "eng"
        ent = tmp_path / "ent"
        eng.mkdir()
        ent.mkdir()
        _write_state(tmp_path, eng, ent)

        subdir = tmp_path / "deep" / "nested"
        subdir.mkdir(parents=True)
        loaded = load_init_state(subdir)
        assert loaded is not None
        assert "engagement_root" in loaded

    def test_load_returns_none_when_not_found(self, tmp_path: Path) -> None:
        result = load_init_state(tmp_path / "no-state-here")
        assert result is None


# ---------------------------------------------------------------------------
# resolve_server_roots — env var / init-state priority chain
# ---------------------------------------------------------------------------

class TestResolveServerRoots:
    """Regression tests for the root resolution priority in gui_server.

    Covers the Docker use case: when --enterprise-root is not given as a CLI
    arg but ARCH_ENTERPRISE_ROOT is set in the environment, the env var must
    be used so that containers can expose both repos without requiring init-state.
    """

    def test_explicit_args_take_priority(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.infrastructure.gui.gui_server import resolve_server_roots
        eng = tmp_path / "eng-arg"
        ent = tmp_path / "ent-arg"
        monkeypatch.setenv("ARCH_REPO_ROOT", str(tmp_path / "eng-env"))
        monkeypatch.setenv("ARCH_ENTERPRISE_ROOT", str(tmp_path / "ent-env"))
        eng_result, ent_result = resolve_server_roots(str(eng), str(ent))
        assert eng_result == eng
        assert ent_result == ent

    def test_env_vars_used_when_no_args_and_no_init_state(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.infrastructure.gui.gui_server import resolve_server_roots
        eng = tmp_path / "eng-env"
        ent = tmp_path / "ent-env"
        monkeypatch.setenv("ARCH_REPO_ROOT", str(eng))
        monkeypatch.setenv("ARCH_ENTERPRISE_ROOT", str(ent))
        # Redirect init-state lookup to an isolated dir with no state file
        monkeypatch.chdir(tmp_path)
        eng_result, ent_result = resolve_server_roots(None, None)
        assert eng_result == eng
        assert ent_result == ent

    def test_enterprise_env_var_used_when_only_repo_root_given(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Mirrors the Docker scenario: --repo-root /repo set, ARCH_ENTERPRISE_ROOT=/enterprise-repo."""
        from src.infrastructure.gui.gui_server import resolve_server_roots
        ent = tmp_path / "enterprise-repo"
        monkeypatch.setenv("ARCH_ENTERPRISE_ROOT", str(ent))
        monkeypatch.delenv("ARCH_REPO_ROOT", raising=False)
        monkeypatch.chdir(tmp_path)
        eng_result, ent_result = resolve_server_roots("/repo", None)
        assert eng_result == Path("/repo")
        assert ent_result == ent

    def test_init_state_used_as_fallback_when_no_env_vars(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.infrastructure.gui.gui_server import resolve_server_roots
        eng = tmp_path / "eng-state"
        ent = tmp_path / "ent-state"
        _write_state(tmp_path, eng, ent)
        monkeypatch.delenv("ARCH_REPO_ROOT", raising=False)
        monkeypatch.delenv("ARCH_ENTERPRISE_ROOT", raising=False)
        monkeypatch.chdir(tmp_path)
        eng_result, ent_result = resolve_server_roots(None, None)
        assert eng_result == eng
        assert ent_result == ent

    def test_returns_none_when_nothing_configured(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.infrastructure.gui.gui_server import resolve_server_roots
        monkeypatch.delenv("ARCH_REPO_ROOT", raising=False)
        monkeypatch.delenv("ARCH_ENTERPRISE_ROOT", raising=False)
        monkeypatch.chdir(tmp_path)
        eng_result, ent_result = resolve_server_roots(None, None)
        assert eng_result is None
        assert ent_result is None
