import type { Effect, ParseResult } from 'effect'
import type {
  Stats,
  EntityList,
  EntityDetail,
  EntityContext,
  ConnectionList,
  Neighbors,
  SearchResult,
  DiagramList,
  DiagramDetail,
  DiagramContext,
  DiagramEntityDiscovery,
  WriteResult,
  DiagramRefs,
  OntologyClassification,
  OntologyPair,
  EntitySchemaInfo,
  EntitySummary,
  EntityDisplayInfo,
  DiagramPreviewResult,
  DiagramConnection,
  PromotionPlan,
  PromotionResult,
} from '../domain'
import type { NetworkError, NotFoundError } from '../domain'
import type { MarkdownError } from '../application/MarkdownService'

export type Direction = 'any' | 'outbound' | 'inbound'

export type RepoScope = 'engagement' | 'global'

export interface ListParams {
  readonly domain?: string
  readonly artifactType?: string
  readonly status?: string
  readonly scope?: RepoScope
  readonly limit?: number
  readonly offset?: number
}

/** Errors that can come from any repository call. */
export type RepoError = NetworkError | ParseResult.ParseError

/** Outbound port: the application's view of the model backend. */
export interface ModelRepository {
  readonly getServerInfo: () => Effect.Effect<unknown, RepoError>
  readonly getStats: () => Effect.Effect<Stats, RepoError>
  readonly listEntities: (params?: ListParams) => Effect.Effect<EntityList, RepoError>
  readonly getEntity: (id: string) => Effect.Effect<EntityDetail, RepoError | NotFoundError | MarkdownError>
  readonly getEntityContext: (id: string) => Effect.Effect<EntityContext, RepoError | NotFoundError | MarkdownError>
  readonly getConnections: (
    entityId: string, direction?: Direction, connType?: string,
  ) => Effect.Effect<ConnectionList, RepoError>
  readonly getNeighbors: (
    entityId: string, maxHops?: number,
  ) => Effect.Effect<Neighbors, RepoError>
  readonly search: (
    query: string, limit?: number,
  ) => Effect.Effect<SearchResult, RepoError>
  readonly listDiagrams: (
    diagramType?: string, status?: string,
  ) => Effect.Effect<DiagramList, RepoError>
  readonly getDiagram: (id: string) => Effect.Effect<DiagramDetail, RepoError | NotFoundError>
  readonly getDiagramContext: (id: string) => Effect.Effect<DiagramContext, RepoError | NotFoundError>
  readonly diagramImageUrl: (filename: string) => string
  readonly getDiagramRefs: (
    sourceId: string, targetId: string,
  ) => Effect.Effect<DiagramRefs, RepoError>
  readonly addConnection: (body: {
    source_entity: string; connection_type: string; target_entity: string;
    description?: string; src_cardinality?: string; tgt_cardinality?: string;
    dry_run?: boolean;
  }) => Effect.Effect<WriteResult, RepoError>
  readonly editConnection: (body: {
    source_entity: string; connection_type: string; target_entity: string;
    description?: string; src_cardinality?: string; tgt_cardinality?: string;
    dry_run?: boolean;
  }) => Effect.Effect<WriteResult, RepoError>
  readonly removeConnection: (body: {
    source_entity: string; connection_type: string; target_entity: string;
    dry_run?: boolean;
  }) => Effect.Effect<WriteResult, RepoError>
  readonly manageConnectionAssociations: (body: {
    source_entity: string; connection_type: string; target_entity: string;
    add_entities?: string[]; remove_entities?: string[];
    dry_run?: boolean;
  }) => Effect.Effect<WriteResult, RepoError>
  readonly getWriteHelp: () => Effect.Effect<unknown, RepoError>
  readonly getOntologyClassification: (sourceType: string) => Effect.Effect<OntologyClassification, RepoError>
  readonly getOntologyPair: (sourceType: string, targetType: string) => Effect.Effect<OntologyPair, RepoError>
  readonly createEntity: (body: {
    artifact_type: string; name: string; summary?: string;
    properties?: Record<string, string>; notes?: string;
    keywords?: string[]; version?: string; status?: string;
    dry_run?: boolean;
  }) => Effect.Effect<WriteResult, RepoError>
  readonly editEntity: (body: {
    artifact_id: string; name?: string; summary?: string;
    properties?: Record<string, string>; notes?: string;
    keywords?: string[]; version?: string; status?: string;
    dry_run?: boolean;
  }) => Effect.Effect<WriteResult, RepoError>
  readonly deleteEntity: (body: {
    artifact_id: string; dry_run?: boolean;
  }) => Effect.Effect<WriteResult, RepoError>
  readonly getEntitySchemata: (artifactType: string) => Effect.Effect<EntitySchemaInfo, RepoError>
  readonly getDiagramEntities: (diagramId: string) => Effect.Effect<EntitySummary[], RepoError>
  readonly getDiagramConnections: (diagramId: string) => Effect.Effect<DiagramConnection[], RepoError>
  readonly getDiagramSvg: (diagramId: string) => Effect.Effect<string, RepoError>
  readonly searchEntityDisplay: (
    query: string, limit?: number,
  ) => Effect.Effect<EntityDisplayInfo[], RepoError>
  readonly discoverDiagramEntities: (params: {
    includedEntityIds?: string[]
    query?: string
    maxHops?: number
    limit?: number
  }) => Effect.Effect<DiagramEntityDiscovery, RepoError>
  readonly previewDiagram: (body: {
    diagram_type: string; name: string;
    entity_ids: string[]; connection_ids: string[];
  }) => Effect.Effect<DiagramPreviewResult, RepoError>
  readonly createDiagram: (body: {
    diagram_type: string; name: string;
    entity_ids: string[]; connection_ids: string[];
    keywords?: string[]; version?: string; status?: string; dry_run?: boolean;
  }) => Effect.Effect<WriteResult, RepoError>
  readonly editDiagram: (body: {
    artifact_id: string; diagram_type: string; name: string;
    entity_ids: string[]; connection_ids: string[];
    version?: string; status?: string; dry_run?: boolean;
  }) => Effect.Effect<WriteResult, RepoError>
  readonly deleteDiagram: (body: {
    artifact_id: string; dry_run?: boolean;
  }) => Effect.Effect<WriteResult, RepoError>
  // ── Admin write methods (active only in --admin-mode) ───────────────────
  readonly adminCreateEntity: (body: {
    artifact_type: string; name: string; summary?: string;
    properties?: Record<string, string>; notes?: string;
    keywords?: string[]; version?: string; status?: string; dry_run?: boolean;
  }) => Effect.Effect<WriteResult, RepoError>
  readonly adminEditEntity: (body: {
    artifact_id: string; name?: string; summary?: string;
    properties?: Record<string, string>; notes?: string;
    keywords?: string[]; version?: string; status?: string; dry_run?: boolean;
  }) => Effect.Effect<WriteResult, RepoError>
  readonly adminDeleteEntity: (body: {
    artifact_id: string; dry_run?: boolean;
  }) => Effect.Effect<WriteResult, RepoError>
  readonly adminAddConnection: (body: {
    source_entity: string; connection_type: string; target_entity: string;
    description?: string; src_cardinality?: string; tgt_cardinality?: string;
    dry_run?: boolean;
  }) => Effect.Effect<WriteResult, RepoError>
  readonly adminRemoveConnection: (body: {
    source_entity: string; connection_type: string; target_entity: string;
    dry_run?: boolean;
  }) => Effect.Effect<WriteResult, RepoError>
  readonly adminDeleteDiagram: (body: {
    artifact_id: string; dry_run?: boolean;
  }) => Effect.Effect<WriteResult, RepoError>
  readonly planPromotion: (body: {
    entity_id: string;
    exclude_entity_ids?: string[];
    exclude_connection_ids?: string[];
  }) => Effect.Effect<PromotionPlan, RepoError>
  readonly executePromotion: (body: {
    entity_id: string;
    exclude_entity_ids?: string[];
    exclude_connection_ids?: string[];
    conflict_resolutions?: Array<{
      engagement_id: string;
      strategy: 'accept_engagement' | 'accept_enterprise' | 'merge';
      merged_fields?: Record<string, unknown>;
    }>;
    dry_run?: boolean;
  }) => Effect.Effect<PromotionResult, RepoError>
}
