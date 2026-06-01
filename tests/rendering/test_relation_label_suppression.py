"""Authored PUML bodies should drop relation-stereotype labels the arrow encodes.

Mirrors the auto-renderer rule (``show_stereotype``): labels are stripped only
for relation types with a distinctive arrow; UML-family flows that share the
generic arrow keep their disambiguating labels.
"""

from __future__ import annotations

from src.domain.archimate_relation_rendering import (
    strip_suppressed_relation_labels,
    suppressed_stereotype_tokens,
)


def test_archimate_relation_stereotypes_are_suppressed() -> None:
    tokens = suppressed_stereotype_tokens()
    assert {"influence", "realization", "association", "serving"} <= tokens


def test_strips_redundant_influence_and_realization_labels() -> None:
    body = (
        "DRV_GR9prv ..> ASS_CK90bp : <<influence>>\n"
        "OUT_AlZjX8 -up-|> GOL_5Fk9di : <<realization>>\n"
    )
    out = strip_suppressed_relation_labels(body)
    assert out == "DRV_GR9prv ..> ASS_CK90bp\nOUT_AlZjX8 -up-|> GOL_5Fk9di\n"


def test_keeps_association_and_cardinality_and_element_lines() -> None:
    for line in (
        "ASS_CK90bp -- GOL_FCfDuc",
        "A --> B : 1 -> *",
        'rectangle "X" <<driver>> as DRV_x',
        "title Motivation Chain: From Drivers to Requirements",
    ):
        assert strip_suppressed_relation_labels(line) == line


def test_keeps_uml_family_labels_without_distinctive_arrow() -> None:
    # sequence/activity/er/usecase flows share the generic arrow → label is load-bearing.
    line = "A --> B : <<sequence-synchronous>>"
    assert strip_suppressed_relation_labels(line) == line


def test_strips_only_the_stereotype_keeping_free_text() -> None:
    line = "A ..> B : <<influence>> needs review"
    assert strip_suppressed_relation_labels(line) == "A ..> B : needs review"
