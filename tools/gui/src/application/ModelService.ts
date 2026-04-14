import type { ModelRepository, ListParams, Direction } from '../ports/ModelRepository'

/**
 * Application service: use-case orchestration layer.
 * Wraps the outbound port and exposes named operations for the UI.
 * Pure: no I/O here — just delegates to the injected repository.
 */
export type ModelService = ReturnType<typeof makeModelService>

export const makeModelService = (repo: ModelRepository) =>
  ({
    getStats: () => repo.getStats(),

    listEntities: (params: ListParams = {}) => repo.listEntities(params),

    getEntity: (id: string) => repo.getEntity(id),

    getConnections: (entityId: string, direction: Direction = 'any') =>
      repo.getConnections(entityId, direction),

    search: (query: string, limit?: number) => repo.search(query, limit),
  }) as const
