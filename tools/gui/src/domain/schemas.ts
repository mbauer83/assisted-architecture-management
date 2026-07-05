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
  host_diagram_id: Schema.optional(Schema.String),
  display_alias: Schema.optional(Schema.String),
  parent_entity_id: Schema.optional(Schema.NullOr(Schema.String)),
  hierarchy_relation_type: Schema.optional(Schema.String),
  hierarchy_depth: Schema.optional(Schema.Number),
  parent_specialization_id: Schema.optional(Schema.NullOr(Schema.String)),
  specialization_depth: Schema.optional(Schema.Number),
  all_parents: Schema.optional(Schema.Array(Schema.Struct({
    parent_id: Schema.String,
    relation_type: Schema.String,
  }))),
  conn_in: Schema.optional(Schema.Number),
  conn_sym: Schema.optional(Schema.Number),
  conn_out: Schema.optional(Schema.Number),
  group: Schema.optional(Schema.String),
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
  properties: Schema.optional(Schema.Record({ key: Schema.String, value: Schema.Unknown })),
  notes: Schema.optional(Schema.String),
  is_global: Schema.optional(Schema.Boolean),
  host_diagram_id: Schema.optional(Schema.String),
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
  record_type: Schema.Union(
    Schema.Literal('entity'),
    Schema.Literal('connection'),
    Schema.Literal('diagram'),
    Schema.Literal('document'),
    Schema.Literal('assurance-node'),   // placeholder; consumed in WU-G3
    Schema.Literal('assurance-edge'),   // placeholder; consumed in WU-G3
  ),
  artifact_id: Schema.String,
  name: Schema.String,
  artifact_type: Schema.optional(Schema.String),
  status: Schema.String,
  path: Schema.String,
  source: Schema.optional(Schema.String),
  target: Schema.optional(Schema.String),
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

// ── Assurance REST responses ─────────────────────────────────────────────────

export const AssuranceNodeSchema = Schema.Struct({
  node_id: Schema.String,
  node_type: Schema.String,
  name: Schema.String,
  status: Schema.String,
  tlp: Schema.String,
  concern_class: Schema.NullOr(Schema.String),
  disposition: Schema.NullOr(Schema.String),
  uca_type: Schema.NullOr(Schema.String),
  binding_status: Schema.NullOr(Schema.String),
  node_role: Schema.NullOr(Schema.String),
  attributes_json: Schema.String,
  content_text: Schema.String,
  created_at: Schema.String,
  updated_at: Schema.String,
  created_by: Schema.String,
  analysis_id: Schema.NullOr(Schema.String),
})
export type AssuranceNode = typeof AssuranceNodeSchema.Type

export const AssuranceNodeListSchema = Schema.Struct({
  nodes: Schema.Array(AssuranceNodeSchema),
  count: Schema.Number,
  visibility_limited: Schema.Boolean,
})
export type AssuranceNodeList = typeof AssuranceNodeListSchema.Type

// ── Frontmatter fields ────────────────────────────────────────────────────────

export const FrontmatterFieldSchema = Schema.Struct({
  name: Schema.String,
  field_type: Schema.String,
  array_items_type: Schema.optional(Schema.NullOr(Schema.String)),
  required: Schema.Boolean,
})
export type FrontmatterField = typeof FrontmatterFieldSchema.Type

// ── Document types ────────────────────────────────────────────────────────────

export const SectionSpecSchema = Schema.Struct({
  name: Schema.String,
  template: Schema.optional(Schema.String),
  required_entity_type_connections: Schema.optional(Schema.Array(Schema.String)),
  suggested_entity_type_connections: Schema.optional(Schema.Array(Schema.String)),
})
export type SectionSpec = typeof SectionSpecSchema.Type

export const DocumentTypeSchema = Schema.Struct({
  doc_type: Schema.String,
  abbreviation: Schema.String,
  name: Schema.String,
  subdirectory: Schema.String,
  required_sections: Schema.Array(Schema.String),
  sections: Schema.optional(Schema.Array(SectionSpecSchema)),
  extra_frontmatter_fields: Schema.optional(Schema.Array(FrontmatterFieldSchema)),
  required_entity_type_connections: Schema.optional(Schema.Array(Schema.String)),
  suggested_entity_type_connections: Schema.optional(Schema.Array(Schema.String)),
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
  group: Schema.optional(Schema.String),
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
  is_global: Schema.optional(Schema.Boolean),
  extra: Schema.optional(Schema.Record({ key: Schema.String, value: Schema.Unknown })),
})
export type DocumentDetail = typeof DocumentDetailSchema.Type

// ── Artifact search (cross-type) — unified with SearchHitSchema ───────────────

export const ArtifactSearchHitSchema = SearchHitSchema
export type ArtifactSearchHit = SearchHit

export const ArtifactSearchResultSchema = SearchResultSchema
export type ArtifactSearchResult = SearchResult

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
  group: Schema.optional(Schema.String),
})
export type DiagramSummary = typeof DiagramSummarySchema.Type

export const DiagramListSchema = Schema.Struct({
  total: Schema.Number,
  items: Schema.Array(DiagramSummarySchema),
})
export type DiagramList = typeof DiagramListSchema.Type

export const DiagramTypeSummarySchema = Schema.Struct({
  key: Schema.String,
  label: Schema.String,
  description: Schema.String,
})
export type DiagramTypeSummary = typeof DiagramTypeSummarySchema.Type

export const MappingSourceSpecSchema = Schema.Struct({
  ontology: Schema.String,
  entity_type: Schema.optional(Schema.NullOr(Schema.String)),
  entity_class: Schema.optional(Schema.NullOr(Schema.String)),
  transparent: Schema.Boolean,
})
export type MappingSourceSpec = typeof MappingSourceSpecSchema.Type

export const PermittedMappingSpecSchema = Schema.Struct({
  entity_types: Schema.Array(Schema.String),
  entity_classes: Schema.Array(Schema.String),
  sources: Schema.Array(MappingSourceSpecSchema),
})
export type PermittedMappingSpec = typeof PermittedMappingSpecSchema.Type

export const DiagramOwnEntityTypePropertySpecSchema = Schema.Struct({
  name: Schema.String,
  schema: Schema.Unknown,
  required: Schema.Boolean,
})
export type DiagramOwnEntityTypePropertySpec = typeof DiagramOwnEntityTypePropertySpecSchema.Type

export const DiagramOwnEntityTypeUiConfigSchema = Schema.Struct({
  entity_type: Schema.String,
  label: Schema.String,
  plural: Schema.String,
  min: Schema.Number,
  max: Schema.NullOr(Schema.Number),
  permitted_mappings: PermittedMappingSpecSchema,
  mapping_required: Schema.Boolean,
  properties: Schema.Array(DiagramOwnEntityTypePropertySpecSchema),
})
export type DiagramOwnEntityTypeUiConfig = typeof DiagramOwnEntityTypeUiConfigSchema.Type

export const DiagramTypeUiConfigSchema = Schema.Struct({
  label: Schema.String,
  description: Schema.String,
  entity_search_filter: Schema.Boolean,
  diagram_only_types: Schema.Array(DiagramOwnEntityTypeUiConfigSchema),
  type_ui_slots: Schema.Record({ key: Schema.String, value: Schema.String }),
  primitive_types: Schema.optional(Schema.Array(Schema.String)),
})
export type DiagramTypeUiConfig = typeof DiagramTypeUiConfigSchema.Type

export const DatatypeClassifierInfoSchema = Schema.Struct({
  type_id: Schema.String,
  label: Schema.String,
  kind: Schema.String,
  scope: Schema.String,
  host_diagram_id: Schema.String,
})

export const DatatypeTypeCatalogSchema = Schema.Struct({
  generation: Schema.Number,
  primitives: Schema.Array(Schema.String),
  classifiers: Schema.Array(DatatypeClassifierInfoSchema),
  next_cursor: Schema.NullOr(Schema.String),
})
export type DatatypeTypeCatalog = typeof DatatypeTypeCatalogSchema.Type

export const DatatypeTypeUsageSchema = Schema.Struct({
  diagram_id: Schema.String,
  classifier_local_id: Schema.String,
  attr_name: Schema.String,
})

export const DatatypeTypeUsagesSchema = Schema.Struct({
  type_id: Schema.String,
  usages: Schema.Array(DatatypeTypeUsageSchema),
})
export type DatatypeTypeUsages = typeof DatatypeTypeUsagesSchema.Type

export const AllocatedIdentifierSchema = Schema.Struct({ id: Schema.String })
export type AllocatedIdentifier = typeof AllocatedIdentifierSchema.Type

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
  diagram_entities: Schema.optional(Schema.Unknown),
  matrix_body: Schema.optional(Schema.String),
  extra: Schema.optional(Schema.Unknown),
})
export type DiagramDetail = typeof DiagramDetailSchema.Type

// ── Matrix diagram ───────────────────────────────────────────────────────────

export const MatrixConnTypeConfigSchema = Schema.Struct({
  conn_type: Schema.String,
  active: Schema.Boolean,
})
export type MatrixConnTypeConfig = typeof MatrixConnTypeConfigSchema.Type

export const MatrixConfigSchema = Schema.Struct({
  artifact_id: Schema.String,
  name: Schema.String,
  status: Schema.String,
  version: Schema.String,
  keywords: Schema.Array(Schema.String),
  entity_ids: Schema.Array(Schema.String),
  from_entity_ids: Schema.optional(Schema.NullOr(Schema.Array(Schema.String))),
  to_entity_ids: Schema.optional(Schema.NullOr(Schema.Array(Schema.String))),
  conn_type_configs: Schema.Array(MatrixConnTypeConfigSchema),
  combined: Schema.Boolean,
  matrix_body: Schema.String,
})
export type MatrixConfig = typeof MatrixConfigSchema.Type

export const MatrixPreviewResultSchema = Schema.Struct({
  markdown: Schema.String,
})
export type MatrixPreviewResult = typeof MatrixPreviewResultSchema.Type

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

export const SyncDiagramToModelResultSchema = Schema.Struct({
  ...WriteResultSchema.fields,
  removed_entity_ids: Schema.Array(Schema.String),
  removed_connection_ids: Schema.Array(Schema.String),
})
export type SyncDiagramToModelResult = typeof SyncDiagramToModelResultSchema.Type

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
  relationship_kind_map: Schema.optional(Schema.Record({ key: Schema.String, value: Schema.Union(Schema.String, Schema.Null) })),
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

export const EntityDisplaySearchResultSchema = Schema.Struct({
  items: Schema.Array(EntityDisplayInfoSchema),
  next_cursor: Schema.NullOr(Schema.String),
})
export type EntityDisplaySearchResult = typeof EntityDisplaySearchResultSchema.Type

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
  edge_key: Schema.optional(Schema.NullOr(Schema.String)),
  edge_label_override: Schema.optional(Schema.NullOr(Schema.String)),
})
export type DiagramConnection = typeof DiagramConnectionSchema.Type

export const C4NavLinkSchema = Schema.Struct({
  diagram_id: Schema.String,
  diagram_name: Schema.String,
  diagram_type: Schema.String,
  scope_entity_id: Schema.optional(Schema.NullOr(Schema.String)),
})
export type C4NavLink = typeof C4NavLinkSchema.Type

export const C4NavigationSchema = Schema.Struct({
  current_level: Schema.Number,
  scope_entity_id: Schema.NullOr(Schema.String),
  scope_entity_name: Schema.NullOr(Schema.String),
  parent_diagrams: Schema.Array(C4NavLinkSchema),
  child_diagrams: Schema.Array(C4NavLinkSchema),
})
export type C4Navigation = typeof C4NavigationSchema.Type

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
  c4_navigation: Schema.optional(Schema.NullOr(C4NavigationSchema)),
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

export const DerivedEntitySchema = Schema.Struct({
  id: Schema.String,
  name: Schema.String,
  item_type: Schema.String,
})
export type DerivedEntity = typeof DerivedEntitySchema.Type

export const DiagramPreviewResultSchema = Schema.Struct({
  puml: Schema.String,
  image: Schema.NullOr(Schema.String),
  warnings: Schema.Array(Schema.String),
  derived_entities: Schema.NullOr(Schema.Array(DerivedEntitySchema)),
})
export type DiagramPreviewResult = typeof DiagramPreviewResultSchema.Type

// ── Entity attribute schemata ─────────────────────────────────────────────────

const EntityAttributeConstraintsSchema = Schema.Struct({
  minimum: Schema.optional(Schema.Number),
  maximum: Schema.optional(Schema.Number),
  exclusiveMinimum: Schema.optional(Schema.Number),
  exclusiveMaximum: Schema.optional(Schema.Number),
  minLength: Schema.optional(Schema.Number),
  maxLength: Schema.optional(Schema.Number),
  pattern: Schema.optional(Schema.String),
})

const EntityAttributeDescriptorSchema = Schema.Struct({
  type: Schema.String,
  enum: Schema.optional(Schema.Array(Schema.String)),
  default: Schema.optional(Schema.String),
  constraints: Schema.optional(EntityAttributeConstraintsSchema),
})
export type EntityAttributeDescriptor = typeof EntityAttributeDescriptorSchema.Type

export const EntitySchemaInfoSchema = Schema.Struct({
  artifact_type: Schema.String,
  schema: Schema.NullOr(Schema.Unknown),
  properties: Schema.Array(Schema.String),
  required: Schema.Array(Schema.String),
  descriptors: Schema.Record({ key: Schema.String, value: EntityAttributeDescriptorSchema }),
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

export const PromotionDocumentConflictSchema = Schema.Struct({
  engagement_id: Schema.String,
  enterprise_id: Schema.String,
  doc_type: Schema.String,
  engagement_title: Schema.String,
  enterprise_title: Schema.String,
})
export type PromotionDocumentConflict = typeof PromotionDocumentConflictSchema.Type

export const PromotionDiagramConflictSchema = Schema.Struct({
  engagement_id: Schema.String,
  enterprise_id: Schema.String,
  diagram_type: Schema.String,
  engagement_name: Schema.String,
  enterprise_name: Schema.String,
})
export type PromotionDiagramConflict = typeof PromotionDiagramConflictSchema.Type

export const PromotionGroupMappingEntrySchema = Schema.Struct({
  engagement_slug: Schema.String,
  engagement_group_id: Schema.String,
  match_status: Schema.Literal('matched_by_id', 'conflict', 'new'),
  enterprise_slug: Schema.String,
  enterprise_group_id: Schema.NullOr(Schema.String),
})
export type PromotionGroupMappingEntry = typeof PromotionGroupMappingEntrySchema.Type

export const PromotionPlanSchema = Schema.Struct({
  entity_id: Schema.String,
  entities_to_add: Schema.Array(Schema.String),
  conflicts: Schema.Array(PromotionConflictSchema),
  connection_ids: Schema.Array(Schema.String),
  already_in_enterprise: Schema.Array(Schema.String),
  warnings: Schema.Array(Schema.String),
  documents_to_add: Schema.Array(Schema.String),
  diagrams_to_add: Schema.Array(Schema.String),
  doc_conflicts: Schema.Array(PromotionDocumentConflictSchema),
  diagram_conflicts: Schema.Array(PromotionDiagramConflictSchema),
  schema_errors: Schema.Array(Schema.String),
  group_mapping: Schema.optional(Schema.Array(PromotionGroupMappingEntrySchema)),
  available_enterprise_groups: Schema.optional(Schema.Array(Schema.Struct({
    slug: Schema.String,
    id: Schema.String,
    name: Schema.String,
  }))),
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

// ── Sync status ───────────────────────────────────────────────────────────────

export const EngagementSyncStatusSchema = Schema.Struct({
  has_uncommitted_changes: Schema.Boolean,
})
export type EngagementSyncStatus = typeof EngagementSyncStatusSchema.Type

export const EnterpriseSyncStatusSchema = Schema.Struct({
  status: Schema.String,
  label: Schema.String,
  branch: Schema.NullOr(Schema.String),
  branch_tip: Schema.NullOr(Schema.String),
  pushed_at: Schema.NullOr(Schema.String),
  commits_behind: Schema.NullOr(Schema.Number),
  commits_ahead: Schema.optional(Schema.Number),
  has_uncommitted_changes: Schema.Boolean,
})
export type EnterpriseSyncStatus = typeof EnterpriseSyncStatusSchema.Type

export const SyncStatusSchema = Schema.Struct({
  engagement: Schema.NullOr(EngagementSyncStatusSchema),
  enterprise: Schema.NullOr(EnterpriseSyncStatusSchema),
})
export type SyncStatus = typeof SyncStatusSchema.Type

export const SyncSaveResultSchema = Schema.Struct({
  ok: Schema.Boolean,
  commit: Schema.optional(Schema.String),
  pushed: Schema.optional(Schema.Boolean),
  message: Schema.optional(Schema.String),
  branch: Schema.optional(Schema.String),
  discarded_branch: Schema.optional(Schema.String),
  already_submitted: Schema.optional(Schema.Boolean),
  nothing_to_discard: Schema.optional(Schema.Boolean),
})
export type SyncSaveResult = typeof SyncSaveResultSchema.Type

// ── Server / write-help metadata ─────────────────────────────────────────────

export const ServerInfoSchema = Schema.Struct({
  admin_mode: Schema.Boolean,
  read_only: Schema.Boolean,
  engagement_root: Schema.NullOr(Schema.String),
  enterprise_root: Schema.NullOr(Schema.String),
})
export type ServerInfo = typeof ServerInfoSchema.Type

export const WriteHelpEntityTypeCatalogEntrySchema = Schema.Struct({
  prefix: Schema.String,
})
export type WriteHelpEntityTypeCatalogEntry =
  typeof WriteHelpEntityTypeCatalogEntrySchema.Type

// ── Entity taxonomy ───────────────────────────────────────────────────────────

export const EntityTaxonomyTypeSchema = Schema.Struct({
  name: Schema.String,
  count: Schema.Number,
})
export type EntityTaxonomyType = typeof EntityTaxonomyTypeSchema.Type

export const EntityTaxonomyDomainSchema = Schema.Struct({
  name: Schema.String,
  count: Schema.Number,
  types: Schema.Array(EntityTaxonomyTypeSchema),
})
export type EntityTaxonomyDomain = typeof EntityTaxonomyDomainSchema.Type

export const EntityTaxonomySchema = Schema.Struct({
  domains: Schema.Array(EntityTaxonomyDomainSchema),
})
export type EntityTaxonomy = typeof EntityTaxonomySchema.Type

// ── Groups ────────────────────────────────────────────────────────────────────

export const GroupEntrySchema = Schema.Struct({
  slug: Schema.String,
  id: Schema.String,
  name: Schema.String,
  description: Schema.optional(Schema.String),
  order: Schema.optional(Schema.Number),
  archived: Schema.optional(Schema.Boolean),
  default: Schema.optional(Schema.Boolean),
  meta_ontology: Schema.optional(Schema.String),
  type_filter: Schema.optional(Schema.Array(Schema.String)),
})
export type GroupEntry = typeof GroupEntrySchema.Type

export const GroupListSchema = Schema.Struct({
  'model-projects': Schema.optional(Schema.Array(GroupEntrySchema)),
  'diagram-collections': Schema.optional(Schema.Array(GroupEntrySchema)),
  'document-collections': Schema.optional(Schema.Array(GroupEntrySchema)),
  'analysis-collections': Schema.optional(Schema.Array(GroupEntrySchema)),
})
export type GroupList = typeof GroupListSchema.Type

export const WriteHelpSchema = Schema.Struct({
  entity_types_by_domain: Schema.Record({
    key: Schema.String,
    value: Schema.Array(Schema.String),
  }),
  entity_type_catalog: Schema.optional(
    Schema.Record({
      key: Schema.String,
      value: WriteHelpEntityTypeCatalogEntrySchema,
    }),
  ),
})
export type WriteHelp = typeof WriteHelpSchema.Type

// ── Authoring guidance (GET /api/authoring-guidance) ───────────────────────────

export const PermittedConnectionsByPeerSchema = Schema.Struct({
  outgoing: Schema.Record({ key: Schema.String, value: Schema.Array(Schema.String) }),
  incoming: Schema.Record({ key: Schema.String, value: Schema.Array(Schema.String) }),
  symmetric: Schema.Record({ key: Schema.String, value: Schema.Array(Schema.String) }),
})

export const EntityTypeGuidanceSchema = Schema.Struct({
  name: Schema.String,
  prefix: Schema.String,
  domain: Schema.optional(Schema.String),
  classes: Schema.Array(Schema.String),
  create_when: Schema.String,
  never_create_when: Schema.String,
  permitted_connections: PermittedConnectionsByPeerSchema,
})
export type EntityTypeGuidance = typeof EntityTypeGuidanceSchema.Type

export const PairGuidanceSchema = Schema.Struct({
  source: Schema.optional(Schema.String),
  target: Schema.optional(Schema.String),
  outgoing: Schema.optional(Schema.Array(Schema.String)),
  incoming: Schema.optional(Schema.Array(Schema.String)),
  symmetric: Schema.optional(Schema.Array(Schema.String)),
  error: Schema.optional(Schema.String),
  known_types: Schema.optional(Schema.Array(Schema.String)),
})
export type PairGuidance = typeof PairGuidanceSchema.Type

export const AuthoringGuidanceSchema = Schema.Struct({
  entity_types: Schema.optional(Schema.Array(EntityTypeGuidanceSchema)),
  total: Schema.optional(Schema.Number),
  domains: Schema.optional(Schema.Array(Schema.String)),
  pair_guidance: Schema.optional(PairGuidanceSchema),
  diagram_type_guidance: Schema.optional(Schema.Unknown),
  error: Schema.optional(Schema.String),
  unknown: Schema.optional(Schema.Array(Schema.String)),
})
export type AuthoringGuidance = typeof AuthoringGuidanceSchema.Type
