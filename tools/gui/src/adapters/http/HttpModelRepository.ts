import { Effect, Schema, ParseResult } from 'effect'
import type { ModelRepository, ListParams, Direction } from '../../ports/ModelRepository'
import { NetworkError, NotFoundError } from '../../domain/errors'
import {
  StatsSchema,
  EntityListSchema,
  EntityDetailSchema,
  ConnectionListSchema,
  NeighborsSchema,
  SearchResultSchema,
  DiagramListSchema,
  DiagramDetailSchema,
  WriteResultSchema,
  DiagramRefsSchema,
} from '../../domain/schemas'
import { parseMarkdown } from '../../application/MarkdownService'

// ── Helpers ───────────────────────────────────────────────────────────────────

const buildUrl = (
  path: string,
  params?: Readonly<Record<string, string | number | boolean | undefined>>,
): string => {
  const url = new URL('/api' + path, window.location.origin)
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

// ── Factory ───────────────────────────────────────────────────────────────────

export const makeHttpModelRepository = (): ModelRepository => ({
  getStats: () => fetchJson(buildUrl('/stats'), StatsSchema),

  listEntities: (params: ListParams = {}) =>
    fetchJson(
      buildUrl('/entities', {
        domain: params.domain, artifact_type: params.artifactType,
        status: params.status, limit: params.limit, offset: params.offset,
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

  getConnections: (entityId: string, direction: Direction = 'any', connType?: string) =>
    fetchJson(
      buildUrl('/connections', { entity_id: entityId, direction, conn_type: connType }),
      ConnectionListSchema,
    ),

  getNeighbors: (entityId: string, maxHops = 1) =>
    fetchJson(buildUrl('/neighbors', { entity_id: entityId, max_hops: maxHops }), NeighborsSchema),

  search: (query: string, limit = 20) =>
    fetchJson(buildUrl('/search', { q: query, limit }), SearchResultSchema),

  listDiagrams: (diagramType?: string, status?: string) =>
    fetchJson(buildUrl('/diagrams', { diagram_type: diagramType, status }), DiagramListSchema),

  getDiagram: (id: string) =>
    fetchJsonNotFound(buildUrl('/diagram', { id }), DiagramDetailSchema, id),

  diagramImageUrl: (filename: string) => `/api/diagram-image/${encodeURIComponent(filename)}`,

  getDiagramRefs: (sourceId: string, targetId: string) =>
    fetchJson(
      buildUrl('/diagram-refs', { source_id: sourceId, target_id: targetId }),
      DiagramRefsSchema,
    ),

  addConnection: (body) => postJson(buildUrl('/connection'), body, WriteResultSchema),

  removeConnection: (body) => postJson(buildUrl('/connection/remove'), body, WriteResultSchema),

  getWriteHelp: () =>
    fetchJson(buildUrl('/write-help'), Schema.Unknown),
})
