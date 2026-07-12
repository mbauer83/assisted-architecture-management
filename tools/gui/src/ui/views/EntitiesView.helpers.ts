/**
 * Pure helper for the "save current filters as viewpoint" entry point: turns the
 * entities-list view's ad-hoc domain/type filters into an `entity_criteria` group in the
 * canonical wire mapping shape, ready to hand to the viewpoints management view's create
 * flow as a seed.
 */

import type { ColumnSpecNode } from '../../domain/viewpointPresentation'
import type { EntityItemSummary, ProjectedOccurrence, ViewpointProjection } from '../../domain'

export const filtersToEntityCriteriaMapping = (domain: string, artifactType: string): Record<string, unknown> => {
  const children: Record<string, unknown>[] = []
  if (domain) children.push({ kind: 'condition', attribute: 'domain', comparator: 'eq', value: domain })
  if (artifactType) children.push({ kind: 'condition', attribute: 'type', comparator: 'eq', value: artifactType })
  return { kind: 'group', conjunction: 'and', children }
}

// ── Viewpoint-driven table execution (companion plan §5.1/§5.3, WU-E9) ────────────

/** Same shape as `GraphExploreView.helpers.ts`'s function of the same name — kept as a
 * small local duplicate rather than a cross-view import (established WU-E8 convention). */
export const projectionByItemId = (projection: ViewpointProjection | null): ReadonlyMap<string, ProjectedOccurrence> =>
  new Map((projection?.items ?? []).map((item) => [item.item_id, item]))

/** §3.3 reserved paths resolvable from the fixed, unstyled `EntityItemSummary` — every
 * other reserved path (`domain`/`subdomain`/`status`/`version`) and any schema attribute
 * path is NOT resolvable here: the summary carries no properties map and no record fields
 * beyond these (the same category of gap WU-E8 recorded for `group_by`). */
export const resolveSummaryColumnValue = (entity: EntityItemSummary, source: string): string | null => {
  switch (source) {
    case 'id': return entity.id
    case 'name': return entity.name
    case 'type': return entity.type
    case 'specialization': return entity.specialization_slugs.join(', ') || null
    case 'group': return entity.group
    default: return null
  }
}

export const RESOLVABLE_COLUMN_SOURCES: readonly string[] = ['id', 'name', 'type', 'specialization', 'group']

export const isColumnSourceResolvable = (source: string): boolean => RESOLVABLE_COLUMN_SOURCES.includes(source)

export interface TableColumn {
  readonly label: string
  readonly source: string
}

const DEFAULT_TABLE_COLUMNS: readonly TableColumn[] = [
  { label: 'Name', source: 'name' },
  { label: 'Type', source: 'type' },
  { label: 'Specialization', source: 'specialization' },
  { label: 'Group', source: 'group' },
]

/** A definition's `columns` (table representation, §5.3) if authored, else the same
 * default set the plain entity catalog shows. */
export const effectiveTableColumns = (columns: readonly ColumnSpecNode[] | null): readonly TableColumn[] =>
  columns && columns.length > 0
    ? columns.map((c) => ({ label: c.label || c.source, source: c.source }))
    : DEFAULT_TABLE_COLUMNS

/** `group_by` (row grouping, §5.1) resolves against the fixed §7.1 summary's three
 * well-known non-attribute dimensions, matching `GraphExploreView.helpers.ts::groupKeyFor` —
 * an arbitrary profile-attribute path falls back to `type` (recorded, not silently
 * mis-grouped). */
export const groupKeyForEntity = (entity: EntityItemSummary, groupBy: string | null): string => {
  if (groupBy === 'group') return entity.group
  if (groupBy === 'specialization') return entity.specialization_slugs[0] ?? '(none)'
  return entity.type
}

export interface TableRowGroup {
  readonly groupKey: string
  readonly entities: readonly EntityItemSummary[]
}

/** Groups the retained population into ordered sections. `groupBy === null` returns one
 * ungrouped section (empty `groupKey`) so the table renders flat, as today. */
export const groupTableRows = (
  entities: readonly EntityItemSummary[],
  groupBy: string | null,
): readonly TableRowGroup[] => {
  if (groupBy === null) return entities.length > 0 ? [{ groupKey: '', entities }] : []
  const byKey = new Map<string, EntityItemSummary[]>()
  for (const entity of entities) {
    const key = groupKeyForEntity(entity, groupBy)
    const bucket = byKey.get(key)
    if (bucket) bucket.push(entity)
    else byKey.set(key, [entity])
  }
  return [...byKey.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([groupKey, groupEntities]) => ({ groupKey, entities: groupEntities }))
}
