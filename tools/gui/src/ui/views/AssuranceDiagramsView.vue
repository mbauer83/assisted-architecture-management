<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import AssuranceDiagramPanel from '../components/AssuranceDiagramPanel.vue'

interface DiagramMeta {
  diagram_id: string
  title: string
  description: string
}

const diagrams = ref<DiagramMeta[]>([])
const selected = ref<string | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)

onMounted(async () => {
  try {
    const resp = await fetch('/api/assurance/diagrams')
    if (resp.status === 423) { error.value = 'Store is locked.'; loading.value = false; return }
    if (!resp.ok) { error.value = `HTTP ${resp.status}`; loading.value = false; return }
    const body = await resp.json() as { diagrams: DiagramMeta[] }
    diagrams.value = body.diagrams ?? []
    selected.value = diagrams.value[0]?.diagram_id ?? null
  } catch (e) {
    error.value = String(e)
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="diagrams-view">
    <div class="diagrams-header">
      <RouterLink
        to="/assurance"
        class="back-link"
      >
        ← Assurance
      </RouterLink>
      <h1 class="diagrams-title">
        Derived Diagrams
      </h1>
      <p class="diagrams-subtitle">
        Live projections from the assurance store. Ephemeral — never persisted.
      </p>
    </div>

    <div
      v-if="loading"
      class="state-msg"
    >
      Loading…
    </div>
    <div
      v-else-if="error"
      class="state-error"
    >
      {{ error }}
    </div>
    <div
      v-else
      class="diagrams-layout"
    >
      <!-- Sidebar: diagram selector -->
      <aside class="diagrams-sidebar">
        <button
          v-for="d in diagrams"
          :key="d.diagram_id"
          class="diagram-btn"
          :class="{ 'diagram-btn--active': selected === d.diagram_id }"
          @click="selected = d.diagram_id"
        >
          <span class="diagram-btn__title">{{ d.title }}</span>
          <span class="diagram-btn__desc">{{ d.description }}</span>
        </button>
      </aside>

      <!-- Main: diagram panel -->
      <main class="diagrams-main">
        <AssuranceDiagramPanel
          v-if="selected"
          :diagram-id="selected"
        />
        <p
          v-else
          class="state-msg"
        >
          Select a diagram on the left.
        </p>
      </main>
    </div>
  </div>
</template>

<style scoped>
.diagrams-view { max-width: 1100px; margin: 0 auto; padding: 32px 24px; }
.back-link { font-size: 13px; color: #64748b; display: block; margin-bottom: 16px; }
.diagrams-title { font-size: 22px; font-weight: 700; margin: 0 0 6px; }
.diagrams-subtitle { color: #64748b; font-size: 14px; margin: 0 0 28px; }
.state-msg { color: #64748b; font-size: 14px; }
.state-error { color: #dc2626; font-size: 14px; }
.diagrams-layout { display: grid; grid-template-columns: 220px 1fr; gap: 20px; }
.diagrams-sidebar { display: flex; flex-direction: column; gap: 8px; }
.diagram-btn {
  display: flex; flex-direction: column; gap: 4px;
  text-align: left; padding: 12px 14px;
  border: 1px solid #e2e8f0; border-radius: 8px;
  background: #fff; cursor: pointer;
}
.diagram-btn:hover { border-color: #2563eb; }
.diagram-btn--active { border-color: #2563eb; background: #eff6ff; }
.diagram-btn__title { font-size: 13px; font-weight: 600; color: #111827; }
.diagram-btn__desc { font-size: 11px; color: #64748b; line-height: 1.4; }
.diagrams-main { min-height: 200px; }
</style>
