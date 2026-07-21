<script setup lang="ts">
import { inject, onMounted, watch, computed, ref } from 'vue'
import { useRoute, useRouter, RouterLink } from 'vue-router'
import { Effect } from 'effect'
import { modelServiceKey } from '../keys'
import { useQuery } from '../composables/useQuery'
import { useForceGraph, type GraphNode, type GraphEdge, type LayoutMode } from '../composables/useForceGraph'
import GraphCanvas from '../components/GraphCanvas.vue'
import { useViewpointExecution } from '../composables/useViewpointExecution'
import { useViewpointParameterPrompt } from '../composables/useViewpointParameterPrompt'
import type { ResolvedViewpointExecution } from '../composables/useViewpointParameterPrompt'
import EdgeConnectionDetails from '../components/EdgeConnectionDetails.vue'
import GraphNodeDetails from '../components/GraphNodeDetails.vue'
import AggregationBanner from '../components/AggregationBanner.vue'
import ExecutionReferenceBar from '../components/ExecutionReferenceBar.vue'
import GraphLayoutToolbar from '../components/GraphLayoutToolbar.vue'
import DomainColorLegend from '../components/DomainColorLegend.vue'
import EdgeProvenanceLegend from '../components/EdgeProvenanceLegend.vue'
import HopDistanceLegend from '../components/HopDistanceLegend.vue'
import ViewpointSelect from '../components/ViewpointSelect.vue'
import ViewpointExecutionDiagnostics from '../components/ViewpointExecutionDiagnostics.vue'
import ViewpointExecutionError from '../components/ViewpointExecutionError.vue'
import ViewpointParameterPrompt from '../components/ViewpointParameterPrompt.vue'
import { computeExecutionDiagnostics, deriveLegend, deriveScaleGradients } from '../components/ViewpointExecutionDiagnostics.helpers'
import {
  groupKeyFor, nodeVisualFor, edgeVisualFor,
  buildConnectionStyleIndex, buildConnectionSummaryIndex, edgeStyleKey, projectionByItemId, explorationRedirectFor,
  anchorDistancesFromResult, effectiveExplorationLayout, distanceColor,
  friendlyEntityName, DOMAIN_COLORS, SPACING_PRESETS, type ExplorationLayoutOverride,
} from './GraphExploreView.helpers'
import type { ParameterDraft } from '../lib/viewpointExecutionParameters'
import { VERIFIED_KEYS, executionQuery, parametersFromQuery } from '../lib/viewpointUrlState'
import { viewpointSummaryFromEnvelope } from '../lib/viewpointSummary'
import { useAggregatedExploration } from '../composables/useAggregatedExploration'
import { presentationFromMapping } from '../../domain/viewpointPresentationSerialization'
import type { PresentationNode } from '../../domain/viewpointPresentation'
import type {
  EntityDetail, ConnectionList, NotFoundError, ViewpointSummary, ViewpointDefinitionEnvelope,
} from '../../domain'
import type { MarkdownError } from '../../application/MarkdownService'
import type { RepoError } from '../../ports/ModelRepository'

const svc = inject(modelServiceKey)!
const route = useRoute()
const router = useRouter()
const rootId = computed(() => (route.query.id as string | undefined) ?? '')

const canvasRef = ref<InstanceType<typeof GraphCanvas> | null>(null)
const svgWidth = ref(800)
const svgHeight = ref(600)
const onCanvasResized = (width: number, height: number) => {
  svgWidth.value = width
  svgHeight.value = height
}
const selectedId = ref<string | null>(null)
const selectedDetail = useQuery<EntityDetail, RepoError | NotFoundError | MarkdownError>()

const {
  nodes, edges, options, layoutMode,
  addNode, addEdge, markExpanded, collapseNode, spreadAroundParent, restart, settleForceLayout,
  applyClusterLayout, applyGroupClusterLayout, applyRadialLayout, applyForceLayout,
} = useForceGraph(() => svgWidth.value, () => svgHeight.value)

const onDragTick = () => {
  if (layoutMode.value === 'force') restart()
}
const fitToView = () => {
  canvasRef.value?.fitToView()
}

// Selected edge (connection) for sidebar
const selectedEdge = ref<GraphEdge | null>(null)

// ── Viewpoint-driven exploration ────────────────────────────────────────────

const viewpoints = ref<ViewpointSummary[]>([])
const viewpointDefinitions = ref<readonly ViewpointDefinitionEnvelope[]>([])
const selectedViewpointSlug = ref<string | null>(null)
const viewpointExecution = useViewpointExecution(svc)

const loadViewpointCatalog = async () => {
  // Viewpoint discovery comes from the dedicated /api/viewpoints source, not authoring
  // guidance — the picker summaries are projected from the same definition envelopes.
  const definitions = await Effect.runPromise(svc.listViewpointDefinitions()).catch(() => [])
  viewpointDefinitions.value = definitions
  viewpoints.value = definitions.map(viewpointSummaryFromEnvelope)
}

const selectedPresentation = computed<PresentationNode | null>(() => {
  const envelope = viewpointDefinitions.value.find((d) => d.slug === selectedViewpointSlug.value)
  return envelope ? presentationFromMapping(envelope.presentation) : null
})
const currentRepresentation = computed(() => selectedPresentation.value?.representation ?? 'exploration')
const entityStyleById = computed(() => projectionByItemId(viewpointExecution.projection.value))
const connectionStyleIndex = computed(() =>
  buildConnectionStyleIndex(viewpointExecution.result.value?.connections ?? [], viewpointExecution.projection.value),
)
const connectionSummaryIndex = computed(() =>
  buildConnectionSummaryIndex(viewpointExecution.result.value?.connections ?? []),
)
const selectedEdgeSummary = computed(() => {
  const edge = selectedEdge.value
  if (!edge) return null
  return connectionSummaryIndex.value.get(edgeStyleKey(edge.source, edge.target, edge.connType)) ?? null
})
const diagnostics = computed(() => computeExecutionDiagnostics(
  viewpointExecution.result.value, selectedPresentation.value, currentRepresentation.value,
))
const selectedEnvelope = computed(() =>
  viewpointDefinitions.value.find((d) => d.slug === selectedViewpointSlug.value) ?? null,
)
const legend = computed(() => deriveLegend(selectedPresentation.value, viewpointExecution.projection.value?.rule_outcomes ?? []))
const scaleGradients = computed(() => deriveScaleGradients(selectedPresentation.value, viewpointExecution.projection.value?.scale_legends ?? []))

// ── Anchored executions: hop distances, distance fill, anchor marking ───────

const anchorIds = computed(() => viewpointExecution.result.value?.anchor_ids ?? [])
const isAnchor = (id: string) => anchorIds.value.includes(id)
const hopDepthById = computed(() => {
  const result = viewpointExecution.result.value
  if (!result || result.anchor_ids.length === 0) return new Map<string, number>()
  return anchorDistancesFromResult(result.entities)
})
const maxHopDepth = computed(() => Math.max(0, ...hopDepthById.value.values()))
const hasUnrankedNodes = computed(() =>
  (viewpointExecution.result.value?.entities ?? []).some((e) => e.anchor_modeled_distance == null),
)

const RADIAL_RING_SPACING = 180
const layoutOverride = ref<ExplorationLayoutOverride>('auto')
const applyExplorationLayout = () => {
  const result = viewpointExecution.result.value
  if (!result) return
  const layout = effectiveExplorationLayout(
    layoutOverride.value, selectedPresentation.value?.displayOptions['layout'], result.anchor_ids.length > 0,
  )
  if (layout === 'radial') {
    applyRadialLayout(hopDepthById.value, RADIAL_RING_SPACING)
    fitToView()
    return
  }
  if (layout === 'force') {
    // Fixed result population: settle synchronously so nodes are immediately
    // hit-testable — nothing drifts away under the pointer.
    settleForceLayout()
    fitToView()
    return
  }
  const groupBy = selectedPresentation.value?.groupBy ?? null
  const byId = new Map(result.entities.map((e) => [e.id, e]))
  applyGroupClusterLayout((id) => {
    const entity = byId.get(id)
    return entity ? groupKeyFor(entity, groupBy) : 'other'
  })
  fitToView()
}

const setExplorationLayout = (value: ExplorationLayoutOverride) => {
  layoutOverride.value = value
  applyExplorationLayout()
}

// ── Scale-adaptive aggregation (over-budget populations open as super-nodes) ──
const {
  activeAggregation, aggregationHint, missingMemberCount,
  populateFromResult, toggleAggregate, resetExpansion, isAggregateNodeId,
} = useAggregatedExploration(viewpointExecution.result, {
  clear: () => { nodes.value = []; edges.value = [] },
  addNode,
  addEdge,
  finalize: () => {
    for (const n of nodes.value) resolveNodeDomain(n)
    applyExplorationLayout()
  },
})

const runViewpointExecution = async (resolved: ResolvedViewpointExecution) => {
  nodes.value = []
  edges.value = []
  selectedId.value = null
  selectedEdge.value = null
  // URL = state: the address always names the ON-SCREEN execution (slug + parameters).
  // Verification pins survive only a same-viewpoint re-run/reload — switching viewpoints
  // must never carry a previous reference's pins forward.
  const pins = route.query.viewpoint === resolved.slug
    ? Object.fromEntries(VERIFIED_KEYS.flatMap((key) => (typeof route.query[key] === 'string' ? [[key, route.query[key]]] : [])))
    : {}
  void router.replace({ query: { ...executionQuery(resolved.slug, resolved.parameters), ...pins } })
  await viewpointExecution.execute(resolved)
  resetExpansion()
  populateFromResult()
}
const viewpointPrompt = useViewpointParameterPrompt(runViewpointExecution, viewpointDefinitions)
const loadViewpointPopulation = (slug: string, preset?: ParameterDraft) => viewpointPrompt.run(slug, preset)

const onSelectViewpoint = (viewpoint: ViewpointSummary | null) => {
  selectedViewpointSlug.value = viewpoint?.slug ?? null
  if (!viewpoint) {
    viewpointExecution.clear()
    void router.replace({ query: rootId.value ? { id: rootId.value } : {} })
    loadRoot()
    return
  }
  const envelope = viewpointDefinitions.value.find((d) => d.slug === viewpoint.slug)
  const redirect = explorationRedirectFor(envelope)
  if (redirect) {
    void router.push(redirect)
    return
  }
  void loadViewpointPopulation(viewpoint.slug)
}

const rerunViewpoint = () => {
  if (selectedViewpointSlug.value) void loadViewpointPopulation(selectedViewpointSlug.value)
}

/** Anchored executions fill unstyled nodes by hop distance from the anchor; a
 * projection-provided `node_color` still wins inside `nodeVisualFor`. */
const nodeFallbackFill = (n: GraphNode) => {
  const depth = hopDepthById.value.get(n.id)
  return depth !== undefined
    ? distanceColor(depth, maxHopDepth.value)
    : DOMAIN_COLORS[n.domain ?? ''] ?? '#6b7280'
}
const nodeVisual = (n: GraphNode) =>
  nodeVisualFor(entityStyleById.value.get(n.id)?.style, nodeFallbackFill(n), n.artifactType)
const edgeVisual = (e: GraphEdge) => {
  const key = edgeStyleKey(e.source, e.target, e.connType)
  return edgeVisualFor(connectionStyleIndex.value.get(key), connectionSummaryIndex.value.get(key)?.certainty ?? null)
}

const applyPreset = (p: typeof SPACING_PRESETS[number]) => {
  options.repulsion = p.repulsion
  options.idealDist = p.idealDist
  restart()
}

const switchLayout = (mode: LayoutMode) => {
  if (mode === 'cluster') applyClusterLayout(rootId.value)
  else applyForceLayout()
}

// ── Data loading ─────────────────────────────────────────────────────────────

const expandNode = (entityId: string) => {
  const beforeIds = new Set(nodes.value.map((n) => n.id))
  void Effect.runPromise(svc.getConnections(entityId, 'any')).then((conns: ConnectionList) => {
    for (const c of conns) {
      const otherId = c.source === entityId ? c.target : c.source
      const isNew = !beforeIds.has(otherId)
      addNode({ id: otherId, label: friendlyEntityName(otherId), type: otherId.split('@')[0], addedBy: isNew ? entityId : undefined })
      addEdge({
          source: c.source,
          target: c.target,
          connType: c.conn_type,
          description: c.content_text,
          srcMultiplicity: c.src_multiplicity || undefined,
          tgtMultiplicity: c.tgt_multiplicity || undefined,
        })
    }
    markExpanded(entityId)
    spreadAroundParent(entityId)
    for (const n of nodes.value) {
      if (!n.domain) resolveNodeDomain(n)
    }
    if (layoutMode.value === 'cluster') {
      const { cx, cy } = applyClusterLayout(rootId.value, entityId)
      if (cx !== undefined && cy !== undefined) canvasRef.value?.centerOn(cx, cy)
    } else restart()
  })
}

const resolveNodeDomain = (n: GraphNode) => {
  Effect.runPromise(svc.getEntity(n.id)).then((d) => {
    n.domain = d.domain
    n.artifactType = d.artifact_type
    n.label = d.name || n.label
    n.totalConns = (d.conn_in ?? 0) + (d.conn_sym ?? 0) + (d.conn_out ?? 0)
  }).catch(() => {})
}

const loadRoot = () => {
  if (!rootId.value) return
  nodes.value = []
  edges.value = []
  selectedId.value = rootId.value
  addNode({ id: rootId.value, label: friendlyEntityName(rootId.value), type: rootId.value.split('@')[0] })
  resolveNodeDomain(nodes.value[0])
  expandNode(rootId.value)
  selectNode(rootId.value)
}

onMounted(() => {
  void loadViewpointCatalog().then(() => {
    const viewpointSlug = route.query.viewpoint as string | undefined
    const preselected = viewpointSlug ? viewpoints.value.find((v) => v.slug === viewpointSlug) : undefined
    if (!preselected) return
    const envelope = viewpointDefinitions.value.find((d) => d.slug === preselected.slug)
    const redirect = explorationRedirectFor(envelope)
    if (redirect) {
      void router.push(redirect)
      return
    }
    // Reload/shared link: URL-carried parameters execute directly (no re-prompt).
    selectedViewpointSlug.value = preselected.slug
    void loadViewpointPopulation(preselected.slug, parametersFromQuery(route.query))
  })
  loadRoot()
})
watch(rootId, () => { if (selectedViewpointSlug.value === null) loadRoot() })

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

const onNodeClick = (n: GraphNode) => {
  if (isAggregateNodeId(n.id)) {
    toggleAggregate(n.id)
    return
  }
  selectNode(n.id)
}

const onNodeDblClick = (n: GraphNode) => {
  // A viewpoint's result is a fixed population — no incremental expand/collapse.
  if (selectedViewpointSlug.value !== null) return
  if (n.expanded) {
    collapseNode(n.id)
    if (layoutMode.value === 'cluster') applyClusterLayout(rootId.value)
    else restart()
  } else {
    expandNode(n.id)
  }
}


const sd = computed(() => selectedDetail.data.value)

const shownEdgeCount = (nodeId: string) =>
  edges.value.filter((e) => e.source === nodeId || e.target === nodeId).length

// + badge: unexpanded AND connections not yet shown (never in viewpoint mode: a
// viewpoint's population is fixed, no incremental expand).
const showExpandBadge = (n: GraphNode) =>
  selectedViewpointSlug.value === null && !n.expanded
  && (n.totalConns === undefined || n.totalConns > shownEdgeCount(n.id))
</script>

<template>
  <div class="graph-layout">
    <div class="graph-canvas">
      <div class="canvas-header">
        <RouterLink
          v-if="rootId"
          :to="{ path: '/entity', query: { id: rootId } }"
          class="back-link"
        >
          ← Back to entity
        </RouterLink>
        <span class="canvas-title">Graph Explorer</span>
        <div class="spacing-controls">
          <span class="spacing-label">Viewpoint:</span>
          <ViewpointSelect
            :model-value="selectedViewpointSlug"
            :viewpoints="viewpoints"
            @select="onSelectViewpoint"
          />
        </div>
        <GraphLayoutToolbar
          :viewpoint-active="selectedViewpointSlug !== null"
          :layout-mode="layoutMode"
          :layout-override="layoutOverride"
          :ideal-dist="options.idealDist"
          :radial-available="anchorIds.length > 0"
          @switch-layout="switchLayout"
          @set-exploration-layout="setExplorationLayout"
          @apply-preset="applyPreset"
        />
      </div>
      <ViewpointExecutionDiagnostics
        v-if="selectedViewpointSlug !== null && !viewpointPrompt.visible.value && !viewpointExecution.errorMessage.value"
        :diagnostics="diagnostics"
        :legend="legend"
        :scale-gradients="scaleGradients"
        :query-summary="viewpointExecution.result.value?.query_summary ?? ''"
        @rerun="rerunViewpoint"
      />
      <AggregationBanner
        v-if="activeAggregation"
        :aggregation="activeAggregation"
        :hint="aggregationHint"
        :total-entity-count="viewpointExecution.result.value?.total_entity_count ?? 0"
        :missing-member-count="missingMemberCount"
      />
      <ExecutionReferenceBar
        v-if="selectedViewpointSlug !== null"
        :envelope="selectedEnvelope"
        :result="viewpointExecution.result.value"
      />
      <HopDistanceLegend
        v-if="anchorIds.length > 0"
        :depths="[...hopDepthById.values()]"
        :has-unranked="hasUnrankedNodes"
      />
      <EdgeProvenanceLegend :connections="viewpointExecution.result.value?.connections ?? []" />
      <DomainColorLegend :domains="nodes.map((n) => n.domain)" />
      <ViewpointParameterPrompt
        v-if="viewpointPrompt.visible.value"
        :parameters="viewpointPrompt.parameters.value"
        @submit="viewpointPrompt.submit"
        @cancel="viewpointPrompt.cancel"
      />
      <ViewpointExecutionError
        v-if="selectedViewpointSlug !== null && viewpointExecution.errorMessage.value"
        :typed-error="viewpointExecution.typedError.value"
        :fallback-message="viewpointExecution.errorMessage.value"
        @retry="rerunViewpoint"
      />
      <GraphCanvas
        ref="canvasRef"
        :nodes="nodes"
        :edges="edges"
        :selected-id="selectedId"
        :selected-edge="selectedEdge"
        :node-visual="nodeVisual"
        :edge-visual="edgeVisual"
        :is-anchor="isAnchor"
        :show-expand-badge="showExpandBadge"
        :cluster-edges="layoutMode === 'cluster'"
        @node-click="onNodeClick"
        @node-dblclick="onNodeDblClick"
        @edge-click="onEdgeClick"
        @drag-tick="onDragTick"
        @resized="onCanvasResized"
      />
    </div>

    <aside class="graph-sidebar">
      <h2 class="sidebar-title">
        Details
      </h2>
      <div
        v-if="!selectedId && !selectedEdge"
        class="sidebar-empty"
      >
        Click a node or edge to view details
      </div>

      <!-- Edge details -->
      <EdgeConnectionDetails
        v-else-if="selectedEdge"
        :edge="selectedEdge"
        :summary="selectedEdgeSummary"
      />

      <!-- Node details -->
      <div
        v-else-if="selectedDetail.loading.value"
        class="sidebar-loading"
      >
        Loading...
      </div>
      <div
        v-else-if="selectedDetail.errorMessage.value"
        class="sidebar-error"
      >
        {{ selectedDetail.errorMessage.value }}
      </div>
      <GraphNodeDetails
        v-else-if="sd && selectedId"
        :detail="sd"
        :selected-id="selectedId"
      />
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

.spacing-controls { display: flex; align-items: center; gap: 4px; }
.spacing-label { font-size: 11px; color: #6b7280; margin-right: 4px; }
.spacing-btn {
  padding: 3px 8px; border-radius: 4px; border: 1px solid #d1d5db;
  background: white; font-size: 11px; cursor: pointer; color: #374151;
}
.spacing-btn:hover { background: #f3f4f6; }
.spacing-btn--active { background: #2563eb; color: white; border-color: #2563eb; }

.graph-sidebar {
  width: 320px; background: white; border-left: 1px solid #e5e7eb;
  padding: 16px; overflow-y: auto; flex-shrink: 0;
}
.sidebar-title { font-size: 14px; font-weight: 600; color: #374151; margin-bottom: 16px; }
.sidebar-empty, .sidebar-loading { font-size: 13px; color: #6b7280; }
.sidebar-error { font-size: 13px; color: #dc2626; }

.mono { font-family: monospace; }
</style>
