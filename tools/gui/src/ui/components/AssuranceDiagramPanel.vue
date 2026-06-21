<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'

const props = defineProps<{
  diagramId: string
}>()

const loading = ref(false)
const puml = ref<string | null>(null)
const svg = ref<string | null>(null)
const error = ref<string | null>(null)
const visibilityLimited = ref(false)
const showPuml = ref(false)

async function load() {
  loading.value = true
  puml.value = null
  svg.value = null
  error.value = null
  visibilityLimited.value = false
  try {
    const resp = await fetch(`/api/assurance/diagrams/${encodeURIComponent(props.diagramId)}/rendered`)
    if (resp.status === 423) { error.value = 'Store is locked.'; return }
    if (resp.status === 404) { error.value = 'Diagram not found.'; return }
    if (!resp.ok) { error.value = `HTTP ${resp.status}`; return }
    const body = await resp.json() as {
      diagram_id: string
      puml: string
      svg: string | null
      visibility_limited: boolean
    }
    puml.value = body.puml
    svg.value = body.svg ?? null
    visibilityLimited.value = body.visibility_limited
  } catch (e) {
    error.value = String(e)
  } finally {
    loading.value = false
  }
}

watch(() => props.diagramId, load)
onMounted(load)
</script>

<template>
  <div class="assurance-diagram-panel">
    <div
      v-if="loading"
      class="panel-state"
    >
      Loading…
    </div>
    <div
      v-else-if="error"
      class="panel-error"
    >
      {{ error }}
    </div>
    <template v-else>
      <p
        v-if="visibilityLimited"
        class="visibility-note"
      >
        Some nodes are withheld by your TLP ceiling.
      </p>

      <!-- SVG render (if plantuml available) -->
      <!-- eslint-disable-next-line vue/no-v-html -->
      <div
        v-if="svg"
        class="svg-container"
        v-html="svg"
      />

      <!-- PUML source toggle -->
      <div class="puml-toggle">
        <button
          class="puml-toggle-btn"
          @click="showPuml = !showPuml"
        >
          {{ showPuml ? 'Hide' : 'Show' }} PUML source
        </button>
        <pre
          v-if="showPuml"
          class="puml-source"
        >{{ puml }}</pre>
      </div>
    </template>
  </div>
</template>

<style scoped>
.assurance-diagram-panel { display: flex; flex-direction: column; gap: 12px; }
.panel-state { color: #64748b; font-size: 13px; }
.panel-error { color: #dc2626; font-size: 13px; }
.visibility-note { font-size: 12px; color: #92400e; background: #fef3c7; padding: 6px 10px; border-radius: 6px; margin: 0; }
.svg-container { overflow-x: auto; border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px; background: #fff; }
.svg-container :deep(svg) { max-width: 100%; height: auto; }
.puml-toggle-btn { font-size: 12px; color: #6b7280; background: none; border: none; cursor: pointer; padding: 0; text-decoration: underline; }
.puml-source { font-size: 11px; background: #1e293b; color: #e2e8f0; padding: 12px; border-radius: 6px; overflow-x: auto; white-space: pre; margin: 0; }
</style>
