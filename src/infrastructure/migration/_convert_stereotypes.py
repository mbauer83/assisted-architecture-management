"""Helper script: convert PascalCase element stereotypes/sprites to snake_case in PUML files."""

from __future__ import annotations

from pathlib import Path

PASCAL_TO_SNAKE: dict[str, str] = {
    "Stakeholder": "stakeholder",
    "Driver": "driver",
    "Assessment": "assessment",
    "Goal": "goal",
    "Outcome": "outcome",
    "Principle": "principle",
    "Requirement": "requirement",
    "Measure": "measure",
    "Value": "value",
    "Capability": "capability",
    "ValueStream": "value_stream",
    "Resource": "resource",
    "CourseOfAction": "course_of_action",
    "Service": "service",
    "Process": "process",
    "Function": "function",
    "Event": "event",
    "Role": "role",
    "Path": "path",
    "AndJunction": "and_junction",
    "OrJunction": "or_junction",
    "Actor": "actor",
    "BusinessActor": "business_actor",
    "BusinessInterface": "business_interface",
    "BusinessObject": "business_object",
    "Product": "product",
    "ApplicationComponent": "application_component",
    "ApplicationInterface": "application_interface",
    "DataObject": "data_object",
    "Node": "node",
    "Device": "device",
    "SystemSoftware": "system_software",
    "TechnologyInterface": "technology_interface",
    "Network": "network",
    "Artifact": "artifact",
    "Equipment": "equipment",
    "Facility": "facility",
    "DistributionNetwork": "distribution_network",
    "Material": "material",
    "WorkPackage": "work_package",
    "Deliverable": "deliverable",
    "Plateau": "plateau",
    "Influence": "influence",
}


def convert_text(text: str) -> tuple[str, int]:
    changes = 0
    for old, new in PASCAL_TO_SNAKE.items():
        substitutions = [
            (f"<<{old}>>", f"<<{new}>>"),
            (f"$archimate_{old}{{", f"$archimate_{new}{{"),
            (f"$archimate_{old}>", f"$archimate_{new}>"),
            (f"$archimate_{old} <", f"$archimate_{new} <"),
            (f"$archimate_{old})", f"$archimate_{new})"),
            (f"sprite $archimate_{old}", f"sprite $archimate_{new}"),
            (f"skinparam rectangle<<{old}>>", f"skinparam rectangle<<{new}>>"),
        ]
        for old_s, new_s in substitutions:
            if old_s in text:
                text = text.replace(old_s, new_s)
                changes += 1
    return text, changes


def convert_repos(*repo_roots: Path) -> None:
    total = 0
    for repo in repo_roots:
        catalog = repo / "diagram-catalog"
        if not catalog.is_dir():
            continue
        for puml in sorted(catalog.rglob("*.puml")):
            text = puml.read_text(encoding="utf-8")
            new_text, n = convert_text(text)
            if n > 0:
                puml.write_text(new_text, encoding="utf-8")
                print(f"  updated {n} pattern(s): {puml.relative_to(repo)}")
                total += 1
    print(f"Total files updated: {total}")


if __name__ == "__main__":
    import sys
    workspace = Path.cwd()
    paths = [Path(a).resolve() for a in sys.argv[1:]] if sys.argv[1:] else [
        workspace / "enterprise-repository",
        *(workspace.glob("engagements/*/architecture-repository")),
    ]
    convert_repos(*paths)
