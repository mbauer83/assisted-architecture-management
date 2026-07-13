import { hierarchy } from 'd3-hierarchy'
import type { GraphEdge, GraphNode } from './useForceGraph'

/** Cluster/dendrogram layout helpers for `useForceGraph` — split into their own module
 * purely to keep `useForceGraph.ts` under the project's per-file line limit; every export
 * here is pure (nodes/edges/viewport passed in, never read from a shared composable
 * closure) so it needs no Vue reactivity of its own. */

interface TreeNode { id: string; children?: TreeNode[] }
interface ClusterBox { ids: string[]; cols: number; cellW: number; cellH: number; width: number; height: number }
type PosMap = Map<string, { x: number; y: number }>

const estimateNodeWidth = (nodes: readonly GraphNode[], id: string): number => {
  const node = nodes.find((n) => n.id === id)
  const label = node?.label ?? id
  return Math.max(140, 44 + label.length * 1.5)
}

const computeTreeMetrics = (
  nodes: readonly GraphNode[],
  node: TreeNode,
  depth: number,
  metrics: Map<string, { depth: number; width: number }>,
): number => {
  const children = node.children ?? []
  const childWidths = children.map((child) => computeTreeMetrics(nodes, child, depth + 1, metrics))
  const siblingGap = Math.max(36, Math.max(0, ...children.map((child) => estimateNodeWidth(nodes, child.id) * 0.15)))
  const subtreeWidth = children.length
    ? Math.max(
        estimateNodeWidth(nodes, node.id),
        childWidths.reduce((sum, width) => sum + width, 0) + siblingGap * (children.length - 1),
      )
    : estimateNodeWidth(nodes, node.id)
  metrics.set(node.id, { depth, width: subtreeWidth })
  return subtreeWidth
}

const assignTreePositions = (
  nodes: readonly GraphNode[],
  node: TreeNode,
  left: number,
  metrics: Map<string, { depth: number; width: number }>,
  posMap: PosMap,
  levelGap: number,
  topPad: number,
) => {
  const metric = metrics.get(node.id)
  if (!metric) return
  const children = node.children ?? []
  const x = left + metric.width / 2
  const y = topPad + metric.depth * levelGap
  posMap.set(node.id, { x, y })

  if (!children.length) return

  const siblingGap = Math.max(36, Math.max(0, ...children.map((child) => estimateNodeWidth(nodes, child.id) * 0.35)))
  let cursor = left
  for (const child of children) {
    const childMetric = metrics.get(child.id)
    if (!childMetric) continue
    assignTreePositions(nodes, child, cursor, metrics, posMap, levelGap, topPad)
    cursor += childMetric.width + siblingGap
  }
}

export const buildTree = (edges: readonly GraphEdge[], rootId: string): TreeNode => {
  const adj = new Map<string, string[]>()
  for (const e of edges) {
    if (!adj.has(e.source)) adj.set(e.source, [])
    if (!adj.has(e.target)) adj.set(e.target, [])
    adj.get(e.source)!.push(e.target)
    adj.get(e.target)!.push(e.source)
  }
  const visited = new Set<string>()
  const walk = (id: string): TreeNode => {
    visited.add(id)
    const kids = (adj.get(id) ?? []).filter((c) => !visited.has(c)).map(walk)
    return kids.length ? { id, children: kids } : { id }
  }
  return walk(rootId)
}

/** Buckets the current node set by `groupOf(id)` and sizes each bucket as its own
 *  roughly-square grid of cells — the member layout a group gets once it's placed. */
export const buildClusterBoxes = (nodes: readonly GraphNode[], groupOf: (id: string) => string): ClusterBox[] => {
  const groups = new Map<string, string[]>()
  for (const n of nodes) {
    const key = groupOf(n.id)
    if (!groups.has(key)) groups.set(key, [])
    groups.get(key)!.push(n.id)
  }
  const sortedGroups = [...groups.entries()].sort(([a], [b]) => a.localeCompare(b))
  return sortedGroups.map(([, ids]) => {
    const cellW = Math.max(140, ...ids.map((id) => estimateNodeWidth(nodes, id))) + 24
    const cellH = 90
    const cols = Math.max(1, Math.ceil(Math.sqrt(ids.length)))
    const rows = Math.ceil(ids.length / cols)
    return { ids, cellW, cellH, cols, width: cols * cellW, height: rows * cellH }
  })
}

/** Shelf-packs each group's box left to right, wrapping to a new row once the row
 *  outgrows a roughly-square target width — a group never shares a row-band with so many
 *  neighbours that it gets squeezed onto one axis, which is what a depth-keyed dendrogram
 *  layout did here previously: every leaf entity sat at the same tree depth regardless of
 *  its group, so they all collapsed onto one shared Y and only spread out along X. */
export const layoutGroupClusters = (
  boxes: readonly ClusterBox[],
  width: number,
  height: number,
): { posMap: PosMap; cx: number; cy: number } => {
  const leftPad = 140
  const topPad = 110
  const groupGap = 80
  const totalArea = boxes.reduce((sum, box) => sum + box.width * box.height, 0)
  const targetRowWidth = Math.max(width, Math.sqrt(totalArea) * 1.4)

  const posMap: PosMap = new Map()
  let rowX = leftPad
  let rowY = topPad
  let rowHeight = 0
  let maxX = leftPad
  for (const box of boxes) {
    if (rowX > leftPad && rowX + box.width > targetRowWidth) {
      rowX = leftPad
      rowY += rowHeight + groupGap
      rowHeight = 0
    }
    box.ids.forEach((id, i) => {
      const col = i % box.cols
      const row = Math.floor(i / box.cols)
      posMap.set(id, { x: rowX + col * box.cellW + box.cellW / 2, y: rowY + row * box.cellH + box.cellH / 2 })
    })
    rowX += box.width + groupGap
    rowHeight = Math.max(rowHeight, box.height)
    maxX = Math.max(maxX, rowX)
  }
  return { posMap, cx: Math.max(width, maxX), cy: Math.max(height, rowY + rowHeight + topPad) }
}

export const layoutTree = (
  nodes: readonly GraphNode[],
  tree: TreeNode,
  width: number,
  height: number,
): { posMap: PosMap; cx: number; cy: number } => {
  const root = hierarchy(tree)
  const leftPad = 140
  const topPad = 110
  const rightPad = 140
  const bottomPad = 110
  const maxDepth = Math.max(...root.descendants().map((d) => d.depth), 0)
  const levelGap = Math.max(110, Math.min(180, width / Math.max(maxDepth + 1, 2)))
  const metrics = new Map<string, { depth: number; width: number }>()
  const totalWidth = computeTreeMetrics(nodes, tree, 0, metrics)
  const posMap: PosMap = new Map()
  assignTreePositions(nodes, tree, leftPad, metrics, posMap, levelGap, topPad)
  const canvasWidth = Math.max(width, totalWidth + leftPad + rightPad)
  const canvasHeight = Math.max(height, topPad + bottomPad + maxDepth * levelGap)
  return { posMap, cx: canvasWidth, cy: canvasHeight }
}
