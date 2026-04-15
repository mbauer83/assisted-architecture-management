import { ref, reactive, onUnmounted } from 'vue'
import { hierarchy, cluster } from 'd3-hierarchy'

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
}

export interface GraphEdge {
  source: string
  target: string
  connType: string
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
  centerPull: 0.003,
  damping: 0.85,
}

const MIN_VELOCITY = 0.01

export function useForceGraph(width: () => number, height: () => number) {
  const nodes = ref<GraphNode[]>([])
  const edges = ref<GraphEdge[]>([])
  const options = reactive<ForceOptions>({ ...DEFAULTS })
  const layoutMode = ref<LayoutMode>('force')
  let animId: number | null = null
  let running = false

  const addNode = (node: Omit<GraphNode, 'x' | 'y' | 'vx' | 'vy' | 'expanded' | 'pinned'>) => {
    if (nodes.value.some((n) => n.id === node.id)) return
    const cx = width() / 2
    const cy = height() / 2
    const angle = Math.random() * Math.PI * 2
    const dist = 60 + Math.random() * 120
    nodes.value.push({
      ...node,
      x: cx + Math.cos(angle) * dist,
      y: cy + Math.sin(angle) * dist,
      vx: 0, vy: 0,
      expanded: false, pinned: false,
    })
  }

  const addEdge = (edge: GraphEdge) => {
    const exists = edges.value.some(
      (e) => e.source === edge.source && e.target === edge.target && e.connType === edge.connType,
    )
    if (!exists) edges.value.push(edge)
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

    // Repulsion between all pairs
    for (let i = 0; i < ns.length; i++) {
      for (let j = i + 1; j < ns.length; j++) {
        const dx = ns[j].x - ns[i].x
        const dy = ns[j].y - ns[i].y
        const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1)
        const force = repulsion / (dist * dist)
        const fx = (dx / dist) * force
        const fy = (dy / dist) * force
        if (!ns[i].pinned) { ns[i].vx -= fx; ns[i].vy -= fy }
        if (!ns[j].pinned) { ns[j].vx += fx; ns[j].vy += fy }
      }
    }
    // Attraction along edges
    for (const e of es) {
      const src = ns.find((n) => n.id === e.source)
      const tgt = ns.find((n) => n.id === e.target)
      if (!src || !tgt) continue
      const dx = tgt.x - src.x
      const dy = tgt.y - src.y
      const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1)
      const force = (dist - idealDist) * attraction
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

  const applyClusterLayout = (rootId: string) => {
    stop()
    layoutMode.value = 'cluster'
    if (nodes.value.length === 0) return
    const tree = buildTree(rootId)
    const root = hierarchy(tree)
    const pad = 60
    cluster<TreeNode>().size([width() - pad * 2, height() - pad * 2])(root)
    const posMap = new Map<string, { x: number; y: number }>()
    for (const d of root.descendants()) {
      posMap.set(d.data.id, { x: (d.x ?? 0) + pad, y: (d.y ?? 0) + pad })
    }
    for (const n of nodes.value) {
      const pos = posMap.get(n.id)
      if (pos) { n.x = pos.x; n.y = pos.y }
      n.vx = 0; n.vy = 0
    }
  }

  const applyForceLayout = () => {
    layoutMode.value = 'force'
    restart()
  }

  onUnmounted(stop)

  return {
    nodes, edges, options, layoutMode,
    addNode, addEdge, markExpanded,
    start, stop, restart,
    applyClusterLayout, applyForceLayout,
  }
}
