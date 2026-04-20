import type { ModelRepository, ListParams, Direction } from '../ports/ModelRepository'

/**
 * Application service: use-case orchestration layer.
 * Wraps the outbound port and exposes named operations for the UI.
 */
export type ModelService = ReturnType<typeof makeModelService>

export const makeModelService = (repo: ModelRepository) =>
  ({
    getServerInfo: () => repo.getServerInfo(),
    getStats: () => repo.getStats(),
    listEntities: (params: ListParams = {}) => repo.listEntities(params),
    listEntitiesGlobal: (params: ListParams = {}) => repo.listEntities({ ...params, scope: 'global' }),
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
    editConnection: (body: Parameters<ModelRepository['editConnection']>[0]) =>
      repo.editConnection(body),
    removeConnection: (body: Parameters<ModelRepository['removeConnection']>[0]) =>
      repo.removeConnection(body),
    manageConnectionAssociations: (body: Parameters<ModelRepository['manageConnectionAssociations']>[0]) =>
      repo.manageConnectionAssociations(body),
    getWriteHelp: () => repo.getWriteHelp(),
    getOntologyClassification: (sourceType: string) => repo.getOntologyClassification(sourceType),
    getOntologyPair: (sourceType: string, targetType: string) => repo.getOntologyPair(sourceType, targetType),
    createEntity: (body: Parameters<ModelRepository['createEntity']>[0]) => repo.createEntity(body),
    editEntity: (body: Parameters<ModelRepository['editEntity']>[0]) => repo.editEntity(body),
    deleteEntity: (body: Parameters<ModelRepository['deleteEntity']>[0]) => repo.deleteEntity(body),
    getEntitySchemata: (artifactType: string) => repo.getEntitySchemata(artifactType),
    getDiagramEntities: (diagramId: string) => repo.getDiagramEntities(diagramId),
    getDiagramConnections: (diagramId: string) => repo.getDiagramConnections(diagramId),
    getDiagramSvg: (diagramId: string) => repo.getDiagramSvg(diagramId),
    searchEntityDisplay: (query: string, limit?: number) => repo.searchEntityDisplay(query, limit),
    previewDiagram: (body: Parameters<ModelRepository['previewDiagram']>[0]) => repo.previewDiagram(body),
    createDiagram: (body: Parameters<ModelRepository['createDiagram']>[0]) => repo.createDiagram(body),
    editDiagram: (body: Parameters<ModelRepository['editDiagram']>[0]) => repo.editDiagram(body),
    deleteDiagram: (body: Parameters<ModelRepository['deleteDiagram']>[0]) => repo.deleteDiagram(body),
    adminCreateEntity: (body: Parameters<ModelRepository['adminCreateEntity']>[0]) => repo.adminCreateEntity(body),
    adminEditEntity: (body: Parameters<ModelRepository['adminEditEntity']>[0]) => repo.adminEditEntity(body),
    adminDeleteEntity: (body: Parameters<ModelRepository['adminDeleteEntity']>[0]) => repo.adminDeleteEntity(body),
    adminAddConnection: (body: Parameters<ModelRepository['adminAddConnection']>[0]) => repo.adminAddConnection(body),
    adminRemoveConnection: (body: Parameters<ModelRepository['adminRemoveConnection']>[0]) => repo.adminRemoveConnection(body),
    adminDeleteDiagram: (body: Parameters<ModelRepository['adminDeleteDiagram']>[0]) => repo.adminDeleteDiagram(body),
    planPromotion: (body: Parameters<ModelRepository['planPromotion']>[0]) => repo.planPromotion(body),
    executePromotion: (body: Parameters<ModelRepository['executePromotion']>[0]) => repo.executePromotion(body),
  }) as const
