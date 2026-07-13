import { describe, expect, it } from 'vitest'
import {
  atDepthCap,
  attributeOptions,
  comparatorsFor,
  depthLabel,
  enumChoicesFor,
  valueKindOptions,
} from '../CriteriaTreeBuilder.helpers'
import type { CriteriaCatalog } from '../../../domain'

const CATALOG: CriteriaCatalog = {
  entity_types: ['application-component', 'process'],
  connection_types: ['archimate-serving'],
  specialization_slugs: ['business-process'],
  entity_attribute_types: { risk_score: 'number', lifecycle_stage: 'string' },
  connection_attribute_types: { strength: 'integer' },
  symmetric_connection_types: [],
  reserved_entity_paths: ['id', 'name', 'type', 'specialization', 'group', 'domain', 'subdomain', 'status', 'version'],
  reserved_connection_paths: ['id', 'type', 'specialization'],
  depth_cap: 4,
  entity_type_domains: { 'application-component': 'application', process: 'common' },
}

describe('attributeOptions', () => {
  it('lists reserved entity paths before schema attributes, schema attributes sorted', () => {
    const options = attributeOptions('entity', CATALOG)
    expect(options.slice(0, 9).map((o) => o.path)).toEqual([
      'id', 'name', 'type', 'specialization', 'group', 'domain', 'subdomain', 'status', 'version',
    ])
    expect(options.slice(9).map((o) => o.path)).toEqual(['lifecycle_stage', 'risk_score'])
    expect(options.find((o) => o.path === 'risk_score')?.declaredType).toBe('number')
    expect(options.find((o) => o.path === 'type')?.reserved).toBe(true)
  })

  it('uses connection reserved paths and schema attributes for connection groups', () => {
    const options = attributeOptions('connection', CATALOG)
    expect(options.map((o) => o.path)).toEqual(['id', 'type', 'specialization', 'strength'])
  })
})

describe('comparatorsFor', () => {
  it('excludes numeric comparators for reserved paths', () => {
    const comparators = comparatorsFor({ path: 'status', reserved: true, declaredType: null })
    expect(comparators).not.toContain('gte')
    expect(comparators).toContain('eq')
  })

  it('includes numeric comparators for a numeric schema attribute', () => {
    const comparators = comparatorsFor({ path: 'risk_score', reserved: false, declaredType: 'number' })
    expect(comparators).toContain('gte')
  })

  it('excludes numeric comparators for a string schema attribute', () => {
    const comparators = comparatorsFor({ path: 'lifecycle_stage', reserved: false, declaredType: 'string' })
    expect(comparators).not.toContain('lt')
  })
})

describe('enumChoicesFor', () => {
  it('offers known entity types for the type attribute on an entity group', () => {
    expect(enumChoicesFor('type', 'entity', CATALOG)).toEqual(['application-component', 'process'])
  })

  it('offers known connection types for the type attribute on a connection group', () => {
    expect(enumChoicesFor('type', 'connection', CATALOG)).toEqual(['archimate-serving'])
  })

  it('offers known specialization slugs regardless of group kind', () => {
    expect(enumChoicesFor('specialization', 'entity', CATALOG)).toEqual(['business-process'])
  })

  it('returns null (free-text) for attributes with no enumerable value set', () => {
    expect(enumChoicesFor('risk_score', 'entity', CATALOG)).toBeNull()
    expect(enumChoicesFor('domain', 'entity', CATALOG)).toBeNull()
  })
})

describe('valueKindOptions', () => {
  it('offers literal and self for entity conditions, not source/target', () => {
    const kinds = valueKindOptions('entity').map((o) => o.kind)
    expect(kinds).toEqual(['literal', 'self'])
  })

  it('offers source and target for connection conditions', () => {
    const kinds = valueKindOptions('connection').map((o) => o.kind)
    expect(kinds).toEqual(['literal', 'self', 'source', 'target'])
  })
})

describe('depth meter', () => {
  it('labels nesting as 1-indexed out of the cap', () => {
    expect(depthLabel(0)).toBe('nesting 1 of 4')
    expect(depthLabel(3)).toBe('nesting 4 of 4')
  })

  it('flags the depth cap once nesting would reach it', () => {
    expect(atDepthCap(2)).toBe(false)
    expect(atDepthCap(3)).toBe(true)
  })
})
