import { describe, expect, it } from 'vitest'
import { useForceGraph } from './useForceGraph'

describe('applyGroupClusterLayout', () => {
  it('spreads a multi-group population across more than one Y position', () => {
    const graph = useForceGraph(() => 1200, () => 800)
    const ids = ['alpha', 'beta', 'gamma'].flatMap((group) =>
      Array.from({ length: 6 }, (_, i) => `${group}-${i}`))
    for (const id of ids) graph.addNode({ id, label: id, type: 'X' })

    graph.applyGroupClusterLayout((id) => id.split('-')[0])

    const ys = new Set(graph.nodes.value.map((n) => n.y))
    expect(ys.size).toBeGreaterThan(1)
  })

  it('does not collapse every node onto a single horizontal line', () => {
    const graph = useForceGraph(() => 1200, () => 800)
    const ids = ['alpha', 'beta', 'gamma', 'delta'].flatMap((group) =>
      Array.from({ length: 4 }, (_, i) => `${group}-${i}`))
    for (const id of ids) graph.addNode({ id, label: id, type: 'X' })

    graph.applyGroupClusterLayout((id) => id.split('-')[0])

    const uniqueY = new Set(graph.nodes.value.map((n) => n.y))
    expect(uniqueY.size).toBeGreaterThan(1)
  })

  it('keeps a single small group\'s members near each other rather than spread the full canvas width', () => {
    const graph = useForceGraph(() => 1200, () => 800)
    for (const id of ['solo-0', 'solo-1', 'solo-2']) graph.addNode({ id, label: id, type: 'X' })

    graph.applyGroupClusterLayout(() => 'solo')

    const xs = graph.nodes.value.map((n) => n.x)
    expect(Math.max(...xs) - Math.min(...xs)).toBeLessThan(600)
  })
})
