<script setup lang="ts">
import { inject, onMounted, watch, computed, ref } from 'vue'
import { useRoute, RouterLink } from 'vue-router'
import { Effect } from 'effect'
import { modelServiceKey } from '../keys'
import { useAsync } from '../composables/useAsync'
import { useForceGraph, type GraphNode, type GraphEdge, type LayoutMode } from '../composables/useForceGraph'
import ArchimateTypeGlyph from '../components/ArchimateTypeGlyph.vue'
import type { EntityDetail, ConnectionList } from '../../domain'

const svc = inject(modelServiceKey)!
const route = useRoute()
const rootId = computed(() => (route.query.id as string | undefined) ?? '')

const svgRef = ref<SVGSVGElement | null>(null)
const svgWidth = ref(800)
const svgHeight = ref(600)
const selectedId = ref<string | null>(null)
const selectedDetail = useAsync<EntityDetail>()

const {
  nodes, edges, options, layoutMode,
  addNode, addEdge, markExpanded, collapseNode, restart,
  applyClusterLayout, applyForceLayout,
} = useForceGraph(() => svgWidth.value, () => svgHeight.value)

// Selected edge (connection) for sidebar
const selectedEdge = ref<GraphEdge | null>(null)

const SPACING_PRESETS = [
  { label: 'Compact', repulsion: 1500, idealDist: 150 },
  { label: 'Normal', repulsion: 3000, idealDist: 250 },
  { label: 'Spacious', repulsion: 6000, idealDist: 400 },
  { label: 'Very spacious', repulsion: 12000, idealDist: 600 },
]

const applyPreset = (p: typeof SPACING_PRESETS[number]) => {
  options.repulsion = p.repulsion
  options.idealDist = p.idealDist
  restart()
}

const LAYOUT_MODES: { value: LayoutMode; label: string }[] = [
  { value: 'force', label: 'Force' },
  { value: 'cluster', label: 'Cluster' },
]

const switchLayout = (mode: LayoutMode) => {
  if (mode === 'cluster') applyClusterLayout(rootId.value)
  else applyForceLayout()
}

// Pan / zoom state
const viewBox = ref({ x: 0, y: 0, w: 800, h: 600 })
const isPanning = ref(false)
const panStart = ref({ x: 0, y: 0 })

// Drag state
const dragging = ref<GraphNode | null>(null)
const dragOffset = ref({ x: 0, y: 0 })

const DOMAIN_COLORS: Record<string, string> = {
  motivation: '#d8c1e4', strategy: '#efbd5d', business: '#f4de7f',
  common: '#e8e5d3', application: '#b6d7e1', technology: '#c3e1b4',
}

const nodeColor = (n: GraphNode) => DOMAIN_COLORS[n.domain ?? ''] ?? '#6b7280'

const friendlyName = (id: string) => {
  const parts = id.split('.')
  return parts.length > 2 ? parts.slice(2).join(' ').replace(/-/g, ' ') : id
}

const truncLabel = (label: string, max = 22) =>
  label.length > max ? label.slice(0, max - 1) + '...' : label

// ── Data loading ─────────────────────────────────────────────────────────────

const expandNode = (entityId: string) => {
  const beforeIds = new Set(nodes.value.map((n) => n.id))
  Effect.runPromise(svc.getConnections(entityId, 'any')).then((conns: ConnectionList) => {
    for (const c of conns) {
      const otherId = c.source === entityId ? c.target : c.source
      const isNew = !beforeIds.has(otherId)
      addNode({ id: otherId, label: friendlyName(otherId), type: otherId.split('@')[0], addedBy: isNew ? entityId : undefined })
      addEdge({ source: c.source, target: c.target, connType: c.conn_type, description: c.content_text })
    }
    markExpanded(entityId)
    for (const n of nodes.value) {
      if (!n.domain) resolveNodeDomain(n)
    }
    if (layoutMode.value === 'cluster') {
      const { cx, cy } = applyClusterLayout(rootId.value, entityId)
      if (cx !== undefined && cy !== undefined) {
        viewBox.value.x = cx - viewBox.value.w / 2
        viewBox.value.y = cy - viewBox.value.h / 2
      }
    } else restart()
  })
}

const resolveNodeDomain = (n: GraphNode) => {
  Effect.runPromise(svc.getEntity(n.id)).then((d) => {
    n.domain = d.domain
    n.label = d.name || n.label
    n.totalConns = (d.conn_in ?? 0) + (d.conn_sym ?? 0) + (d.conn_out ?? 0)
  }).catch(() => {})
}

const loadRoot = () => {
  if (!rootId.value) return
  nodes.value = []
  edges.value = []
  selectedId.value = rootId.value
  addNode({ id: rootId.value, label: friendlyName(rootId.value), type: rootId.value.split('@')[0] })
  resolveNodeDomain(nodes.value[0])
  expandNode(rootId.value)
  selectNode(rootId.value)
}

onMounted(() => {
  updateSvgSize()
  loadRoot()
})
watch(rootId, loadRoot)

const updateSvgSize = () => {
  if (!svgRef.value) return
  const rect = svgRef.value.parentElement?.getBoundingClientRect()
  if (rect) {
    svgWidth.value = rect.width
    svgHeight.value = rect.height
    viewBox.value = { x: 0, y: 0, w: rect.width, h: rect.height }
  }
}

// ── Selection ────────────────────────────────────────────────────────────────

const selectNode = (id: string) => {
  selectedId.value = id
  selectedEdge.value = null
  selectedDetail.run(svc.getEntity(id))
}

const onEdgeClick = (e: typeof edges.value[number]) => {
  selectedEdge.value = e
  selectedId.value = null
}

const onNodeClick = (n: GraphNode) => selectNode(n.id)

const onNodeDblClick = (n: GraphNode) => {
  if (n.expanded) {
    collapseNode(n.id)
    if (layoutMode.value === 'cluster') applyClusterLayout(rootId.value)
    else restart()
  } else {
    expandNode(n.id)
  }
}

// ── Drag ─────────────────────────────────────────────────────────────────────

const toSvgCoords = (clientX: number, clientY: number) => {
  const svg = svgRef.value
  if (!svg) return { x: clientX, y: clientY }
  const pt = svg.createSVGPoint()
  pt.x = clientX; pt.y = clientY
  const ctm = svg.getScreenCTM()?.inverse()
  if (!ctm) return { x: clientX, y: clientY }
  const svgPt = pt.matrixTransform(ctm)
  return { x: svgPt.x, y: svgPt.y }
}

const onNodeMouseDown = (e: MouseEvent, n: GraphNode) => {
  e.preventDefault(); e.stopPropagation()
  dragging.value = n
  n.pinned = true
  const svgPt = toSvgCoords(e.clientX, e.clientY)
  dragOffset.value = { x: n.x - svgPt.x, y: n.y - svgPt.y }
}

const onSvgMouseMove = (e: MouseEvent) => {
  if (dragging.value) {
    const svgPt = toSvgCoords(e.clientX, e.clientY)
    dragging.value.x = svgPt.x + dragOffset.value.x
    dragging.value.y = svgPt.y + dragOffset.value.y
    if (layoutMode.value === 'force') restart()
    return
  }
  if (isPanning.value) {
    const dx = (e.clientX - panStart.value.x) * (viewBox.value.w / svgWidth.value)
    const dy = (e.clientY - panStart.value.y) * (viewBox.value.h / svgHeight.value)
    viewBox.value.x -= dx; viewBox.value.y -= dy
    panStart.value = { x: e.clientX, y: e.clientY }
  }
}

const onSvgMouseUp = () => {
  if (dragging.value) {
    dragging.value.pinned = false; dragging.value = null
    if (layoutMode.value === 'force') restart()
  }
  isPanning.value = false
}

const onSvgMouseDown = (e: MouseEvent) => {
  isPanning.value = true
  panStart.value = { x: e.clientX, y: e.clientY }
}

const onWheel = (e: WheelEvent) => {
  e.preventDefault()
  const factor = e.deltaY > 0 ? 1.1 : 0.9
  const svgPt = toSvgCoords(e.clientX, e.clientY)
  const vb = viewBox.value
  vb.x = svgPt.x - (svgPt.x - vb.x) * factor
  vb.y = svgPt.y - (svgPt.y - vb.y) * factor
  vb.w *= factor; vb.h *= factor
}

const vb = computed(() => `${viewBox.value.x} ${viewBox.value.y} ${viewBox.value.w} ${viewBox.value.h}`)

const sd = computed(() => selectedDetail.data.value)

const edgePath = (e: typeof edges.value[number]) => {
  const src = nodes.value.find((n) => n.id === e.source)
  const tgt = nodes.value.find((n) => n.id === e.target)
  if (!src || !tgt) return ''
  if (layoutMode.value === 'cluster') {
    const midY = (src.y + tgt.y) / 2
    return `M ${src.x} ${src.y} V ${midY} H ${tgt.x} V ${tgt.y}`
  }
  return `M ${src.x} ${src.y} L ${tgt.x} ${tgt.y}`
}
</script>

<template>
  <div class="graph-layout">
    <div class="graph-canvas">
      <div class="canvas-header">
        <RouterLink v-if="rootId" :to="{ path: '/entity', query: { id: rootId } }" class="back-link">
          ← Back to entity
        </RouterLink>
        <span class="canvas-title">Graph Explorer</span>
        <div class="spacing-controls">
          <span class="spacing-label">Layout:</span>
          <button
            v-for="m in LAYOUT_MODES" :key="m.value"
            class="spacing-btn" :class="{ 'spacing-btn--active': layoutMode === m.value }"
            @click="switchLayout(m.value)"
          >{{ m.label }}</button>
        </div>
        <div v-if="layoutMode === 'force'" class="spacing-controls">
          <span class="spacing-label">Spacing:</span>
          <button
            v-for="p in SPACING_PRESETS" :key="p.label"
            class="spacing-btn" :class="{ 'spacing-btn--active': options.idealDist === p.idealDist }"
            @click="applyPreset(p)"
          >{{ p.label }}</button>
        </div>
      </div>
      <svg
        ref="svgRef"
        class="graph-svg"
        :viewBox="vb"
        @mousedown.self="onSvgMouseDown"
        @mousemove="onSvgMouseMove"
        @mouseup="onSvgMouseUp"
        @mouseleave="onSvgMouseUp"
        @wheel.prevent="onWheel"
      >
        <defs>
          <marker id="arrowhead" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
            <polygon points="0 0, 8 3, 0 6" fill="#9ca3af" />
          </marker>
        </defs>
        <!-- Edges (wider hit area via transparent overlay) -->
        <g v-for="(e, i) in edges" :key="'e'+i" class="graph-edge" @click.stop="onEdgeClick(e)">
          <path :d="edgePath(e)" stroke="#d1d5db" stroke-width="1.5" fill="none" marker-end="url(#arrowhead)" />
          <path :d="edgePath(e)" stroke="transparent" stroke-width="10" fill="none"
            :class="{ 'edge-selected': selectedEdge === e }" />
        </g>
        <!-- Nodes -->
        <g
          v-for="n in nodes" :key="n.id"
          class="graph-node"
          :transform="`translate(${n.x}, ${n.y})`"
          @mousedown="onNodeMouseDown($event, n)"
          @click.stop="onNodeClick(n)"
          @dblclick.stop="onNodeDblClick(n)"
        >
          <circle
            r="24"
            :fill="nodeColor(n)"
            :opacity="selectedId === n.id ? 1 : 0.8"
            :stroke="selectedId === n.id ? '#1e293b' : 'white'"
            :stroke-width="selectedId === n.id ? 3 : 2"
          />
          <text dy="4" text-anchor="middle" fill="#252327" font-size="9" font-weight="600">
            {{ n.type }}
          </text>
          <text dy="40" text-anchor="middle" fill="#374151" font-size="10">
            {{ truncLabel(n.label) }}
          </text>
          <!-- + badge: show if unexpanded AND (totalConns unknown OR > 0) -->
          <circle
            v-if="!n.expanded && (n.totalConns === undefined || n.totalConns > 0)"
            cx="17" cy="-17" r="7"
            fill="#2563eb" stroke="white" stroke-width="1.5" cursor="pointer"
          />
          <text
            v-if="!n.expanded && (n.totalConns === undefined || n.totalConns > 0)"
            x="17" y="-14"
            text-anchor="middle" fill="#252327" font-size="9" font-weight="bold"
            pointer-events="none"
          >+</text>
        </g>
      </svg>
    </div>

    <aside class="graph-sidebar">
      <h2 class="sidebar-title">Details</h2>
      <div v-if="!selectedId && !selectedEdge" class="sidebar-empty">Click a node or edge to view details</div>

      <!-- Edge details -->
      <template v-else-if="selectedEdge">
        <div class="detail-field"><label>Connection type</label><span class="detail-value mono">{{ selectedEdge.connType }}</span></div>
        <div class="detail-field">
          <label>Source</label>
          <RouterLink :to="{ path: '/entity', query: { id: selectedEdge.source } }" class="detail-value detail-link">{{ friendlyName(selectedEdge.source) }}</RouterLink>
        </div>
        <div class="detail-field">
          <label>Target</label>
          <RouterLink :to="{ path: '/entity', query: { id: selectedEdge.target } }" class="detail-value detail-link">{{ friendlyName(selectedEdge.target) }}</RouterLink>
        </div>
        <div v-if="selectedEdge.description?.trim()" class="detail-content">
          <label>Description</label>
          <div class="content-body">{{ selectedEdge.description.trim() }}</div>
        </div>
      </template>

      <!-- Node details -->
      <div v-else-if="selectedDetail.loading.value" class="sidebar-loading">Loading...</div>
      <div v-else-if="selectedDetail.error.value" class="sidebar-error">{{ selectedDetail.error.value }}</div>
      <template v-else-if="sd">
        <div class="detail-field">
          <label>Name</label>
          <RouterLink :to="{ path: '/entity', query: { id: selectedId } }" class="detail-value detail-link">{{ sd.name }}</RouterLink>
        </div>
        <div class="detail-field">
          <label>Type</label>
          <span class="detail-type">
            <ArchimateTypeGlyph :type="sd.artifact_type" :size="16" class="detail-glyph" />
            <span class="detail-value mono">{{ sd.artifact_type }}</span>
          </span>
        </div>
        <div class="detail-field"><label>Domain</label><span class="detail-value domain-badge" :class="`domain--${sd.domain}`">{{ sd.domain }}</span></div>
        <div class="detail-field"><label>Status</label><span class="detail-value status-badge" :class="`status--${sd.status}`">{{ sd.status }}</span></div>
        <div class="detail-field"><label>Version</label><span class="detail-value">{{ sd.version }}</span></div>
        <div class="detail-field"><label>Artifact ID</label><span class="detail-value mono id-value">{{ sd.artifact_id }}</span></div>
        <div v-if="sd.content_html" class="detail-content">
          <label>Content</label>
          <div class="content-body markdown-body" v-html="sd.content_html"></div>
        </div>
        <div class="detail-explore">
          <RouterLink :to="{ path: '/graph', query: { id: selectedId } }" class="explore-link">Explore graph →</RouterLink>
        </div>
      </template>
    </aside>
  </div>
</template>

<style scoped>
.graph-layout { display: flex; height: calc(100vh - 96px); gap: 0; margin: -24px; }

.graph-canvas { flex: 1; display: flex; flex-direction: column; background: #fafafa; }
.canvas-header {
  display: flex; align-items: center; gap: 12px; padding: 12px 16px;
  border-bottom: 1px solid #e5e7eb; background: white;
}
.back-link { font-size: 13px; color: #6b7280; }
.back-link:hover { color: #374151; }
.canvas-title { font-size: 14px; font-weight: 600; color: #374151; margin-right: auto; }

.spacing-controls { display: flex; align-items: center; gap: 4px; }
.spacing-label { font-size: 11px; color: #6b7280; margin-right: 4px; }
.spacing-btn {
  padding: 3px 8px; border-radius: 4px; border: 1px solid #d1d5db;
  background: white; font-size: 11px; cursor: pointer; color: #374151;
}
.spacing-btn:hover { background: #f3f4f6; }
.spacing-btn--active { background: #2563eb; color: white; border-color: #2563eb; }

.graph-svg { flex: 1; cursor: grab; user-select: none; }
.graph-svg:active { cursor: grabbing; }
.graph-node { cursor: pointer; }
.graph-node:hover circle:first-child { filter: brightness(1.15); }
.graph-edge { cursor: pointer; }
.graph-edge:hover path:first-child { stroke: #6b7280; }
.edge-selected { stroke: #2563eb !important; opacity: 0.3; }

.graph-sidebar {
  width: 320px; background: white; border-left: 1px solid #e5e7eb;
  padding: 16px; overflow-y: auto; flex-shrink: 0;
}
.sidebar-title { font-size: 14px; font-weight: 600; color: #374151; margin-bottom: 16px; }
.sidebar-empty, .sidebar-loading { font-size: 13px; color: #6b7280; }
.sidebar-error { font-size: 13px; color: #dc2626; }

.detail-field { margin-bottom: 12px; }
.detail-field label { display: block; font-size: 11px; color: #6b7280; text-transform: uppercase; letter-spacing: .05em; margin-bottom: 2px; }
.detail-value { font-size: 13px; color: #1e293b; }
.detail-type { display: inline-flex; align-items: center; gap: 8px; }
.detail-glyph { color: #374151; fill: none; flex: 0 0 auto; }
.detail-link { font-weight: 600; }
.id-value { font-size: 11px; color: #9ca3af; word-break: break-all; }
.mono { font-family: monospace; }
.detail-content { margin-top: 16px; }
.detail-content label { display: block; font-size: 11px; color: #6b7280; text-transform: uppercase; letter-spacing: .05em; margin-bottom: 6px; }
.content-body { font-size: 13px; line-height: 1.5; color: #374151; max-height: 300px; overflow-y: auto; white-space: pre-wrap; }
.content-body :deep(p) { margin: 0.5rem 0; }
.detail-explore { margin-top: 12px; }
.explore-link { font-size: 12px; color: #2563eb; font-weight: 500; }
.domain-badge, .status-badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 500; }
.domain--motivation  { background: #d8c1e4; color: #252327; }
.domain--strategy    { background: #efbd5d; color: #252327; }
.domain--business    { background: #f4de7f; color: #252327; }
.domain--common      { background: #e8e5d3; color: #252327; }
.domain--application { background: #b6d7e1; color: #252327; }
.domain--technology  { background: #c3e1b4; color: #252327; }
.status--draft       { background: #f3f4f6; color: #6b7280; }
.status--active      { background: #dcfce7; color: #166534; }
.status--deprecated  { background: #fee2e2; color: #991b1b; }
</style>
