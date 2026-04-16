"""
generate_macros.py — Regenerate _macros.puml from entity §display ###archimate blocks.

Usage:
    uv run python -m src.tools.generate_macros [REPO_ROOT]

The script scans every .md entity file under <REPO_ROOT>/model/ for a
§display ###archimate block, extracts domain/element-type/label/alias fields,
and writes <REPO_ROOT>/diagram-catalog/_macros.puml.

Alias convention (PlantUML):
    Aliases follow the pattern TYPE_random (e.g. DRV_Qw7Er1).
    In diagram source files, reference elements by their alias.
"""


import math
import re
import sys
import json
from pathlib import Path

import yaml

from src.common.ontology_loader import ENTITY_TYPES
from src.common.settings import archimate_type_markers, sprite_scale

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DISPLAY_SECTION = re.compile(r"<!--\s*§display\s*-->", re.IGNORECASE)
_ARCHIMATE_H3 = re.compile(r"###\s*archimate\b", re.IGNORECASE)
_YAML_FENCE = re.compile(r"```ya?ml\s*\n(.*?)```", re.DOTALL)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_GLYPHS_PATH = _PROJECT_ROOT / "tools" / "gui" / "src" / "ui" / "lib" / "archimateGlyphs.json"


def _extract_archimate_block(content: str) -> dict | None:
    """Return the parsed archimate YAML block from §display, or None."""
    m = _DISPLAY_SECTION.search(content)
    if not m:
        return None
    display_text = content[m.end():]
    h3 = _ARCHIMATE_H3.search(display_text)
    if not h3:
        return None
    after_h3 = display_text[h3.end():]
    fence = _YAML_FENCE.search(after_h3)
    if not fence:
        return None
    try:
        return yaml.safe_load(fence.group(1)) or {}
    except yaml.YAMLError:
        return None


_DOMAIN_ORDER = {
    "motivation": 0,
    "strategy": 1,
    "common": 2,
    "business": 3,
    "application": 4,
    "technology": 5,
    "implementation": 6,
}

_PREFIX_ORDER = [
    "STK", "DRV", "ASM", "GOL", "OUT", "PRI", "REQ", "CST", "MEA", "VAL",
    "CAP", "VS", "RES", "COA",
    "SRV", "PRC", "FNC", "INT", "EVT", "ROL",
    "ACT", "BIF", "BOB",
    "APP", "AIF", "DOB",
    "NOD", "DEV", "SSW", "TIF", "PTH", "NET", "ART",
    "EQP", "FAC", "DIS", "MAT",
    "WP", "DEL", "IEV", "PLT",
]


def _sort_key(entry: tuple[str, str, str]) -> tuple[int, int, str]:
    """Sort by domain → prefix → alias."""
    domain, _, alias = entry
    prefix = alias.split("_")[0] if "_" in alias else alias
    domain_idx = _DOMAIN_ORDER.get(domain.lower(), 99)
    prefix_idx = _PREFIX_ORDER.index(prefix) if prefix in _PREFIX_ORDER else 99
    return domain_idx, prefix_idx, alias


def _load_glyphs() -> dict:
    return json.loads(_GLYPHS_PATH.read_text(encoding="utf-8"))


_SPRITE_STROKE = "#252327"
_LINE_HALF_W = 0.65  # half of 1.3 stroke-width — for open-path → rect conversion

_SVG_ELEM_RE = re.compile(
    r"<(?P<tag>circle|path|rect|line|ellipse|polyline|polygon|use)"
    r"(?P<attrs>[^>]*?)"
    r"(?P<close>/?>)"
)
_PATH_CMD_RE = re.compile(r"([MmHhVvLlZzAaCcQqSsTt])([^MmHhVvLlZzAaCcQqSsTt]*)")
_NUM_RE = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")
_SUBPATH_SPLIT_RE = re.compile(r"(?=M)")  # Split compound paths at absolute moveto


def _ensure_attr(attrs: str, name: str, value: str) -> str:
    """Return attrs with name=value appended unless the attribute is already set."""
    if f"{name}=" in attrs:
        return attrs
    return f"{attrs} {name}=\"{value}\""


def _parse_path_segments(d: str) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """Return straight-line (x1,y1)→(x2,y2) segments from an SVG path d-value.

    Handles M/m/H/h/V/v/L/l commands.  Curves and arcs are ignored.
    """
    segs: list[tuple[tuple[float, float], tuple[float, float]]] = []
    cx = cy = 0.0
    for cmd, raw in _PATH_CMD_RE.findall(d):
        vals = [float(v) for v in _NUM_RE.findall(raw)]
        if cmd == "M":
            pairs = [(vals[i], vals[i + 1]) for i in range(0, len(vals) - 1, 2)]
            if pairs:
                cx, cy = pairs[0]
                for x2, y2 in pairs[1:]:
                    segs.append(((cx, cy), (x2, y2)))
                    cx, cy = x2, y2
        elif cmd == "m":
            pairs = [(vals[i], vals[i + 1]) for i in range(0, len(vals) - 1, 2)]
            if pairs:
                cx, cy = cx + pairs[0][0], cy + pairs[0][1]
                for dx, dy in pairs[1:]:
                    x2, y2 = cx + dx, cy + dy
                    segs.append(((cx, cy), (x2, y2)))
                    cx, cy = x2, y2
        elif cmd == "H":
            for x2 in vals:
                segs.append(((cx, cy), (x2, cy)))
                cx = x2
        elif cmd == "h":
            for dx in vals:
                x2 = cx + dx
                segs.append(((cx, cy), (x2, cy)))
                cx = x2
        elif cmd == "V":
            for y2 in vals:
                segs.append(((cx, cy), (cx, y2)))
                cy = y2
        elif cmd == "v":
            for dy in vals:
                y2 = cy + dy
                segs.append(((cx, cy), (cx, y2)))
                cy = y2
        elif cmd in ("L", "l"):
            rel = cmd == "l"
            for i in range(0, len(vals) - 1, 2):
                x2 = cx + vals[i] if rel else vals[i]
                y2 = cy + vals[i + 1] if rel else vals[i + 1]
                segs.append(((cx, cy), (x2, y2)))
                cx, cy = x2, y2
    return segs


def _seg_to_path(p1: tuple[float, float], p2: tuple[float, float]) -> str | None:
    """Convert any line segment to a thin filled closed-path polygon.

    Axis-aligned segments use compact rect syntax.  Diagonal segments are
    rendered as a rotated thin rectangle (4-point closed polygon).
    Returns None if the segment is too short to render.
    """
    x1, y1 = p1
    x2, y2 = p2
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy)
    if length < 0.2:
        return None
    hw = _LINE_HALF_W
    if abs(dy) < 0.05:  # Horizontal
        xm = min(x1, x2)
        return (
            f'<path d="M{xm:.2f} {y1 - hw:.2f}h{length:.2f}v{hw * 2:.2f}H{xm:.2f}z"'
            f' fill="{_SPRITE_STROKE}"/>'
        )
    if abs(dx) < 0.05:  # Vertical
        ym = min(y1, y2)
        return (
            f'<path d="M{x1 - hw:.2f} {ym:.2f}v{length:.2f}h{hw * 2:.2f}V{ym:.2f}z"'
            f' fill="{_SPRITE_STROKE}"/>'
        )
    # Diagonal: perpendicular unit vector scaled by half-width
    nx, ny = (-dy / length) * hw, (dx / length) * hw
    ax, ay = x1 + nx, y1 + ny
    bx, by = x1 - nx, y1 - ny
    cx, cy = x2 - nx, y2 - ny
    ex, ey = x2 + nx, y2 + ny
    return (
        f'<path d="M{ax:.2f} {ay:.2f}L{bx:.2f} {by:.2f}L{cx:.2f} {cy:.2f}L{ex:.2f} {ey:.2f}z"'
        f' fill="{_SPRITE_STROKE}"/>'
    )


def _open_path_to_elements(d: str) -> str:
    """Convert an open SVG path (no z) to PlantUML-renderable filled rect elements.

    Compound paths (multiple ``M`` commands) are split and each sub-path is
    processed independently — this keeps capability bars as 3 separate rects.

    Two strategies per sub-path:
    1. U-shape detection: all segments axis-aligned AND start ≈ end on same axis
       → single filled bounding-box rect (e.g. bar chart bars).
    2. Per-segment conversion: H/V lines → thin filled rects.
       Diagonal segments are skipped.
    """
    # Split at absolute M to handle compound paths as independent sub-paths
    sub_paths = [s for s in _SUBPATH_SPLIT_RE.split(d) if s.strip()]
    if len(sub_paths) > 1:
        return "".join(_open_path_to_elements(sub) for sub in sub_paths)

    segs = _parse_path_segments(d)
    if not segs:
        return ""

    # Only attempt U-shape when every segment is axis-aligned (no diagonals)
    all_aligned = all(
        abs(s[0][0] - s[1][0]) < 0.05 or abs(s[0][1] - s[1][1]) < 0.05
        for s in segs
    )
    if all_aligned and len(segs) >= 2:
        sx, sy = segs[0][0]
        ex, ey = segs[-1][1]
        all_x = [p[0] for s in segs for p in s]
        all_y = [p[1] for s in segs for p in s]
        x_min, x_max = min(all_x), max(all_x)
        y_min, y_max = min(all_y), max(all_y)
        w, h = x_max - x_min, y_max - y_min
        if w > 0.5 and h > 0.5 and (abs(sy - ey) < 0.1 or abs(sx - ex) < 0.1):
            return (
                f'<path d="M{x_min:.2f} {y_min:.2f}h{w:.2f}v{h:.2f}H{x_min:.2f}z"'
                f' fill="{_SPRITE_STROKE}"/>'
            )

    # Per-segment fallback: H/V segments → thin closed paths; diagonals skipped
    return "".join(r for s in segs if (r := _seg_to_path(*s)))


def _rect_to_outline_paths(attrs: str) -> str:
    """Convert a <rect> element to four thin closed-path border segments.

    PlantUML's SVG sprite renderer cannot render ``<rect>`` elements at all.
    Four thin filled ``<path>`` rectangles are used to approximate a hollow-box
    outline.  Border thickness equals the standard line width (``_LINE_HALF_W*2``).
    """
    x_m = re.search(r'\bx="([^"]*)"', attrs)
    y_m = re.search(r'\by="([^"]*)"', attrs)
    w_m = re.search(r'\bwidth="([^"]*)"', attrs)
    h_m = re.search(r'\bheight="([^"]*)"', attrs)
    if not (x_m and y_m and w_m and h_m):
        return ""
    x = float(x_m.group(1))
    y = float(y_m.group(1))
    w = float(w_m.group(1))
    h = float(h_m.group(1))
    t = _LINE_HALF_W * 2  # border thickness = full stroke width
    parts: list[str] = [
        # Top border
        f'<path d="M{x:.2f} {y:.2f}h{w:.2f}v{t:.2f}H{x:.2f}z" fill="{_SPRITE_STROKE}"/>',
        # Bottom border
        f'<path d="M{x:.2f} {y + h - t:.2f}h{w:.2f}v{t:.2f}H{x:.2f}z" fill="{_SPRITE_STROKE}"/>',
    ]
    inner_h = h - 2 * t
    if inner_h > 0.1:
        # Left border
        parts.append(
            f'<path d="M{x:.2f} {y + t:.2f}v{inner_h:.2f}h{t:.2f}V{y + t:.2f}z" fill="{_SPRITE_STROKE}"/>'
        )
        # Right border
        parts.append(
            f'<path d="M{x + w - t:.2f} {y + t:.2f}v{inner_h:.2f}h{t:.2f}V{y + t:.2f}z" fill="{_SPRITE_STROKE}"/>'
        )
    return "".join(parts)


def _browser_markup_to_plantuml_svg(markup: str) -> str:
    """Convert browser SVG markup to PlantUML-compatible sprite SVG.

    archimateGlyphs.json is designed for browsers where:
    - ``fill="currentColor"`` resolves via CSS
    - Presentation attributes inherit from the parent ``<svg>``
    - Stroke draws paths visually

    PlantUML's Java SVG sprite renderer does NOT support any of the above:
    - No attribute inheritance from parent ``<svg>``
    - ``<path>`` elements: only fill is drawn; stroke is ignored entirely
    - Confirmed: open paths with fill="none" render as nothing

    Strategy applied here:
    - ``fill="currentColor"`` → ``fill="#252327"`` (substituted before element patching)
    - Closed ``<path>`` (has z): rendered as solid filled shape
    - Open ``<path>`` (no z): H/V line segments → thin filled ``<rect>``; U-shapes →
      filled bounding rect; diagonals skipped
    - ``<circle>`` / ``<rect>`` / ``<ellipse>``: explicit fill="none" + stroke for outlines
    """
    markup = markup.replace('fill="currentColor"', f'fill="{_SPRITE_STROKE}"')

    def _patch(m: re.Match) -> str:
        tag = m.group("tag")
        attrs = m.group("attrs")
        close = m.group("close")

        if tag == "path":
            d_m = re.search(r'\bd="([^"]*)"', attrs)
            d_val = d_m.group(1) if d_m else ""
            if re.search(r"[Zz]", d_val):
                # Closed path → solid filled shape (PlantUML ignores fill="none")
                attrs = _ensure_attr(attrs, "fill", _SPRITE_STROKE)
                attrs = _ensure_attr(attrs, "stroke", "none")
                return f"<{tag}{attrs}{close}"
            # Open path → closed-path thin proxies for H/V segments
            return _open_path_to_elements(d_val)

        if tag == "rect":
            # PlantUML cannot render <rect> elements at all — replace with
            # four thin closed-path border segments (hollow box outline)
            return _rect_to_outline_paths(attrs)

        # circle / ellipse — outline with explicit stroke (stroke works on these)
        attrs = _ensure_attr(attrs, "fill", "none")
        attrs = _ensure_attr(attrs, "stroke", _SPRITE_STROKE)
        attrs = _ensure_attr(attrs, "stroke-width", "1.3")
        return f"<{tag}{attrs}{close}"

    result = _SVG_ELEM_RE.sub(_patch, markup)
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16">{result}</svg>'


def _generate_glyph_include(repo_root: Path) -> Path:
    glyphs = _load_glyphs()
    mode = archimate_type_markers()
    lines = [
        "' _archimate-glyphs.puml — generated ArchiMate glyph sprites",
        "' Auto-generated from tools/gui/src/ui/lib/archimateGlyphs.json.",
        "' Do not edit manually.",
        "",
    ]
    if mode == "icons":
        lines.append("hide stereotype")
        lines.append("")
        for info in sorted(ENTITY_TYPES.values(), key=lambda item: item.archimate_element_type):
            kind = glyphs["types"].get(info.artifact_type)
            if not kind:
                continue
            markup = glyphs["kinds"].get(kind)
            if not markup:
                continue
            sprite_name = f"$archimate_{info.archimate_element_type}"
            lines.append(f"sprite {sprite_name} {_browser_markup_to_plantuml_svg(markup)}")
    out_path = repo_root / "diagram-catalog" / "_archimate-glyphs.puml"
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_path


def _macro_label(label: str, element_type: str) -> str:
    if archimate_type_markers() != "icons":
        return label
    scale = sprite_scale()
    return f"<$archimate_{element_type}{{scale={scale}}}> {label}"


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
    roots_to_scan: list[Path] = []
    if enterprise_root and (enterprise_root / "model").is_dir():
        roots_to_scan.append(enterprise_root)
    entities_root = repo_root / "model"
    if not entities_root.is_dir():
        raise FileNotFoundError(f"model/ not found under {repo_root}")
    roots_to_scan.append(repo_root)

    _generate_glyph_include(repo_root)
    entries: list[tuple[str, str, str]] = []  # (domain, macro_line, alias)
    seen_aliases: set[str] = set()

    for scan_root in roots_to_scan:
        model_dir = scan_root / "model"
        for md_file in sorted(model_dir.rglob("*.md")):
            if md_file.name.endswith(".outgoing.md"):
                continue
            content = md_file.read_text(encoding="utf-8")
            archimate = _extract_archimate_block(content)
            if not archimate:
                continue

            label = archimate.get("label", "")
            element_type = archimate.get("element-type", "")
            alias_raw = archimate.get("alias", "")

            if not (label and element_type and alias_raw):
                continue

            alias = alias_raw.replace("-", "_")
            if alias in seen_aliases:
                continue
            seen_aliases.add(alias)

            domain = archimate.get("domain", "")
            if not domain:
                rel = md_file.relative_to(model_dir)
                domain = rel.parts[0] if rel.parts else "unknown"

            proc_name = f"$DECL_{alias}"
            macro_line = (
                f"!procedure {proc_name}()\n"
                f'  rectangle "{_macro_label(label, element_type)}" <<{element_type}>> as {alias}\n'
                f"!endprocedure"
            )
            entries.append((domain, macro_line, alias))

    entries.sort(key=_sort_key)

    lines: list[str] = [
        "' _macros.puml — ArchiMate element procedure library",
        "' Auto-generated from entity §display ###archimate blocks.",
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
    out_path = repo_root / "diagram-catalog" / "_macros.puml"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(output, encoding="utf-8")
    print(f"Written {len(entries)} macros → {out_path}")
    return out_path


def main() -> None:
    if len(sys.argv) > 1:
        repo_root = Path(sys.argv[1]).resolve()
    else:
        project_root = Path(__file__).resolve().parent.parent.parent
        repo_root = (
            project_root
            / "engagements"
            / "ENG-ARCH-REPO"
            / "architecture-repository"
        )

    if not repo_root.is_dir():
        print(f"ERROR: repo_root does not exist: {repo_root}", file=sys.stderr)
        sys.exit(1)

    generate_macros(repo_root)


if __name__ == "__main__":
    main()
