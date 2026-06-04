import { computed, type ComputedRef } from 'vue'
import type { EntitySummary } from '../../domain'

export function useHierarchicalEntities(source: ComputedRef<EntitySummary[]>): ComputedRef<EntitySummary[]> {
  return computed(() => {
    const items = source.value
    const byId = new Map(items.map(item => [item.artifact_id, item]))
    type ChildEntry = { entity: EntitySummary; relationType: string | undefined }
    const children = new Map<string, ChildEntry[]>()
    for (const item of items) {
      const rawParents = item.all_parents?.length
        ? item.all_parents
        : item.parent_entity_id
          ? [{ parent_id: item.parent_entity_id, relation_type: item.hierarchy_relation_type ?? '' }]
          : []
      for (const p of rawParents.filter(p => byId.has(p.parent_id))) {
        const bucket = children.get(p.parent_id) ?? []
        bucket.push({ entity: item, relationType: p.relation_type || undefined })
        children.set(p.parent_id, bucket)
      }
    }
    const hasParent = new Set<string>()
    for (const entries of children.values()) for (const { entity } of entries) hasParent.add(entity.artifact_id)
    const roots = items.filter(item => !hasParent.has(item.artifact_id))
    const ordered: EntitySummary[] = []
    const visited = new Set<string>()
    const currentPath = new Set<string>()
    const visit = (item: EntitySummary, depth: number, parentId: string | null, relationType: string | null, parentKey: string) => {
      if (currentPath.has(item.artifact_id)) return
      const key = `${item.artifact_id}::${parentKey}`
      if (visited.has(key)) return
      visited.add(key)
      ordered.push(parentId !== null
        ? { ...item, parent_entity_id: parentId, hierarchy_relation_type: relationType ?? undefined, hierarchy_depth: depth, specialization_depth: depth }
        : { ...item, hierarchy_depth: depth, specialization_depth: depth })
      currentPath.add(item.artifact_id)
      for (const { entity: child, relationType: rt } of children.get(item.artifact_id) ?? []) {
        visit(child, depth + 1, item.artifact_id, rt ?? null, key)
      }
      currentPath.delete(item.artifact_id)
    }
    for (const root of roots) visit(root, 0, null, null, '')
    return ordered
  })
}
