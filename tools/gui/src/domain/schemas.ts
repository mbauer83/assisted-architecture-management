import { Schema } from 'effect'

// ── Stats ────────────────────────────────────────────────────────────────────

export const StatsSchema = Schema.Struct({
  entities: Schema.Number,
  connections: Schema.Number,
  diagrams: Schema.Number,
  documents: Schema.optional(Schema.Number),
  entities_by_domain: Schema.Record({ key: Schema.String, value: Schema.Number }),
  connections_by_type: Schema.Record({ key: Schema.String, value: Schema.Number }),
  documents_by_type: Schema.optional(Schema.Record({ key: Schema.String, value: Schema.Number })),
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
  is_global: Schema.optional(Schema.Boolean),
  display_alias: Schema.optional(Schema.String),
  parent_entity_id: Schema.optional(Schema.NullOr(Schema.String)),
  hierarchy_relation_type: Schema.optional(Schema.String),
  hierarchy_depth: Schema.optional(Schema.Number),
  parent_specialization_id: Schema.optional(Schema.NullOr(Schema.String)),
  specialization_depth: Schema.optional(Schema.Number),
  conn_in: Schema.optional(Schema.Number),
  conn_sym: Schema.optional(Schema.Number),
  conn_out: Schema.optional(Schema.Number),
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
  keywords: Schema.optional(Schema.Array(Schema.String)),
  summary: Schema.optional(Schema.String),
  properties: Schema.optional(Schema.Record({ key: Schema.String, value: Schema.String })),
  notes: Schema.optional(Schema.String),
  is_global: Schema.optional(Schema.Boolean),
  conn_in: Schema.optional(Schema.Number),
  conn_sym: Schema.optional(Schema.Number),
  conn_out: Schema.optional(Schema.Number),
  content_text: Schema.optional(Schema.String),
  content_html: Schema.optional(Schema.String),
  display_blocks: Schema.optional(Schema.Record({ key: Schema.String, value: Schema.String })),
  extra: Schema.optional(Schema.Record({ key: Schema.String, value: Schema.Unknown })),
})
export type EntityDetail = typeof EntityDetailSchema.Type

// ── Connection record ─────────────────────────────────────────────────────────

export const ConnectionRecordSchema = Schema.Struct({
  artifact_id: Schema.String,
  source: Schema.String,
  target: Schema.String,
  source_name: Schema.optional(Schema.String),
  target_name: Schema.optional(Schema.String),
  conn_type: Schema.String,
  version: Schema.String,
  status: Schema.String,
  path: Schema.String,
  content_text: Schema.String,
  src_cardinality: Schema.optional(Schema.String),
  tgt_cardinality: Schema.optional(Schema.String),
  associated_entities: Schema.optional(Schema.Array(Schema.String)),
})
export type ConnectionRecord = typeof ConnectionRecordSchema.Type

export const ConnectionListSchema = Schema.Array(ConnectionRecordSchema)
export type ConnectionList = typeof ConnectionListSchema.Type

export const EntityContextConnectionSchema = Schema.extend(
  ConnectionRecordSchema,
  Schema.Struct({
    source_artifact_type: Schema.String,
    target_artifact_type: Schema.String,
    source_domain: Schema.String,
    target_domain: Schema.String,
    source_scope: Schema.String,
    target_scope: Schema.String,
    other_entity_id: Schema.String,
    direction: Schema.String,
  }),
)
export type EntityContextConnection = typeof EntityContextConnectionSchema.Type

export const EntityContextSchema = Schema.Struct({
  entity: EntityDetailSchema,
  connections: Schema.Struct({
    outbound: Schema.Array(EntityContextConnectionSchema),
    inbound: Schema.Array(EntityContextConnectionSchema),
    symmetric: Schema.Array(EntityContextConnectionSchema),
  }),
  counts: Schema.Struct({
    conn_in: Schema.Number,
    conn_out: Schema.Number,
    conn_sym: Schema.Number,
  }),
  generation: Schema.Number,
  etag: Schema.String,
})
export type EntityContext = typeof EntityContextSchema.Type

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
  is_global: Schema.optional(Schema.Boolean),
  domain: Schema.optional(Schema.String),
  subdomain: Schema.optional(Schema.String),
  diagram_type: Schema.optional(Schema.String),
})
export type SearchHit = typeof SearchHitSchema.Type

export const SearchResultSchema = Schema.Struct({
  query: Schema.String,
  hits: Schema.Array(SearchHitSchema),
})
export type SearchResult = typeof SearchResultSchema.Type

// ── Document types ────────────────────────────────────────────────────────────

export const DocumentTypeSchema = Schema.Struct({
  doc_type: Schema.String,
  abbreviation: Schema.String,
  name: Schema.String,
  subdirectory: Schema.String,
  required_sections: Schema.Array(Schema.String),
})
export type DocumentType = typeof DocumentTypeSchema.Type

export const DocumentTypesSchema = Schema.Array(DocumentTypeSchema)

export const DocumentSummarySchema = Schema.Struct({
  artifact_id: Schema.String,
  doc_type: Schema.String,
  title: Schema.String,
  status: Schema.String,
  path: Schema.String,
  keywords: Schema.Array(Schema.String),
  sections: Schema.Array(Schema.String),
})
export type DocumentSummary = typeof DocumentSummarySchema.Type

export const DocumentListSchema = Schema.Struct({
  total: Schema.Number,
  items: Schema.Array(DocumentSummarySchema),
})
export type DocumentList = typeof DocumentListSchema.Type

export const DocumentDetailSchema = Schema.Struct({
  artifact_id: Schema.String,
  artifact_type: Schema.Literal('document'),
  doc_type: Schema.String,
  title: Schema.String,
  status: Schema.String,
  record_type: Schema.Literal('document'),
  path: Schema.String,
  keywords: Schema.Array(Schema.String),
  sections: Schema.Array(Schema.String),
  content_snippet: Schema.String,
  content_text: Schema.optional(Schema.String),
  extra: Schema.optional(Schema.Record({ key: Schema.String, value: Schema.Unknown })),
})
export type DocumentDetail = typeof DocumentDetailSchema.Type

// ── Artifact search (cross-type) ──────────────────────────────────────────────

export const ArtifactSearchHitSchema = Schema.Struct({
  score: Schema.Number,
  record_type: Schema.Union(
    Schema.Literal('entity'),
    Schema.Literal('connection'),
    Schema.Literal('diagram'),
    Schema.Literal('document'),
  ),
  artifact_id: Schema.String,
  name: Schema.String,
  status: Schema.String,
  path: Schema.String,
})
export type ArtifactSearchHit = typeof ArtifactSearchHitSchema.Type

export const ArtifactSearchResultSchema = Schema.Struct({
  query: Schema.String,
  hits: Schema.Array(ArtifactSearchHitSchema),
})
export type ArtifactSearchResult = typeof ArtifactSearchResultSchema.Type

// ── Reference search ─────────────────────────────────────────────────────────

export const ReferenceSearchHitSchema = Schema.Struct({
  artifact_id: Schema.String,
  record_type: Schema.Union(
    Schema.Literal('entity'),
    Schema.Literal('diagram'),
    Schema.Literal('document'),
  ),
  name: Schema.String,
  status: Schema.String,
  path: Schema.String,
  domain: Schema.optional(Schema.NullOr(Schema.String)),
  artifact_type: Schema.optional(Schema.String),
  diagram_type: Schema.optional(Schema.String),
  doc_type: Schema.optional(Schema.String),
  sections: Schema.optional(Schema.Array(Schema.String)),
  is_global: Schema.optional(Schema.Boolean),
})
export type ReferenceSearchHit = typeof ReferenceSearchHitSchema.Type

export const ReferenceSearchResultSchema = Schema.Struct({
  query: Schema.String,
  hits: Schema.Array(ReferenceSearchHitSchema),
})
export type ReferenceSearchResult = typeof ReferenceSearchResultSchema.Type

// ── Diagram summary ──────────────────────────────────────────────────────────

export const DiagramSummarySchema = Schema.Struct({
  artifact_id: Schema.String,
  name: Schema.String,
  diagram_type: Schema.String,
  version: Schema.String,
  status: Schema.String,
  path: Schema.String,
})
export type DiagramSummary = typeof DiagramSummarySchema.Type

export const DiagramListSchema = Schema.Struct({
  total: Schema.Number,
  items: Schema.Array(DiagramSummarySchema),
})
export type DiagramList = typeof DiagramListSchema.Type

// ── Diagram detail ───────────────────────────────────────────────────────────

export const DiagramDetailSchema = Schema.Struct({
  artifact_id: Schema.String,
  artifact_type: Schema.String,
  name: Schema.String,
  diagram_type: Schema.String,
  version: Schema.String,
  status: Schema.String,
  record_type: Schema.Literal('diagram'),
  path: Schema.String,
  is_global: Schema.optional(Schema.Boolean),
  content_snippet: Schema.String,
  puml_source: Schema.optional(Schema.String),
  rendered_filename: Schema.optional(Schema.NullOr(Schema.String)),
  entity_ids_used: Schema.optional(Schema.Array(Schema.String)),
  connection_ids_used: Schema.optional(Schema.Array(Schema.String)),
  extra: Schema.optional(Schema.Unknown),
})
export type DiagramDetail = typeof DiagramDetailSchema.Type

// ── Write results ────────────────────────────────────────────────────────────

export const WriteResultSchema = Schema.Struct({
  wrote: Schema.Boolean,
  path: Schema.String,
  artifact_id: Schema.String,
  content: Schema.NullOr(Schema.String),
  warnings: Schema.Array(Schema.String),
  verification: Schema.NullOr(Schema.Unknown),
})
export type WriteResult = typeof WriteResultSchema.Type

// ── Ontology ──────────────────────────────────────────────────────────────────

export const OntologyClassificationSchema = Schema.Struct({
  source_type: Schema.String,
  outgoing: Schema.Record({ key: Schema.String, value: Schema.Array(Schema.String) }),
  incoming: Schema.Record({ key: Schema.String, value: Schema.Array(Schema.String) }),
  symmetric: Schema.Record({ key: Schema.String, value: Schema.Array(Schema.String) }),
})
export type OntologyClassification = typeof OntologyClassificationSchema.Type

export const OntologyPairSchema = Schema.Struct({
  source_type: Schema.String,
  target_type: Schema.String,
  connection_types: Schema.Array(Schema.String),
  symmetric: Schema.Array(Schema.String),
})
export type OntologyPair = typeof OntologyPairSchema.Type

// ── Diagram refs ─────────────────────────────────────────────────────────────

export const DiagramRefSchema = Schema.Struct({
  artifact_id: Schema.String,
  name: Schema.String,
})
export type DiagramRef = typeof DiagramRefSchema.Type

export const DiagramRefsSchema = Schema.Array(DiagramRefSchema)
export type DiagramRefs = typeof DiagramRefsSchema.Type

// ── Entity display info (diagram create form) ────────────────────────────────

export const EntityDisplayInfoSchema = Schema.Struct({
  artifact_id: Schema.String,
  name: Schema.String,
  artifact_type: Schema.String,
  domain: Schema.String,
  subdomain: Schema.String,
  status: Schema.String,
  display_alias: Schema.String,
  element_type: Schema.String,
  element_label: Schema.String,
})
export type EntityDisplayInfo = typeof EntityDisplayInfoSchema.Type

// ── Diagram preview result ────────────────────────────────────────────────────

export const DiagramConnectionSchema = Schema.Struct({
  artifact_id: Schema.String,
  source: Schema.String,
  target: Schema.String,
  conn_type: Schema.String,
  version: Schema.String,
  status: Schema.String,
  path: Schema.String,
  content_text: Schema.String,
  source_name: Schema.String,
  target_name: Schema.String,
  source_alias: Schema.NullOr(Schema.String),
  target_alias: Schema.NullOr(Schema.String),
})
export type DiagramConnection = typeof DiagramConnectionSchema.Type

export const DiagramContextSchema = Schema.Struct({
  diagram: DiagramDetailSchema,
  entities: Schema.Array(EntitySummarySchema),
  connections: Schema.Array(DiagramConnectionSchema),
  candidate_connections: Schema.Array(EntityContextConnectionSchema),
  suggested_entities: Schema.Array(
    Schema.Struct({
      hop: Schema.Number,
      items: Schema.Array(EntityDisplayInfoSchema),
    }),
  ),
  explicit_connection_pairs: Schema.Array(Schema.Array(Schema.String)),
  generation: Schema.Number,
  etag: Schema.String,
})
export type DiagramContext = typeof DiagramContextSchema.Type

export const DiagramEntityDiscoverySchema = Schema.Struct({
  search_results: Schema.Array(EntityDisplayInfoSchema),
  candidate_connections: Schema.Array(EntityContextConnectionSchema),
  suggested_entities: Schema.Array(
    Schema.Struct({
      hop: Schema.Number,
      items: Schema.Array(EntityDisplayInfoSchema),
    }),
  ),
})
export type DiagramEntityDiscovery = typeof DiagramEntityDiscoverySchema.Type

export const DiagramPreviewResultSchema = Schema.Struct({
  puml: Schema.String,
  image: Schema.NullOr(Schema.String),
  warnings: Schema.Array(Schema.String),
})
export type DiagramPreviewResult = typeof DiagramPreviewResultSchema.Type

// ── Entity attribute schemata ─────────────────────────────────────────────────

export const EntitySchemaInfoSchema = Schema.Struct({
  artifact_type: Schema.String,
  schema: Schema.NullOr(Schema.Unknown),
  properties: Schema.Array(Schema.String),
  required: Schema.Array(Schema.String),
})
export type EntitySchemaInfo = typeof EntitySchemaInfoSchema.Type

// ── Promotion ─────────────────────────────────────────────────────────────────

export const PromotionConflictSchema = Schema.Struct({
  engagement_id: Schema.String,
  enterprise_id: Schema.String,
  artifact_type: Schema.String,
  engagement_name: Schema.String,
  enterprise_name: Schema.String,
  engagement_fields: Schema.Record({ key: Schema.String, value: Schema.Unknown }),
  enterprise_fields: Schema.Record({ key: Schema.String, value: Schema.Unknown }),
})
export type PromotionConflict = typeof PromotionConflictSchema.Type

export const PromotionPlanSchema = Schema.Struct({
  entity_id: Schema.String,
  entities_to_add: Schema.Array(Schema.String),
  conflicts: Schema.Array(PromotionConflictSchema),
  connection_ids: Schema.Array(Schema.String),
  already_in_enterprise: Schema.Array(Schema.String),
  warnings: Schema.Array(Schema.String),
})
export type PromotionPlan = typeof PromotionPlanSchema.Type

export const PromotionResultSchema = Schema.Struct({
  dry_run: Schema.Boolean,
  executed: Schema.Boolean,
  copied_files: Schema.Array(Schema.String),
  updated_files: Schema.Array(Schema.String),
  verification_errors: Schema.Array(Schema.String),
  rolled_back: Schema.Boolean,
})
export type PromotionResult = typeof PromotionResultSchema.Type
