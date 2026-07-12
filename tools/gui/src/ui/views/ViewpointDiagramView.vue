<script setup lang="ts">
/**
 * Ad-hoc `diagram` execution representation (companion plan §5.1, WU-E9): renders a
 * viewpoint's repository-context population through the same rendering engine as a real
 * diagram (fixed cross-layer ArchiMate notation), never persisted as a `.puml` artifact, no
 * `ViewpointApplication`. `node_color`/`edge_color`/`edge_emphasis` are highlight overlays
 * applied client-side onto the returned SVG — the same technique WU-E5a's ghost/hide
 * overlay uses on a real diagram, never baked into the rendered notation.
 */
import { computed, inject, nextTick, onMounted, ref } from 'vue'
import { Effect } from 'effect'
import { RouterLink, useRoute } from 'vue-router'
import { modelServiceKey } from '../keys'
import { useViewpointExecution } from '../composables/useViewpointExecution'
import ViewpointExecutionDiagnostics from '../components/ViewpointExecutionDiagnostics.vue'
import { computeExecutionDiagnostics, deriveLegend } from '../components/ViewpointExecutionDiagnostics.helpers'
import { presentationFromMapping } from '../../domain/viewpointPresentationSerialization'
import { resolveElementMap } from '../lib/diagramViewerExtensions'
import { sanitizeDiagramSvg } from '../lib/svgSanitize'
import {
  applyEdgeHighlightOverlay, applyNodeColorOverlay, projectionByItemId, toDiagramConnectionStub, toEntitySummaryStub,
} from './ViewpointDiagramView.helpers'
import type { ViewpointDefinitionEnvelope } from '../../domain'

const svc = inject(modelServiceKey)!
const route = useRoute()
const slug = computed(() => (route.query.viewpoint as string | undefined) ?? '')

const definitions = ref<readonly ViewpointDefinitionEnvelope[]>([])
const execution = useViewpointExecution(svc)
const svgMarkup = ref<string | null>(null)
const diagramWarnings = ref<readonly string[]>([])
const diagramLoading = ref(false)
const diagramError = ref<string | null>(null)
const svgContainer = ref<HTMLElement | null>(null)

const presentation = computed(() => {
  const envelope = definitions.value.find((d) => d.slug === slug.value)
  return envelope ? presentationFromMapping(envelope.presentation) : null
})
const diagnostics = computed(() => computeExecutionDiagnostics(execution.result.value, presentation.value, 'diagram'))
const legend = computed(() => deriveLegend(presentation.value))
const svgHtml = computed(() => (svgMarkup.value ? sanitizeDiagramSvg(svgMarkup.value) : null))

const applyOverlay = () => {
  const svgEl = svgContainer.value?.querySelector('svg')
  const result = execution.result.value
  if (!svgEl || !result) return
  const entityStyleById = projectionByItemId(execution.projection.value?.items ?? [])
  const { nodes, edges } = resolveElementMap('archimate-layered', svgEl, {
    entities: result.entities.map(toEntitySummaryStub),
    connections: result.connections.map(toDiagramConnectionStub),
  })
  for (const [entityId, elems] of nodes) applyNodeColorOverlay(elems, entityStyleById.get(entityId)?.style.node_color)
  for (const [connId, elems] of edges) {
    const style = entityStyleById.get(connId)?.style
    applyEdgeHighlightOverlay(elems, style?.edge_color, style?.edge_emphasis)
  }
}

const load = async () => {
  definitions.value = await Effect.runPromise(svc.listViewpointDefinitions()).catch(() => [])
  await execution.execute({ slug: slug.value })
  diagramLoading.value = true
  diagramError.value = null
  const exit = await Effect.runPromiseExit(svc.executeViewpointDiagram({ slug: slug.value }))
  diagramLoading.value = false
  if (exit._tag === 'Success') {
    svgMarkup.value = exit.value.svg
    diagramWarnings.value = exit.value.warnings
  } else {
    diagramError.value = String(exit.cause)
  }
  await nextTick()
  applyOverlay()
}
const rerun = () => void load()

onMounted(() => { if (slug.value) void load() })
</script>

<template>
  <div class="page">
    <div class="hdr">
      <h1 class="pg-title">
        {{ slug }} <span class="count">(diagram)</span>
      </h1>
      <RouterLink
        to="/viewpoints"
        class="back-link"
      >
        ← Viewpoints
      </RouterLink>
    </div>

    <ViewpointExecutionDiagnostics
      :diagnostics="diagnostics"
      :legend="legend"
      :query-summary="execution.result.value?.query_summary ?? ''"
      @rerun="rerun"
    />

    <div
      v-for="warning in diagramWarnings"
      :key="warning"
      class="diagram-warning"
    >
      {{ warning }}
    </div>

    <div
      v-if="execution.loading.value || diagramLoading"
      class="state-msg"
    >
      Rendering…
    </div>
    <div
      v-else-if="execution.errorMessage.value || diagramError"
      class="state-msg state-msg--error"
    >
      {{ execution.errorMessage.value || diagramError }}
    </div>
    <div
      v-else-if="svgHtml"
      ref="svgContainer"
      class="svg-wrap"
      v-html="svgHtml"
    />
    <div
      v-else
      class="state-msg"
    >
      Nothing to render.
    </div>
  </div>
</template>

<style scoped>
.page { max-width: 1200px; margin: 0 auto; padding: 24px 16px; }
.hdr { display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; }
.pg-title { font-size: 20px; font-weight: 600; margin: 0; }
.count { color: #6b7280; font-weight: 400; font-size: 14px; }
.back-link { font-size: 13px; color: #6b7280; text-decoration: none; }
.back-link:hover { color: #374151; }
.state-msg { color: #9ca3af; font-size: 14px; padding: 24px 0; }
.state-msg--error { color: #dc2626; }
.diagram-warning { color: #92400e; background: #fef3c7; padding: 4px 8px; border-radius: 4px; font-size: 12px; margin-bottom: 6px; }
.svg-wrap { overflow: auto; border: 1px solid #e5e7eb; border-radius: 8px; padding: 12px; }
.svg-wrap :deep(svg) { display: block; max-width: none; }
</style>
