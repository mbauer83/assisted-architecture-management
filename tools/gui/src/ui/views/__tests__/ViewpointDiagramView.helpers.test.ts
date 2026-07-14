// @vitest-environment jsdom
//
// jsdom is required: these helpers manipulate real SVG DOM elements (style overlay
// application), which a node environment cannot construct.
import { describe, expect, it } from 'vitest'
import {
  applyEdgeHighlightOverlay, applyNodeColorOverlay, markDerivedConnections, projectionByItemId,
  toDiagramConnectionStub, toEntitySummaryStub,
} from '../ViewpointDiagramView.helpers'
import type { ConnectionItemSummary, DiagramConnection, EntityItemSummary, ProjectedOccurrence } from '../../../domain'

const SVG_NS = 'http://www.w3.org/2000/svg'
const svgEl = (tag: string): SVGElement => document.createElementNS(SVG_NS, tag)

const groupWith = (childTag: string): { group: SVGElement; child: SVGElement } => {
  const group = svgEl('g')
  const child = svgEl(childTag)
  group.appendChild(child)
  return { group, child }
}

describe('toEntitySummaryStub', () => {
  const entity: EntityItemSummary = {
    id: 'APC@1.EntSch.a', name: 'Alpha', type: 'application-component',
    specialization_slugs: [], group: 'uncategorized', membership: 'primary',
  }

  it('falls back to the raw artifact id when no alias lookup is given', () => {
    const stub = toEntitySummaryStub(entity)
    expect(stub.artifact_id).toBe('APC@1.EntSch.a')
    expect(stub.display_alias).toBe('APC@1.EntSch.a')
    expect(stub.name).toBe('Alpha')
    expect(stub.artifact_type).toBe('application-component')
  })

  it('resolves display_alias from the given entity_aliases lookup — the rendered SVG PlantUML alias, not the artifact id', () => {
    const aliasById = new Map([['APC@1.EntSch.a', 'JNA_zGOowi']])
    expect(toEntitySummaryStub(entity, aliasById).display_alias).toBe('JNA_zGOowi')
  })
})

describe('toDiagramConnectionStub', () => {
  const conn: ConnectionItemSummary = {
    id: 'c1', type: 'serving', source: 'a', target: 'b', certainty: null, hops: null, via_connection_ids: [],
  }

  it('falls back to the raw source/target artifact ids when no alias lookup is given', () => {
    const stub = toDiagramConnectionStub(conn)
    expect(stub.artifact_id).toBe('c1')
    expect(stub.source_alias).toBe('a')
    expect(stub.target_alias).toBe('b')
    expect(stub.conn_type).toBe('serving')
  })

  it('resolves source_alias/target_alias from the given alias lookup', () => {
    const aliasById = new Map([['a', 'ent0042'], ['b', 'ent0099']])
    const stub = toDiagramConnectionStub(conn, new Map(), aliasById)
    expect(stub.source_alias).toBe('ent0042')
    expect(stub.target_alias).toBe('ent0099')
  })

  it('falls back to the raw id when no name lookup is given', () => {
    expect(toDiagramConnectionStub(conn)).toMatchObject({ source_name: 'a', target_name: 'b' })
  })

  it('resolves source_name/target_name from the given lookup', () => {
    const nameById = new Map([['a', 'Alpha'], ['b', 'Beta']])
    expect(toDiagramConnectionStub(conn, nameById)).toMatchObject({ source_name: 'Alpha', target_name: 'Beta' })
  })

  it('carries certainty/hops/via_connection_ids straight through for a derived connection', () => {
    const derived: ConnectionItemSummary = {
      id: 'derived::archimate-serving::x', type: 'archimate-serving', source: 'a', target: 'b',
      certainty: 'potential', hops: 3, via_connection_ids: ['CON@1', 'CON@2', 'CON@3'],
    }
    const stub = toDiagramConnectionStub(derived)
    expect(stub.certainty).toBe('potential')
    expect(stub.hops).toBe(3)
    expect(stub.via_connection_ids).toEqual(['CON@1', 'CON@2', 'CON@3'])
  })

  it('carries a real (non-derived) connection\'s null certainty/hops and empty via_connection_ids through unchanged', () => {
    const stub = toDiagramConnectionStub(conn)
    expect(stub.certainty).toBeNull()
    expect(stub.hops).toBeNull()
    expect(stub.via_connection_ids).toEqual([])
  })
})

describe('markDerivedConnections', () => {
  const stubConnection = (overrides: Partial<DiagramConnection>): DiagramConnection => ({
    artifact_id: 'c1', source: 'a', target: 'b', conn_type: 'serving',
    version: '', status: '', path: '', content_text: '', source_name: 'a', target_name: 'b',
    source_alias: null, target_alias: null, certainty: null, hops: null, via_connection_ids: [], ...overrides,
  })

  it('sets data-certainty on the SVG elements matched to a derived connection', () => {
    const { group } = groupWith('path')
    const edges = new Map([['c1', [group]]])
    markDerivedConnections(edges, [stubConnection({ artifact_id: 'c1', certainty: 'potential' })])
    expect(group.getAttribute('data-certainty')).toBe('potential')
  })

  it('leaves a real (non-derived) connection\'s elements untouched', () => {
    const { group } = groupWith('path')
    const edges = new Map([['c1', [group]]])
    markDerivedConnections(edges, [stubConnection({ artifact_id: 'c1', certainty: null })])
    expect(group.hasAttribute('data-certainty')).toBe(false)
  })

  it('ignores an edge whose connection id has no matching entry at all', () => {
    const { group } = groupWith('path')
    const edges = new Map([['unmatched', [group]]])
    markDerivedConnections(edges, [stubConnection({ artifact_id: 'c1', certainty: 'certain' })])
    expect(group.hasAttribute('data-certainty')).toBe(false)
  })
})

describe('applyNodeColorOverlay', () => {
  it('sets an important stroke override on shape children when a token is given', () => {
    const { group, child } = groupWith('rect')
    applyNodeColorOverlay([group], 'critical')
    expect(child.style.getPropertyValue('stroke')).toBe('rgb(220, 38, 38)')
    expect(child.style.getPropertyPriority('stroke')).toBe('important')
    expect(child.style.getPropertyValue('stroke-width')).toBe('3')
  })

  it('never touches the shape\'s native stroke when no token is given — PlantUML relies on it for visibility', () => {
    const { group, child } = groupWith('polygon')
    child.setAttribute('style', 'stroke:#181818;stroke-width:1;')
    applyNodeColorOverlay([group], undefined)
    expect(child.style.getPropertyValue('stroke')).toBe('rgb(24, 24, 24)')
    expect(child.style.getPropertyValue('stroke-width')).toBe('1')
  })

  it('only targets rect/polygon/path descendants, not the group itself', () => {
    const { group } = groupWith('text')
    applyNodeColorOverlay([group], 'critical')
    expect(group.style.getPropertyValue('stroke')).toBe('')
  })
})

describe('applyEdgeHighlightOverlay', () => {
  it('applies color and the token-mapped stroke-width/dash pattern', () => {
    const { group, child } = groupWith('path')
    applyEdgeHighlightOverlay([group], 'caution', 'caution')
    expect(child.style.getPropertyValue('stroke')).toBe('rgb(217, 119, 6)')
    expect(child.style.getPropertyValue('stroke-width')).toBe('2.5')
    expect(child.style.getPropertyValue('stroke-dasharray')).toBe('6 3')
  })

  it('sets no dash pattern when the emphasis token has none', () => {
    const { group, child } = groupWith('path')
    applyEdgeHighlightOverlay([group], undefined, 'emphasis')
    expect(child.style.getPropertyValue('stroke-dasharray')).toBe('')
  })

  it('never touches the shape\'s native stroke when neither color nor emphasis is given — a connector line has no fill and relies entirely on its native stroke for visibility', () => {
    const { group, child } = groupWith('path')
    child.setAttribute('style', 'stroke:#181818;stroke-width:1;')
    applyEdgeHighlightOverlay([group], undefined, undefined)
    expect(child.style.getPropertyValue('stroke')).toBe('rgb(24, 24, 24)')
    expect(child.style.getPropertyValue('stroke-width')).toBe('1')
  })
})

describe('projectionByItemId', () => {
  it('indexes projected occurrences by item id', () => {
    const items: ProjectedOccurrence[] = [
      { item_id: 'a', item_kind: 'entity', state: 'visible', membership: 'primary', reasons: [], style: { node_color: 'positive' } },
    ]
    expect(projectionByItemId(items).get('a')?.style.node_color).toBe('positive')
  })
})
