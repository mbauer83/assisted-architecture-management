"""Compose an isolated persona brief from the canonical catalog — allowlist-based.

The ONLY sanctioned way to build a persona brief: copies exclusively the
persona-visible fields, so the evaluator's answer-key material (candidate_routes,
fit_kind, preconditions, expected_catalog_action) can never leak into a persona
context by manual-composition mistake. Guarded by tests/tools/test_usability_helpers.py.

Usage:
  python tools/usability_test/compose_persona_brief.py PERSONA_ID \
      [--catalog spec/personas/personas.yaml] [--json]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

PERSONA_FIELDS: tuple[str, ...] = (
    "name", "segment", "capabilities", "resources", "cognitive_profile",
    "focus", "strategies", "budgets",
)
QUESTION_FIELDS: tuple[str, ...] = ("id", "text", "information_need", "decision_artifact")
CHALLENGE_FIELDS: tuple[str, ...] = ("id", "text")


def compose_brief(catalog: dict[str, Any], persona_id: str) -> dict[str, Any]:
    """Persona-visible projection of one catalog entry; raises on unknown id."""
    persona = next((p for p in catalog["personas"] if p["id"] == persona_id), None)
    if persona is None:
        raise SystemExit(f"unknown persona id {persona_id!r}")
    brief: dict[str, Any] = {field: persona[field] for field in PERSONA_FIELDS}
    brief["questions"] = [
        {field: question[field] for field in QUESTION_FIELDS} for question in persona["questions"]
    ]
    brief["authoring_challenge"] = {
        field: persona["authoring_challenge"][field] for field in CHALLENGE_FIELDS
    }
    return brief


def render_markdown(persona_id: str, brief: dict[str, Any]) -> str:
    lines = [f"# Persona brief: {brief['name']} ({persona_id})", ""]
    for field in PERSONA_FIELDS:
        if field == "budgets":
            budgets = brief[field]
            lines.append(
                f"- **action budgets**: {budgets['max_task_actions']} per question task, "
                f"{budgets['max_authoring_actions']} for the authoring challenge "
                "(one action = click / submitted text / selection / navigation / tab switch; "
                "when the budget is exhausted you abandon and say why)"
            )
        elif field != "name":
            lines.append(f"- **{field}**: {brief[field]}")
    lines.append("\n## Your questions\n")
    for question in brief["questions"]:
        lines.append(f"### {question['id']}: {question['text']}")
        lines.append(f"- What counts as answered: {question['information_need']}")
        lines.append(f"- The answer must feed a: {question['decision_artifact']}\n")
    challenge = brief["authoring_challenge"]
    lines.append(f"## Authoring challenge {challenge['id']}\n\n{challenge['text']}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("persona_id")
    parser.add_argument("--catalog", default="spec/personas/personas.yaml")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of markdown")
    args = parser.parse_args()

    catalog: Any = yaml.safe_load(Path(args.catalog).read_text(encoding="utf-8"))
    brief = compose_brief(catalog, args.persona_id)
    print(json.dumps(brief, indent=2) if args.json else render_markdown(args.persona_id, brief))


if __name__ == "__main__":
    main()
