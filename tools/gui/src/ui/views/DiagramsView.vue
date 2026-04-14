<script setup lang="ts">
import { inject, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter, RouterLink } from 'vue-router'
import { modelServiceKey } from '../keys'
import { useAsync } from '../composables/useAsync'
import type { DiagramList } from '../../domain'

const svc = inject(modelServiceKey)!
const route = useRoute()
const router = useRouter()
const { data, error, loading, run } = useAsync<DiagramList>()

const DIAGRAM_TYPES = [
  { key: '', label: 'All' },
  { key: 'archimate-motivation', label: 'Motivation' },
  { key: 'archimate-strategy', label: 'Strategy' },
  { key: 'archimate-business', label: 'Business' },
  { key: 'archimate-application', label: 'Application' },
  { key: 'archimate-technology', label: 'Technology' },
  { key: 'archimate-layered', label: 'Layered' },
]

const selectedType = ref((route.query.type as string) ?? '')

const load = () => {
  run(svc.listDiagrams(selectedType.value || undefined))
}

const selectType = (key: string) => {
  selectedType.value = key
  router.replace({ path: '/diagrams', query: key ? { type: key } : {} })
  load()
}

onMounted(load)
watch(() => route.query.type, (t) => {
  selectedType.value = (t as string) ?? ''
  load()
})
</script>

<template>
  <div>
    <h1 class="page-title">Diagrams</h1>

    <div class="filter-bar">
      <button
        v-for="dt in DIAGRAM_TYPES" :key="dt.key"
        class="filter-btn" :class="{ 'filter-btn--active': selectedType === dt.key }"
        @click="selectType(dt.key)"
      >{{ dt.label }}</button>
    </div>

    <div v-if="loading" class="state-msg">Loading...</div>
    <div v-else-if="error" class="state-msg state-msg--error">{{ error }}</div>

    <template v-else-if="data">
      <p class="result-count">{{ data.total }} diagram{{ data.total !== 1 ? 's' : '' }}</p>

      <div class="diagram-grid">
        <RouterLink
          v-for="d in data.items" :key="d.artifact_id"
          :to="{ path: '/diagram', query: { id: d.artifact_id } }"
          class="diagram-card card"
        >
          <div class="diagram-name">{{ d.name }}</div>
          <div class="diagram-meta">
            <span class="diagram-type-badge">{{ d.diagram_type.replace('archimate-', '') }}</span>
            <span class="status-badge" :class="`status--${d.status}`">{{ d.status }}</span>
          </div>
          <div class="diagram-id mono">{{ d.artifact_id }}</div>
        </RouterLink>
      </div>
    </template>
  </div>
</template>

<style scoped>
.page-title { font-size: 22px; font-weight: 600; margin-bottom: 20px; }
.result-count { font-size: 13px; color: #6b7280; margin-bottom: 12px; }
.state-msg { color: #6b7280; }
.state-msg--error { color: #dc2626; }
.mono { font-family: monospace; }

.filter-bar { display: flex; gap: 6px; margin-bottom: 20px; flex-wrap: wrap; }
.filter-btn {
  padding: 5px 12px; border-radius: 6px; border: 1px solid #d1d5db;
  background: white; font-size: 13px; cursor: pointer; color: #374151;
}
.filter-btn:hover { background: #f9fafb; }
.filter-btn--active { background: #2563eb; color: white; border-color: #2563eb; }

.diagram-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px;
}
.card {
  background: white; border-radius: 8px; border: 1px solid #e5e7eb; padding: 16px;
  color: inherit;
}
.card:hover { text-decoration: none; box-shadow: 0 2px 8px rgba(0,0,0,.08); }

.diagram-name { font-weight: 600; font-size: 14px; margin-bottom: 8px; }
.diagram-meta { display: flex; gap: 8px; align-items: center; margin-bottom: 6px; }
.diagram-id { font-size: 11px; color: #9ca3af; }

.diagram-type-badge {
  padding: 2px 8px; border-radius: 4px; font-size: 11px;
  background: #dbeafe; color: #1e40af; font-weight: 500;
}
.status-badge { padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 500; }
.status--draft { background: #f3f4f6; color: #6b7280; }
.status--active { background: #dcfce7; color: #166534; }
.status--deprecated { background: #fee2e2; color: #991b1b; }
</style>
