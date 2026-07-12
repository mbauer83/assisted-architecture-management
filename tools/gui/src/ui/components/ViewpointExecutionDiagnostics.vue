<script setup lang="ts">
/**
 * Shared execution-diagnostics panel (companion plan §7.1/§5.1) — the four counts,
 * truncation/empty/unsupported-capability states, the plain-language query summary as
 * the active-filter display, and the derived legend. Reused by every execution
 * representation (WU-E8 exploration; WU-E9 table/matrix/diagram) so diagnostics never
 * drift between surfaces. Ephemeral/read-only: nothing here is persisted.
 */
import type { ExecutionDiagnostics, LegendEntry } from './ViewpointExecutionDiagnostics.helpers'
import { tokenColor, tokenLabel } from '../lib/viewpointStyleTokens'

defineProps<{
  diagnostics: ExecutionDiagnostics
  legend: readonly LegendEntry[]
  querySummary: string
}>()
const emit = defineEmits<{ rerun: [] }>()
</script>

<template>
  <div class="vp-diagnostics">
    <div class="vp-diagnostics-row">
      <span class="vp-filter-label">Active filter:</span>
      <span class="vp-filter-summary">{{ querySummary }}</span>
      <button
        class="vp-rerun-btn"
        title="Re-run this viewpoint against the current model"
        @click="emit('rerun')"
      >
        ↻ Re-run
      </button>
    </div>

    <div
      v-if="diagnostics.isEmpty || diagnostics.emptyReason"
      class="vp-empty-state"
    >
      {{ diagnostics.emptyReason }}
    </div>

    <template v-else>
      <div class="vp-counts">
        Entities: {{ diagnostics.returnedEntityCount }} / {{ diagnostics.totalEntityCount }} ·
        Connections: {{ diagnostics.returnedConnectionCount }} / {{ diagnostics.totalConnectionCount }}
      </div>

      <div
        v-if="diagnostics.truncated"
        class="vp-warning"
      >
        {{ diagnostics.truncationMessage }}
      </div>
    </template>

    <div
      v-if="diagnostics.unsupportedCapabilities.length > 0"
      class="vp-warning"
    >
      Not rendered in this view: {{ diagnostics.unsupportedCapabilities.join(', ') }}
    </div>

    <div
      v-for="warning in diagnostics.warnings"
      :key="warning"
      class="vp-warning"
    >
      {{ warning }}
    </div>

    <div
      v-if="legend.length > 0"
      class="vp-legend"
    >
      <span
        v-for="entry in legend"
        :key="`${entry.capability}:${entry.token}:${entry.label}`"
        class="vp-legend-entry"
      >
        <span
          class="vp-legend-swatch"
          :style="{ background: tokenColor(entry.token) }"
        />
        {{ entry.capability }}: {{ tokenLabel(entry.token) }} ({{ entry.label }})
      </span>
    </div>
  </div>
</template>

<style scoped>
.vp-diagnostics {
  display: flex; flex-direction: column; gap: 6px; padding: 8px 12px;
  border-bottom: 1px solid #e5e7eb; background: #f9fafb; font-size: 12px;
}
.vp-diagnostics-row { display: flex; align-items: center; gap: 8px; }
.vp-filter-label { color: #6b7280; font-weight: 600; }
.vp-filter-summary { color: #374151; flex: 1; }
.vp-rerun-btn {
  padding: 2px 8px; border-radius: 4px; border: 1px solid #d1d5db;
  background: white; font-size: 11px; cursor: pointer; color: #374151;
}
.vp-rerun-btn:hover { background: #f3f4f6; }
.vp-counts { color: #6b7280; }
.vp-empty-state { color: #6b7280; font-style: italic; }
.vp-warning { color: #92400e; background: #fef3c7; padding: 4px 8px; border-radius: 4px; }
.vp-legend { display: flex; flex-wrap: wrap; gap: 10px; }
.vp-legend-entry { display: inline-flex; align-items: center; gap: 4px; color: #374151; }
.vp-legend-swatch { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
</style>
