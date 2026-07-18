<script setup lang="ts">
import type { LayoutMode } from '../composables/useForceGraph'
import {
  EXPLORATION_LAYOUT_OPTIONS, SPACING_PRESETS, type ExplorationLayoutOverride,
} from '../views/GraphExploreView.helpers'

export type SpacingPreset = typeof SPACING_PRESETS[number]

const LAYOUT_MODES: { value: LayoutMode; label: string }[] = [
  { value: 'force', label: 'Force' },
  { value: 'cluster', label: 'Cluster' },
]

/** The graph explorer's layout/spacing button groups: free-exploration layout modes,
 * viewpoint-execution layout overrides, and force-layout spacing presets. Spacing stays
 * visible whenever the force layout is active — it must never vanish after a render. */
defineProps<{
  viewpointActive: boolean
  layoutMode: LayoutMode
  layoutOverride: ExplorationLayoutOverride
  idealDist: number
  /** Radial layout is anchor-centric — without an anchored execution it has no center
   * and would fling every node off-viewport, so the option is disabled with a reason. */
  radialAvailable: boolean
}>()
const emit = defineEmits<{
  'switch-layout': [mode: LayoutMode]
  'set-exploration-layout': [value: ExplorationLayoutOverride]
  'apply-preset': [preset: SpacingPreset]
}>()
</script>

<template>
  <div
    v-if="!viewpointActive"
    class="spacing-controls"
  >
    <span class="spacing-label">Layout:</span>
    <button
      v-for="m in LAYOUT_MODES"
      :key="m.value"
      class="spacing-btn"
      :class="{ 'spacing-btn--active': layoutMode === m.value }"
      @click="emit('switch-layout', m.value)"
    >
      {{ m.label }}
    </button>
  </div>
  <div
    v-else
    class="spacing-controls"
  >
    <span class="spacing-label">Layout:</span>
    <button
      v-for="o in EXPLORATION_LAYOUT_OPTIONS"
      :key="o.value"
      class="spacing-btn"
      :class="{ 'spacing-btn--active': layoutOverride === o.value }"
      :disabled="o.value === 'radial' && !radialAvailable"
      :title="o.value === 'radial' && !radialAvailable
        ? 'Radial layout needs an anchored execution — it arranges nodes in rings around the anchor'
        : undefined"
      @click="emit('set-exploration-layout', o.value)"
    >
      {{ o.label }}
    </button>
  </div>
  <div
    v-if="layoutMode === 'force'"
    class="spacing-controls"
  >
    <span class="spacing-label">Spacing:</span>
    <button
      v-for="p in SPACING_PRESETS"
      :key="p.label"
      class="spacing-btn"
      :class="{ 'spacing-btn--active': idealDist === p.idealDist }"
      @click="emit('apply-preset', p)"
    >
      {{ p.label }}
    </button>
  </div>
</template>

<style scoped>
.spacing-controls { display: inline-flex; align-items: center; gap: 4px; margin-left: 12px; }
.spacing-label { font-size: 11.5px; color: #6b7280; }
.spacing-btn {
  font-size: 11.5px; padding: 3px 10px; border: 1px solid #d1d5db; border-radius: 5px;
  background: white; cursor: pointer; color: #374151;
}
.spacing-btn:hover:not(:disabled) { background: #f3f4f6; }
.spacing-btn:disabled { color: #c4c8cf; cursor: not-allowed; }
.spacing-btn--active { background: #2563eb; color: white; border-color: #2563eb; }
</style>
