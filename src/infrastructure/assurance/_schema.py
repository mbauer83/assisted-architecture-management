"""SQLCipher DDL for the confidential assurance store.

Applied at store initialisation and on each unlock (idempotent — IF NOT EXISTS).
"""

ASSURANCE_SCHEMA_SQL = """
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS assurance_analyses (
    analysis_id            TEXT PRIMARY KEY,
    name                   TEXT NOT NULL,
    method                 TEXT NOT NULL,
    architecture_anchor_id TEXT NOT NULL DEFAULT '',
    status                 TEXT NOT NULL DEFAULT 'draft',
    tlp                    TEXT NOT NULL DEFAULT 'TLP:WHITE',
    created_at             TEXT NOT NULL,
    updated_at             TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS assurance_nodes (
    node_id         TEXT PRIMARY KEY,
    node_type       TEXT NOT NULL,
    name            TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'draft',
    tlp             TEXT NOT NULL DEFAULT 'TLP:WHITE',
    concern_class   TEXT,
    disposition     TEXT,
    uca_type        TEXT,
    binding_status  TEXT,
    node_role       TEXT,
    analysis_id     TEXT,
    attributes_json TEXT NOT NULL DEFAULT '{}',
    content_text    TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    created_by      TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS assurance_edges (
    edge_id         TEXT PRIMARY KEY,
    source_id       TEXT NOT NULL,
    target_id       TEXT NOT NULL,
    conn_type       TEXT NOT NULL,
    attributes_json TEXT NOT NULL DEFAULT '{}',
    created_at      TEXT NOT NULL,
    FOREIGN KEY (source_id) REFERENCES assurance_nodes(node_id) ON DELETE CASCADE,
    FOREIGN KEY (target_id) REFERENCES assurance_nodes(node_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS arch_refs (
    assurance_node_id TEXT NOT NULL,
    arch_artifact_id  TEXT NOT NULL,
    ref_type          TEXT NOT NULL,
    resolved_at       TEXT,
    PRIMARY KEY (assurance_node_id, arch_artifact_id, ref_type)
);

CREATE TABLE IF NOT EXISTS audit_log (
    seq          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp    TEXT NOT NULL,
    operation    TEXT NOT NULL,
    node_id      TEXT,
    payload_json TEXT NOT NULL DEFAULT '{}',
    prev_hash    TEXT NOT NULL DEFAULT '',
    entry_hash   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS baselines (
    baseline_id TEXT PRIMARY KEY,
    created_at  TEXT NOT NULL,
    head_seq    INTEGER NOT NULL,
    head_hash   TEXT NOT NULL,
    notes       TEXT NOT NULL DEFAULT '',
    analysis_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_nodes_type     ON assurance_nodes(node_type);
CREATE INDEX IF NOT EXISTS idx_nodes_status   ON assurance_nodes(status);
CREATE INDEX IF NOT EXISTS idx_nodes_cc       ON assurance_nodes(concern_class);
CREATE INDEX IF NOT EXISTS idx_analyses_method ON assurance_analyses(method);
CREATE INDEX IF NOT EXISTS idx_analyses_status ON assurance_analyses(status);
CREATE INDEX IF NOT EXISTS idx_edges_source   ON assurance_edges(source_id);
CREATE INDEX IF NOT EXISTS idx_edges_target   ON assurance_edges(target_id);
CREATE INDEX IF NOT EXISTS idx_edges_type     ON assurance_edges(conn_type);
CREATE INDEX IF NOT EXISTS idx_refs_arch      ON arch_refs(arch_artifact_id);
CREATE INDEX IF NOT EXISTS idx_audit_seq      ON audit_log(seq);
CREATE INDEX IF NOT EXISTS idx_audit_op       ON audit_log(operation);

CREATE TABLE IF NOT EXISTS dek_store (
    subject_id  TEXT PRIMARY KEY,
    dek_hex     TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    shredded_at TEXT
);

CREATE TABLE IF NOT EXISTS legal_holds (
    hold_id     TEXT PRIMARY KEY,
    baseline_id TEXT NOT NULL,
    held_by     TEXT NOT NULL DEFAULT '',
    reason      TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL,
    released_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_holds_baseline ON legal_holds(baseline_id);
"""

# Applied once after executescript to add columns to existing tables.
# Each entry is executed and OperationalError (duplicate column) is silently ignored.
# Column-adding ALTERs must precede any index that references the new column,
# because the main schema script (which only has IF NOT EXISTS guards) runs first.
ASSURANCE_SCHEMA_MIGRATIONS: list[str] = [
    "ALTER TABLE baselines ADD COLUMN timestamp_token_hex TEXT",
    "ALTER TABLE assurance_nodes ADD COLUMN analysis_id TEXT",
    "CREATE INDEX IF NOT EXISTS idx_nodes_an_type ON assurance_nodes(analysis_id, node_type, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_nodes_an_status ON assurance_nodes(analysis_id, status)",
]

SCHEMA_VERSION = "3"

# Archive-only schema — used when the archive needs a separate local SQLite file
# (non-SQLCipher store backends: pocketbase, private-git).
ARCHIVE_ONLY_SCHEMA_SQL = """
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;

CREATE TABLE IF NOT EXISTS audit_log (
    seq          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp    TEXT NOT NULL,
    operation    TEXT NOT NULL,
    node_id      TEXT,
    payload_json TEXT NOT NULL DEFAULT '{}',
    prev_hash    TEXT NOT NULL DEFAULT '',
    entry_hash   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS baselines (
    baseline_id TEXT PRIMARY KEY,
    created_at  TEXT NOT NULL,
    head_seq    INTEGER NOT NULL,
    head_hash   TEXT NOT NULL,
    notes       TEXT NOT NULL DEFAULT '',
    analysis_id TEXT,
    timestamp_token_hex TEXT
);

CREATE INDEX IF NOT EXISTS idx_audit_seq ON audit_log(seq);
CREATE INDEX IF NOT EXISTS idx_audit_op  ON audit_log(operation);
"""
