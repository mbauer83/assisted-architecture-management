<script setup lang="ts">
import { inject, onMounted, watch, computed, ref } from 'vue'
import { useRoute, RouterLink } from 'vue-router'
import { modelServiceKey } from '../keys'
import { useAsync } from '../composables/useAsync'
import type { DiagramDetail } from '../../domain'

const svc = inject(modelServiceKey)!
const route = useRoute()

const diagramId = computed(() => (route.query.id as string | undefined) ?? '')
const detail = useAsync<DiagramDetail>()
const showSource = ref(false)

const load = () => {
  if (!diagramId.value) return
  detail.run(svc.getDiagram(diagramId.value))
}

onMounted(load)
watch(diagramId, load)

const imageUrl = computed(() => {
  const d = detail.data.value
  if (!d?.rendered_filename) return null
  return svc.diagramImageUrl(d.rendered_filename)
})
</script>

<template>
  <div>
    <RouterLink to="/diagrams" class="back-link">← Browse diagrams</RouterLink>

    <div v-if="detail.loading.value" class="state-msg">Loading...</div>
    <div v-else-if="detail.error.value" class="state-msg state-msg--error">{{ detail.error.value }}</div>

    <template v-else-if="detail.data.value">
      <div class="diagram-header">
        <div class="title-row">
          <h1 class="diagram-name">{{ detail.data.value.name }}</h1>
          <span class="status-badge" :class="`status--${detail.data.value.status}`">
            {{ detail.data.value.status }}
          </span>
        </div>
        <div class="meta-row">
          <span class="type-badge">{{ detail.data.value.diagram_type.replace('archimate-', '') }}</span>
          <span class="sep">·</span>
          <span class="meta-item">v{{ detail.data.value.version }}</span>
        </div>
        <div class="artifact-id mono">{{ detail.data.value.artifact_id }}</div>
      </div>

      <div v-if="imageUrl" class="rendered-card card">
        <img :src="imageUrl" :alt="detail.data.value.name" class="rendered-img" />
      </div>
      <div v-else class="card no-render">
        <p>No rendered image available.</p>
      </div>

      <div v-if="detail.data.value.puml_source" class="source-section">
        <button class="toggle-btn" @click="showSource = !showSource">
          {{ showSource ? 'Hide' : 'Show' }} PlantUML source
        </button>
        <pre v-if="showSource" class="puml-source">{{ detail.data.value.puml_source }}</pre>
      </div>
    </template>
  </div>
</template>

<style scoped>
.back-link { font-size: 13px; color: #6b7280; display: inline-block; margin-bottom: 16px; }
.back-link:hover { color: #374151; }

.state-msg { color: #6b7280; padding: 4px 0; }
.state-msg--error { color: #dc2626; }

.diagram-header { margin-bottom: 20px; }
.title-row { display: flex; align-items: center; gap: 12px; margin-bottom: 8px; }
.diagram-name { font-size: 22px; font-weight: 700; }
.meta-row { display: flex; align-items: center; gap: 8px; font-size: 13px; color: #374151; margin-bottom: 6px; }
.sep { color: #9ca3af; }
.artifact-id { font-size: 11px; color: #9ca3af; }
.mono { font-family: monospace; }

.card { background: white; border-radius: 8px; border: 1px solid #e5e7eb; }
.rendered-card { padding: 16px; margin-bottom: 16px; overflow-x: auto; }
.rendered-img { max-width: 100%; height: auto; display: block; }
.no-render { padding: 24px; color: #6b7280; text-align: center; margin-bottom: 16px; }

.source-section { margin-top: 16px; }
.toggle-btn {
  padding: 6px 14px; border-radius: 6px; border: 1px solid #d1d5db;
  background: white; font-size: 13px; cursor: pointer; color: #374151; margin-bottom: 8px;
}
.toggle-btn:hover { background: #f9fafb; }

.puml-source {
  background: #1e293b; color: #e2e8f0; padding: 16px; border-radius: 8px;
  font-size: 12px; line-height: 1.5; overflow-x: auto; white-space: pre;
}

.type-badge {
  padding: 2px 8px; border-radius: 4px; font-size: 11px;
  background: #dbeafe; color: #1e40af; font-weight: 500;
}
.status-badge { padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 500; }
.status--draft { background: #f3f4f6; color: #6b7280; }
.status--active { background: #dcfce7; color: #166534; }
.status--deprecated { background: #fee2e2; color: #991b1b; }
</style>
