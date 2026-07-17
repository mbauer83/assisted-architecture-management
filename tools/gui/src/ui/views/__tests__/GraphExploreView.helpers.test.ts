import { describe, it, expect } from 'vitest'
import {
  groupKeyFor, nodeVisualFor, edgeVisualFor, projectionByItemId, edgeStyleKey, buildConnectionStyleIndex,
  nodeShapePoints, explorationRedirectFor, hopDistances, effectiveExplorationLayout, distanceColor, distanceLegend,
  contrastTextColor,
} from '../GraphExploreView.helpers'
import { tokenColor, tokenShape, tokenIconLetter, tokenEdgeEmphasis, resolveStyleColor } from '../../lib/viewpointStyleTokens'
import type { ViewpointDefinitionEnvelope } from '../../../domain'

const mkEnvelope = (representation: string | null): ViewpointDefinitionEnvelope => ({
  slug: 'application-structure', version: 1, name: 'Application Structure', tier: 'module',
  scope_summary: { unrestricted: true }, query_summary: null,
  presentation: representation === null ? undefined : { representation },
})

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

describe('explorationRedirectFor', () => {
  it('stays put (returns null) for an exploration-representation definition', () => {
    expect(explorationRedirectFor(mkEnvelope('exploration'))).toBeNull()
  })

  it('stays put when the definition carries no presentation at all', () => {
    expect(explorationRedirectFor(mkEnvelope(null))).toBeNull()
  })

  it('redirects to the diagram surface for a diagram-representation definition', () => {
    expect(explorationRedirectFor(mkEnvelope('diagram'))).toEqual({
      path: '/viewpoints/diagram', query: { viewpoint: 'application-structure' },
    })
  })

  it('redirects to the matrix/table surfaces for matrix/table representations', () => {
    expect(explorationRedirectFor(mkEnvelope('matrix'))?.path).toBe('/viewpoints/matrix')
    expect(explorationRedirectFor(mkEnvelope('table'))?.path).toBe('/entities')
  })

  it('stays put when no envelope was found for the selected slug', () => {
    expect(explorationRedirectFor(undefined)).toBeNull()
  })
})

describe('hopDistances', () => {
  const edge = (source: string, target: string) => ({ source, target })

  it('computes BFS depth from a single anchor over undirected edges', () => {
    const distances = hopDistances(
      ['a'],
      [edge('a', 'b'), edge('c', 'b'), edge('c', 'd')],
      ['a', 'b', 'c', 'd'],
    )
    expect(distances.get('a')).toBe(0)
    expect(distances.get('b')).toBe(1)
    expect(distances.get('c')).toBe(2) // reached against the c→b edge direction
    expect(distances.get('d')).toBe(3)
  })

  it('takes the shortest path when several exist', () => {
    const distances = hopDistances(
      ['a'],
      [edge('a', 'b'), edge('b', 'c'), edge('c', 'd'), edge('a', 'd')],
      ['a', 'b', 'c', 'd'],
    )
    expect(distances.get('d')).toBe(1)
    expect(distances.get('c')).toBe(2)
  })

  it('is multi-source: each node gets the distance to its nearest anchor', () => {
    const distances = hopDistances(
      ['a', 'z'],
      [edge('a', 'b'), edge('b', 'c'), edge('c', 'z')],
      ['a', 'b', 'c', 'z'],
    )
    expect(distances.get('a')).toBe(0)
    expect(distances.get('z')).toBe(0)
    expect(distances.get('b')).toBe(1)
    expect(distances.get('c')).toBe(1)
  })

  it('omits unreachable nodes from the map', () => {
    const distances = hopDistances(['a'], [edge('a', 'b')], ['a', 'b', 'island'])
    expect(distances.has('island')).toBe(false)
    expect(distances.size).toBe(2)
  })

  it('ignores anchors and edge endpoints outside the node population', () => {
    const distances = hopDistances(['ghost', 'a'], [edge('a', 'ghost'), edge('a', 'b')], ['a', 'b'])
    expect(distances.get('a')).toBe(0)
    expect(distances.get('b')).toBe(1)
    expect(distances.has('ghost')).toBe(false)
  })
})

describe('effectiveExplorationLayout', () => {
  it('lets an explicit user override win over everything', () => {
    expect(effectiveExplorationLayout('force', 'radial', true)).toBe('force')
    expect(effectiveExplorationLayout('clusters', undefined, true)).toBe('clusters')
  })

  it('uses the definition display option when the override is auto', () => {
    expect(effectiveExplorationLayout('auto', 'force', true)).toBe('force')
    expect(effectiveExplorationLayout('auto', 'clusters', true)).toBe('clusters')
  })

  it('ignores an unknown or absent display option', () => {
    expect(effectiveExplorationLayout('auto', 'spiral', false)).toBe('clusters')
    expect(effectiveExplorationLayout('auto', undefined, false)).toBe('clusters')
  })

  it('defaults an anchored execution to radial and an unanchored one to clusters', () => {
    expect(effectiveExplorationLayout('auto', undefined, true)).toBe('radial')
    expect(effectiveExplorationLayout('auto', undefined, false)).toBe('clusters')
  })
})

describe('contrastTextColor', () => {
  it('uses white text on dark fills and dark ink on light fills', () => {
    expect(contrastTextColor('#dc2626')).toBe('#ffffff')
    expect(contrastTextColor('#4f6d83')).toBe('#ffffff')
    expect(contrastTextColor('#fbbf24')).toBe('#252327')
    expect(contrastTextColor('#ffffff')).toBe('#252327')
  })

  it('defaults to dark ink for non-hex input', () => {
    expect(contrastTextColor('neutral')).toBe('#252327')
  })
})

describe('distanceColor', () => {
  it('maps depth 0 to the near endpoint and max depth to the far endpoint', () => {
    expect(distanceColor(0, 4)).toBe(tokenColor('heat-near'))
    expect(distanceColor(4, 4)).toBe(tokenColor('heat-far'))
  })

  it('uses the near endpoint when everything is at depth 0', () => {
    expect(distanceColor(0, 0)).toBe(tokenColor('heat-near'))
  })

  it('interpolates intermediate depths on the heat-near→heat-far scale', () => {
    expect(distanceColor(1, 2)).toBe(resolveStyleColor({ position: 0.5, tokens: ['heat-near', 'heat-far'] }))
    expect(distanceColor(1, 2)).not.toBe(tokenColor('heat-near'))
    expect(distanceColor(1, 2)).not.toBe(tokenColor('heat-far'))
  })
})

describe('distanceLegend', () => {
  it('produces one chip per hop count with the node colors', () => {
    const legend = distanceLegend(2)
    expect(legend.map((entry) => entry.label)).toEqual(['0 hops', '1 hop', '2 hops'])
    expect(legend[0].color).toBe(tokenColor('heat-near'))
    expect(legend[2].color).toBe(tokenColor('heat-far'))
    expect(legend[1].color).toBe(distanceColor(1, 2))
  })

  it('shows a single near-colored chip for a depth-0-only population', () => {
    expect(distanceLegend(0)).toEqual([{ label: '0 hops', color: tokenColor('heat-near') }])
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
