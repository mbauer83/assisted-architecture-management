from __future__ import annotations

import re
from functools import lru_cache


@lru_cache(maxsize=1)
def _registry():
    from src.infrastructure.app_bootstrap import get_module_registry  # noqa: PLC0415

    return get_module_registry()


def display_connection_label(conn_type: str) -> str:
    return conn_type.removeprefix("archimate-")


def suppressed_stereotype_tokens() -> frozenset[str]:
    """Stereotype label tokens whose relation type is fully conveyed by its arrow.

    A connection type with ``show_stereotype == False`` declares a distinctive
    ``puml_arrow``; the arrow alone identifies the relation, so an explicit
    ``<<token>>`` edge label is redundant. The token is the label form the
    renderer would emit, i.e. ``display_connection_label(conn_type)``.
    """
    reg = _registry()
    return frozenset(
        display_connection_label(str(name)).lower()
        for name, info in reg.all_connection_types().items()
        if not info.show_stereotype
    )


_STEREOTYPE_TOKEN_RE = re.compile(r"<<\s*([A-Za-z][A-Za-z0-9_-]*)\s*>>")
_EDGE_LABEL_RE = re.compile(r"^(?P<head>.*?)(?P<sep>\s*:\s*)(?P<label>\S.*?)\s*$")


def strip_suppressed_relation_labels(body: str) -> str:
    """Remove redundant ``: <<reltype>>`` edge labels from an authored PUML body.

    Mirrors the auto-renderer rule (``show_stereotype``): a stereotype label is
    dropped only when the arrow style already encodes the relation. Labels for
    relation types without a distinctive arrow (``show_stereotype == True`` —
    e.g. sequence/activity/ER/use-case flows) and free-text/cardinality labels
    are left untouched.
    """
    suppressed = suppressed_stereotype_tokens()
    if not suppressed:
        return body
    out: list[str] = []
    for line in body.split("\n"):
        match = _EDGE_LABEL_RE.match(line)
        if match and "<<" in match.group("label"):
            def _drop(token: re.Match[str]) -> str:
                return "" if token.group(1).lower() in suppressed else token.group(0)

            new_label = _STEREOTYPE_TOKEN_RE.sub(_drop, match.group("label")).strip()
            if new_label != match.group("label"):
                head = match.group("head")
                line = head if not new_label else f"{head}{match.group('sep')}{new_label}"
        out.append(line)
    return "\n".join(out)


def format_cardinality_label(src_cardinality: str, tgt_cardinality: str) -> str:
    """Return a compact cardinality label for a connection, or '' when neither end is set."""
    has_src = bool(src_cardinality)
    has_tgt = bool(tgt_cardinality)
    if has_src and has_tgt:
        return f"{src_cardinality} -> {tgt_cardinality}"
    if has_src:
        return f"{src_cardinality} ->"
    if has_tgt:
        return f"-> {tgt_cardinality}"
    return ""
