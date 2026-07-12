import { describe, expect, it } from 'vitest'
import {
  csvToList, firstErrorNodeId, formatPreviewCounts, formatScopeSummary, isSemanticEdit, listToCsv,
} from '../ViewpointsManagementView.helpers'
import { mkDefinitionDraft } from '../../../domain/viewpointDefinitionDraft'
import type { ViewpointValidationIssue } from '../../../domain'

describe('isSemanticEdit', () => {
  it('is false when only descriptive fields change', () => {
    const original = mkDefinitionDraft()
    original.slug = 'x'
    original.name = 'X'
    const current = { ...original, description: 'now described', rationale: 'because' }
    expect(isSemanticEdit(current, original)).toBe(false)
  })

  it('is true when scope changes', () => {
    const original = mkDefinitionDraft()
    original.slug = 'x'
    const current = { ...original, scope: { entityTypes: ['application-component'], connectionTypes: null } }
    expect(isSemanticEdit(current, original)).toBe(true)
  })

  it('is true when the query criteria changes', () => {
    const original = mkDefinitionDraft()
    original.slug = 'x'
    const current = structuredClone(original)
    current.query!.entityCriteria.children.push({
      kind: 'condition', id: 'n999', attribute: 'status', comparator: 'eq', value: { kind: 'literal', literal: 'active' }, negate: false,
    })
    expect(isSemanticEdit(current, original)).toBe(true)
  })
})

describe('csv helpers', () => {
  it('round-trips a comma-separated list, trimming whitespace', () => {
    expect(csvToList('a, b ,  c')).toEqual(['a', 'b', 'c'])
    expect(listToCsv(['a', 'b', 'c'])).toBe('a, b, c')
  })

  it('drops empty entries', () => {
    expect(csvToList('a, , b,')).toEqual(['a', 'b'])
  })
})

describe('formatScopeSummary', () => {
  it('reports unrestricted', () => {
    expect(formatScopeSummary({ unrestricted: true })).toBe('unrestricted')
  })

  it('lists entity and connection types when restricted', () => {
    expect(formatScopeSummary({ unrestricted: false, entity_types: ['application-component'] }))
      .toBe('entities: application-component')
    expect(formatScopeSummary({ unrestricted: false, entity_types: ['a'], connection_types: ['b'] }))
      .toBe('entities: a; connections: b')
  })
})

describe('formatPreviewCounts', () => {
  it('is empty when there is no preview result yet', () => {
    expect(formatPreviewCounts(null)).toBe('')
  })

  it('pluralizes entity/connection nouns correctly', () => {
    expect(formatPreviewCounts({ total_entity_count: 1, total_connection_count: 1 })).toBe('1 entity / 1 connection')
    expect(formatPreviewCounts({ total_entity_count: 0, total_connection_count: 5 })).toBe('0 entities / 5 connections')
    expect(formatPreviewCounts({ total_entity_count: 3, total_connection_count: 2 })).toBe('3 entities / 2 connections')
  })
})

describe('firstErrorNodeId', () => {
  it('is null when there are no error-severity issues', () => {
    const draft = mkDefinitionDraft()
    const warningOnly: ViewpointValidationIssue[] = [
      { severity: 'warning', code: 'w', path: '/query/entity_criteria', message: 'm', expected: null, found: null },
    ]
    expect(firstErrorNodeId(warningOnly, draft)).toBeNull()
  })

  it('maps the first error issue to its builder node, ignoring a leading warning', () => {
    const draft = mkDefinitionDraft()
    const entityCriteriaId = draft.query!.entityCriteria.id
    const issues: ViewpointValidationIssue[] = [
      { severity: 'warning', code: 'w', path: '/slug', message: 'descriptive', expected: null, found: null },
      { severity: 'error', code: 'e', path: '/query/entity_criteria', message: 'bad criteria', expected: null, found: null },
    ]
    expect(firstErrorNodeId(issues, draft)).toBe(entityCriteriaId)
  })
})
