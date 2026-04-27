import { ref, reactive, onUnmounted } from 'vue'
import { hierarchy } from 'd3-hierarchy'

export type LayoutMode = 'force' | 'cluster'

export interface GraphNode {
  id: string
  label: string
  type: string // artifact_type prefix e.g. "GOL", "APP"
  domain?: string
  x: number
  y: number
  vx: number
  vy: number
  expanded: boolean
  pinned: boolean
  totalConns?: number   // sum of conn_in + conn_sym + conn_out; undefined = not yet loaded
  addedBy?: string      // id of the node whose expansion added this node
}

export interface GraphEdge {
  source: string
  target: string
  connType: string
  description?: string  // raw content_text from the connection
  srcCardinality?: string
  tgtCardinality?: string
}

export interface ForceOptions {
  repulsion: number
  attraction: number
  idealDist: number
  centerPull: number
  damping: number
}

const DEFAULTS: ForceOptions = {
  repulsion: 3000,
  attraction: 0.005,
  idealDist: 250,
  centerPull: 0.0005,
  damping: 0.85,
}

const MIN_VELOCITY = 0.01
// When a node is expanded its spring to its own parent lengthens by this factor,
// pushing the whole sub-cluster away.  Un-expanded siblings keep the normal idealDist.
const EXPANSION_FACTOR = 2.0
// Expanded cluster-centres repel each other more strongly so clusters don't overlap.
const EXPANDED_REPULSION = 4.0

export function useForceGraph(width: () => number, height: () => number) {
  const nodes = ref<GraphNode[]>([])
  const edges = ref<GraphEdge[]>([])
  const options = reactive<ForceOptions>({ ...DEFAULTS })
  const layoutMode = ref<LayoutMode>('force')
  let animId: number | null = null
  let running = false

  const addNode = (node: Omit<GraphNode, 'x' | 'y' | 'vx' | 'vy' | 'expanded' | 'pinned'>) => {
    if (nodes.value.some((n) => n.id === node.id)) return
    const parent = node.addedBy ? nodes.value.find((n) => n.id === node.addedBy) : null
    const ox = parent ? parent.x : width() / 2
    const oy = parent ? parent.y : height() / 2
    const angle = Math.random() * Math.PI * 2
    const dist = options.idealDist * (0.8 + Math.random() * 0.5)
    nodes.value.push({
      ...node,
      x: ox + Math.cos(angle) * dist,
      y: oy + Math.sin(angle) * dist,
      vx: 0, vy: 0,
      expanded: false, pinned: false,
    })
  }

  /** Distribute nodes added by expanding `parentId` in an arc pointing away from the grandparent.
   *  Root expansions use a full ring; all others use a 160° arc on the far side. */
  const spreadAroundParent = (parentId: string) => {
    const parent = nodes.value.find((n) => n.id === parentId)
    const children = nodes.value.filter((n) => n.addedBy === parentId)
    if (!parent || children.length === 0) return

    const grandparent = parent.addedBy ? nodes.value.find((n) => n.id === parent.addedBy) : null
    const awayAngle = grandparent
      ? Math.atan2(parent.y - grandparent.y, parent.x - grandparent.x)
      : Math.atan2(parent.y - height() / 2, parent.x - width() / 2)

    const dist = options.idealDist * 1.1
    const isRoot = !grandparent
    const halfSpread = isRoot ? Math.PI : Math.PI * 0.8
    children.forEach((n, i) => {
      const t = children.length > 1 ? i / (children.length - 1) - 0.5 : 0
      const angle = awayAngle + halfSpread * 2 * t
      n.x = parent.x + Math.cos(angle) * dist
      n.y = parent.y + Math.sin(angle) * dist
      n.vx = Math.cos(angle) * 5
      n.vy = Math.sin(angle) * 5
    })
  }

  const addEdge = (edge: GraphEdge) => {
    const exists = edges.value.some(
      (e) => e.source === edge.source && e.target === edge.target && e.connType === edge.connType,
    )
    if (!exists) edges.value.push({ ...edge })
  }

  const markExpanded = (id: string) => {
    const n = nodes.value.find((n) => n.id === id)
    if (n) n.expanded = true
  }

  const tick = () => {
    const ns = nodes.value
    const es = edges.value
    const cx = width() / 2
    const cy = height() / 2
    const { repulsion, attraction, idealDist, centerPull, damping } = options

    // Repulsion between all pairs; expanded cluster-centres repel each other extra.
    for (let i = 0; i < ns.length; i++) {
      for (let j = i + 1; j < ns.length; j++) {
        const dx = ns[j].x - ns[i].x
        const dy = ns[j].y - ns[i].y
        const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1)
        const r = (ns[i].expanded && ns[j].expanded) ? repulsion * EXPANDED_REPULSION : repulsion
        const force = r / (dist * dist)
        const fx = (dx / dist) * force
        const fy = (dy / dist) * force
        if (!ns[i].pinned) { ns[i].vx -= fx; ns[i].vy -= fy }
        if (!ns[j].pinned) { ns[j].vx += fx; ns[j].vy += fy }
      }
    }
    // Attraction along edges.
    // When the child side of a parent→child edge is expanded, use a longer spring so
    // the sub-cluster moves away from the grandparent.  Un-expanded siblings keep
    // idealDist.  Multi-connected nodes settle at the geometric centre of their springs.
    for (const e of es) {
      const src = ns.find((n) => n.id === e.source)
      const tgt = ns.find((n) => n.id === e.target)
      if (!src || !tgt) continue
      const childNode = src.addedBy === tgt.id ? src
        : tgt.addedBy === src.id ? tgt
        : null
      const springDist = childNode?.expanded ? idealDist * EXPANSION_FACTOR : idealDist
      const dx = tgt.x - src.x
      const dy = tgt.y - src.y
      const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1)
      const force = (dist - springDist) * attraction
      const fx = (dx / dist) * force
      const fy = (dy / dist) * force
      if (!src.pinned) { src.vx += fx; src.vy += fy }
      if (!tgt.pinned) { tgt.vx -= fx; tgt.vy -= fy }
    }
    // Center gravity + apply velocities
    let maxV = 0
    for (const n of ns) {
      if (n.pinned) { n.vx = 0; n.vy = 0; continue }
      n.vx += (cx - n.x) * centerPull
      n.vy += (cy - n.y) * centerPull
      n.vx *= damping
      n.vy *= damping
      n.x += n.vx
      n.y += n.vy
      maxV = Math.max(maxV, Math.abs(n.vx), Math.abs(n.vy))
    }
    return maxV > MIN_VELOCITY
  }

  const start = () => {
    if (running) return
    running = true
    const loop = () => {
      const active = tick()
      if (active && running) {
        animId = requestAnimationFrame(loop)
      } else {
        running = false
      }
    }
    animId = requestAnimationFrame(loop)
  }

  const stop = () => {
    running = false
    if (animId !== null) { cancelAnimationFrame(animId); animId = null }
  }

  const restart = () => { stop(); start() }

  // ── Cluster / dendrogram layout ──────────────────────────────────────────

  interface TreeNode { id: string; children?: TreeNode[] }

  const estimateNodeWidth = (id: string) => {
    const node = nodes.value.find((n) => n.id === id)
    const label = node?.label ?? id
    return Math.max(140, 44 + label.length * 1.5)
  }

  const computeTreeMetrics = (
    node: TreeNode,
    depth: number,
    metrics: Map<string, { depth: number; width: number }>,
  ): number => {
    const children = node.children ?? []
    const childWidths = children.map((child) => computeTreeMetrics(child, depth + 1, metrics))
    const siblingGap = Math.max(36, Math.max(0, ...children.map((child) => estimateNodeWidth(child.id) * 0.15)))
    const subtreeWidth = children.length
      ? Math.max(
          estimateNodeWidth(node.id),
          childWidths.reduce((sum, width) => sum + width, 0) + siblingGap * (children.length - 1),
        )
      : estimateNodeWidth(node.id)
    metrics.set(node.id, { depth, width: subtreeWidth })
    return subtreeWidth
  }

  const assignTreePositions = (
    node: TreeNode,
    left: number,
    metrics: Map<string, { depth: number; width: number }>,
    posMap: Map<string, { x: number; y: number }>,
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

    const siblingGap = Math.max(36, Math.max(0, ...children.map((child) => estimateNodeWidth(child.id) * 0.35)))
    let cursor = left
    for (const child of children) {
      const childMetric = metrics.get(child.id)
      if (!childMetric) continue
      assignTreePositions(child, cursor, metrics, posMap, levelGap, topPad)
      cursor += childMetric.width + siblingGap
    }
  }

  const buildTree = (rootId: string): TreeNode => {
    const adj = new Map<string, string[]>()
    for (const e of edges.value) {
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

  const applyClusterLayout = (rootId: string, centerId?: string): { cx?: number; cy?: number } => {
    stop()
    layoutMode.value = 'cluster'
    if (nodes.value.length === 0) return {}
    const tree = buildTree(rootId)
    const root = hierarchy(tree)
    const leftPad = 140
    const topPad = 110
    const rightPad = 140
    const bottomPad = 110
    const maxDepth = Math.max(...root.descendants().map((d) => d.depth), 0)
    const levelGap = Math.max(110, Math.min(180, width() / Math.max(maxDepth + 1, 2)))
    const metrics = new Map<string, { depth: number; width: number }>()
    const totalWidth = computeTreeMetrics(tree, 0, metrics)
    const posMap = new Map<string, { x: number; y: number }>()
    assignTreePositions(tree, leftPad, metrics, posMap, levelGap, topPad)

    const canvasWidth = Math.max(width(), totalWidth + leftPad + rightPad)
    const canvasHeight = Math.max(height(), topPad + bottomPad + maxDepth * levelGap)
    for (const nd of nodes.value) {
      const pos = posMap.get(nd.id)
      if (pos) { nd.x = pos.x; nd.y = pos.y }
      nd.vx = 0; nd.vy = 0
    }
    const target = centerId ?? rootId
    const pos = posMap.get(target)
    return pos ? { cx: Math.min(Math.max(pos.x, 0), canvasWidth), cy: Math.min(Math.max(pos.y, 0), canvasHeight) } : {}
  }

  /** Remove a node and all nodes that were added exclusively by its expansion. */
  const collapseNode = (id: string) => {
    const toRemove = new Set<string>()
    const collect = (nodeId: string) => {
      for (const n of nodes.value) {
        if (n.addedBy === nodeId && !toRemove.has(n.id)) {
          toRemove.add(n.id)
          collect(n.id)
        }
      }
    }
    collect(id)
    // Only remove a node if ALL its edges connect to either the collapsed subtree or the source
    const retained = nodes.value.filter((n) => !toRemove.has(n.id)).map((n) => n.id)
    const retainedSet = new Set(retained)
    const safeToRemove = new Set<string>()
    for (const rid of toRemove) {
      const hasOutsideEdge = edges.value.some((e) =>
        (e.source === rid || e.target === rid) &&
        retainedSet.has(e.source === rid ? e.target : e.source) &&
        e.source !== id && e.target !== id,
      )
      if (!hasOutsideEdge) safeToRemove.add(rid)
    }
    if (safeToRemove.size === 0) return
    nodes.value = nodes.value.filter((n) => !safeToRemove.has(n.id))
    edges.value = edges.value.filter(
      (e) => !safeToRemove.has(e.source) && !safeToRemove.has(e.target),
    )
    const collapsed = nodes.value.find((n) => n.id === id)
    if (collapsed) collapsed.expanded = false
  }

  const applyForceLayout = () => {
    layoutMode.value = 'force'
    restart()
  }

  onUnmounted(stop)

  return {
    nodes, edges, options, layoutMode,
    addNode, addEdge, markExpanded, collapseNode, spreadAroundParent,
    start, stop, restart,
    applyClusterLayout, applyForceLayout,
  }
}
