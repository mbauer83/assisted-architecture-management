import { describe, expect, it } from 'vitest'
import { endpointValue, literalValue, mkGroup, selfValue } from './viewpointCriteria'
import {
  connectionSelectionFromMapping,
  connectionSelectionToMapping,
  groupFromMapping,
  groupToMapping,
  neighborInclusionFromMapping,
  neighborInclusionToMapping,
} from './viewpointCriteriaSerialization'

describe('condition value refs', () => {
  it('serializes a literal value as a plain scalar', () => {
    const group = mkGroup('entity')
    group.children = [{ kind: 'condition', id: 'c1', attribute: 'status', comparator: 'eq', value: literalValue('active'), negate: false }]
    expect(groupToMapping(group).children).toEqual([{ kind: 'condition', attribute: 'status', comparator: 'eq', value: 'active' }])
  })

  it('serializes a self attribute reference as {from: self, attribute}', () => {
    const group = mkGroup('entity')
    group.children = [{ kind: 'condition', id: 'c1', attribute: 'end_date', comparator: 'gte', value: selfValue('start_date'), negate: false }]
    expect(groupToMapping(group).children).toEqual([
      { kind: 'condition', attribute: 'end_date', comparator: 'gte', value: { from: 'self', attribute: 'start_date' } },
    ])
  })

  it('serializes an endpoint attribute reference as {from: source|target, attribute}', () => {
    const group = mkGroup('connection')
    group.children = [{ kind: 'condition', id: 'c1', attribute: 'strength', comparator: 'gte', value: endpointValue('target', 'threshold'), negate: false }]
    expect(groupToMapping(group).children).toEqual([
      { kind: 'condition', attribute: 'strength', comparator: 'gte', value: { from: 'target', attribute: 'threshold' } },
    ])
  })

  it('round-trips a self reference through from-mapping', () => {
    const parsed = groupFromMapping(
      { kind: 'group', conjunction: 'and', children: [{ kind: 'condition', attribute: 'end_date', comparator: 'gte', value: { from: 'self', attribute: 'start_date' } }] },
      'entity',
    )
    const condition = parsed.children[0]
    expect(condition.kind).toBe('condition')
    expect(condition.kind === 'condition' && condition.value).toEqual(selfValue('start_date'))
  })

  it('omits negate when false and includes it when true', () => {
    const group = mkGroup('entity')
    group.children = [
      { kind: 'condition', id: 'c1', attribute: 'type', comparator: 'eq', value: literalValue('x'), negate: false },
      { kind: 'condition', id: 'c2', attribute: 'type', comparator: 'eq', value: literalValue('y'), negate: true },
    ]
    const mapped = groupToMapping(group).children as Record<string, unknown>[]
    expect(mapped[0]).not.toHaveProperty('negate')
    expect(mapped[1].negate).toBe(true)
  })
})

describe('incident conditions', () => {
  it('omits direction when either, includes it otherwise', () => {
    const outgoing = groupFromMapping(
      { kind: 'group', conjunction: 'and', children: [{ kind: 'incident', direction: 'outgoing' }] },
      'entity',
    )
    expect(groupToMapping(outgoing).children).toEqual([{ kind: 'incident', direction: 'outgoing' }])

    const either = groupFromMapping({ kind: 'group', conjunction: 'and', children: [{ kind: 'incident' }] }, 'entity')
    expect(groupToMapping(either).children).toEqual([{ kind: 'incident' }])
  })

  it('nests connection_criteria and endpoint_criteria', () => {
    const raw = {
      kind: 'group', conjunction: 'and',
      children: [{
        kind: 'incident',
        connection_criteria: { kind: 'group', conjunction: 'and', children: [{ kind: 'condition', attribute: 'type', comparator: 'eq', value: 'archimate-serving' }] },
        endpoint_criteria: { kind: 'group', conjunction: 'and', children: [{ kind: 'condition', attribute: 'type', comparator: 'eq', value: 'process' }] },
      }],
    }
    const parsed = groupFromMapping(raw, 'entity')
    expect(groupToMapping(parsed)).toEqual(raw)
  })
})

describe('neighbor inclusion', () => {
  it('round-trips direction and both criteria legs', () => {
    const raw = {
      direction: 'outgoing',
      connection_criteria: { kind: 'group', conjunction: 'and', children: [{ kind: 'condition', attribute: 'type', comparator: 'eq', value: 'archimate-serving' }] },
      neighbor_criteria: { kind: 'group', conjunction: 'and', children: [{ kind: 'condition', attribute: 'type', comparator: 'eq', value: 'process' }] },
    }
    const parsed = neighborInclusionFromMapping(raw)
    expect(neighborInclusionToMapping(parsed)).toEqual(raw)
  })
})

describe('connection selection', () => {
  it('omits enabled when true and the default empty criteria', () => {
    const selection = connectionSelectionFromMapping(null)
    expect(connectionSelectionToMapping(selection)).toEqual({})
  })

  it('serializes enabled:false and non-default criteria', () => {
    const raw = {
      enabled: false,
      criteria: { kind: 'group', conjunction: 'and', children: [{ kind: 'condition', attribute: 'type', comparator: 'eq', value: 'archimate-serving' }] },
    }
    const parsed = connectionSelectionFromMapping(raw)
    expect(connectionSelectionToMapping(parsed)).toEqual(raw)
  })
})
