import { describe, it, expect } from 'vitest'
import {
  fitViewBox, wrapLabel,
  groupKeyFor, nodeVisualFor, edgeVisualFor, projectionByItemId, edgeStyleKey, buildConnectionStyleIndex,
  buildConnectionSummaryIndex, DERIVED_EDGE_DASH,
  nodeShapePoints, explorationRedirectFor, anchorDistancesFromResult, effectiveExplorationLayout, distanceColor, distanceLegend,
  contrastTextColor,
} from '../GraphExploreView.helpers'
import { tokenColor, tokenShape, tokenIconLetter, tokenEdgeEmphasis, resolveStyleColor } from '../../lib/viewpointStyleTokens'
import type { ViewpointDefinitionEnvelope } from '../../../domain'

const mkEnvelope = (representation: string | null): ViewpointDefinitionEnvelope => ({
  slug: 'application-structure', version: 1, name: 'Application Structure', tier: 'module',
  scope_summary: { unrestricted: true }, query_summary: null, fork_status: null,
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

  it('gives an unstyled derived edge its provenance dash, denser for potential', () => {
    expect(edgeVisualFor(undefined, 'certain').dashArray).toBe(DERIVED_EDGE_DASH.certain)
    expect(edgeVisualFor(undefined, 'potential').dashArray).toBe(DERIVED_EDGE_DASH.potential)
    expect(DERIVED_EDGE_DASH.certain).not.toBe(DERIVED_EDGE_DASH.potential)
  })

  it('lets an authored edge_emphasis dash win over the provenance dash', () => {
    const emphasis = tokenEdgeEmphasis('caution')
    expect(edgeVisualFor({ edge_emphasis: 'caution' }, 'certain').dashArray).toBe(emphasis.dashArray)
  })
})

describe('buildConnectionSummaryIndex', () => {
  it('joins each connection summary onto its source/target/type key', () => {
    const derived = {
      id: 'derived::x', type: 'archimate-serving', source: 'ENT@A', target: 'ENT@B',
      certainty: 'certain' as const, hops: 2, via_connection_ids: ['c1', 'c2'], witness_steps: [],
    }
    const index = buildConnectionSummaryIndex([derived])
    expect(index.get(edgeStyleKey('ENT@A', 'ENT@B', 'archimate-serving'))?.hops).toBe(2)
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
    const connections = [{ id: 'CON@ab', type: 'archimate-serving', source: 'ENT@A', target: 'ENT@B', certainty: null, hops: null, via_connection_ids: [], witness_steps: [] }]
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
    const connections = [{ id: 'CON@ab', type: 'archimate-serving', source: 'ENT@A', target: 'ENT@B', certainty: null, hops: null, via_connection_ids: [], witness_steps: [] }]
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

describe('anchorDistancesFromResult', () => {
  it('maps each ranked entity to its server-computed modeled distance', () => {
    const distances = anchorDistancesFromResult([
      { id: 'a', anchor_modeled_distance: 0 },
      { id: 'b', anchor_modeled_distance: 1 },
      { id: 'c', anchor_modeled_distance: 4 }, // witness-chain length, NOT one traversal step
    ])
    expect(distances.get('a')).toBe(0)
    expect(distances.get('b')).toBe(1)
    expect(distances.get('c')).toBe(4)
  })

  it('leaves unranked entities out of the map instead of defaulting them', () => {
    const distances = anchorDistancesFromResult([
      { id: 'a', anchor_modeled_distance: 0 },
      { id: 'island', anchor_modeled_distance: null },
      { id: 'legacy' },
    ])
    expect(distances.has('island')).toBe(false)
    expect(distances.has('legacy')).toBe(false)
    expect(distances.size).toBe(1)
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
  it('shows the real observed ring set, not a dense 0..max range', () => {
    const legend = distanceLegend([0, 1, 2, 4, 2, 1])
    expect(legend.map((entry) => entry.label)).toEqual(['1 hop', '2 hops', '4 hops'])
    expect(legend[2].color).toBe(tokenColor('heat-far'))
    expect(legend[0].color).toBe(distanceColor(1, 4))
    expect(legend[1].color).toBe(distanceColor(2, 4))
  })

  it('omits the anchor distance (0) — the Anchor chip already names it', () => {
    expect(distanceLegend([0])).toEqual([])
  })

  it('is empty for no observed distances', () => {
    expect(distanceLegend([])).toEqual([])
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

describe('fitViewBox', () => {
  it('bounds every node with padding, aspect-corrected to the container', () => {
    const box = fitViewBox([{ x: 0, y: 0 }, { x: 1000, y: 100 }], 800, 600, 50)
    expect(box.x).toBe(-50)
    expect(box.w).toBe(1100)
    // Content is wider than the container ratio → height is corrected up to match.
    expect(box.h).toBeCloseTo(1100 / (800 / 600))
    // Every node stays inside the box.
    expect(box.y).toBeLessThan(0)
    expect(box.y + box.h).toBeGreaterThan(100)
  })

  it('falls back to the container rect when there is nothing to fit', () => {
    expect(fitViewBox([], 800, 600)).toEqual({ x: 0, y: 0, w: 800, h: 600 })
  })
})

describe('wrapLabel', () => {
  it('keeps short labels on one line', () => {
    expect(wrapLabel('Query Engine')).toEqual(['Query Engine'])
  })

  it('wraps at word boundaries up to two lines', () => {
    expect(wrapLabel('Canonical Per-Repo Artifact Index', 14, 2)).toEqual(['Canonical', 'Per-Repo…'])
  })

  it('ellipsizes when content remains beyond the last line', () => {
    const lines = wrapLabel('Architecture Management Platform Backend Service', 14, 2)
    expect(lines).toHaveLength(2)
    expect(lines[1].endsWith('…')).toBe(true)
  })

  it('hard-truncates a single overlong word', () => {
    const lines = wrapLabel('supercalifragilisticexpialidocious', 14, 2)
    expect(lines[0].length).toBeLessThanOrEqual(14)
    expect(lines[0].endsWith('…')).toBe(true)
  })
})
