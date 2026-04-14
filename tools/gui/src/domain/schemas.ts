import { Schema } from 'effect'

// ── Stats ────────────────────────────────────────────────────────────────────

export const StatsSchema = Schema.Struct({
  entities: Schema.Number,
  connections: Schema.Number,
  diagrams: Schema.Number,
  entities_by_domain: Schema.Record({ key: Schema.String, value: Schema.Number }),
  connections_by_type: Schema.Record({ key: Schema.String, value: Schema.Number }),
})
export type Stats = typeof StatsSchema.Type

// ── Entity summary (list view) ────────────────────────────────────────────────

export const EntitySummarySchema = Schema.Struct({
  artifact_id: Schema.String,
  artifact_type: Schema.String,
  name: Schema.String,
  version: Schema.String,
  status: Schema.String,
  domain: Schema.String,
  subdomain: Schema.String,
  path: Schema.String,
})
export type EntitySummary = typeof EntitySummarySchema.Type

export const EntityListSchema = Schema.Struct({
  total: Schema.Number,
  items: Schema.Array(EntitySummarySchema),
})
export type EntityList = typeof EntityListSchema.Type

// ── Entity detail (read view) ─────────────────────────────────────────────────

export const EntityDetailSchema = Schema.Struct({
  artifact_id: Schema.String,
  artifact_type: Schema.String,
  name: Schema.String,
  version: Schema.String,
  status: Schema.String,
  domain: Schema.String,
  subdomain: Schema.String,
  record_type: Schema.Literal('entity'),
  path: Schema.String,
  content_snippet: Schema.String,
  content_text: Schema.optional(Schema.String),
  content_html: Schema.optional(Schema.String), // New field for rendered HTML
  display_blocks: Schema.optional(Schema.Record({ key: Schema.String, value: Schema.String })),
  extra: Schema.optional(Schema.Unknown),
})
export type EntityDetail = typeof EntityDetailSchema.Type

// ── Connection record ─────────────────────────────────────────────────────────

export const ConnectionRecordSchema = Schema.Struct({
  artifact_id: Schema.String,
  source: Schema.String,
  target: Schema.String,
  conn_type: Schema.String,
  version: Schema.String,
  status: Schema.String,
  path: Schema.String,
  content_text: Schema.String,
})
export type ConnectionRecord = typeof ConnectionRecordSchema.Type

export const ConnectionListSchema = Schema.Array(ConnectionRecordSchema)
export type ConnectionList = typeof ConnectionListSchema.Type

// ── Neighbors ────────────────────────────────────────────────────────────────

export const NeighborsSchema = Schema.Record({ key: Schema.String, value: Schema.Array(Schema.String) })
export type Neighbors = typeof NeighborsSchema.Type

// ── Search ────────────────────────────────────────────────────────────────────

export const SearchHitSchema = Schema.Struct({
  score: Schema.Number,
  record_type: Schema.Literal('entity', 'connection', 'diagram'),
  artifact_id: Schema.String,
  name: Schema.String,
  artifact_type: Schema.String,
  status: Schema.String,
  path: Schema.String,
  domain: Schema.optional(Schema.String),
  subdomain: Schema.optional(Schema.String),
})
export type SearchHit = typeof SearchHitSchema.Type

export const SearchResultSchema = Schema.Struct({
  query: Schema.String,
  hits: Schema.Array(SearchHitSchema),
})
export type SearchResult = typeof SearchResultSchema.Type
