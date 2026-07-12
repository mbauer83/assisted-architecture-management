<script setup lang="ts">
/**
 * Ephemeral viewpoint-execution matrix (companion plan §5.1/§5.4, WU-E9): read-only
 * rendering via the viewpoint's `matrix` presentation — grouped axes (one population,
 * displayed with row/column grouping) or criteria axes (two independent populations,
 * `result.matrix_axes`). Never persisted, no `ViewpointApplication`.
 */
import { computed, inject, onMounted, ref } from 'vue'
import { Effect } from 'effect'
import { RouterLink, useRoute } from 'vue-router'
import { modelServiceKey } from '../keys'
import { useViewpointExecution } from '../composables/useViewpointExecution'
import ViewpointExecutionDiagnostics from '../components/ViewpointExecutionDiagnostics.vue'
import { computeExecutionDiagnostics, deriveLegend } from '../components/ViewpointExecutionDiagnostics.helpers'
import { presentationFromMapping } from '../../domain/viewpointPresentationSerialization'
import {
  buildMatrixCells, cellEmphasisToken, cellKey, projectionByItemId, resolveMatrixAxes,
} from './ViewpointMatrixView.helpers'
import { tokenColor, tokenLabel } from '../lib/viewpointStyleTokens'
import type { ViewpointDefinitionEnvelope } from '../../domain'

const svc = inject(modelServiceKey)!
const route = useRoute()
const slug = computed(() => (route.query.viewpoint as string | undefined) ?? '')

const definitions = ref<readonly ViewpointDefinitionEnvelope[]>([])
const execution = useViewpointExecution(svc)

const presentation = computed(() => {
  const envelope = definitions.value.find((d) => d.slug === slug.value)
  return envelope ? presentationFromMapping(envelope.presentation) : null
})
const diagnostics = computed(() => computeExecutionDiagnostics(execution.result.value, presentation.value, 'matrix'))
const legend = computed(() => deriveLegend(presentation.value))
const entityStyleById = computed(() => projectionByItemId(execution.projection.value))
const axes = computed(() => resolveMatrixAxes(presentation.value, execution.result.value))
const cells = computed(() => buildMatrixCells(axes.value.rowIds, axes.value.columnIds, execution.result.value?.connections ?? []))
const entityNameById = computed(() => new Map((execution.result.value?.entities ?? []).map((e) => [e.id, e.name])))

const cellLabel = (rowId: string, columnId: string): string => {
  const cell = cells.value.get(cellKey(rowId, columnId))
  return cell ? `${cell.connectionCount} (${cell.connectionTypes.join(', ')})` : ''
}
const cellColor = (rowId: string, columnId: string): string | null => {
  const token = cellEmphasisToken(rowId, columnId, entityStyleById.value)
  return token !== undefined ? tokenColor(token) : null
}
const cellTitle = (rowId: string, columnId: string): string | undefined => {
  const token = cellEmphasisToken(rowId, columnId, entityStyleById.value)
  return token !== undefined ? tokenLabel(token) : undefined
}

const load = async () => {
  definitions.value = await Effect.runPromise(svc.listViewpointDefinitions()).catch(() => [])
  await execution.execute({ slug: slug.value })
}
const rerun = () => void load()

onMounted(() => { if (slug.value) void load() })
</script>

<template>
  <div class="page">
    <div class="hdr">
      <h1 class="pg-title">
        {{ slug }} <span class="count">(matrix)</span>
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
      v-if="execution.loading.value"
      class="state-msg"
    >
      Loading…
    </div>
    <div
      v-else-if="execution.errorMessage.value"
      class="state-msg state-msg--error"
    >
      {{ execution.errorMessage.value }}
    </div>
    <div
      v-else-if="axes.rowIds.length > 0 && axes.columnIds.length > 0"
      class="matrix-scroll"
    >
      <table class="matrix-table">
        <thead>
          <tr>
            <th />
            <th
              v-for="columnId in axes.columnIds"
              :key="columnId"
            >
              {{ entityNameById.get(columnId) ?? columnId }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="rowId in axes.rowIds"
            :key="rowId"
          >
            <th>{{ entityNameById.get(rowId) ?? rowId }}</th>
            <td
              v-for="columnId in axes.columnIds"
              :key="columnId"
              :style="cellColor(rowId, columnId) ? { background: cellColor(rowId, columnId) as string } : {}"
              :title="cellTitle(rowId, columnId)"
            >
              {{ cellLabel(rowId, columnId) }}
            </td>
          </tr>
        </tbody>
      </table>
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
.matrix-scroll { overflow: auto; max-height: clamp(300px, 65vh, 800px); border: 1px solid #e5e7eb; border-radius: 8px; }
.matrix-table { border-collapse: collapse; font-size: 12px; }
.matrix-table th, .matrix-table td { border: 1px solid #e5e7eb; padding: 6px 8px; text-align: center; white-space: nowrap; }
.matrix-table thead th { position: sticky; top: 0; background: #f9fafb; z-index: 1; }
.matrix-table tbody th { position: sticky; left: 0; background: #f9fafb; text-align: left; z-index: 1; }
</style>
