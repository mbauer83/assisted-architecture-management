<script setup lang="ts">
/**
 * Ad-hoc `diagram` execution representation: renders a
 * viewpoint's repository-context population through the same rendering engine as a real
 * diagram (fixed cross-layer ArchiMate notation), never persisted as a `.puml` artifact, no
 * `ViewpointApplication`. `node_color`/`edge_color`/`edge_emphasis` are highlight overlays
 * applied client-side onto the returned SVG — the same technique the ghost/hide
 * overlay uses on a real diagram, never baked into the rendered notation.
 */
import { computed, inject, nextTick, onMounted, ref, watch } from 'vue'
import { Effect } from 'effect'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { modelServiceKey } from '../keys'
import { useViewpointExecution } from '../composables/useViewpointExecution'
import { useViewpointParameterPrompt } from '../composables/useViewpointParameterPrompt'
import { executionTitleFor } from './ViewpointsManagementView.helpers'
import type { ResolvedViewpointExecution } from '../composables/useViewpointParameterPrompt'
import { useFittedPanZoom } from '../composables/useFittedPanZoom'
import { useSidebarResize } from '../composables/useSidebarResize'
import { useDiagramSvgSelection, type DiagramSvgSelectionDetail } from '../composables/useDiagramSvgSelection'
import { useWitnessChain, type WitnessChainDisplay } from '../composables/useWitnessChain'
import DiagramEntitySidebar from '../components/DiagramEntitySidebar.vue'
import ViewpointExecutionDiagnostics from '../components/ViewpointExecutionDiagnostics.vue'
import ViewpointExecutionError from '../components/ViewpointExecutionError.vue'
import ViewpointParameterPrompt from '../components/ViewpointParameterPrompt.vue'
import { computeExecutionDiagnostics, deriveLegend, deriveScaleGradients } from '../components/ViewpointExecutionDiagnostics.helpers'
import { presentationFromMapping } from '../../domain/viewpointPresentationSerialization'
import { resolveElementMap } from '../lib/diagramViewerExtensions'
import { sanitizeDiagramSvg } from '../lib/svgSanitize'
import {
  anchorBadges, applyEdgeHighlightOverlay, applyNodeColorOverlay, centerAnchorsAfterFit,
  markAnchorEntities, markDerivedConnections, projectionByItemId,
  toDiagramConnectionStub, toEntitySummaryStub,
} from './ViewpointDiagramView.helpers'
import type { ViewpointDefinitionEnvelope } from '../../domain'

const svc = inject(modelServiceKey)!
const route = useRoute()
const router = useRouter()
const slug = computed(() => (route.query.viewpoint as string | undefined) ?? '')

const definitions = ref<readonly ViewpointDefinitionEnvelope[]>([])
const execution = useViewpointExecution(svc)
const svgMarkup = ref<string | null>(null)
const diagramWarnings = ref<readonly string[]>([])
const diagramLoading = ref(false)
const diagramError = ref<string | null>(null)
const entityAliases = ref<Readonly<Record<string, string>>>({})

const presentation = computed(() => {
  const envelope = definitions.value.find((d) => d.slug === slug.value)
  return envelope ? presentationFromMapping(envelope.presentation) : null
})
const diagnostics = computed(() => computeExecutionDiagnostics(execution.result.value, presentation.value, 'diagram'))
const legend = computed(() => deriveLegend(presentation.value, execution.projection.value?.rule_outcomes ?? []))
const scaleGradients = computed(() => deriveScaleGradients(presentation.value, execution.projection.value?.scale_legends ?? []))
const svgHtml = computed(() => (svgMarkup.value ? sanitizeDiagramSvg(svgMarkup.value) : null))

// ── Pan/zoom + click-to-select (same composables `DiagramDetailView.vue` uses for a
// persisted diagram) — this rendering is ephemeral, but the viewport/interactivity needs
// are identical, so nothing type-specific is duplicated here. ──────────────────────────
const detail = computed<DiagramSvgSelectionDetail>(() => ({ diagram_type: 'archimate-layered' }))
const aliasById = computed(() => new Map(Object.entries(entityAliases.value)))
const diagramEntities = computed(() => execution.result.value?.entities.map((e) => toEntitySummaryStub(e, aliasById.value)) ?? [])
const diagramConnections = computed(() => {
  const result = execution.result.value
  if (!result) return []
  const nameById = new Map(result.entities.map((e) => [e.id, e.name]))
  return result.connections.map((c) => toDiagramConnectionStub(c, nameById, aliasById.value))
})
const noDrilldown = ref({})
const diagramIdRef = ref('')

const rerun = () => void load()

const selection = useDiagramSvgSelection({
  svc, router, svgHtml, detail, diagramEntities, diagramConnections,
  drilldownByEntityId: noDrilldown, diagramId: diagramIdRef, reload: rerun,
})
const { svgContainer } = selection

// ── Witness chain for a selected derived connection — a real modeled connection has no
// composed chain to show, so this stays null for everything but a derived edge. ────────
const witnessChain = useWitnessChain(svc)
const witnessChainDisplay = computed<WitnessChainDisplay | null>(() => {
  const conn = selection.selectedConnection.value
  if (!conn?.certainty) return null
  return { loading: witnessChain.loading.value, segments: witnessChain.segments.value, broken: witnessChain.broken.value }
})
watch(() => selection.selectedConnection.value, (conn) => {
  if (conn?.certainty && conn.via_connection_ids?.length) {
    void witnessChain.load(conn.source, conn.target, conn.via_connection_ids)
  } else {
    witnessChain.clear()
  }
})

const containerRef = ref<HTMLElement | null>(null)
const panZoom = useFittedPanZoom(containerRef, svgContainer)
const mainGridRef = ref<HTMLElement | null>(null)
const sidebarResize = useSidebarResize(mainGridRef)

watch(svgHtml, (svg) => { if (svg) void panZoom.fitDiagramToViewport() })

const anchorLegend = computed(() =>
  anchorBadges(execution.result.value?.anchor_ids ?? [], execution.result.value?.entities ?? []))

const applyOverlay = (): readonly Element[] => {
  const svgEl = svgContainer.value?.querySelector('svg')
  const result = execution.result.value
  if (!svgEl || !result) return []
  const entityStyleById = projectionByItemId(execution.projection.value?.items ?? [])
  const { nodes, edges } = resolveElementMap('archimate-layered', svgEl, {
    entities: diagramEntities.value,
    connections: diagramConnections.value,
  })
  for (const [entityId, elems] of nodes) applyNodeColorOverlay(elems, entityStyleById.get(entityId)?.style.node_color)
  for (const [connId, elems] of edges) {
    const style = entityStyleById.get(connId)?.style
    applyEdgeHighlightOverlay(elems, style?.edge_color, style?.edge_emphasis)
  }
  markDerivedConnections(edges, diagramConnections.value)
  return markAnchorEntities(result.anchor_ids, nodes)
}

const panBy = (dx: number, dy: number) => { panZoom.tx.value += dx; panZoom.ty.value += dy }

const runExecution = async (resolved: ResolvedViewpointExecution) => {
  await execution.execute(resolved)
  diagramLoading.value = true
  diagramError.value = null
  const exit = await Effect.runPromiseExit(svc.executeViewpointDiagram(resolved))
  diagramLoading.value = false
  if (exit._tag === 'Success') {
    svgMarkup.value = exit.value.svg
    diagramWarnings.value = exit.value.warnings
    entityAliases.value = exit.value.entity_aliases ?? {}
  } else {
    diagramError.value = String(exit.cause)
  }
  await nextTick()
  await centerAnchorsAfterFit(applyOverlay(), containerRef.value, panZoom.fitDiagramToViewport, panBy)
}
const prompt = useViewpointParameterPrompt(runExecution, definitions)

const load = async () => {
  definitions.value = await Effect.runPromise(svc.listViewpointDefinitions()).catch(() => [])
  await prompt.run(slug.value)
}

onMounted(() => { if (slug.value) void load() })
</script>

<template>
  <div class="page">
    <div class="hdr">
      <h1 class="pg-title">
        {{ executionTitleFor(slug, definitions) }} <span class="count">— diagram</span>
      </h1>
      <RouterLink
        to="/viewpoints"
        class="back-link"
      >
        ← Viewpoints
      </RouterLink>
    </div>

    <ViewpointExecutionDiagnostics
      v-if="!prompt.visible.value && !execution.errorMessage.value && !diagramError"
      :diagnostics="diagnostics"
      :legend="legend"
      :scale-gradients="scaleGradients"
      :query-summary="execution.result.value?.query_summary ?? ''"
      @rerun="rerun"
    />

    <div
      v-if="anchorLegend.length && !prompt.visible.value"
      class="anchor-legend"
    >
      <span
        v-for="badge in anchorLegend"
        :key="badge.id"
        class="anchor-badge"
      >◎ anchor: {{ badge.name }}</span>
    </div>

    <div
      v-for="warning in diagramWarnings"
      :key="warning"
      class="diagram-warning"
    >
      {{ warning }}
    </div>

    <ViewpointParameterPrompt
      v-if="prompt.visible.value"
      :parameters="prompt.parameters.value"
      @submit="prompt.submit"
      @cancel="prompt.cancel"
    />

    <div
      v-if="execution.loading.value || diagramLoading"
      class="state-msg"
    >
      Rendering…
    </div>
    <ViewpointExecutionError
      v-else-if="execution.errorMessage.value || diagramError"
      :typed-error="execution.typedError.value"
      :fallback-message="execution.errorMessage.value || diagramError || 'Execution failed'"
      @retry="rerun"
    />
    <div
      v-else-if="svgHtml"
      ref="mainGridRef"
      class="main-grid"
      :style="sidebarResize.gridStyle.value"
    >
      <div
        ref="containerRef"
        class="img-container"
        @mousedown="panZoom.onMouseDown"
        @dblclick="panZoom.resetView"
      >
        <div :style="panZoom.canvasStyle.value">
          <div
            ref="svgContainer"
            class="svg-wrap"
            v-html="svgHtml"
          />
        </div>
        <button
          v-if="panZoom.isTransformed.value"
          class="reset-btn"
          title="Reset view"
          @click.stop="panZoom.resetView"
        >
          ⊙ Reset
        </button>
        <div class="zoom-hint">
          Scroll to zoom · Drag to pan · Click entity to inspect · Double-click to reset
        </div>
      </div>

      <div
        class="sidebar-splitter"
        role="separator"
        aria-orientation="vertical"
        aria-label="Resize sidebar"
        @mousedown="sidebarResize.startResize"
      />

      <DiagramEntitySidebar
        :entities="diagramEntities"
        :viewer-extension="selection.viewerExtension.value"
        :selected-id="selection.selectedId.value"
        :selected-connection="selection.selectedConnection.value"
        :selected-sub-part="selection.selectedSubPart.value"
        :entity-query="selection.entityQuery"
        :edge-label-input="selection.edgeLabelInput.value"
        :edge-label-error="selection.edgeLabelMutation.errorMessage.value"
        :witness-chain="witnessChainDisplay"
        @select-entity="selection.selectEntity($event)"
        @clear-connection="selection.clearConnection()"
        @clear-sub-part="selection.clearSubPart()"
        @update:edge-label-input="selection.edgeLabelInput.value = $event"
        @save-edge-label="selection.saveEdgeLabel()"
      />
    </div>
    <div
      v-else
      class="state-msg"
    >
      Nothing to render.
    </div>
  </div>
</template>

<style scoped>
.page { max-width: 100%; padding: 24px 16px; }
.hdr { display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; }
.pg-title { font-size: 20px; font-weight: 600; margin: 0; }
.count { color: #6b7280; font-weight: 400; font-size: 14px; }
.back-link { font-size: 13px; color: #6b7280; text-decoration: none; }
.back-link:hover { color: #374151; }
.state-msg { color: #9ca3af; font-size: 14px; padding: 24px 0; }
.state-msg--error { color: #dc2626; }
.diagram-warning { color: #92400e; background: #fef3c7; padding: 4px 8px; border-radius: 4px; font-size: 12px; margin-bottom: 6px; }
.anchor-legend { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 6px; }
.anchor-badge { color: #6d28d9; background: #f5f3ff; border: 1px dashed #8b5cf6; border-radius: 4px; padding: 2px 8px; font-size: 12px; }

.main-grid { --sidebar-width: 320px; display: grid; grid-template-columns: minmax(0, 1fr) 12px var(--sidebar-width); gap: 0; align-items: start; }
@media (max-width: 800px) { .main-grid { grid-template-columns: 1fr; } }

.img-container {
  position: relative; overflow: hidden; background: #f8fafc;
  border: 1px solid #e5e7eb; border-radius: 8px;
  min-height: 400px; height: clamp(420px, 78vh, 980px);
  cursor: grab; user-select: none;
}
@media (max-width: 800px) { .img-container { height: clamp(360px, 68vh, 820px); } }
.img-container:active { cursor: grabbing; }
.svg-wrap { display: inline-block; padding: 12px; }
.svg-wrap :deep(svg) { display: block; max-width: none; }
.svg-wrap :deep([data-entity-id]) { cursor: pointer; }
.svg-wrap :deep([data-entity-id]:hover) > :not(title) { opacity: 0.85; }
.svg-wrap :deep([data-entity-id]:hover) polygon,
.svg-wrap :deep([data-entity-id]:hover) rect,
.svg-wrap :deep([data-entity-id]:hover) polyline,
.svg-wrap :deep([data-entity-id]:hover) ellipse { stroke: #2563eb !important; stroke-width: 2 !important; }
.svg-wrap :deep(.svg-selected) polygon,
.svg-wrap :deep(.svg-selected) rect,
.svg-wrap :deep(.svg-selected) polyline,
.svg-wrap :deep(.svg-selected) ellipse { stroke: #2563eb !important; stroke-width: 2.5 !important; }
.svg-wrap :deep([data-conn-id]) { cursor: pointer; }
.svg-wrap :deep([data-conn-id]:hover) path,
.svg-wrap :deep([data-conn-id]:hover) polygon,
.svg-wrap :deep([data-conn-id]:hover) line,
.svg-wrap :deep([data-conn-id]:hover) polyline { stroke: #2563eb !important; stroke-width: 2 !important; }
.svg-wrap :deep(.svg-conn-selected) path,
.svg-wrap :deep(.svg-conn-selected) polygon,
.svg-wrap :deep(.svg-conn-selected) line,
.svg-wrap :deep(.svg-conn-selected) polyline { stroke: #2563eb !important; stroke-width: 2.5 !important; }
.reset-btn { position: absolute; top: 8px; right: 8px; padding: 4px 10px; background: rgba(255,255,255,.92); border: 1px solid #d1d5db; border-radius: 5px; font-size: 12px; cursor: pointer; color: #374151; }
.reset-btn:hover { background: white; }
.zoom-hint { position: absolute; bottom: 6px; left: 50%; transform: translateX(-50%); font-size: 11px; color: #9ca3af; background: rgba(255,255,255,.8); padding: 2px 8px; border-radius: 4px; pointer-events: none; white-space: nowrap; }

.sidebar-splitter {
  position: sticky;
  top: 16px;
  height: clamp(420px, 78vh, 980px);
  cursor: col-resize;
  background: transparent;
}
.sidebar-splitter::before {
  content: '';
  display: block;
  width: 4px;
  height: 100%;
  margin: 0 auto;
  border-radius: 999px;
  background: #e5e7eb;
  transition: background-color 0.15s ease;
}
.sidebar-splitter:hover::before { background: #93c5fd; }
@media (max-width: 800px) {
  .sidebar-splitter { display: none; }
}
</style>
