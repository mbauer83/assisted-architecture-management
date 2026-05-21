"""
generate_static_includes.py — Regenerate ArchiMate static include files.

Writes two files into <REPO_ROOT>/diagram-catalog/:
  _archimate-glyphs.puml     — SVG sprite definitions for all entity types
  _archimate-stereotypes.puml — skinparam blocks for all entity types

These files are derived from the installed ontology, not from entity instance files.
Regenerate after installing a new ontology version or when first initialising a repo.

Usage:
    uv run python -m src.infrastructure.rendering.generate_static_includes [REPO_ROOT]
"""

from __future__ import annotations

import sys
from pathlib import Path

from src.config.repo_paths import DIAGRAM_CATALOG
from src.config.settings import archimate_type_markers


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sprite_key(artifact_type: str) -> str:
    return artifact_type.replace("-", "_")


def _generate_glyph_include(repo_root: Path) -> Path:
    """Write _archimate-glyphs.puml using ontology sprite_for() methods."""
    from src.infrastructure.app_bootstrap import get_module_registry  # noqa: PLC0415

    registry = get_module_registry()
    mode = archimate_type_markers()
    lines = [
        "' _archimate-glyphs.puml — generated ArchiMate glyph sprites",
        "' Auto-generated — do not edit manually.",
        "",
    ]
    if mode == "icons":
        lines.append("hide stereotype")
        lines.append("")
        for om in registry.all_ontologies().values():
            for artifact_type in sorted(om.entity_types):
                sprite_line = om.sprite_for(str(artifact_type))
                if sprite_line:
                    lines.append(sprite_line)
    out_path = repo_root / DIAGRAM_CATALOG / "_archimate-glyphs.puml"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_path


_DOMAIN_COLORS: dict[str, dict[str, str]] = {
    "motivation": {
        "bg": "#EDD6F0",
        "border": "#7B3F9A",
        "grouping_bg": "#F7EEF9",
        "grouping_name": "MotivationGrouping",
    },
    "strategy": {
        "bg": "#F5DEB3",
        "border": "#8B6914",
        "grouping_bg": "#FAF0D9",
        "grouping_name": "StrategyGrouping",
    },
    "common": {
        "bg": "#E0D8CC",
        "border": "#8C7E6A",
        "grouping_bg": "#EDE8E1",
        "grouping_name": "CommonGrouping",
    },
    "business": {
        "bg": "#FFFAC8",
        "border": "#B8860B",
        "grouping_bg": "#FFFDEC",
        "grouping_name": "BusinessGrouping",
    },
    "application": {
        "bg": "#CCF2FF",
        "border": "#0078A0",
        "grouping_bg": "#E8F8FF",
        "grouping_name": "ApplicationGrouping",
    },
    "technology": {
        "bg": "#CCFFCC",
        "border": "#2E7D32",
        "grouping_bg": "#E8FFEE",
        "grouping_name": "TechnologyGrouping",
    },
    "implementation": {
        "bg": "#FFE4C4",
        "border": "#8D4E00",
        "grouping_bg": "#FFF3E8",
        "grouping_name": "ImplementationGrouping",
    },
}

_STEREOTYPE_HEADER = """\
hide stereotype

skinparam defaultFontName "Helvetica Neue, Helvetica, Arial, sans-serif"
skinparam defaultFontSize 12
skinparam shadowing false
skinparam roundcorner 4
skinparam backgroundColor #FAFAFA

skinparam linetype ortho
skinparam nodesep 60
skinparam ranksep 80

skinparam rectangle<<Grouping>> {
  BackgroundColor #FFFFFF
  BorderColor #9E9E9E
}
"""


def _stereotype_block(name: str, bg: str, border: str) -> str:
    return f"skinparam rectangle<<{name}>> {{\n  BackgroundColor {bg}\n  BorderColor {border}\n}}"


def _generate_stereotype_include(repo_root: Path) -> Path:
    """Write _archimate-stereotypes.puml with domain colors and skinparam blocks."""
    from src.infrastructure.app_bootstrap import get_module_registry  # noqa: PLC0415

    registry = get_module_registry()

    lines: list[str] = [
        "' _archimate-stereotypes.puml — ArchiMate skinparam definitions",
        "' Auto-generated — do not edit manually.",
        "",
        _STEREOTYPE_HEADER,
    ]

    # Group entity types by domain (first hierarchy element).
    domain_types: dict[str, list[str]] = {}
    for om in registry.all_ontologies().values():
        for artifact_type, info in om.entity_types.items():
            domain = info.hierarchy[0] if info.hierarchy else "common"
            domain_types.setdefault(domain, []).append(str(artifact_type))

    from src.domain.ontology_catalog import domain_order  # noqa: PLC0415

    ordered_domains = domain_order()

    for domain in ordered_domains:
        colors = _DOMAIN_COLORS.get(domain)
        if not colors:
            continue
        types_in_domain = sorted(domain_types.get(domain, []))
        if not types_in_domain:
            continue

        lines.append(f"' {'-' * 75}")
        lines.append(f"' {domain.capitalize()} layer")
        lines.append(f"' {'-' * 75}")
        lines.append(_stereotype_block(colors["grouping_name"], colors["grouping_bg"], colors["border"]))
        for artifact_type in types_in_domain:
            key = _sprite_key(artifact_type)
            lines.append(_stereotype_block(key, colors["bg"], colors["border"]))
        lines.append("")

    out_path = repo_root / DIAGRAM_CATALOG / "_archimate-stereotypes.puml"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_static_includes(repo_root: Path) -> None:
    """Write _archimate-glyphs.puml and _archimate-stereotypes.puml to *repo_root*.

    Idempotent — safe to call repeatedly.
    """
    _generate_glyph_include(repo_root)
    _generate_stereotype_include(repo_root)


def main() -> None:
    if len(sys.argv) > 1:
        repo_root = Path(sys.argv[1]).resolve()
    else:
        from src.config.workspace_paths import resolve_workspace_repo_roots  # noqa: PLC0415

        roots = resolve_workspace_repo_roots(Path.cwd())
        if roots is None:
            print(
                "ERROR: no repo_root argument provided and no workspace configuration found. "
                "Run arch-init or provide arch-workspace.yaml.",
                file=sys.stderr,
            )
            sys.exit(1)
        repo_root = roots[0]

    if not repo_root.is_dir():
        print(f"ERROR: repo_root does not exist: {repo_root}", file=sys.stderr)
        sys.exit(1)

    generate_static_includes(repo_root)
    print(f"Written _archimate-glyphs.puml and _archimate-stereotypes.puml → {repo_root / 'diagram-catalog'}")


if __name__ == "__main__":
    main()
