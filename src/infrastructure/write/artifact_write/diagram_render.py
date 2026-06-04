"""Diagram PlantUML rendering helpers (PNG, SVG, and entity-body rendering)."""

import os
import re
import subprocess
import tempfile
from pathlib import Path

from src.application.repo_path_helpers import rendered_dir_for_diagram, repo_root_for_diagram_path
from src.application.verification.artifact_verifier_syntax import find_graphviz_dot, find_plantuml_jar
from src.config.settings import plantuml_limit_size, render_dpi
from src.infrastructure.rendering.puml_safety import strip_leading_puml_frontmatter

from .diagram_references import _prepare_diagram_puml_body
from .parse_existing import parse_diagram_file


def _render_diagram_entities_puml(
    diagram_type: str,
    name: str,
    diagram_entities: dict[str, object],
    diagram_connections: list[dict[str, object]] | None,
    repo_root: Path,
) -> str:
    from src.infrastructure.diagram_types import get_diagram_type  # noqa: PLC0415

    diagram_type_mod = get_diagram_type(diagram_type)
    return diagram_type_mod.renderer.render_body(
        name,
        [],
        [],
        diagram_type,
        repo_root,
        diagram_entities=diagram_entities,
        diagram_connections=diagram_connections,
    )


def _render_diagram_png(puml_path: Path, warnings: list[str]) -> Path | None:
    """Render a PUML file to PNG using PlantUML. Returns the PNG path or None."""
    repo_root = repo_root_for_diagram_path(puml_path) or puml_path.parent.parent.parent
    rendered_dir = rendered_dir_for_diagram(puml_path, repo_root)
    rendered_dir.mkdir(parents=True, exist_ok=True)

    # Extract @startuml..@enduml into a temp file (skip YAML frontmatter)
    content = strip_leading_puml_frontmatter(puml_path.read_text(encoding="utf-8"))
    start = content.find("@startuml")
    end = content.find("@enduml")
    if start == -1 or end == -1:
        warnings.append("Cannot render: @startuml/@enduml markers not found")
        return None

    puml_body = content[start : end + len("@enduml")]
    diagram_type = str(parse_diagram_file(puml_path).frontmatter.get("diagram-type", "archimate"))
    puml_body = _prepare_diagram_puml_body(puml_body, repo_root, diagram_type)

    # Strip the diagram name so PlantUML uses the temp-file stem as the output filename.
    # When @startuml carries a name PlantUML uses that name instead, which breaks the
    # temp→final rename below.
    puml_body_for_render = re.sub(r"@startuml\s+\S+", "@startuml", puml_body, count=1)

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".puml", dir=puml_path.parent, delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(puml_body_for_render)
        tmp_path = Path(tmp.name)

    jar = find_plantuml_jar()
    if jar is None:
        warnings.append("plantuml.jar not found; render skipped")
        tmp_path.unlink(missing_ok=True)
        return None

    try:
        env = None
        dot = find_graphviz_dot()
        if dot is not None:
            env = {**os.environ, "GRAPHVIZ_DOT": str(dot)}
        # Run java from the diagrams/ directory (same directory as the temp input file).
        # PlantUML relativises the -o path against the Java process's initial CWD and
        # then re-applies that relative form against the input file's directory.  When
        # both are the same directory the path arithmetic is correct; running from the
        # project root produces a doubled/wrong path.
        dpi = render_dpi()
        result = subprocess.run(
            [
                "java",
                "-Djava.awt.headless=true",
                f"-DPLANTUML_LIMIT_SIZE={plantuml_limit_size()}",
                "-jar",
                str(jar.resolve()),
                "-tpng",
                f"-Sdpi={dpi}",
                "-o",
                str(rendered_dir.resolve()),
                tmp_path.name,
            ],
            cwd=str(puml_path.parent),
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
        )
        if result.returncode != 0:
            warnings.append(f"PlantUML render failed: {result.stderr[:200]}")
            return None

        rendered = rendered_dir / f"{tmp_path.stem}.png"
        if rendered.exists():
            final = rendered_dir / f"{puml_path.stem}.png"
            rendered.rename(final)
            return final
        return None
    except (OSError, subprocess.TimeoutExpired) as exc:
        warnings.append(f"PlantUML render error: {exc}")
        return None
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass


def _render_diagram_svg(puml_path: Path, warnings: list[str]) -> Path | None:
    """Render a PUML file to SVG using PlantUML. Returns the SVG path or None."""
    repo_root = repo_root_for_diagram_path(puml_path) or puml_path.parent.parent.parent
    rendered_dir = rendered_dir_for_diagram(puml_path, repo_root)
    rendered_dir.mkdir(parents=True, exist_ok=True)

    content = strip_leading_puml_frontmatter(puml_path.read_text(encoding="utf-8"))
    start = content.find("@startuml")
    end = content.find("@enduml")
    if start == -1 or end == -1:
        return None

    puml_body = content[start : end + len("@enduml")]
    diagram_type = str(parse_diagram_file(puml_path).frontmatter.get("diagram-type", "archimate"))
    puml_body = _prepare_diagram_puml_body(puml_body, repo_root, diagram_type)
    puml_body_for_render = re.sub(r"@startuml\s+\S+", "@startuml", puml_body, count=1)

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".puml", dir=puml_path.parent, delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(puml_body_for_render)
        tmp_path = Path(tmp.name)

    jar = find_plantuml_jar()
    if jar is None:
        tmp_path.unlink(missing_ok=True)
        return None

    try:
        env = None
        dot = find_graphviz_dot()
        if dot is not None:
            env = {**os.environ, "GRAPHVIZ_DOT": str(dot)}
        result = subprocess.run(
            [
                "java",
                "-Djava.awt.headless=true",
                f"-DPLANTUML_LIMIT_SIZE={plantuml_limit_size()}",
                "-jar",
                str(jar.resolve()),
                "-tsvg",
                "-o",
                str(rendered_dir.resolve()),
                tmp_path.name,
            ],
            cwd=str(puml_path.parent),
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
        )
        if result.returncode != 0:
            return None

        rendered = rendered_dir / f"{tmp_path.stem}.svg"
        if rendered.exists():
            final = rendered_dir / f"{puml_path.stem}.svg"
            rendered.rename(final)
            return final
        return None
    except (OSError, subprocess.TimeoutExpired):
        return None
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass
