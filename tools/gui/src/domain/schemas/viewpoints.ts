import { Schema } from 'effect'

// ── Viewpoints (GUI selector/overlay) ─────────────────────────────────────────

export const ViewpointApplicationSchema = Schema.Struct({
  slug: Schema.String,
  version: Schema.Number,
  enforcement_override: Schema.optional(Schema.Literal('off', 'warn', 'ghost')),
  derivation_params: Schema.optional(Schema.Record({ key: Schema.String, value: Schema.Unknown })),
})
export type ViewpointApplication = typeof ViewpointApplicationSchema.Type

export const ViewpointSummarySchema = Schema.Struct({
  slug: Schema.String,
  version: Schema.Number,
  name: Schema.String,
  description: Schema.String,
  purpose: Schema.Array(Schema.String),
  content: Schema.Array(Schema.String),
  scope: Schema.Unknown,
})
export type ViewpointSummary = typeof ViewpointSummarySchema.Type

export const ProjectedOccurrenceSchema = Schema.Struct({
  item_id: Schema.String,
  item_kind: Schema.Literal('entity', 'connection'),
  state: Schema.Literal('visible', 'ghosted'),
  membership: Schema.Literal('primary', 'expanded'),
  reasons: Schema.Array(Schema.Literal('out_of_scope', 'criteria_mismatch', 'endpoint_excluded')),
  style: Schema.Record({ key: Schema.String, value: Schema.String }),
})
export type ProjectedOccurrence = typeof ProjectedOccurrenceSchema.Type

export const ViewpointProjectionSchema = Schema.Struct({
  applied: Schema.Boolean,
  target: Schema.optional(Schema.Literal('repository', 'diagram', 'matrix')),
  items: Schema.optional(Schema.Array(ProjectedOccurrenceSchema)),
  stale_pin: Schema.optional(Schema.Boolean),
  warnings: Schema.optional(Schema.Array(Schema.String)),
})
export type ViewpointProjection = typeof ViewpointProjectionSchema.Type

// ── Viewpoint execution ────────────────────────────────────────────────────────
// Fixed, non-customizable per-item summaries — deliberately unstyled (D15 boundary, §2).
// Style tokens come from the separate `execute-projection` endpoint (`ViewpointProjectionSchema`
// above), never from this contract, so MCP/REST content can never disagree with the GUI.

export const EntityItemSummarySchema = Schema.Struct({
  id: Schema.String,
  name: Schema.String,
  type: Schema.String,
  specialization_slugs: Schema.Array(Schema.String),
  group: Schema.String,
  membership: Schema.Literal('primary', 'expanded'),
})
export type EntityItemSummary = typeof EntityItemSummarySchema.Type

export const ConnectionItemSummarySchema = Schema.Struct({
  id: Schema.String,
  type: Schema.String,
  source: Schema.String,
  target: Schema.String,
})
export type ConnectionItemSummary = typeof ConnectionItemSummarySchema.Type

export const MatrixAxisIdsSchema = Schema.Struct({
  row_entity_ids: Schema.Array(Schema.String),
  column_entity_ids: Schema.Array(Schema.String),
})
export type MatrixAxisIds = typeof MatrixAxisIdsSchema.Type

export const ViewpointExecutionResultSchema = Schema.Struct({
  slug: Schema.NullOr(Schema.String),
  version: Schema.NullOr(Schema.Number),
  query_schema: Schema.Number,
  repo_scope: Schema.String,
  executed_at: Schema.String,
  index_generation: Schema.NullOr(Schema.Number),
  entity_ids: Schema.Array(Schema.String),
  connection_ids: Schema.Array(Schema.String),
  entities: Schema.Array(EntityItemSummarySchema),
  connections: Schema.Array(ConnectionItemSummarySchema),
  total_entity_count: Schema.Number,
  returned_entity_count: Schema.Number,
  total_connection_count: Schema.Number,
  returned_connection_count: Schema.Number,
  truncated: Schema.Boolean,
  entity_limit: Schema.Number,
  matrix_axes: Schema.NullOr(MatrixAxisIdsSchema),
  warnings: Schema.Array(Schema.String),
  duration_ms: Schema.Number,
  query_summary: Schema.String,
})
export type ViewpointExecutionResult = typeof ViewpointExecutionResultSchema.Type

export interface ViewpointExecutionRequest {
  readonly slug?: string
  readonly query?: unknown
  readonly limit?: number
}

/** GUI-only ad-hoc ArchiMate-notation rendering (the ad-hoc `diagram` representation) —
 * unstyled; `node_color`/`edge_color`/`edge_emphasis` overlays are applied client-side
 * onto the returned SVG. */
export const ViewpointDiagramResultSchema = Schema.Struct({
  svg: Schema.NullOr(Schema.String),
  warnings: Schema.Array(Schema.String),
})
export type ViewpointDiagramResult = typeof ViewpointDiagramResultSchema.Type

// ── Viewpoint definitions (management view) ───────────────────────────────────
// `query`/`presentation`/`scope` stay `Unknown` here (matching the existing
// `ViewpointSummarySchema.scope` convention above) — their recursive wire shape is
// modeled by plain TS types in `viewpointCriteria.ts`, decoded/encoded by
// `viewpointCriteriaSerialization.ts`, not by Effect Schema.

export const ScopeSummarySchema = Schema.Struct({
  unrestricted: Schema.Boolean,
  entity_types: Schema.optional(Schema.Array(Schema.String)),
  connection_types: Schema.optional(Schema.Array(Schema.String)),
  excluded_entity_types: Schema.optional(Schema.Array(Schema.String)),
  excluded_domains: Schema.optional(Schema.Array(Schema.String)),
  excluded_connection_types: Schema.optional(Schema.Array(Schema.String)),
})
export type ScopeSummary = typeof ScopeSummarySchema.Type

export const ViewpointDefinitionEnvelopeSchema = Schema.Struct({
  slug: Schema.String,
  version: Schema.Number,
  name: Schema.String,
  description: Schema.optional(Schema.String),
  rationale: Schema.optional(Schema.String),
  purpose: Schema.optional(Schema.Union(Schema.String, Schema.Array(Schema.String))),
  content: Schema.optional(Schema.Union(Schema.String, Schema.Array(Schema.String))),
  stakeholders: Schema.optional(Schema.Array(Schema.String)),
  concerns: Schema.optional(Schema.Array(Schema.String)),
  scope: Schema.optional(Schema.Unknown),
  representation_types: Schema.optional(Schema.Array(Schema.String)),
  derivation_defaults: Schema.optional(Schema.Record({ key: Schema.String, value: Schema.Unknown })),
  query: Schema.optional(Schema.Unknown),
  presentation: Schema.optional(Schema.Unknown),
  tier: Schema.Literal('module', 'enterprise', 'engagement'),
  scope_summary: ScopeSummarySchema,
  query_summary: Schema.NullOr(Schema.String),
})
export type ViewpointDefinitionEnvelope = typeof ViewpointDefinitionEnvelopeSchema.Type

export const ViewpointDefinitionListSchema = Schema.Struct({
  viewpoints: Schema.Array(ViewpointDefinitionEnvelopeSchema),
})

export const CriteriaCatalogSchema = Schema.Struct({
  entity_types: Schema.Array(Schema.String),
  connection_types: Schema.Array(Schema.String),
  specialization_slugs: Schema.Array(Schema.String),
  entity_attribute_types: Schema.Record({ key: Schema.String, value: Schema.String }),
  connection_attribute_types: Schema.Record({ key: Schema.String, value: Schema.String }),
  symmetric_connection_types: Schema.Array(Schema.String),
  reserved_entity_paths: Schema.Array(Schema.String),
  reserved_connection_paths: Schema.Array(Schema.String),
  depth_cap: Schema.Number,
  // entity type slug -> owning domain (hierarchy[0]) — lets the scope picker group entity
  // types by domain and support "exclude this whole domain" bulk actions.
  entity_type_domains: Schema.Record({ key: Schema.String, value: Schema.String }),
})
export type CriteriaCatalog = typeof CriteriaCatalogSchema.Type

export const ViewpointSummarizeResultSchema = Schema.Struct({ summary: Schema.String })

export const ViewpointValidationIssueSchema = Schema.Struct({
  severity: Schema.Literal('error', 'warning'),
  code: Schema.String,
  path: Schema.String,
  message: Schema.String,
  expected: Schema.NullOr(Schema.String),
  found: Schema.NullOr(Schema.String),
})
export type ViewpointValidationIssue = typeof ViewpointValidationIssueSchema.Type

export const ViewpointReferencerSchema = Schema.Struct({
  artifact_id: Schema.String,
  target_kind: Schema.Literal('diagram', 'matrix'),
})
export type ViewpointReferencer = typeof ViewpointReferencerSchema.Type

export const ViewpointReferencerListSchema = Schema.Struct({
  referencers: Schema.Array(ViewpointReferencerSchema),
})

export const ViewpointPersistResultSchema = Schema.Struct({
  ok: Schema.Boolean,
  action: Schema.Literal('create', 'edit', 'delete'),
  slug: Schema.String,
  version: Schema.NullOr(Schema.Number),
  dry_run: Schema.Boolean,
  issues: Schema.Array(ViewpointValidationIssueSchema),
  referencers: Schema.Array(ViewpointReferencerSchema),
})
export type ViewpointPersistResult = typeof ViewpointPersistResultSchema.Type
