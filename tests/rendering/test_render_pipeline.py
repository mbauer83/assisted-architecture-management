"""Tests for the _render_puml pipeline — specifically the archimate include injection gate.

These tests do NOT require a PlantUML jar or a real engagement repository; they mock
subprocess.run so they run fast and deterministically.  Their job is to verify that the
PUML body written to the temp file before PlantUML is invoked is correct for each diagram
type — particularly that archimate includes are injected for archimate/matrix kinds and
skipped for all other kinds (e.g. activity).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from src.infrastructure.rendering.diagram_builder import _needs_archimate_includes, render_puml_preview

# ── Unit tests for the predicate ─────────────────────────────────────────────


def test_needs_archimate_includes_true_for_archimate_kinds() -> None:
    for kind in ["archimate-business", "archimate-application", "archimate-technology", "archimate-layered"]:
        assert _needs_archimate_includes(kind), kind


def test_needs_archimate_includes_true_for_matrix() -> None:
    assert _needs_archimate_includes("matrix")


def test_needs_archimate_includes_true_for_none() -> None:
    # None = unknown type; preserve old default behavior
    assert _needs_archimate_includes(None)


def test_needs_archimate_includes_false_for_activity() -> None:
    assert not _needs_archimate_includes("activity")


def test_needs_archimate_includes_false_for_custom_kinds() -> None:
    for kind in ["sequence", "gantt", "mindmap", "flow"]:
        assert not _needs_archimate_includes(kind), kind


# ── Integration-style pipeline tests (subprocess mocked) ─────────────────────

_ACTIVITY_PUML = """\
@startuml activity-test
title Test

start

:Do something;

stop
@enduml
"""

_ARCHIMATE_PUML = """\
@startuml arch-test
title Test
rectangle "Actor" <<business_actor>> as a1
@enduml
"""


def _make_fake_png(tmp_path: Path) -> MagicMock:
    """Patch subprocess.run so it writes a 1-byte fake PNG into the output dir."""

    def _fake_run(cmd: list[str], **_kwargs: object) -> MagicMock:
        out_dir = Path(cmd[cmd.index("-o") + 1])
        (out_dir / "out.png").write_bytes(b"\x89PNG")
        result = MagicMock()
        result.returncode = 0
        return result

    return _fake_run


_VERIFIER_MOD = "src.application.verification.artifact_verifier_syntax"
_SETTINGS_MOD = "src.config.settings"
_BUILDER_MOD = "src.infrastructure.rendering.diagram_builder"


def _captured_puml(tmp_path: Path, puml: str, diagram_type: str | None) -> str:
    """Run render_puml_preview with mocked subprocess; return the PUML written to the temp file."""
    diag_dir = tmp_path / "diagram-catalog" / "diagrams"
    diag_dir.mkdir(parents=True)

    written: list[str] = []

    def _fake_run(cmd: list[str], **kwargs: object) -> MagicMock:
        puml_arg = cmd[-1]
        written.append((diag_dir / puml_arg).read_text(encoding="utf-8"))
        out_dir = Path(cmd[cmd.index("-o") + 1])
        (out_dir / "out.png").write_bytes(b"\x89PNG")
        result = MagicMock()
        result.returncode = 0
        return result

    with (
        patch("subprocess.run", side_effect=_fake_run),
        patch(f"{_VERIFIER_MOD}.find_plantuml_jar", return_value=Path("plantuml.jar")),
        patch(f"{_VERIFIER_MOD}.find_graphviz_dot", return_value=None),
        patch(f"{_SETTINGS_MOD}.plantuml_limit_size", return_value=8192),
        patch(f"{_SETTINGS_MOD}.render_dpi", return_value=96),
    ):
        render_puml_preview(puml, tmp_path, diagram_type)

    assert written, "subprocess.run was not called — temp file was not created"
    return written[0]


def test_activity_puml_has_no_archimate_include_injected(tmp_path: Path) -> None:
    body = _captured_puml(tmp_path, _ACTIVITY_PUML, "activity")
    assert "_archimate-stereotypes.puml" not in body
    assert "!include" not in body


def test_activity_puml_preserves_v2_constructs(tmp_path: Path) -> None:
    body = _captured_puml(tmp_path, _ACTIVITY_PUML, "activity")
    assert "start" in body
    assert ":Do something;" in body
    assert "stop" in body


def test_archimate_puml_gets_stereotypes_include_injected(tmp_path: Path) -> None:
    written: list[str] = []
    diag_dir = tmp_path / "diagram-catalog" / "diagrams"
    diag_dir.mkdir(parents=True)

    def _fake_run(cmd: list[str], **kwargs: object) -> MagicMock:
        puml_arg = cmd[-1]
        written.append((diag_dir / puml_arg).read_text(encoding="utf-8"))
        out_dir = Path(cmd[cmd.index("-o") + 1])
        (out_dir / "out.png").write_bytes(b"\x89PNG")
        r = MagicMock()
        r.returncode = 0
        return r

    with (
        patch("subprocess.run", side_effect=_fake_run),
        patch(f"{_VERIFIER_MOD}.find_plantuml_jar", return_value=Path("plantuml.jar")),
        patch(f"{_VERIFIER_MOD}.find_graphviz_dot", return_value=None),
        patch(f"{_SETTINGS_MOD}.plantuml_limit_size", return_value=8192),
        patch(f"{_SETTINGS_MOD}.render_dpi", return_value=96),
        patch(f"{_BUILDER_MOD}.inject_archimate_includes", side_effect=lambda b, _r: b),
    ):
        render_puml_preview(_ARCHIMATE_PUML, tmp_path, "archimate-business")

    assert written
    assert "_archimate-stereotypes.puml" in written[0]
