"""Confidentiality routing for assurance diagram sources.

Rule G-f keeps *rendered* assurance images off disk. The same confidentiality boundary must
cover the diagram *source*: an assurance diagram whose classification is above the
publishability ceiling carries sensitive analysis content (bowtie/GSN/UCA node labels) in its
frontmatter and PUML body, so its `.puml` must not land in the git-tracked catalog.

Confidentiality is driven by the TLP classification (see ``src.domain.classification``), not a
blanket per-type flag: an assurance diagram explicitly classified TLP:WHITE/GREEN is
publishable (renders and persists to the catalog like any diagram — this is what lets the
self-describing model ship a public assurance example), while anything above that, or
unclassified, is confidential and is redirected to a gitignored location.
"""

from __future__ import annotations

from pathlib import Path

from src.domain.classification import is_publishable


def is_assurance_diagram_type(diagram_type: str) -> bool:
    """True if *diagram_type* belongs to the assurance module (module_class == 'assurance')."""
    try:
        from src.infrastructure.diagram_type_registry import find_diagram_type  # noqa: PLC0415

        dt = find_diagram_type(diagram_type)
    except (ImportError, AttributeError, TypeError):
        return False
    return dt is not None and getattr(dt, "module_class", None) == "assurance"


def is_confidential_diagram_source(diagram_type: str, tlp: str | None) -> bool:
    """True if this diagram's source must be kept out of the shared catalog.

    Only assurance diagram types are gated; for those, an unclassified or above-ceiling TLP is
    confidential (conservative default), while a publishable TLP (<= GREEN) is not.
    """
    return is_assurance_diagram_type(diagram_type) and not is_publishable(tlp)


def ensure_confidential_gitignore(confidential_root: Path) -> None:
    """Write a self-contained ``.gitignore`` so the confidential dir's contents never reach git.

    A ``*`` ignore travels with the directory regardless of which git repo encloses the
    engagement, protecting the authoring machine from accidentally committing confidential
    diagram sources. Idempotent.
    """
    confidential_root.mkdir(parents=True, exist_ok=True)
    gitignore = confidential_root / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("# Confidential assurance diagram sources — never commit.\n*\n", encoding="utf-8")
