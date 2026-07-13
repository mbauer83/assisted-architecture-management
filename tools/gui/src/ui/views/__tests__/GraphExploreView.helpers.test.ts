import { describe, it, expect } from 'vitest'
import {
  groupKeyFor, nodeVisualFor, edgeVisualFor, projectionByItemId, edgeStyleKey, buildConnectionStyleIndex,
  nodeShapePoints,
} from '../GraphExploreView.helpers'
import { tokenColor, tokenShape, tokenIconLetter, tokenEdgeEmphasis } from '../../lib/viewpointStyleTokens'

const entity = { type: 'application-component', group: 'core', specialization_slugs: ['custom-spec'] }

describe('groupKeyFor', () => {
  it('groups by group when group_by is "group"', () => {
    expect(groupKeyFor(entity, 'group')).toBe('core')
  })

  it('groups by first specialization slug when group_by is "specialization"', () => {
    expect(groupKeyFor(entity, 'specialization')).toBe('custom-spec')
  })

  it('falls back to "(none)" when specialization requested but absent', () => {
    expect(groupKeyFor({ ...entity, specialization_slugs: [] }, 'specialization')).toBe('(none)')
  })

  it('groups by type for "type", null, and any unresolvable attribute path', () => {
    expect(groupKeyFor(entity, 'type')).toBe('application-component')
    expect(groupKeyFor(entity, null)).toBe('application-component')
    expect(groupKeyFor(entity, 'some.custom.attribute')).toBe('application-component')
  })
})

describe('nodeVisualFor', () => {
  it('falls back to the domain color and default shape/icon when unstyled', () => {
    expect(nodeVisualFor(undefined, '#abcabc')).toEqual({ color: '#abcabc', shape: 'circle', iconLetter: null })
  })

  it('resolves node_color/node_shape/node_icon from the style map', () => {
    const visual = nodeVisualFor({ node_color: 'critical', node_shape: 'critical', node_icon: 'critical' }, '#abcabc')
    expect(visual).toEqual({
      color: tokenColor('critical'), shape: tokenShape('critical'), iconLetter: tokenIconLetter('critical'),
    })
  })
})

describe('edgeVisualFor', () => {
  it('returns all-null (default edge rendering) when unstyled', () => {
    expect(edgeVisualFor(undefined)).toEqual({ stroke: null, strokeWidth: null, dashArray: undefined })
  })

  it('resolves edge_color/edge_emphasis from the style map', () => {
    const visual = edgeVisualFor({ edge_color: 'caution', edge_emphasis: 'caution' })
    const emphasis = tokenEdgeEmphasis('caution')
    expect(visual).toEqual({ stroke: tokenColor('caution'), strokeWidth: emphasis.strokeWidth, dashArray: emphasis.dashArray })
  })

  it('resolves edge_color independently of edge_emphasis', () => {
    expect(edgeVisualFor({ edge_color: 'positive' })).toEqual({
      stroke: tokenColor('positive'), strokeWidth: null, dashArray: undefined,
    })
  })
})

describe('projectionByItemId', () => {
  it('indexes items by item_id', () => {
    const projection = {
      applied: true, target: 'repository' as const,
      items: [
        { item_id: 'ENT@A', item_kind: 'entity' as const, state: 'visible' as const, membership: 'primary' as const, reasons: [], style: { node_color: 'positive' } },
      ],
    }
    const byId = projectionByItemId(projection)
    expect(byId.get('ENT@A')?.style).toEqual({ node_color: 'positive' })
  })

  it('returns an empty map for a null projection', () => {
    expect(projectionByItemId(null).size).toBe(0)
  })
})

describe('buildConnectionStyleIndex', () => {
  it('joins a connection style back onto its source/target/type key', () => {
    const connections = [{ id: 'CON@ab', type: 'archimate-serving', source: 'ENT@A', target: 'ENT@B', certainty: null, hops: null, via_connection_ids: [] }]
    const projection = {
      applied: true, target: 'repository' as const,
      items: [
        {
          item_id: 'CON@ab', item_kind: 'connection' as const, state: 'visible' as const,
          membership: 'primary' as const, reasons: [], style: { edge_color: 'critical' },
        },
      ],
    }
    const index = buildConnectionStyleIndex(connections, projection)
    expect(index.get(edgeStyleKey('ENT@A', 'ENT@B', 'archimate-serving'))).toEqual({ edge_color: 'critical' })
  })

  it('omits connections absent from the projection', () => {
    const connections = [{ id: 'CON@ab', type: 'archimate-serving', source: 'ENT@A', target: 'ENT@B', certainty: null, hops: null, via_connection_ids: [] }]
    expect(buildConnectionStyleIndex(connections, null).size).toBe(0)
  })
})

describe('nodeShapePoints', () => {
  it('produces a distinct point count per shape', () => {
    expect(nodeShapePoints('triangle', 24).split(' ')).toHaveLength(3)
    expect(nodeShapePoints('diamond', 24).split(' ')).toHaveLength(4)
    expect(nodeShapePoints('square', 24).split(' ')).toHaveLength(4)
    expect(nodeShapePoints('circle', 24).split(' ')).toHaveLength(24)
  })

  it('gives diamond and square the same vertex count but a different orientation', () => {
    expect(nodeShapePoints('diamond', 24)).not.toBe(nodeShapePoints('square', 24))
  })
})
