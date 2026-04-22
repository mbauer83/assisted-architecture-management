
from datetime import date
from pathlib import Path

from src.common.workspace_paths import infer_repo_scope


def today_iso() -> str:
    return date.today().isoformat()


def assert_engagement_write_root(repo_root: Path) -> None:
    """Reject writes to the enterprise repository root.

    This guard is called unconditionally by all standard MCP write tools and
    normal GUI write endpoints.  It is intentionally not bypassable via any
    argument — admin-mode GUI writes use a separate code path that calls
    assert_enterprise_write_root instead.
    """
    p = repo_root.resolve()
    if infer_repo_scope(p) == "enterprise":
        raise ValueError(
            "Refusing to write to enterprise repository. "
            "Point repo_root at an engagement repository."
        )


def assert_enterprise_write_root(repo_root: Path) -> None:
    """Accept only the enterprise repository root — for admin-mode GUI writes."""
    p = repo_root.resolve()
    if infer_repo_scope(p) != "enterprise":
        raise ValueError(
            "Admin write expected enterprise repository root, got: "
            f"{p}"
        )


def engagement_id_from_repo_root(repo_root: Path) -> str:
    # engagements/<id>/work-repositories/<repo>/
    parts = repo_root.resolve().parts
    if "engagements" in parts:
        idx = parts.index("engagements")
        if idx + 1 < len(parts):
            return parts[idx + 1]
    return "ENG-UNKNOWN"
