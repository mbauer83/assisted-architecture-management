<script setup lang="ts">
/**
 * Assurance neighborhood explorer: renders the policy-filtered traversal from
 * GET /api/assurance/neighbors on the generic graph canvas. Double-click
 * expands a node with a fresh one-hop request (that is also how partial
 * results continue past a size budget — no continuation tokens). A locked
 * store collapses the whole panel and nothing further is fetched.
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, RouterLink } from 'vue-router'
import GraphCanvas from '../components/GraphCanvas.vue'
import AssuranceNodeDetail from '../components/AssuranceNodeDetail.vue'
import { useForceGraph, type GraphNode, type GraphEdge } from '../composables/useForceGraph'
import type { NodeVisual, EdgeVisual } from '../components/GraphCanvas.helpers'
import {
  assuranceNodeColor, clearsGraph, emptyPanelState, nodeTypeLabel,
  outcomeForResponse, panelStateForOutcome,
  type AssuranceGraphPanelState, type AssuranceNeighborsResponse,
} from './AssuranceGraphExploreView.helpers'

const route = useRoute()
const rootId = computed(() => (route.query.node_id as string | undefined) ?? '')

const canvasRef = ref<InstanceType<typeof GraphCanvas> | null>(null)
const svgWidth = ref(800)
const svgHeight = ref(600)
const onCanvasResized = (width: number, height: number) => {
  svgWidth.value = width
  svgHeight.value = height
}

const {
  nodes, edges, addNode, addEdge, markExpanded, settleForceLayout, applyRadialLayout,
} = useForceGraph(() => svgWidth.value, () => svgHeight.value)

const panel = ref<AssuranceGraphPanelState>(emptyPanelState())
const loading = ref(false)
const nodeTypeById = ref(new Map<string, string>())
const selectedEdge = ref<GraphEdge | null>(null)

const nodeVisual = (n: GraphNode): NodeVisual => ({
  color: assuranceNodeColor(nodeTypeById.value.get(n.id) ?? ''),
  shape: 'circle',
  iconLetter: null,
})
const edgeVisual = (): EdgeVisual => ({ stroke: null, strokeWidth: null, dashArray: undefined })
const isRoot = (id: string) => id === rootId.value

const applyGraph = (response: AssuranceNeighborsResponse, merge: boolean) => {
  if (!merge) {
    nodes.value = []
    edges.value = []
  }
  for (const node of response.nodes) {
    nodeTypeById.value.set(node.node_id, node.node_type)
    addNode({
      id: node.node_id,
      label: node.name,
      type: nodeTypeLabel(node.node_id),
      addedBy: merge && !node.is_root ? response.root_id : undefined,
    })
  }
  for (const edge of response.edges) {
    addEdge({ source: edge.source_id, target: edge.target_id, connType: edge.conn_type })
  }
  markExpanded(response.root_id)
  if (merge) {
    settleForceLayout()
  } else {
    const hops = new Map(response.nodes.map((n) => [n.node_id, n.hop]))
    applyRadialLayout(hops, 180)
  }
  canvasRef.value?.fitToView()
}

const fetchNeighbors = async (nodeId: string, merge: boolean) => {
  if (!nodeId || panel.value.lockedMessage) return
  loading.value = true
  try {
    const resp = await fetch(`/api/assurance/neighbors?node_id=${encodeURIComponent(nodeId)}`)
    const body: unknown = await resp.json().catch(() => null)
    const outcome = outcomeForResponse(resp.status, body)
    panel.value = panelStateForOutcome(outcome, panel.value)
    if (clearsGraph(outcome)) {
      nodes.value = []
      edges.value = []
      selectedEdge.value = null
      return
    }
    if (outcome.kind === 'graph') applyGraph(outcome.response, merge)
  } catch {
    panel.value = { ...panel.value, errorMessage: 'Neighbor request failed.', retryable: true }
  } finally {
    loading.value = false
  }
}

const loadRoot = () => {
  panel.value = { ...emptyPanelState(), selectedNodeId: rootId.value || null }
  void fetchNeighbors(rootId.value, false)
}

onMounted(loadRoot)
watch(rootId, loadRoot)

const onNodeClick = (n: GraphNode) => {
  panel.value = { ...panel.value, selectedNodeId: n.id }
  selectedEdge.value = null
}
const onNodeDblClick = (n: GraphNode) => {
  void fetchNeighbors(n.id, true)
}
const onEdgeClick = (e: GraphEdge) => {
  selectedEdge.value = e
  panel.value = { ...panel.value, selectedNodeId: null }
}
const retry = () => {
  void fetchNeighbors(rootId.value, false)
}
</script>

<template>
  <div class="graph-layout">
    <div class="graph-canvas">
      <div class="canvas-header">
        <RouterLink
          v-if="rootId"
          :to="{ path: '/assurance/browse', query: { node_id: rootId } }"
          class="back-link"
        >
          ← Back to browse
        </RouterLink>
        <span class="canvas-title">Assurance Graph</span>
      </div>
      <div
        v-if="!rootId"
        class="panel-banner"
      >
        Pick a starting node:
        <RouterLink to="/assurance/browse">
          browse the assurance nodes
        </RouterLink>
        and use “Explore graph” on a node's detail panel.
      </div>
      <div
        v-else-if="panel.lockedMessage"
        class="panel-banner panel-banner--locked"
      >
        {{ panel.lockedMessage }}
      </div>
      <div
        v-else-if="panel.errorMessage"
        class="panel-banner panel-banner--error"
      >
        {{ panel.errorMessage }}
        <button
          v-if="panel.retryable"
          type="button"
          class="retry-btn"
          @click="retry"
        >
          Retry
        </button>
      </div>
      <GraphCanvas
        v-if="!panel.lockedMessage"
        ref="canvasRef"
        :nodes="nodes"
        :edges="edges"
        :selected-id="panel.selectedNodeId"
        :selected-edge="selectedEdge"
        :node-visual="nodeVisual"
        :edge-visual="edgeVisual"
        :is-anchor="isRoot"
        :loading="loading"
        :notice="panel.truncationNotice"
        @node-click="onNodeClick"
        @node-dblclick="onNodeDblClick"
        @edge-click="onEdgeClick"
        @resized="onCanvasResized"
      />
    </div>

    <aside class="graph-sidebar">
      <h2 class="sidebar-title">
        Details
      </h2>
      <div
        v-if="selectedEdge"
        class="edge-summary"
      >
        <span class="mono">{{ selectedEdge.source }}</span>
        <span class="edge-conn-type">{{ selectedEdge.connType }}</span>
        <span class="mono">{{ selectedEdge.target }}</span>
      </div>
      <AssuranceNodeDetail
        v-else-if="panel.selectedNodeId"
        :node-id="panel.selectedNodeId"
      />
      <div
        v-else
        class="sidebar-empty"
      >
        Click a node or edge to view details
      </div>
    </aside>
  </div>
</template>

<style scoped>
.graph-layout { display: flex; height: calc(100vh - 96px); gap: 0; margin: -24px; }
.graph-canvas { flex: 1; display: flex; flex-direction: column; background: #fafafa; position: relative; }
.canvas-header {
  display: flex; align-items: center; gap: 12px; padding: 12px 16px;
  border-bottom: 1px solid #e5e7eb; background: white;
}
.back-link { font-size: 13px; color: #6b7280; }
.back-link:hover { color: #374151; }
.canvas-title { font-size: 14px; font-weight: 600; color: #374151; margin-right: auto; }

.panel-banner { font-size: 13px; padding: 10px 16px; }
.panel-banner--locked { background: #fef9c3; color: #854d0e; border-bottom: 1px solid #facc15; }
.panel-banner--error { background: #fee2e2; color: #991b1b; border-bottom: 1px solid #fca5a5; }
.retry-btn {
  margin-left: 8px; padding: 2px 10px; border: 1px solid #d1d5db; border-radius: 4px;
  background: white; font-size: 12px; cursor: pointer; color: #374151;
}
.retry-btn:hover { background: #f3f4f6; }

.graph-sidebar {
  width: 320px; background: white; border-left: 1px solid #e5e7eb;
  overflow-y: auto; flex-shrink: 0;
}
.sidebar-title { font-size: 14px; font-weight: 600; color: #374151; margin: 16px; }
.sidebar-empty { font-size: 13px; color: #6b7280; margin: 0 16px; }
.edge-summary {
  display: flex; flex-direction: column; gap: 4px; margin: 0 16px;
  font-size: 12px; color: #374151;
}
.edge-conn-type { color: #6b7280; font-style: italic; }
.mono { font-family: monospace; }
</style>
