"""
generate_macros.py — Regenerate _macros.puml from entity §display blocks.

Usage:
    uv run python -m src.infrastructure.rendering.generate_macros [REPO_ROOT]

Scans every .md entity file under <REPO_ROOT>/model/ for a §display block,
extracts label/alias, derives the stereotype key from the entity's artifact_type,
and writes <REPO_ROOT>/diagram-catalog/_macros.puml.

Alias convention (PlantUML):
    Aliases follow the pattern TYPE_random (e.g. DRV_Qw7Er1).
    In diagram source files, reference elements by their alias.
"""

import re
import sys
from pathlib import Path

import yaml

from src.application.artifact_parsing import normalize_puml_alias
from src.config.repo_paths import DIAGRAM_CATALOG, MODEL
from src.config.settings import archimate_type_markers, sprite_scale

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DISPLAY_SECTION = re.compile(r"<!--\s*§display\s*-->", re.IGNORECASE)
_H3_SECTION = re.compile(r"###\s+(\S+)", re.IGNORECASE)
_YAML_FENCE = re.compile(r"```ya?ml\s*\n(.*?)```", re.DOTALL)
_FRONTMATTER = re.compile(r"^---\n(.*?)\n---", re.DOTALL)


def _extract_frontmatter(content: str) -> dict:
    m = _FRONTMATTER.match(content)
    if not m:
        return {}
    try:
        result: object = yaml.safe_load(m.group(1)) or {}
        return result if isinstance(result, dict) else {}
    except yaml.YAMLError:
        return {}


def _extract_display_section_for_id(content: str, section_id: str) -> dict | None:
    m = _DISPLAY_SECTION.search(content)
    if not m:
        return None
    display_text = content[m.end() :]
    for h3_match in _H3_SECTION.finditer(display_text):
        if h3_match.group(1).lower() == section_id.lower():
            after_h3 = display_text[h3_match.end() :]
            fence = _YAML_FENCE.search(after_h3)
            if not fence:
                return None
            try:
                result: object = yaml.safe_load(fence.group(1)) or {}
                return result if isinstance(result, dict) else None
            except yaml.YAMLError:
                return None
    return None


def _sprite_key(artifact_type: str) -> str:
    return artifact_type.replace("-", "_")


def _macro_label(label: str, artifact_type: str) -> str:
    if archimate_type_markers() != "icons":
        return label
    scale = sprite_scale()
    key = _sprite_key(artifact_type)
    return f"<$archimate_{key}{{scale={scale}}}> {label}"


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


def _domain_order_index() -> dict[str, int]:
    from src.domain.ontology_catalog import domain_order  # noqa: PLC0415

    return {d: i for i, d in enumerate(domain_order())}


_PREFIX_ORDER = [
    "STK",
    "DRV",
    "ASS",
    "GOL",
    "OUT",
    "PRI",
    "REQ",
    "MEA",
    "VAL",
    "CAP",
    "VS",
    "RES",
    "COA",
    "SRV",
    "PRC",
    "FNC",
    "EVT",
    "ROL",
    "PTH",
    "JNA",
    "JNO",
    "ACT",
    "BIF",
    "BOB",
    "PRD",
    "APP",
    "AIF",
    "DOB",
    "NOD",
    "DEV",
    "SSW",
    "TIF",
    "NET",
    "ART",
    "EQP",
    "FAC",
    "DIS",
    "MAT",
    "WP",
    "DEL",
    "PLT",
]


def _sort_key(entry: tuple[str, str, str]) -> tuple[int, int, str]:
    domain, _, alias = entry
    prefix = alias.split("_")[0] if "_" in alias else alias
    domain_idx = _domain_order_index().get(domain.lower(), 99)
    prefix_idx = _PREFIX_ORDER.index(prefix) if prefix in _PREFIX_ORDER else 99
    return domain_idx, prefix_idx, alias


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def generate_macros(repo_root: Path, *, enterprise_root: Path | None = None) -> Path:
    """Scan model/ directories and write diagram-catalog/_macros.puml.

    When *enterprise_root* is provided, macros from both repos are combined
    so that engagement diagrams can reference enterprise entities.  The macros
    file is always written to *repo_root* (the engagement repo).

    Returns the path to the written file.
    """
    from src.infrastructure.app_bootstrap import get_module_registry  # noqa: PLC0415

    registry = get_module_registry()

    roots_to_scan: list[Path] = []
    if enterprise_root and (enterprise_root / MODEL).is_dir():
        roots_to_scan.append(enterprise_root)
    entities_root = repo_root / MODEL
    if not entities_root.is_dir():
        raise FileNotFoundError(f"{MODEL}/ not found under {repo_root}")
    roots_to_scan.append(repo_root)

    _generate_glyph_include(repo_root)
    _generate_stereotype_include(repo_root)
    entries: list[tuple[str, str, str]] = []  # (domain, macro_line, alias)
    seen_aliases: set[str] = set()

    for scan_root in roots_to_scan:
        model_dir = scan_root / MODEL
        for md_file in sorted(model_dir.rglob("*.md")):
            if md_file.name.endswith(".outgoing.md"):
                continue
            content = md_file.read_text(encoding="utf-8")
            fm = _extract_frontmatter(content)
            artifact_type = str(fm.get("artifact-type", ""))
            if not artifact_type:
                continue

            entity_info = registry.find_entity_type(
                __import__("src.domain.module_types", fromlist=["EntityTypeName"]).EntityTypeName(artifact_type)
            )
            ontology = (
                registry.ontology_for_entity_type(
                    __import__("src.domain.module_types", fromlist=["EntityTypeName"]).EntityTypeName(artifact_type)
                )
                if entity_info
                else None
            )

            section_id = ontology.display_section_id if ontology else "archimate"
            block = _extract_display_section_for_id(content, section_id)
            if not block:
                continue

            label = str(block.get("label", "")).strip()
            alias_raw = str(block.get("alias", "")).strip()
            if not (label and alias_raw):
                continue

            alias = normalize_puml_alias(alias_raw)
            if alias in seen_aliases:
                continue
            seen_aliases.add(alias)

            domain = entity_info.hierarchy[0] if entity_info and entity_info.hierarchy else ""
            if not domain:
                rel = md_file.relative_to(model_dir)
                domain = rel.parts[0] if rel.parts else "unknown"

            stereotype = _sprite_key(artifact_type) if artifact_type else ""
            proc_name = f"$DECL_{alias}"
            macro_line = (
                f"!procedure {proc_name}()\n"
                f'  rectangle "{_macro_label(label, artifact_type)}" <<{stereotype}>> as {alias}\n'
                f"!endprocedure"
            )
            entries.append((domain, macro_line, alias))

    entries.sort(key=_sort_key)

    lines: list[str] = [
        "' _macros.puml — ArchiMate element procedure library",
        "' Auto-generated from entity §display blocks.",
        "' Do not edit manually — regenerated by generate_macros().",
        "'",
        "' USAGE CONVENTION:",
        "'   Declare element inside a grouping rectangle:  $DECL_DRV_Qw7Er1()",
        "'   Reference element in a connection line:       DRV_Qw7Er1",
        "",
    ]

    current_domain = None
    for domain, macro_line, _ in entries:
        if domain != current_domain:
            if current_domain is not None:
                lines.append("")
            lines.append(f"' {'-' * 75}")
            lines.append(f"' {domain}")
            lines.append(f"' {'-' * 75}")
            current_domain = domain
        lines.append(macro_line)

    output = "\n".join(lines) + "\n"
    out_path = repo_root / DIAGRAM_CATALOG / "_macros.puml"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(output, encoding="utf-8")
    print(f"Written {len(entries)} macros → {out_path}")
    return out_path


def main() -> None:
    if len(sys.argv) > 1:
        repo_root = Path(sys.argv[1]).resolve()
    else:
        from src.config.workspace_paths import resolve_workspace_repo_roots

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

    generate_macros(repo_root)


if __name__ == "__main__":
    main()
