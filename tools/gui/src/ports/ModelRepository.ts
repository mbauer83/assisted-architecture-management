import type { Effect, ParseResult } from 'effect'
import type {
  Stats,
  EntityList,
  EntityDetail,
  ConnectionList,
  Neighbors,
  SearchResult,
  DiagramList,
  DiagramDetail,
  WriteResult,
  DiagramRefs,
} from '../domain'
import type { NetworkError, NotFoundError } from '../domain'
import type { MarkdownError } from '../application/MarkdownService'

export type Direction = 'any' | 'outbound' | 'inbound'

export interface ListParams {
  readonly domain?: string
  readonly artifactType?: string
  readonly status?: string
  readonly limit?: number
  readonly offset?: number
}

/** Errors that can come from any repository call. */
export type RepoError = NetworkError | ParseResult.ParseError

/** Outbound port: the application's view of the model backend. */
export interface ModelRepository {
  readonly getStats: () => Effect.Effect<Stats, RepoError>
  readonly listEntities: (params?: ListParams) => Effect.Effect<EntityList, RepoError>
  readonly getEntity: (id: string) => Effect.Effect<EntityDetail, RepoError | NotFoundError | MarkdownError>
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
  readonly diagramImageUrl: (filename: string) => string
  readonly getDiagramRefs: (
    sourceId: string, targetId: string,
  ) => Effect.Effect<DiagramRefs, RepoError>
  readonly addConnection: (body: {
    source_entity: string; connection_type: string; target_entity: string;
    description?: string; dry_run?: boolean;
  }) => Effect.Effect<WriteResult, RepoError>
  readonly removeConnection: (body: {
    source_entity: string; connection_type: string; target_entity: string;
    dry_run?: boolean;
  }) => Effect.Effect<WriteResult, RepoError>
  readonly getWriteHelp: () => Effect.Effect<unknown, RepoError>
}
