
import subprocess
import tempfile
from pathlib import Path
import re
from collections.abc import Callable
from src.common.artifact_verifier import ArtifactVerifier
from src.common.artifact_verifier_syntax import find_plantuml_jar
from src.common.repo_paths import DIAGRAM_CATALOG, DIAGRAMS, RENDERED
from src.common.settings import plantuml_limit_size, render_dpi
from src.common.artifact_write import (
    DiagramConnectionInferenceMode,
    format_diagram_puml,
    infer_archimate_connection_ids_from_puml,
    infer_entity_ids_from_puml,
)
from src.common.artifact_write_layout import optimize_puml_layout
from src.tools.generate_macros import generate_macros

from .boundary import assert_engagement_write_root
from .types import WriteResult
from .verify import verify_content_in_temp_path


def _verification_to_dict(path: Path, res) -> dict[str, object]:
    return {
        "path": str(path),
        "file_type": "diagram",
        "valid": res.valid,
        "issues": [
            {"severity": i.severity, "code": i.code, "message": i.message, "location": i.location}
            for i in res.issues
        ],
    }


def _render_diagram_png(puml_path: Path, warnings: list[str]) -> Path | None:
    """Render a PUML file to PNG using PlantUML. Returns the PNG path or None."""
    # Render into the sibling rendered/ directory (diagram-catalog/rendered/),
    # not a nested subdirectory under diagrams/.
    rendered_dir = puml_path.parent.parent / RENDERED
    rendered_dir.mkdir(parents=True, exist_ok=True)

    # Extract @startuml..@enduml into a temp file (skip YAML frontmatter)
    content = puml_path.read_text(encoding="utf-8")
    start = content.find("@startuml")
    end = content.find("@enduml")
    if start == -1 or end == -1:
        warnings.append("Cannot render: @startuml/@enduml markers not found")
        return None

    puml_body = content[start:end + len("@enduml")]

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
        # Run java from the diagrams/ directory (same directory as the temp input file).
        # PlantUML relativises the -o path against the Java process's initial CWD and
        # then re-applies that relative form against the input file's directory.  When
        # both are the same directory the path arithmetic is correct; running from the
        # project root produces a doubled/wrong path.
        dpi = render_dpi()
        result = subprocess.run(
            ["java", "-Djava.awt.headless=true", f"-DPLANTUML_LIMIT_SIZE={plantuml_limit_size()}", "-jar", str(jar.resolve()),
             "-tpng", f"-Sdpi={dpi}", "-o", str(rendered_dir.resolve()), tmp_path.name],
            cwd=str(puml_path.parent),
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            warnings.append(f"PlantUML render failed: {result.stderr[:200]}")
            return None

        rendered = rendered_dir / f"{tmp_path.stem}.png"
        if rendered.exists():
            stem = puml_path.stem
            parts = stem.split(".", 2)
            friendly_name = parts[2] if len(parts) >= 3 else stem
            final = rendered_dir / f"{friendly_name}.png"
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
    rendered_dir = puml_path.parent.parent / RENDERED
    rendered_dir.mkdir(parents=True, exist_ok=True)

    content = puml_path.read_text(encoding="utf-8")
    start = content.find("@startuml")
    end = content.find("@enduml")
    if start == -1 or end == -1:
        return None

    puml_body = content[start:end + len("@enduml")]
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
        result = subprocess.run(
            ["java", "-Djava.awt.headless=true", f"-DPLANTUML_LIMIT_SIZE={plantuml_limit_size()}", "-jar", str(jar.resolve()),
             "-tsvg", "-o", str(rendered_dir.resolve()), tmp_path.name],
            cwd=str(puml_path.parent),
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            return None

        rendered = rendered_dir / f"{tmp_path.stem}.svg"
        if rendered.exists():
            stem = puml_path.stem
            parts = stem.split(".", 2)
            friendly_name = parts[2] if len(parts) >= 3 else stem
            final = rendered_dir / f"{friendly_name}.svg"
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


def create_diagram(
    *,
    repo_root: Path,
    verifier: ArtifactVerifier,
    clear_repo_caches: Callable[[Path], None],
    diagram_type: str,
    name: str,
    puml: str,
    artifact_id: str | None,
    keywords: list[str] | None = None,
    entity_ids_used: list[str] | None = None,
    connection_ids_used: list[str] | None = None,
    version: str,
    status: str,
    last_updated: str | None,
    connection_inference: DiagramConnectionInferenceMode = "none",
    auto_include_stereotypes: bool = True,
    dry_run: bool,
) -> WriteResult:
    assert_engagement_write_root(repo_root)

    effective_id = artifact_id
    if effective_id is None:
        m = re.search(r"@startuml\s+(\S+)", puml)
        if m:
            effective_id = m.group(1).strip()
    if effective_id is None:
        raise ValueError("artifact_id is required, or puml must contain '@startuml <artifact-id>'")

    puml_body = puml.strip("\n") + "\n"
    warnings: list[str] = []

    # Auto-include stereotypes + glyphs for archimate diagrams
    stereotypes_path = repo_root / DIAGRAM_CATALOG / "_archimate-stereotypes.puml"
    if (
        auto_include_stereotypes
        and "archimate" in diagram_type.lower()
        and stereotypes_path.exists()
        and "_archimate-stereotypes.puml" not in puml_body
    ):
        puml_body = re.sub(
            r"(@startuml\s+\S+\s*)\n",
            r"\1\n!include ../_archimate-stereotypes.puml\n",
            puml_body,
            count=1,
        )

    glyphs_path = repo_root / DIAGRAM_CATALOG / "_archimate-glyphs.puml"
    if (
        auto_include_stereotypes
        and "archimate" in diagram_type.lower()
        and glyphs_path.exists()
        and "_archimate-glyphs.puml" not in puml_body
    ):
        puml_body = re.sub(
            r"(!include \.\./\_archimate-stereotypes\.puml)\n",
            r"\1\n!include ../_archimate-glyphs.puml\n",
            puml_body,
            count=1,
        )

    # Auto-layout: insert hidden links and arrow direction hints
    puml_body = optimize_puml_layout(puml_body)

    from .boundary import today_iso
    last = last_updated or today_iso()

    content = format_diagram_puml(
        artifact_id=effective_id,
        diagram_type=diagram_type,
        name=name,
        version=version,
        status=status,
        last_updated=last,
        keywords=keywords,
        entity_ids_used=entity_ids_used,
        connection_ids_used=connection_ids_used,
        puml_body=puml_body,
    )

    path = repo_root / DIAGRAM_CATALOG / DIAGRAMS / f"{effective_id}.puml"

    if dry_run:
        res = verify_content_in_temp_path(
            verifier=verifier,
            file_type="diagram",
            desired_name=path.name,
            content=content,
            support_repo_root=repo_root,
        )
        return WriteResult(
            wrote=False,
            path=path,
            artifact_id=effective_id,
            content=content,
            warnings=warnings,
            verification=_verification_to_dict(path, res),
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    prev = path.read_text(encoding="utf-8") if path.exists() else None
    path.write_text(content, encoding="utf-8")

    res = verifier.verify_diagram_file(path)
    if not res.valid:
        if prev is None:
            try:
                path.unlink()
            except OSError:
                pass
        else:
            path.write_text(prev, encoding="utf-8")
        return WriteResult(
            wrote=False,
            path=path,
            artifact_id=effective_id,
            content=content,
            warnings=warnings,
            verification=_verification_to_dict(path, res),
        )

    # Render PNG + SVG after successful write
    png_path = _render_diagram_png(path, warnings)
    if png_path:
        warnings.append(f"Rendered PNG: {png_path}")
    _render_diagram_svg(path, warnings)

    clear_repo_caches(path)

    return WriteResult(
        wrote=True,
        path=path,
        artifact_id=effective_id,
        content=None,
        warnings=warnings,
        verification=_verification_to_dict(path, res),
    )
