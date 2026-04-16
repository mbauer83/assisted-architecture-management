import type { ModelRepository, ListParams, Direction } from '../ports/ModelRepository'

/**
 * Application service: use-case orchestration layer.
 * Wraps the outbound port and exposes named operations for the UI.
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
    listDiagrams: (diagramType?: string, status?: string) =>
      repo.listDiagrams(diagramType, status),
    getDiagram: (id: string) => repo.getDiagram(id),
    diagramImageUrl: (filename: string) => repo.diagramImageUrl(filename),
    getDiagramRefs: (sourceId: string, targetId: string) =>
      repo.getDiagramRefs(sourceId, targetId),
    addConnection: (body: Parameters<ModelRepository['addConnection']>[0]) =>
      repo.addConnection(body),
    removeConnection: (body: Parameters<ModelRepository['removeConnection']>[0]) =>
      repo.removeConnection(body),
    getWriteHelp: () => repo.getWriteHelp(),
    getOntologyClassification: (sourceType: string) => repo.getOntologyClassification(sourceType),
    getOntologyPair: (sourceType: string, targetType: string) => repo.getOntologyPair(sourceType, targetType),
    createEntity: (body: Parameters<ModelRepository['createEntity']>[0]) => repo.createEntity(body),
    editEntity: (body: Parameters<ModelRepository['editEntity']>[0]) => repo.editEntity(body),
    getEntitySchemata: (artifactType: string) => repo.getEntitySchemata(artifactType),
    getDiagramEntities: (diagramId: string) => repo.getDiagramEntities(diagramId),
    searchEntityDisplay: (query: string, limit?: number) => repo.searchEntityDisplay(query, limit),
    previewDiagram: (body: Parameters<ModelRepository['previewDiagram']>[0]) => repo.previewDiagram(body),
    createDiagram: (body: Parameters<ModelRepository['createDiagram']>[0]) => repo.createDiagram(body),
    editDiagram: (body: Parameters<ModelRepository['editDiagram']>[0]) => repo.editDiagram(body),
  }) as const
