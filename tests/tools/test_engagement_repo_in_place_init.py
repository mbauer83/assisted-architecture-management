"""Regression: auto-initialize an existing git clone that lacks the arch-repo structure.

Reproduces the docker-compose startup failure where a freshly-created remote (cloned with
only a README onto branch ``main``) was reported as "existing clone OK" and then rejected
with "cloned engagement repo has no model/ directory", looping forever. With
``initialize_if_empty`` the structure must instead be scaffolded into the clone in place.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from src.config.repo_paths import ARCH_REPO, MODEL
from src.infrastructure.workspace import workspace_init
from src.infrastructure.workspace.engagement_repo_template import initialize_arch_repo_in_place
from src.infrastructure.workspace.workspace_init import _resolve_repo


def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@local.invalid", *args],
        cwd=cwd, check=True, capture_output=True, text=True,
    )


def _clone_with_readme(path: Path) -> Path:
    """A git checkout on main with one commit (README) but no arch-repo structure."""
    path.mkdir(parents=True)
    _git(["init", "-b", "main"], path)
    (path / "README.md").write_text("# Engagement\n", encoding="utf-8")
    _git(["add", "-A"], path)
    _git(["commit", "-m", "initial readme"], path)
    return path


def _is_clean(path: Path) -> bool:
    out = subprocess.run(["git", "status", "--porcelain"], cwd=path, capture_output=True, text=True)
    return not out.stdout.strip()


def _commit_count(path: Path) -> int:
    out = subprocess.run(["git", "rev-list", "--count", "HEAD"], cwd=path, capture_output=True, text=True)
    return int(out.stdout.strip())


class TestInitializeArchRepoInPlace:
    def test_scaffolds_structure_into_existing_clone(self, tmp_path: Path) -> None:
        repo = _clone_with_readme(tmp_path / "eng")

        initialize_arch_repo_in_place(repo)

        assert (repo / MODEL).is_dir()
        assert (repo / ARCH_REPO).is_dir()
        assert (repo / "README.md").exists()  # pre-existing content is preserved

    def test_commits_the_scaffold_on_top_of_existing_history(self, tmp_path: Path) -> None:
        repo = _clone_with_readme(tmp_path / "eng")

        initialize_arch_repo_in_place(repo)

        assert _is_clean(repo), "scaffold must be committed, leaving a clean tree"
        assert _commit_count(repo) == 2  # readme + scaffold

    def test_idempotent_second_call_is_noop(self, tmp_path: Path) -> None:
        repo = _clone_with_readme(tmp_path / "eng")
        initialize_arch_repo_in_place(repo)

        initialize_arch_repo_in_place(repo)

        assert _commit_count(repo) == 2
        assert _is_clean(repo)


class TestResolveRepoAutoInit:
    def test_clone_without_model_is_initialized_when_flag_set(self, tmp_path: Path) -> None:
        _clone_with_readme(tmp_path / "eng")
        spec = {"git": {"url": "git@example.com:org/eng.git", "branch": "main", "path": "eng"}}

        result = _resolve_repo("engagement", spec, tmp_path, initialize_if_empty=True)

        assert result == (tmp_path / "eng").resolve()
        assert (tmp_path / "eng" / MODEL).is_dir()

    def test_clone_without_model_still_raises_without_flag(self, tmp_path: Path) -> None:
        _clone_with_readme(tmp_path / "eng")
        spec = {"git": {"url": "git@example.com:org/eng.git", "branch": "main", "path": "eng"}}

        with pytest.raises(SystemExit, match="no model/ directory"):
            _resolve_repo("engagement", spec, tmp_path, initialize_if_empty=False)


class TestArchInitMainWiring:
    """End-to-end: the --initialize-*-if-empty CLI flags reach _resolve_repo and scaffold.

    This is the exact docker entrypoint path (arch-init --initialize-engagement-repo-if-empty
    --initialize-enterprise-repo-if-empty) that the container runs on first boot.
    """

    def test_main_auto_initializes_empty_clones(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        eng = _clone_with_readme(tmp_path / "data" / "engagement")
        ent = _clone_with_readme(tmp_path / "data" / "enterprise")
        config = tmp_path / "arch-workspace.yaml"
        config.write_text(
            "engagement:\n"
            "  git: { url: 'git@example.com:org/eng.git', branch: main, path: data/engagement }\n"
            "enterprise:\n"
            "  git: { url: 'git@example.com:org/ent.git', branch: main, path: data/enterprise }\n",
            encoding="utf-8",
        )
        # Dests already exist locally — no cloning or credentials needed.
        monkeypatch.setattr(workspace_init, "_collect_init_credentials", lambda _cfg: None)

        workspace_init.main([
            "--config", str(config),
            "--initialize-engagement-repo-if-empty",
            "--initialize-enterprise-repo-if-empty",
        ])

        assert (eng / MODEL).is_dir()
        assert (ent / MODEL).is_dir()
        assert workspace_init.load_init_state(tmp_path) is not None
