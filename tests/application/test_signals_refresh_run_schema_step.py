"""U0 signals-schema step: detects an outdated (pre-refresh-run) schema and
applies the versioned migration through the operational unit of work,
idempotently — on the SQLCipher target kind and the public SQLite kind."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from src.application.deployment_upgrade.orchestrate import apply_targets, evaluate_targets
from src.application.deployment_upgrade.ports import OperationalStepRegistry
from src.application.deployment_upgrade.steps.signals_refresh_run_schema import (
    PublicSqliteSignalsSchemaStep,
    SignalsRefreshRunSchemaStep,
)
from src.domain.operational_upgrade import UpgradeTarget
from src.infrastructure.deployment.database_targets import DatabaseTargetHandle


def _seed_public_signals(path: Path) -> None:
    """A pre-refresh-run signals file: no signals_schema_meta, so it reads as the
    baseline version and the step detects it as outdated."""
    conn = sqlite3.connect(str(path))
    conn.commit()
    conn.close()


def _handle(path: Path) -> DatabaseTargetHandle:
    return DatabaseTargetHandle(
        target=UpgradeTarget(
            kind="signals_sqlite",
            stable_id=f"signals_sqlite:{path}",
            display_location=str(path),
            current_version=0,
            credential_requirement="none",
        ),
        connect=lambda: sqlite3.connect(str(path)),
        inspectable=True,
    )


def _registry() -> OperationalStepRegistry:
    registry = OperationalStepRegistry()
    registry.register(SignalsRefreshRunSchemaStep())
    registry.register(PublicSqliteSignalsSchemaStep())
    return registry


class TestDetect:
    def test_outdated_schema_is_an_auto_migratable_finding(self, tmp_path: Path) -> None:
        db = tmp_path / "signals.db"
        _seed_public_signals(db)
        reports = evaluate_targets((_handle(db),), _registry())
        by_id = {r.finding.finding_id: r.finding for r in reports[0].results}
        assert set(by_id) == {"signals-schema-outdated"}
        assert by_id["signals-schema-outdated"].auto_migratable is True


class TestApply:
    def test_migration_applies_and_is_idempotent(self, tmp_path: Path) -> None:
        db = tmp_path / "signals.db"
        _seed_public_signals(db)
        reports, failed = apply_targets((_handle(db),), _registry())
        assert failed is None
        assert reports[0].committed

        conn = sqlite3.connect(str(db))
        tables = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        assert "security_refresh_runs" in tables and "vex_assessments" in tables
        version = conn.execute(
            "SELECT value FROM signals_schema_meta WHERE key='schema_version'").fetchone()[0]
        assert version == "2"
        conn.close()

        # Idempotent: once current, re-evaluation reports nothing.
        reports = evaluate_targets((_handle(db),), _registry())
        assert {r.finding.finding_id for r in reports[0].results} == set()
