"""SQLCipher persistence for the assurance analysis aggregate.

Free functions over an open sqlcipher3 connection; the store adapter delegates
its analysis CRUD here to stay focused and within the per-file size budget.
"""

from __future__ import annotations

from typing import Any

from src.infrastructure.assurance import _analysis_records as analyses
from src.infrastructure.assurance._sqlcipher_util import now_iso, where


def create(
    conn: Any,
    name: str,
    method: str,
    architecture_anchor_id: str = "",
    *,
    tlp: str,
    status: str,
) -> str:
    rec = analyses.new_analysis_record(name, method, architecture_anchor_id, tlp=tlp, status=status)
    conn.execute(
        "INSERT INTO assurance_analyses "
        "(analysis_id, name, method, architecture_anchor_id, status, tlp, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            rec["analysis_id"], rec["name"], rec["method"], rec["architecture_anchor_id"],
            rec["status"], rec["tlp"], rec["created_at"], rec["updated_at"],
        ),
    )
    conn.commit()
    return str(rec["analysis_id"])


def get(conn: Any, analysis_id: str) -> dict[str, object] | None:
    row = conn.execute(
        "SELECT * FROM assurance_analyses WHERE analysis_id = ?", (analysis_id,)
    ).fetchone()
    return row if row else None


def list_analyses(
    conn: Any,
    *,
    method: str | None = None,
    status: str | None = None,
) -> list[dict[str, object]]:
    clause, params = where({"method": method, "status": status})
    rows = conn.execute(
        f"SELECT * FROM assurance_analyses {clause} ORDER BY created_at", params
    ).fetchall()
    return list(rows)


def delete(conn: Any, analysis_id: str) -> None:
    conn.execute("DELETE FROM assurance_analyses WHERE analysis_id = ?", (analysis_id,))
    conn.commit()


def update(conn: Any, analysis_id: str, attrs: dict[str, object]) -> None:
    sets: list[str] = ["updated_at = ?"]
    params: list[object] = [now_iso()]
    for key, value in attrs.items():
        if key in analyses.ANALYSIS_UPDATABLE:
            sets.append(f"{key} = ?")
            params.append(value)
    params.append(analysis_id)
    conn.execute(
        f"UPDATE assurance_analyses SET {', '.join(sets)} WHERE analysis_id = ?", params
    )
    conn.commit()
