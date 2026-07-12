from __future__ import annotations

import re


def display_connection_label(conn_type: str) -> str:
    return conn_type.removeprefix("archimate-")


def format_specialization_guillemet(specialization_name: str) -> str:
    """Render a specialization's display name as a guillemet stereotype, e.g. ``«Business
    Service»`` — visually distinct from the ``<<connection-type>>`` ASCII-bracket
    stereotype used for relationship types, so a reader can tell them apart at a glance."""
    return f"«{specialization_name}»"


_STEREOTYPE_TOKEN_RE = re.compile(r"<<\s*([A-Za-z][A-Za-z0-9_-]*)\s*>>")
_EDGE_LABEL_RE = re.compile(r"^(?P<head>.*?)(?P<sep>\s*:\s*)(?P<label>\S.*?)\s*$")


def strip_suppressed_relation_labels(body: str, suppressed: frozenset[str]) -> str:
    """Remove redundant ``: <<reltype>>`` edge labels from an authored PUML body.

    ``suppressed`` is the set of lower-cased display label tokens whose arrow
    style already encodes the relation (``show_stereotype == False``).
    Obtain from ``DiagramTypeCatalog.suppressed_stereotype_tokens()``.
    """
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


def format_multiplicity_label(src_multiplicity: str, tgt_multiplicity: str) -> str:
    """Return a compact multiplicity label for a connection, or '' when neither end is set."""
    has_src = bool(src_multiplicity)
    has_tgt = bool(tgt_multiplicity)
    if has_src and has_tgt:
        return f"{src_multiplicity} -> {tgt_multiplicity}"
    if has_src:
        return f"{src_multiplicity} ->"
    if has_tgt:
        return f"-> {tgt_multiplicity}"
    return ""
