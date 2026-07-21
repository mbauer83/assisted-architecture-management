"""Security-signals schema: versioned DDL shared by the runtime stores and the
operational upgrade step.

Version 1 is the empty baseline (a fresh store carries no signal tables until a
migration runs). Version 2 creates the refresh-run aggregate — the sole signals
model. The list is append-only — never edit a shipped entry; add a new version.
"""

from __future__ import annotations

# Connection PRAGMAs applied on every signals-store open: WAL durability and FK
# enforcement. Kept separate from the table DDL so opening a store never depends on
# any particular table definition.
SIGNALS_PRAGMAS_SQL = """
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA foreign_keys = ON;
"""

_REFRESH_RUN_DDL = """
CREATE TABLE IF NOT EXISTS security_refresh_runs (
    run_id                 TEXT PRIMARY KEY,
    anchor_entity_id       TEXT NOT NULL,
    request_id             TEXT NOT NULL,
    request_payload_digest TEXT NOT NULL,
    bom_digest             TEXT NOT NULL DEFAULT '',
    bom_serial             TEXT,
    bom_version            TEXT,
    generator_metadata     TEXT NOT NULL DEFAULT '{}',
    source_metadata        TEXT NOT NULL DEFAULT '{}',
    diagnostics            TEXT NOT NULL DEFAULT '{}',
    status                 TEXT NOT NULL,
    started_at             TEXT NOT NULL,
    completed_at           TEXT,
    activated_at           TEXT,
    superseded_at          TEXT,
    failed_at              TEXT,
    failure_reason         TEXT,
    tlp                    TEXT NOT NULL DEFAULT 'TLP:AMBER',
    UNIQUE (anchor_entity_id, request_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_one_active_run_per_anchor
    ON security_refresh_runs(anchor_entity_id) WHERE status = 'active';

CREATE INDEX IF NOT EXISTS idx_runs_anchor_status
    ON security_refresh_runs(anchor_entity_id, status);

CREATE TABLE IF NOT EXISTS run_components (
    component_id        TEXT PRIMARY KEY,
    run_id              TEXT NOT NULL,
    source_component_id TEXT NOT NULL DEFAULT '',
    bom_ref             TEXT NOT NULL DEFAULT '',
    purl           TEXT,
    cpe            TEXT,
    name           TEXT NOT NULL,
    version        TEXT,
    component_type TEXT,
    group_name     TEXT,
    directness     TEXT NOT NULL DEFAULT 'unknown',
    tlp            TEXT NOT NULL DEFAULT 'TLP:AMBER',
    FOREIGN KEY (run_id) REFERENCES security_refresh_runs(run_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_run_components_run ON run_components(run_id);

CREATE UNIQUE INDEX IF NOT EXISTS idx_run_components_source
    ON run_components(run_id, source_component_id);

CREATE TABLE IF NOT EXISTS canonical_vulnerabilities (
    canonical_id TEXT PRIMARY KEY,
    created_at   TEXT NOT NULL,
    merged_into  TEXT
);

CREATE TABLE IF NOT EXISTS vulnerability_aliases (
    alias        TEXT PRIMARY KEY,
    canonical_id TEXT NOT NULL,
    source       TEXT NOT NULL DEFAULT '',
    created_at   TEXT NOT NULL,
    FOREIGN KEY (canonical_id) REFERENCES canonical_vulnerabilities(canonical_id)
);

CREATE INDEX IF NOT EXISTS idx_aliases_canonical ON vulnerability_aliases(canonical_id);

CREATE TABLE IF NOT EXISTS run_vulnerability_findings (
    finding_id                 TEXT PRIMARY KEY,
    run_id                     TEXT NOT NULL,
    component_id               TEXT NOT NULL,
    canonical_vulnerability_id TEXT NOT NULL,
    severity_band              TEXT,
    cvss_score                 REAL,
    cvss_vector                TEXT,
    severity_source            TEXT,
    applicability              TEXT NOT NULL DEFAULT 'applicable',
    provenance                 TEXT NOT NULL DEFAULT '{}',
    tlp                        TEXT NOT NULL DEFAULT 'TLP:AMBER',
    UNIQUE (run_id, component_id, canonical_vulnerability_id),
    FOREIGN KEY (run_id) REFERENCES security_refresh_runs(run_id) ON DELETE CASCADE,
    FOREIGN KEY (component_id) REFERENCES run_components(component_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_findings_run ON run_vulnerability_findings(run_id);

CREATE TABLE IF NOT EXISTS vex_assessments (
    assessment_id              TEXT PRIMARY KEY,
    anchor_entity_id           TEXT NOT NULL,
    canonical_component_id     TEXT NOT NULL,
    canonical_vulnerability_id TEXT NOT NULL,
    revision                   INTEGER NOT NULL,
    disposition                TEXT NOT NULL,
    justification              TEXT NOT NULL DEFAULT '',
    author                     TEXT NOT NULL,
    source                     TEXT NOT NULL DEFAULT '',
    created_at                 TEXT NOT NULL,
    tlp                        TEXT NOT NULL DEFAULT 'TLP:AMBER',
    UNIQUE (anchor_entity_id, canonical_component_id, canonical_vulnerability_id, revision)
);

CREATE INDEX IF NOT EXISTS idx_vex_key
    ON vex_assessments(anchor_entity_id, canonical_component_id, canonical_vulnerability_id);
"""

SIGNALS_MIGRATIONS: list[tuple[int, str]] = [
    (2, _REFRESH_RUN_DDL),
]

SIGNALS_SCHEMA_VERSION = 2
_LEGACY_BASELINE_VERSION = 1



def signals_migration_statements(ddl: str) -> list[str]:
    return [stmt.strip() for stmt in ddl.split(";") if stmt.strip()]
