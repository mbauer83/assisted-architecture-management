"""Operational migration: bring a security-signals database to the refresh-run
schema (versioned ``signals_schema_meta`` + the run aggregate tables).

The refresh-run aggregate is the sole signals model; metrics read only the
active run. The public SQLite backend is deprecated for metrics but its schema
is kept current for queryability."""

from __future__ import annotations

from src.application.deployment_upgrade.ports import (
    OperationalTargetUnitOfWork,
    OperationalTargetView,
)
from src.domain.operational_upgrade import TargetKind
from src.domain.repository_upgrade import AppliedFinding, UpgradeFinding
from src.domain.signals_schema import (
    SIGNALS_MIGRATIONS,
    SIGNALS_SCHEMA_VERSION,
    signals_migration_statements,
)


def _table_exists(view: OperationalTargetView, table: str) -> bool:
    value = view.query_scalar(
        "SELECT count(*) FROM sqlite_master WHERE type='table' AND name=?", (table,)
    )
    return bool(int(value)) if isinstance(value, (int, float, str)) else False


def _current_version(view: OperationalTargetView) -> int:
    if not _table_exists(view, "signals_schema_meta"):
        return 1
    value = view.query_scalar(
        "SELECT value FROM signals_schema_meta WHERE key='schema_version'"
    )
    return int(value) if isinstance(value, (int, float, str)) else 1


class _SignalsRefreshRunSchemaStep:
    id = "signals-0002-refresh-run-schema"
    version = 1
    kind: TargetKind = "assurance_sqlcipher"
    description = "Versioned refresh-run schema for security signals"

    def detect(self, view: OperationalTargetView) -> list[UpgradeFinding]:
        findings: list[UpgradeFinding] = []
        location = view.target.display_location
        current = _current_version(view)
        if current < SIGNALS_SCHEMA_VERSION:
            findings.append(UpgradeFinding(
                step_id=self.id,
                finding_id="signals-schema-outdated",
                location=location,
                description=(
                    f"security-signals schema is at version {current}; "
                    f"version {SIGNALS_SCHEMA_VERSION} adds the refresh-run aggregate"
                ),
                severity="warning",
                auto_migratable=True,
                rewrite_summary="apply the ordered signals migrations (refresh-run tables + version stamp)",
            ))
        return findings

    def apply(
        self,
        view: OperationalTargetView,
        uow: OperationalTargetUnitOfWork,
        findings: list[UpgradeFinding],
    ) -> list[AppliedFinding]:
        schema_finding = next(
            (f for f in findings if f.finding_id == "signals-schema-outdated"), None,
        )
        if schema_finding is None:
            return []
        uow.execute_sql(
            "CREATE TABLE IF NOT EXISTS signals_schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        current = _current_version(view)
        for version, ddl in SIGNALS_MIGRATIONS:
            if version <= current:
                continue
            for statement in signals_migration_statements(ddl):
                uow.execute_sql(statement)
            uow.execute_sql(
                "INSERT OR REPLACE INTO signals_schema_meta(key, value) VALUES ('schema_version', ?)",
                (str(version),),
            )
        return [AppliedFinding(
            finding=schema_finding,
            outcome="applied",
            detail=f"migrated signals schema to version {SIGNALS_SCHEMA_VERSION}",
        )]



class SignalsRefreshRunSchemaStep(_SignalsRefreshRunSchemaStep):
    """Co-located SQLCipher signals (the metrics-capable backend)."""

    id = "signals-0002-refresh-run-schema"
    kind: TargetKind = "assurance_sqlcipher"


class PublicSqliteSignalsSchemaStep(_SignalsRefreshRunSchemaStep):
    """Public SQLite signals file — schema kept current for queryability even
    though the backend is deprecated for metrics."""

    id = "signals-0002-refresh-run-schema-public"
    kind: TargetKind = "signals_sqlite"
