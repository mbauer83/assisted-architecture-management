"""
SDLC Multi-Agent System — domain vocabulary for search and NLP.

Provides the canonical bidirectional synonym map used by:
  - ``ModelRepository.search`` / ``search_artifacts`` (keyword expansion)
  - ``LearningStore.query_learnings`` (optional synonym expansion in Stage 5b)
  - Any future NLP pipeline operating on framework artifact text

Keeping this here (not inside model_query.py or archimate_types.py) allows
all search/query components to share a single maintained vocabulary without
circular imports.

Coverage
--------
Three semantic domains are covered:

1. **Agent abbreviations ↔ expanded role titles**
   PM ↔ "project manager", SA ↔ "solution architect", etc.

2. **Protocol / concept abbreviations ↔ expanded terms**
   CQ ↔ "clarification request/question", ALG ↔ "algedonic", ADM ↔ "TOGAF phases", etc.

3. **ArchiMate artifact-id prefix ↔ element type**
   APP ↔ "application component", etc.
   Also common domain concepts → related terms for improved recall.

Usage
-----
Import ``expand_tokens`` for the one-hop expansion used in scoring::

    from src.common.domain_vocabulary import expand_tokens, DOMAIN_SYNONYMS

    expanded = expand_tokens(["pm", "decision"])
    # → ["pm", "decision", "project", "manager", "orchestration", ...]
"""


# ---------------------------------------------------------------------------
# Primary synonym map  (key → list of expansion terms, all lowercase)
# ---------------------------------------------------------------------------
# Keys are the "short" or "abbreviation" form.  Values are the expanded terms.
# The reverse index is built automatically below so lookups are bidirectional.

DOMAIN_SYNONYMS: dict[str, list[str]] = {

    # -----------------------------------------------------------------------
    # Common domain concepts ↔ related terms (improves recall for natural-language queries)
    # -----------------------------------------------------------------------
    "policy":     ["rule", "constraint", "principle", "governance"],
    "trace":      ["traceability", "link", "reference", "dependency"],
    "diagram":    ["puml", "visualization", "view", "model"],
    "entity":     ["artifact", "model", "element", "instance"],
    "connection": ["relation", "link", "edge", "association", "realization"],
}

# ---------------------------------------------------------------------------
# Auto-built reverse index  (expansion term → list of abbreviation keys)
# ---------------------------------------------------------------------------
REVERSE_SYNONYMS: dict[str, list[str]] = {}
for _key, _vals in DOMAIN_SYNONYMS.items():
    for _val in _vals:
        REVERSE_SYNONYMS.setdefault(_val, []).append(_key)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def expand_tokens(tokens: list[str]) -> list[str]:
    """Return *tokens* plus one-hop synonym expansion (order preserved, no duplicates).

    Both directions are followed: ``"pm"`` expands to ``["project", "manager", …]``
    and ``"manager"`` expands to include ``"pm"`` (via the reverse index).

    This gives significantly better recall for natural-language discovery queries
    against a corpus that uses both formal abbreviations (``PM Agent``) and
    descriptive prose (``"the project manager coordinates specialist agents"``).

    Parameters
    ----------
    tokens:
        Lowercased tokens from a query (output of :func:`tokenize_query`).

    Returns
    -------
    list[str]
        Original tokens followed by expansion terms, deduplicated.

    Examples
    --------
    >>> expand_tokens(["pm", "decision"])
    ['pm', 'decision', 'project', 'manager', 'orchestration', 'coordinator', 'supervisor']
    """
    seen: set[str] = set(tokens)
    expanded: list[str] = list(tokens)
    for tok in tokens:
        for syn in DOMAIN_SYNONYMS.get(tok, []):
            if syn not in seen:
                expanded.append(syn)
                seen.add(syn)
        for syn in REVERSE_SYNONYMS.get(tok, []):
            if syn not in seen:
                expanded.append(syn)
                seen.add(syn)
    return expanded

def archimate_prefix_to_type() -> dict[str, str]:
    """Return the canonical mapping of artifact-id prefix → ArchiMate element type.

    Used for display, reporting, and filter-hint generation.
    """
    return {
        "STK": "stakeholder",
        "DRV": "driver",
        "ASS": "assessment",
        "GOL": "goal",
        "OUT": "outcome",
        "PRI": "principle",
        "REQ": "requirement",
        "MEA": "meaning",
        "VAL": "value",
        "CAP": "capability",
        "VS":  "value-stream",
        "RES": "resource",
        "COA": "course-of-action",
        "ACT": "business-actor",
        "ROL": "role",
        "PRC": "process",
        "FNC": "function",
        "CLB": "collaboration",
        "SRV": "service",
        "EVT": "event",
        "BOB": "business-object",
        "BIF": "business-interface",
        "PRD": "product",
        "APP": "application-component",
        "AIF": "application-interface",
        "DOB": "data-object",
        "NOD": "node",
        "DEV": "device",
        "SSW": "system-software",
        "TSV": "technology-service",
        "ART": "artifact",
        "NET": "network",
        "TIF": "technology-interface",
        "WP":  "work-package",
        "DEL": "deliverable",
        "PLT": "plateau",
    }
