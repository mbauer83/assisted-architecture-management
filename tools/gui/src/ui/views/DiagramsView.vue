<script setup lang="ts">
import { computed, inject, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter, RouterLink } from 'vue-router'
import type { RepoScope, RepoError } from '../../ports/ModelRepository'
import { modelServiceKey } from '../keys'
import { useQuery } from '../composables/useQuery'
import type { DiagramList } from '../../domain'
import DownloadMenu from '../components/DownloadMenu.vue'

const props = defineProps<{ scope?: RepoScope }>()

const isGlobal = computed(() => props.scope === 'global')

const svc = inject(modelServiceKey)!
const route = useRoute()
const router = useRouter()
const diagramsState = useQuery<DiagramList, RepoError>()

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

const basePath = computed(() => isGlobal.value ? '/global/diagrams' : '/diagrams')

const load = () => {
  if (isGlobal.value) return
  diagramsState.run(svc.listDiagrams(selectedType.value || undefined))
}

const selectType = (key: string) => {
  selectedType.value = key
  void router.replace({ path: basePath.value, query: key ? { type: key } : {} })
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
    <div class="page-header">
      <h1 class="page-title">
        <span
          v-if="isGlobal"
          class="global-badge"
        >Global</span>
        Diagrams
      </h1>
      <RouterLink
        v-if="!isGlobal"
        to="/diagram/create"
        class="create-btn"
      >
        + Create Diagram
      </RouterLink>
    </div>

    <template v-if="isGlobal">
      <p class="state-msg">
        No diagrams in the global repository yet.
      </p>
    </template>
    <template v-else>
      <div class="filter-bar">
        <button
          v-for="dt in DIAGRAM_TYPES"
          :key="dt.key"
          class="filter-btn"
          :class="{ 'filter-btn--active': selectedType === dt.key }"
          @click="selectType(dt.key)"
        >
          {{ dt.label }}
        </button>
      </div>

      <div
        v-if="diagramsState.loading.value"
        class="state-msg"
      >
        Loading...
      </div>
      <div
        v-else-if="diagramsState.errorMessage.value"
        class="state-msg state-msg--error"
      >
        {{ diagramsState.errorMessage.value }}
      </div>

      <template v-else-if="diagramsState.data.value">
        <p class="result-count">
          {{ diagramsState.data.value.total }} diagram{{ diagramsState.data.value.total !== 1 ? 's' : '' }}
        </p>

        <div class="diagram-grid">
          <div
            v-for="d in diagramsState.data.value.items"
            :key="d.artifact_id"
            class="diagram-card card"
          >
            <RouterLink
              :to="{ path: '/diagram', query: { id: d.artifact_id } }"
              class="card-link"
            >
              <div class="diagram-name">
                {{ d.name }}
              </div>
              <div class="diagram-meta">
                <span class="diagram-type-badge">{{ d.diagram_type.replace('archimate-', '') }}</span>
                <span
                  class="status-badge"
                  :class="`status--${d.status}`"
                >{{ d.status }}</span>
              </div>
              <div class="diagram-id mono">
                {{ d.artifact_id }}
              </div>
            </RouterLink>
            <DownloadMenu
              :diagram-id="d.artifact_id"
              :diagram-name="d.name"
              class="card-dl"
            />
          </div>
        </div>
      </template>
    </template> <!-- end v-else (non-global) -->
  </div>
</template>

<style scoped>
.page-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; }
.page-title { font-size: 22px; font-weight: 600; margin-bottom: 0; display: flex; align-items: center; gap: 8px; }
.global-badge {
  display: inline-block; background: #fef3c7; color: #92400e;
  border: 1px solid #fde68a; border-radius: 4px;
  padding: 2px 8px; font-size: 11px; font-weight: 700;
  text-transform: uppercase; letter-spacing: .05em;
}
.create-btn {
  padding: 7px 14px; background: #2563eb; color: white; border-radius: 6px;
  font-size: 13px; font-weight: 500; text-decoration: none;
}
.create-btn:hover { background: #1d4ed8; text-decoration: none; }
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
  background: white; border-radius: 8px; border: 1px solid #e5e7eb;
  position: relative;
}
.card:hover { box-shadow: 0 2px 8px rgba(0,0,0,.08); }
.card-link { display: block; padding: 16px; color: inherit; text-decoration: none; }
.card-link:hover { text-decoration: none; }
.card-dl { position: absolute; top: 10px; right: 10px; }

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
