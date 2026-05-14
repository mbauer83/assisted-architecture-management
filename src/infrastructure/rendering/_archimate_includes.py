"""Shared display-block parsing and ArchiMate include expansion helpers."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_CALLED_MACRO_RE = re.compile(r'\$(?:DECL|NEST)_([A-Za-z0-9_]+)\(\)')


def _load_macro_alias_map(repo_root: Path) -> dict[str, str]:
    """Return {alias: procedure_body} for every $DECL_ALIAS() in _macros.puml."""
    macros_path = repo_root / "diagram-catalog" / "_macros.puml"
    try:
        text = macros_path.read_text(encoding="utf-8")
    except OSError:
        return {}
    alias_map: dict[str, str] = {}
    for m in re.finditer(
        r"!procedure \$DECL_([A-Za-z0-9_]+)\(\)\n(.*?)!endprocedure",
        text,
        re.DOTALL,
    ):
        alias_map[m.group(1)] = m.group(2)
    return alias_map


def parse_archimate_display_block(raw: str) -> dict[str, Any]:
    import yaml as _yaml

    text = re.sub(r"^```(?:yaml)?\n", "", raw.strip(), count=1)
    text = re.sub(r"\n```$", "", text, count=1)
    try:
        loaded: Any = _yaml.safe_load(text) or {}
    except Exception:  # noqa: BLE001
        return {}
    return loaded if isinstance(loaded, dict) else {}


def inject_archimate_includes(body: str, repo_root: Path) -> str:
    """Inline only the ArchiMate stereotypes and sprites actually used by *body*."""
    if "_archimate-stereotypes.puml" not in body:
        return body

    # Diagrams that use $DECL_*() macros declare elements inside _macros.puml procedures.
    # Those procedures contain the <<stereotype>> and <$sprite> references, not the body.
    if "_macros.puml" in body:
        called_aliases = set(_CALLED_MACRO_RE.findall(body))
        alias_map = _load_macro_alias_map(repo_root)
        scan_text = body + "\n" + "\n".join(
            alias_map[alias] for alias in called_aliases if alias in alias_map
        )
    else:
        scan_text = body

    needed_types = set(re.findall(r"<<(\w+)>>", scan_text))
    needed_sprites = set(re.findall(r"<\$archimate_(\w+)", scan_text))
    already_sprites = set(re.findall(r"^sprite \$archimate_(\w+)", body, re.MULTILINE))
    sprites_to_inject = needed_sprites - already_sprites

    header, stereotype_map = _load_stereotype_map(repo_root)
    sprite_map = _load_sprite_map(repo_root)

    clean_header = _strip_puml_comments(header)
    parts: list[str] = [clean_header] if clean_header else []
    for name in sorted(needed_types):
        if name in stereotype_map:
            parts.append(stereotype_map[name])
    for name in sorted(sprites_to_inject):
        if name in sprite_map:
            parts.append(sprite_map[name])

    replacement = "\n".join(parts) + "\n"
    result = body.replace("!include ../_archimate-stereotypes.puml\n", replacement, 1)
    return result.replace("!include ../_archimate-glyphs.puml\n", "")


def _load_sprite_map(repo_root: Path) -> dict[str, str]:
    """Return {sprite_key: full_sprite_line} from _archimate-glyphs.puml.

    Sprite keys use snake_case (e.g. ``stakeholder``, ``system_software``).
    """
    glyphs_path = repo_root / "diagram-catalog" / "_archimate-glyphs.puml"
    sprites: dict[str, str] = {}
    try:
        for line in glyphs_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("sprite $archimate_"):
                match = re.match(r"sprite \$archimate_(\w+)", line)
                if match:
                    sprites[match.group(1)] = line
    except OSError:
        pass
    return sprites


def _load_stereotype_map(repo_root: Path) -> tuple[str, dict[str, str]]:
    stereo_path = repo_root / "diagram-catalog" / "_archimate-stereotypes.puml"
    try:
        content = stereo_path.read_text(encoding="utf-8")
    except OSError:
        return "", {}
    first = content.find("skinparam rectangle<<")
    if first == -1:
        return content, {}
    header = content[:first].rstrip("\n") + "\n"
    blocks: dict[str, str] = {}
    for match in re.finditer(r"(skinparam rectangle<<(\w+)>>\s*\{[^}]+\})", content[first:]):
        blocks[match.group(2)] = match.group(1)
    return header, blocks


def _strip_puml_comments(text: str) -> str:
    lines = [line for line in text.splitlines() if not line.lstrip().startswith("'")]
    return "\n".join(lines).strip("\n")
