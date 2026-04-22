import { Effect, Schema, ParseResult } from 'effect'
import type { ModelRepository, ListParams, Direction } from '../../ports/ModelRepository'
import { NetworkError, NotFoundError } from '../../domain/errors'
import {
  StatsSchema,
  EntityListSchema,
  EntityDetailSchema,
  EntityContextSchema,
  ConnectionListSchema,
  NeighborsSchema,
  SearchResultSchema,
  DocumentTypesSchema,
  DocumentListSchema,
  DocumentDetailSchema,
  ArtifactSearchResultSchema,
  ReferenceSearchResultSchema,
  DiagramListSchema,
  DiagramDetailSchema,
  DiagramContextSchema,
  DiagramEntityDiscoverySchema,
  WriteResultSchema,
  DiagramRefsSchema,
  OntologyClassificationSchema,
  OntologyPairSchema,
  EntitySchemaInfoSchema,
  EntitySummarySchema,
  EntityDisplayInfoSchema,
  DiagramPreviewResultSchema,
  DiagramConnectionSchema,
  PromotionPlanSchema,
  PromotionResultSchema,
} from '../../domain/schemas'
import { parseMarkdown } from '../../application/MarkdownService'

// ── Helpers ───────────────────────────────────────────────────────────────────

const buildUrl = (
  path: string,
  params?: Readonly<Record<string, string | number | boolean | undefined>>,
  adminPath?: boolean,
): string => {
  const url = new URL((adminPath ? '/admin/api' : '/api') + path, window.location.origin)
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined) url.searchParams.set(k, String(v))
    }
  }
  return url.toString()
}

const fetchJson = <A, I>(
  url: string,
  schema: Schema.Schema<A, I>,
): Effect.Effect<A, NetworkError | ParseResult.ParseError> =>
  Effect.tryPromise({
    try: async () => {
      const resp = await fetch(url)
      if (resp.status === 404) throw new NotFoundError({ id: url })
      if (!resp.ok) throw new NetworkError({ status: resp.status, message: resp.statusText })
      return resp.json() as Promise<unknown>
    },
    catch: (e) =>
      e instanceof NetworkError ? e : new NetworkError({ status: 0, message: String(e) }),
  }).pipe(Effect.flatMap(Schema.decodeUnknown(schema)))

const fetchJsonNotFound = <A, I>(
  url: string,
  schema: Schema.Schema<A, I>,
  id: string,
): Effect.Effect<A, NetworkError | ParseResult.ParseError | NotFoundError> =>
  Effect.tryPromise({
    try: async () => {
      const resp = await fetch(url)
      if (resp.status === 404) throw new NotFoundError({ id })
      if (!resp.ok) throw new NetworkError({ status: resp.status, message: resp.statusText })
      return resp.json() as Promise<unknown>
    },
    catch: (e) => {
      if (e instanceof NotFoundError || e instanceof NetworkError) return e
      return new NetworkError({ status: 0, message: String(e) })
    },
  }).pipe(Effect.flatMap(Schema.decodeUnknown(schema)))

const fetchText = (url: string): Effect.Effect<string, NetworkError> =>
  Effect.tryPromise({
    try: async () => {
      const resp = await fetch(url)
      if (!resp.ok) throw new NetworkError({ status: resp.status, message: resp.statusText })
      return resp.text()
    },
    catch: (e) => e instanceof NetworkError ? e : new NetworkError({ status: 0, message: String(e) }),
  })

const postJson = <A, I>(
  url: string,
  body: unknown,
  schema: Schema.Schema<A, I>,
): Effect.Effect<A, NetworkError | ParseResult.ParseError> =>
  Effect.tryPromise({
    try: async () => {
      const resp = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!resp.ok) {
        const text = await resp.text().catch(() => resp.statusText)
        throw new NetworkError({ status: resp.status, message: text })
      }
      return resp.json() as Promise<unknown>
    },
    catch: (e) =>
      e instanceof NetworkError ? e : new NetworkError({ status: 0, message: String(e) }),
  }).pipe(Effect.flatMap(Schema.decodeUnknown(schema)))

const putJson = <A, I>(
  url: string,
  body: unknown,
  schema: Schema.Schema<A, I>,
): Effect.Effect<A, NetworkError | ParseResult.ParseError> =>
  Effect.tryPromise({
    try: async () => {
      const resp = await fetch(url, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!resp.ok) {
        const text = await resp.text().catch(() => resp.statusText)
        throw new NetworkError({ status: resp.status, message: text })
      }
      return resp.json() as Promise<unknown>
    },
    catch: (e) =>
      e instanceof NetworkError ? e : new NetworkError({ status: 0, message: String(e) }),
  }).pipe(Effect.flatMap(Schema.decodeUnknown(schema)))

const deleteReq = <A, I>(
  url: string,
  schema: Schema.Schema<A, I>,
): Effect.Effect<A, NetworkError | ParseResult.ParseError> =>
  Effect.tryPromise({
    try: async () => {
      const resp = await fetch(url, { method: 'DELETE' })
      if (!resp.ok) {
        const text = await resp.text().catch(() => resp.statusText)
        throw new NetworkError({ status: resp.status, message: text })
      }
      return resp.json() as Promise<unknown>
    },
    catch: (e) =>
      e instanceof NetworkError ? e : new NetworkError({ status: 0, message: String(e) }),
  }).pipe(Effect.flatMap(Schema.decodeUnknown(schema)))

// ── Factory ───────────────────────────────────────────────────────────────────

export const makeHttpModelRepository = (): ModelRepository => ({
  getServerInfo: () => fetchJson(buildUrl('/admin/server-info'), Schema.Unknown),
  getStats: () => fetchJson(buildUrl('/stats'), StatsSchema),

  listEntities: (params: ListParams = {}) =>
    fetchJson(
      buildUrl('/entities', {
        domain: params.domain, artifact_type: params.artifactType,
        status: params.status, scope: params.scope,
        limit: params.limit, offset: params.offset,
      }),
      EntityListSchema,
    ),

  getEntity: (id: string) =>
    fetchJsonNotFound(buildUrl('/entity', { id }), EntityDetailSchema, id).pipe(
      Effect.flatMap((entity) => {
        if (entity.content_text) {
          return parseMarkdown(entity.content_text).pipe(
            Effect.map((html) => ({ ...entity, content_html: html })),
          )
        }
        return Effect.succeed({ ...entity })
      }),
    ),

  getEntityContext: (id: string) =>
    fetchJsonNotFound(buildUrl('/entity-context', { id }), EntityContextSchema, id).pipe(
      Effect.flatMap((context) => {
        if (context.entity.content_text) {
          return parseMarkdown(context.entity.content_text).pipe(
            Effect.map((html) => ({ ...context, entity: { ...context.entity, content_html: html } })),
          )
        }
        return Effect.succeed({ ...context, entity: { ...context.entity } })
      }),
    ),

  getConnections: (entityId: string, direction: Direction = 'any', connType?: string) =>
    fetchJson(
      buildUrl('/connections', { entity_id: entityId, direction, conn_type: connType }),
      ConnectionListSchema,
    ),

  getNeighbors: (entityId: string, maxHops = 1) =>
    fetchJson(buildUrl('/neighbors', { entity_id: entityId, max_hops: maxHops }), NeighborsSchema),

  search: (query: string, limit = 20) =>
    fetchJson(buildUrl('/search', { q: query, limit }), SearchResultSchema),

  listDocumentTypes: () =>
    fetchJson(buildUrl('/document-types'), DocumentTypesSchema).pipe(
      Effect.map((items) => [...items] as import('../../domain').DocumentType[]),
    ),

  listDocuments: (params = {}) =>
    fetchJson(buildUrl('/documents', params), DocumentListSchema),

  getDocument: (id) =>
    fetchJsonNotFound(buildUrl('/document', { id }), DocumentDetailSchema, id),

  createDocument: (body) =>
    postJson(buildUrl('/document'), body, WriteResultSchema),

  editDocument: (id, body) =>
    putJson(buildUrl(`/document/${encodeURIComponent(id)}`), body, WriteResultSchema),

  deleteDocument: (id, dry_run) =>
    deleteReq(buildUrl(`/document/${encodeURIComponent(id)}`, { dry_run }), WriteResultSchema),

  artifactSearch: (q, params = {}) =>
    fetchJson(buildUrl('/artifact-search', { q, ...params }), ArtifactSearchResultSchema),

  searchReferenceArtifacts: (params) =>
    fetchJson(buildUrl('/reference-search', {
      q: params.q,
      kind: params.kind,
      domains: params.domains?.join(','),
      entity_types: params.entity_types?.join(','),
      doc_types: params.doc_types?.join(','),
      limit: params.limit,
    }), ReferenceSearchResultSchema),

  listDiagrams: (diagramType?: string, status?: string) =>
    fetchJson(buildUrl('/diagrams', { diagram_type: diagramType, status }), DiagramListSchema),

  getDiagram: (id: string) =>
    fetchJsonNotFound(buildUrl('/diagram', { id }), DiagramDetailSchema, id),

  getDiagramContext: (id: string) =>
    fetchJsonNotFound(buildUrl('/diagram-context', { id }), DiagramContextSchema, id),

  diagramImageUrl: (filename: string) => `/api/diagram-image/${encodeURIComponent(filename)}`,

  getDiagramRefs: (sourceId: string, targetId: string) =>
    fetchJson(
      buildUrl('/diagram-refs', { source_id: sourceId, target_id: targetId }),
      DiagramRefsSchema,
    ),

  addConnection: (body) => postJson(buildUrl('/connection'), body, WriteResultSchema),

  editConnection: (body) => postJson(buildUrl('/connection/edit'), body, WriteResultSchema),

  removeConnection: (body) => postJson(buildUrl('/connection/remove'), body, WriteResultSchema),

  manageConnectionAssociations: (body) =>
    postJson(buildUrl('/connection/associate'), body, WriteResultSchema),

  getWriteHelp: () =>
    fetchJson(buildUrl('/write-help'), Schema.Unknown),

  getOntologyClassification: (sourceType: string) =>
    fetchJson(
      buildUrl('/ontology', { source_type: sourceType }),
      OntologyClassificationSchema,
    ),

  getOntologyPair: (sourceType: string, targetType: string) =>
    fetchJson(
      buildUrl('/ontology', { source_type: sourceType, target_type: targetType }),
      OntologyPairSchema,
    ),

  createEntity: (body) => postJson(buildUrl('/entity'), body, WriteResultSchema),

  editEntity: (body) => postJson(buildUrl('/entity/edit'), body, WriteResultSchema),
  deleteEntity: (body) => postJson(buildUrl('/entity/remove'), body, WriteResultSchema),

  getEntitySchemata: (artifactType: string) =>
    fetchJson(buildUrl('/entity-schemata', { artifact_type: artifactType }), EntitySchemaInfoSchema),

  getDiagramEntities: (diagramId: string) =>
    fetchJson(buildUrl('/diagram-entities', { id: diagramId }), Schema.Array(EntitySummarySchema)).pipe(
      Effect.map((arr) => arr as import('../../domain').EntitySummary[]),
    ),

  getDiagramConnections: (diagramId: string) =>
    fetchJson(buildUrl('/diagram-connections', { id: diagramId }), Schema.Array(DiagramConnectionSchema)).pipe(
      Effect.map((arr) => arr as import('../../domain').DiagramConnection[]),
    ),

  getDiagramSvg: (diagramId: string) =>
    fetchText(buildUrl('/diagram-svg', { id: diagramId })),

  searchEntityDisplay: (query: string, limit = 20) =>
    fetchJson(
      buildUrl('/entity-display-search', { q: query, limit }),
      Schema.Array(EntityDisplayInfoSchema),
    ).pipe(Effect.map((arr) => arr as import('../../domain').EntityDisplayInfo[])),

  discoverDiagramEntities: ({ includedEntityIds = [], query, maxHops = 2, limit = 20 }) =>
    fetchJson(
      buildUrl('/diagram-entity-discovery', {
        q: query,
        max_hops: maxHops,
        limit,
        included_entity_ids: includedEntityIds.join(','),
      }),
      DiagramEntityDiscoverySchema,
    ),

  previewDiagram: (body) =>
    postJson(buildUrl('/diagram/preview'), body, DiagramPreviewResultSchema),

  createDiagram: (body) =>
    postJson(buildUrl('/diagram'), body, WriteResultSchema),

  editDiagram: (body) =>
    postJson(buildUrl('/diagram/edit'), body, WriteResultSchema),
  deleteDiagram: (body) =>
    postJson(buildUrl('/diagram/remove'), body, WriteResultSchema),

  adminCreateEntity: (body) =>
    postJson(buildUrl('/admin/entity', undefined, true), body, WriteResultSchema),
  adminEditEntity: (body) =>
    postJson(buildUrl('/admin/entity/edit', undefined, true), body, WriteResultSchema),
  adminDeleteEntity: (body) =>
    postJson(buildUrl('/admin/entity/remove', undefined, true), body, WriteResultSchema),
  adminAddConnection: (body) =>
    postJson(buildUrl('/admin/connection', undefined, true), body, WriteResultSchema),
  adminRemoveConnection: (body) =>
    postJson(buildUrl('/admin/connection/remove', undefined, true), body, WriteResultSchema),
  adminDeleteDiagram: (body) =>
    postJson(buildUrl('/admin/diagram/remove', undefined, true), body, WriteResultSchema),

  planPromotion: (body) =>
    postJson(buildUrl('/promote/plan'), body, PromotionPlanSchema),

  executePromotion: (body) =>
    postJson(buildUrl('/promote/execute'), body, PromotionResultSchema),
})
