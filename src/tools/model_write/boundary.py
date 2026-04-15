
from datetime import date
from pathlib import Path


def today_iso() -> str:
    return date.today().isoformat()


def assert_engagement_write_root(repo_root: Path) -> None:
    """Reject writes to the enterprise repository root."""
    p = repo_root.resolve()
    if "enterprise-repository" in p.parts:
        raise ValueError(
            "Refusing to write to enterprise repository. "
            "Point repo_root at an engagement repository."
        )


def engagement_id_from_repo_root(repo_root: Path) -> str:
    # engagements/<id>/work-repositories/<repo>/
    parts = repo_root.resolve().parts
    if "engagements" in parts:
        idx = parts.index("engagements")
        if idx + 1 < len(parts):
            return parts[idx + 1]
    return "ENG-UNKNOWN"
