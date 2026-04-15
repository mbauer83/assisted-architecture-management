<script setup lang="ts">
import { inject, onMounted, watch, computed, ref } from 'vue'
import { useRoute, RouterLink } from 'vue-router'
import { Effect } from 'effect'
import { modelServiceKey } from '../keys'
import { useAsync } from '../composables/useAsync'
import { useForceGraph, type GraphNode, type LayoutMode } from '../composables/useForceGraph'
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
  addNode, addEdge, markExpanded, restart,
  applyClusterLayout, applyForceLayout,
} = useForceGraph(() => svgWidth.value, () => svgHeight.value)

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
  motivation: '#d97706', strategy: '#059669', business: '#ca8a04',
  common: '#92735a', application: '#2563eb', technology: '#16a34a',
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
  Effect.runPromise(svc.getConnections(entityId, 'any')).then((conns: ConnectionList) => {
    for (const c of conns) {
      const otherId = c.source === entityId ? c.target : c.source
      addNode({ id: otherId, label: friendlyName(otherId), type: otherId.split('@')[0] })
      addEdge({ source: c.source, target: c.target, connType: c.conn_type })
    }
    markExpanded(entityId)
    // Resolve domain for newly added nodes
    for (const n of nodes.value) {
      if (!n.domain) resolveNodeDomain(n)
    }
    if (layoutMode.value === 'cluster') applyClusterLayout(rootId.value)
    else restart()
  })
}

const resolveNodeDomain = (n: GraphNode) => {
  Effect.runPromise(svc.getEntity(n.id)).then((d) => {
    n.domain = d.domain
    n.label = d.name || n.label
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
  selectedDetail.run(svc.getEntity(id))
}

const onNodeClick = (n: GraphNode) => selectNode(n.id)

const onNodeDblClick = (n: GraphNode) => {
  if (!n.expanded) expandNode(n.id)
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
        <!-- Edges -->
        <g v-for="(e, i) in edges" :key="'e'+i">
          <path :d="edgePath(e)" stroke="#d1d5db" stroke-width="1.5" fill="none" marker-end="url(#arrowhead)" />
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
          <text dy="4" text-anchor="middle" fill="white" font-size="9" font-weight="600">
            {{ n.type }}
          </text>
          <text dy="40" text-anchor="middle" fill="#374151" font-size="10">
            {{ truncLabel(n.label) }}
          </text>
          <circle
            v-if="!n.expanded"
            cx="17" cy="-17" r="7"
            fill="#2563eb" stroke="white" stroke-width="1.5" cursor="pointer"
          />
          <text
            v-if="!n.expanded"
            x="17" y="-14"
            text-anchor="middle" fill="white" font-size="9" font-weight="bold"
            pointer-events="none"
          >+</text>
        </g>
      </svg>
    </div>

    <aside class="graph-sidebar">
      <h2 class="sidebar-title">Details</h2>
      <div v-if="!selectedId" class="sidebar-empty">Click a node to view details</div>
      <div v-else-if="selectedDetail.loading.value" class="sidebar-loading">Loading...</div>
      <div v-else-if="selectedDetail.error.value" class="sidebar-error">{{ selectedDetail.error.value }}</div>
      <template v-else-if="sd">
        <div class="detail-field">
          <label>Name</label>
          <RouterLink :to="{ path: '/entity', query: { id: selectedId } }" class="detail-value detail-link">{{ sd.name }}</RouterLink>
        </div>
        <div class="detail-field"><label>Type</label><span class="detail-value mono">{{ sd.artifact_type }}</span></div>
        <div class="detail-field"><label>Domain</label><span class="detail-value domain-badge" :class="`domain--${sd.domain}`">{{ sd.domain }}</span></div>
        <div class="detail-field"><label>Status</label><span class="detail-value status-badge" :class="`status--${sd.status}`">{{ sd.status }}</span></div>
        <div class="detail-field"><label>Version</label><span class="detail-value">{{ sd.version }}</span></div>
        <div class="detail-field"><label>Artifact ID</label><span class="detail-value mono id-value">{{ sd.artifact_id }}</span></div>
        <div v-if="sd.content_html" class="detail-content">
          <label>Content</label>
          <div class="content-body markdown-body" v-html="sd.content_html"></div>
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
.detail-link { font-weight: 600; }
.id-value { font-size: 11px; color: #9ca3af; word-break: break-all; }
.mono { font-family: monospace; }
.detail-content { margin-top: 16px; }
.detail-content label { display: block; font-size: 11px; color: #6b7280; text-transform: uppercase; letter-spacing: .05em; margin-bottom: 6px; }
.content-body { font-size: 13px; line-height: 1.5; color: #374151; max-height: 300px; overflow-y: auto; }
.content-body :deep(p) { margin: 0.5rem 0; }
.domain-badge, .status-badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 500; }
.domain--motivation { background: #fef3c7; color: #92400e; }
.domain--strategy { background: #d1fae5; color: #065f46; }
.domain--business { background: #fef9c3; color: #713f12; }
.domain--common { background: #f5f0eb; color: #57534e; }
.domain--application { background: #dbeafe; color: #1e40af; }
.domain--technology { background: #dcfce7; color: #14532d; }
.status--draft { background: #f3f4f6; color: #6b7280; }
.status--active { background: #dcfce7; color: #166534; }
.status--deprecated { background: #fee2e2; color: #991b1b; }
</style>
