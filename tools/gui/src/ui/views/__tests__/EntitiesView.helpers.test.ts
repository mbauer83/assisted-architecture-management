import { describe, expect, it } from 'vitest'
import {
  effectiveTableColumns, filtersToEntityCriteriaMapping, groupKeyForEntity, groupTableRows,
  isColumnSourceResolvable, projectionByItemId, resolveSummaryColumnValue,
} from '../EntitiesView.helpers'
import type { ColumnSpecNode } from '../../../domain/viewpointPresentation'
import type { EntityItemSummary, ViewpointProjection } from '../../../domain'

const entity = (overrides: Partial<EntityItemSummary> = {}): EntityItemSummary => ({
  id: 'APC@1.EntSch.a', name: 'Alpha', type: 'application-component',
  specialization_slugs: [], group: 'uncategorized', membership: 'primary', ...overrides,
})

describe('filtersToEntityCriteriaMapping', () => {
  it('is a match-all AND group when no filters are active', () => {
    expect(filtersToEntityCriteriaMapping('', '')).toEqual({ kind: 'group', conjunction: 'and', children: [] })
  })

  it('includes a domain condition when a domain filter is active', () => {
    expect(filtersToEntityCriteriaMapping('application', '')).toEqual({
      kind: 'group', conjunction: 'and',
      children: [{ kind: 'condition', attribute: 'domain', comparator: 'eq', value: 'application' }],
    })
  })

  it('includes both conditions when domain and type filters are active', () => {
    expect(filtersToEntityCriteriaMapping('application', 'application-component')).toEqual({
      kind: 'group', conjunction: 'and',
      children: [
        { kind: 'condition', attribute: 'domain', comparator: 'eq', value: 'application' },
        { kind: 'condition', attribute: 'type', comparator: 'eq', value: 'application-component' },
      ],
    })
  })
})

describe('resolveSummaryColumnValue', () => {
  it('resolves every §3.3 reserved path present on the fixed summary', () => {
    const e = entity({ specialization_slugs: ['micro-service'] })
    expect(resolveSummaryColumnValue(e, 'id')).toBe('APC@1.EntSch.a')
    expect(resolveSummaryColumnValue(e, 'name')).toBe('Alpha')
    expect(resolveSummaryColumnValue(e, 'type')).toBe('application-component')
    expect(resolveSummaryColumnValue(e, 'specialization')).toBe('micro-service')
    expect(resolveSummaryColumnValue(e, 'group')).toBe('uncategorized')
  })

  it('returns null for a specialization-less entity and for unresolvable paths', () => {
    expect(resolveSummaryColumnValue(entity(), 'specialization')).toBeNull()
    expect(resolveSummaryColumnValue(entity(), 'domain')).toBeNull()
    expect(resolveSummaryColumnValue(entity(), 'status')).toBeNull()
    expect(resolveSummaryColumnValue(entity(), 'some.schema.attribute')).toBeNull()
  })
})

describe('isColumnSourceResolvable', () => {
  it('is true for reserved paths carried by the summary, false otherwise', () => {
    expect(isColumnSourceResolvable('name')).toBe(true)
    expect(isColumnSourceResolvable('group')).toBe(true)
    expect(isColumnSourceResolvable('domain')).toBe(false)
    expect(isColumnSourceResolvable('status')).toBe(false)
  })
})

describe('effectiveTableColumns', () => {
  it('falls back to the default four-column set when a definition has no columns', () => {
    expect(effectiveTableColumns(null).map((c) => c.source)).toEqual(['name', 'type', 'specialization', 'group'])
    expect(effectiveTableColumns([]).map((c) => c.source)).toEqual(['name', 'type', 'specialization', 'group'])
  })

  it('uses the definition columns, filling in the source as label when label is blank', () => {
    const columns: ColumnSpecNode[] = [
      { id: 'c1', label: 'Domain', source: 'domain' },
      { id: 'c2', label: '', source: 'status' },
    ]
    expect(effectiveTableColumns(columns)).toEqual([
      { label: 'Domain', source: 'domain' },
      { label: 'status', source: 'status' },
    ])
  })
})

describe('groupKeyForEntity', () => {
  it('resolves group/specialization/type and falls back to type for anything else', () => {
    const e = entity({ group: 'core', specialization_slugs: ['micro-service'], type: 'application-component' })
    expect(groupKeyForEntity(e, 'group')).toBe('core')
    expect(groupKeyForEntity(e, 'specialization')).toBe('micro-service')
    expect(groupKeyForEntity(e, 'type')).toBe('application-component')
    expect(groupKeyForEntity(e, 'some.schema.attribute')).toBe('application-component')
  })

  it('uses "(none)" when grouping by specialization and none is present', () => {
    expect(groupKeyForEntity(entity({ specialization_slugs: [] }), 'specialization')).toBe('(none)')
  })
})

describe('groupTableRows', () => {
  const rows = [
    entity({ id: 'a', type: 'application-component' }),
    entity({ id: 'b', type: 'business-actor' }),
    entity({ id: 'c', type: 'application-component' }),
  ]

  it('returns one ungrouped section when groupBy is null', () => {
    expect(groupTableRows(rows, null)).toEqual([{ groupKey: '', entities: rows }])
  })

  it('returns no sections for an empty population', () => {
    expect(groupTableRows([], null)).toEqual([])
  })

  it('buckets by group key, sections sorted by key', () => {
    const grouped = groupTableRows(rows, 'type')
    expect(grouped.map((g) => g.groupKey)).toEqual(['application-component', 'business-actor'])
    expect(grouped[0].entities.map((e) => e.id)).toEqual(['a', 'c'])
    expect(grouped[1].entities.map((e) => e.id)).toEqual(['b'])
  })
})

describe('projectionByItemId', () => {
  it('indexes projection items by id, empty map for null projection', () => {
    expect(projectionByItemId(null).size).toBe(0)
    const projection: ViewpointProjection = {
      applied: true,
      target: 'repository',
      items: [{ item_id: 'a', item_kind: 'entity', state: 'visible', membership: 'primary', reasons: [], style: { badges: 'positive' } }],
      stale_pin: false,
      warnings: [],
    }
    const byId = projectionByItemId(projection)
    expect(byId.get('a')?.style.badges).toBe('positive')
  })
})
