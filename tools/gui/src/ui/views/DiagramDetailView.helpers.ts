import type { C4Navigation, EntitySummary } from '../../domain'

/**
 * Build alias→artifactId map for SVG interactivity.
 * Stores both the raw alias and a PlantUML-safe variant (non-alphanumeric chars → '_').
 */
export function buildAliasToId(entities: ReadonlyArray<EntitySummary>): Map<string, string> {
  const map = new Map<string, string>()
  for (const e of entities) {
    if (e.display_alias) {
      map.set(e.display_alias, e.artifact_id)
      map.set(e.display_alias.replace(/[^a-zA-Z0-9_]/g, '_'), e.artifact_id)
    }
  }
  return map
}

/** True when the entity lives inside a diagram (no standalone file). */
export function isDiagramOnly(entity: { host_diagram_id?: string | null }): boolean {
  return !!entity.host_diagram_id
}

/**
 * Builds a map of entityId → childDiagramId from the C4 navigation context.
 *
 * For L2→L3 children, the child carries its own scope_entity_id (the container
 * whose component diagram it is). For L1/L2 same-scope children, the child shares
 * the parent's scope entity — fall back to c4Nav.scope_entity_id.
 */
export function buildDrilldownByEntityId(
  c4Nav: C4Navigation | null | undefined,
): Record<string, string> {
  if (!c4Nav) return {}
  const map: Record<string, string> = {}
  for (const child of c4Nav.child_diagrams) {
    const entityId = child.scope_entity_id ?? c4Nav.scope_entity_id
    if (entityId) map[entityId] = child.diagram_id
  }
  return map
}
