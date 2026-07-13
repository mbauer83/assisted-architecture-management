// @vitest-environment jsdom
//
// jsdom is required: these helpers manipulate real SVG DOM elements (style overlay
// application), which a node environment cannot construct.
import { describe, expect, it } from 'vitest'
import {
  applyEdgeHighlightOverlay, applyNodeColorOverlay, projectionByItemId, toDiagramConnectionStub, toEntitySummaryStub,
} from '../ViewpointDiagramView.helpers'
import type { ConnectionItemSummary, EntityItemSummary, ProjectedOccurrence } from '../../../domain'

const SVG_NS = 'http://www.w3.org/2000/svg'
const svgEl = (tag: string): SVGElement => document.createElementNS(SVG_NS, tag)

const groupWith = (childTag: string): { group: SVGElement; child: SVGElement } => {
  const group = svgEl('g')
  const child = svgEl(childTag)
  group.appendChild(child)
  return { group, child }
}

describe('toEntitySummaryStub', () => {
  it('carries artifact_id/name/type and sets display_alias to the artifact id', () => {
    const entity: EntityItemSummary = {
      id: 'APC@1.EntSch.a', name: 'Alpha', type: 'application-component',
      specialization_slugs: [], group: 'uncategorized', membership: 'primary',
    }
    const stub = toEntitySummaryStub(entity)
    expect(stub.artifact_id).toBe('APC@1.EntSch.a')
    expect(stub.display_alias).toBe('APC@1.EntSch.a')
    expect(stub.name).toBe('Alpha')
    expect(stub.artifact_type).toBe('application-component')
  })
})

describe('toDiagramConnectionStub', () => {
  it('sets source_alias/target_alias to the source/target artifact ids', () => {
    const conn: ConnectionItemSummary = {
      id: 'c1', type: 'serving', source: 'a', target: 'b', certainty: null, hops: null, via_connection_ids: [],
    }
    const stub = toDiagramConnectionStub(conn)
    expect(stub.artifact_id).toBe('c1')
    expect(stub.source_alias).toBe('a')
    expect(stub.target_alias).toBe('b')
    expect(stub.conn_type).toBe('serving')
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

  it('clears any override when no token is given', () => {
    const { group, child } = groupWith('polygon')
    applyNodeColorOverlay([group], 'positive')
    applyNodeColorOverlay([group], undefined)
    expect(child.style.getPropertyValue('stroke')).toBe('')
    expect(child.style.getPropertyValue('stroke-width')).toBe('')
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

  it('clears the dash pattern when the emphasis token has none', () => {
    const { group, child } = groupWith('path')
    applyEdgeHighlightOverlay([group], undefined, 'caution')
    applyEdgeHighlightOverlay([group], undefined, 'emphasis')
    expect(child.style.getPropertyValue('stroke-dasharray')).toBe('')
  })

  it('leaves stroke untouched when no color token is given', () => {
    const { group, child } = groupWith('path')
    applyEdgeHighlightOverlay([group], undefined, undefined)
    expect(child.style.getPropertyValue('stroke')).toBe('')
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
