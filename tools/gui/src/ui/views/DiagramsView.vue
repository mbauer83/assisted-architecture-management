<script setup lang="ts">
import { computed, inject, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter, RouterLink } from 'vue-router'
import { Effect } from 'effect'
import type { RepoScope, RepoError } from '../../ports/ModelRepository'
import { modelServiceKey } from '../keys'
import { useQuery } from '../composables/useQuery'
import type { DiagramTypeSummary, DiagramList, DiagramSummary, GroupList } from '../../domain'
import DownloadMenu from '../components/DownloadMenu.vue'
import GroupSelector from '../components/GroupSelector.vue'

const props = defineProps<{ scope?: RepoScope }>()

const isGlobal = computed(() => props.scope === 'global')

const svc = inject(modelServiceKey)!
const route = useRoute()
const router = useRouter()
const diagramsState = useQuery<DiagramList, RepoError>()
const groupsState = useQuery<GroupList, RepoError>()
const diagramKinds = ref<DiagramTypeSummary[]>([])
const showArchivedGroups = ref(false)

const selectedType = ref((route.query.type as string) ?? '')
const activeGroup = computed(() => (route.query.group as string | undefined) ?? '')

const basePath = computed(() => isGlobal.value ? '/global/diagrams' : '/diagrams')
const diagramFilters = computed(() => {
  const seen = new Set<string>(['', 'archimate-all'])
  const filters = [
    { key: '', label: 'All' },
    { key: 'archimate-all', label: 'ArchiMate' },
  ]
  for (const kind of diagramKinds.value) {
    if (seen.has(kind.key)) continue
    seen.add(kind.key)
    filters.push({ key: kind.key, label: kind.label.replace(/\s+Diagram$/i, '') })
  }
  filters.push({ key: 'other', label: 'Other' })
  return filters
})
const createDiagramRoute = (kind: DiagramTypeSummary) => {
  if (kind.key === 'matrix') return { path: '/diagram/create/matrix' }
  return { path: '/diagram/create', query: { type: kind.key } }
}
const showCreateMenu = ref(false)
let _closeMenuTimer: ReturnType<typeof setTimeout> | null = null
const closeCreateMenu = () => { _closeMenuTimer = setTimeout(() => { showCreateMenu.value = false }, 150) }
const keepCreateMenu = () => { if (_closeMenuTimer !== null) { clearTimeout(_closeMenuTimer); _closeMenuTimer = null } }

const STORAGE_KEY = 'arch_group_diagram-collection'

const setGroup = (g: string) => {
  void router.replace({ path: basePath.value, query: { ...(selectedType.value ? { type: selectedType.value } : {}), group: g || undefined } })
  if (!isGlobal.value) localStorage.setItem(STORAGE_KEY, g)
}
const goToGroups = () => {
  localStorage.removeItem(STORAGE_KEY)
  void router.push('/diagrams/groups')
}

const load = () => {
  if (isGlobal.value) return
  diagramsState.run(svc.listDiagrams(undefined))
}
const loadGroups = () => { if (!isGlobal.value) groupsState.run(svc.listGroups('diagram-collection')) }

const loadDiagramTypes = () => {
  if (isGlobal.value) return
  void Effect.runPromise(svc.listDiagramTypes())
    .then((kinds) => { diagramKinds.value = kinds })
    .catch(() => { diagramKinds.value = [] })
}

const matchesFilter = (d: DiagramSummary, filterKey: string): boolean => {
  if (!filterKey) return true
  if (filterKey === 'archimate-all') return d.diagram_type === 'archimate' || d.diagram_type.startsWith('archimate-')
  if (filterKey === 'matrix') return d.diagram_type === 'matrix'
  if (filterKey === 'other') return d.diagram_type !== 'matrix' && d.diagram_type !== 'archimate' && !d.diagram_type.startsWith('archimate-')
  return d.diagram_type === filterKey
}

const groupOptions = computed(() => {
  const all = diagramsState.data.value?.items ?? []
  const counts: Record<string, number> = {}
  for (const item of all) { const g = item.group ?? 'uncategorized'; counts[g] = (counts[g] ?? 0) + 1 }
  const registry = groupsState.data.value?.['diagram-collections'] ?? []
  if (registry.length > 0) {
    // Whole-catalog member_count from the registry — the loaded list is group-filtered, so
    // counting it shows zero for every non-active group.
    return registry.map(g => ({
      slug: g.slug, name: g.name, count: g.member_count ?? 0,
      archived: g.archived ?? false, type_filter: g.type_filter ?? [],
    }))
  }
  return Object.entries(counts).sort(([a], [b]) => a.localeCompare(b)).map(([slug, count]) => ({ slug, name: slug, count, type_filter: [] as string[] }))
})

const activeGroupTypeFilter = computed(() =>
  groupOptions.value.find(g => g.slug === activeGroup.value)?.type_filter ?? [],
)

const filteredItems = computed(() => {
  const items = diagramsState.data.value?.items ?? []
  return items.filter(d =>
    matchesFilter(d, selectedType.value) &&
    (!activeGroup.value || (d.group ?? 'uncategorized') === activeGroup.value) &&
    (activeGroupTypeFilter.value.length === 0 || activeGroupTypeFilter.value.includes(d.diagram_type)),
  )
})

const diagramTypeLabel = (diagramType: string): string => {
  if (diagramType === 'matrix') return 'matrix'
  if (diagramType === 'archimate') return 'archimate'
  if (diagramType.startsWith('archimate-')) return diagramType.replace('archimate-', '')
  return diagramType
}

const selectType = (key: string) => {
  selectedType.value = key
  void router.replace({ path: basePath.value, query: { ...(key ? { type: key } : {}), ...(activeGroup.value ? { group: activeGroup.value } : {}) } })
  load()
}

let refreshEventSource: EventSource | null = null
onMounted(() => {
  if (!isGlobal.value && !route.query.group) {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved === null) {
      void router.replace('/diagrams/groups')
      return
    }
    if (saved) {
      void router.replace({ path: basePath.value, query: { ...(selectedType.value ? { type: selectedType.value } : {}), group: saved } })
    }
  }
  loadDiagramTypes()
  load()
  loadGroups()
  refreshEventSource = new EventSource('/api/events')
  refreshEventSource.addEventListener('artifact_write_completed', () => { load(); loadGroups() })
})
onUnmounted(() => { refreshEventSource?.close() })
watch(() => route.query.type, (t) => { selectedType.value = (t as string) ?? ''; load() })
</script>

<template>
  <div class="layout">
    <aside
      v-if="!isGlobal"
      class="sidebar"
    >
      <div class="sidebar-header">
        <h2 class="sidebar-title">
          Collection
        </h2>
        <RouterLink
          to="/diagrams/groups"
          class="manage-link"
          title="Manage collections"
        >
          ⚙
        </RouterLink>
      </div>
      <GroupSelector
        :groups="groupOptions"
        :model-value="activeGroup"
        :show-archived="showArchivedGroups"
        :manageable="true"
        axis="diagram-collection"
        @update:model-value="setGroup"
        @update:show-archived="v => showArchivedGroups = v"
        @group-mutated="() => { load(); loadGroups() }"
        @navigate-to-groups="goToGroups"
      />
    </aside>
    <section class="content">
      <div class="page-header">
        <h1 class="page-title">
          <span
            v-if="isGlobal"
            class="global-badge"
          >Global</span>
          Diagrams
        </h1>
        <div
          v-if="!isGlobal"
          class="create-wrap"
          @mouseenter="keepCreateMenu"
        >
          <button
            class="create-btn"
            @click="showCreateMenu = !showCreateMenu"
            @blur="closeCreateMenu"
          >
            + Create Diagram ▾
          </button>
          <div
            v-if="showCreateMenu"
            class="create-menu"
            @mouseenter="keepCreateMenu"
          >
            <RouterLink
              v-for="kind in diagramKinds"
              :key="kind.key"
              :to="createDiagramRoute(kind)"
              class="create-opt"
              @click="showCreateMenu = false"
            >
              {{ kind.label }}
            </RouterLink>
          </div>
        </div>
      </div>

      <template v-if="isGlobal">
        <p class="state-msg">
          No diagrams in the global repository yet.
        </p>
      </template>
      <template v-else>
        <div class="filter-bar">
          <button
            v-for="dt in diagramFilters"
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
          <p
            v-if="filteredItems.length === 0 && activeGroup"
            class="state-msg"
          >
            No diagrams in "{{ groupOptions.find(g => g.slug === activeGroup)?.name ?? activeGroup }}" yet.
          </p>
          <p class="result-count">
            {{ filteredItems.length }} diagram{{ filteredItems.length !== 1 ? 's' : '' }}
          </p>

          <div class="diagram-grid">
            <div
              v-for="d in filteredItems"
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
                  <span class="diagram-type-badge">{{ diagramTypeLabel(d.diagram_type) }}</span>
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
    </section>
  </div>
</template>

<style scoped>
.layout { display: flex; gap: 24px; }
.sidebar { width: 190px; flex-shrink: 0; }
.sidebar-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px; }
.sidebar-title { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: .05em; color: #6b7280; }
.manage-link { font-size: 14px; color: #9ca3af; text-decoration: none; }
.manage-link:hover { color: #374151; }
.content { flex: 1; min-width: 0; }
.page-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; }
.page-title { font-size: 22px; font-weight: 600; margin-bottom: 0; display: flex; align-items: center; gap: 8px; }
.global-badge {
  display: inline-block; background: #fef3c7; color: #92400e;
  border: 1px solid #fde68a; border-radius: 4px;
  padding: 2px 8px; font-size: 11px; font-weight: 700;
  text-transform: uppercase; letter-spacing: .05em;
}
.create-wrap { position: relative; }
.create-btn {
  padding: 7px 14px; background: #2563eb; color: white; border-radius: 6px;
  font-size: 13px; font-weight: 500; border: none; cursor: pointer;
}
.create-btn:hover { background: #1d4ed8; }
.create-menu {
  position: absolute; right: 0; top: calc(100% + 4px); z-index: 20;
  background: white; border: 1px solid #e5e7eb; border-radius: 6px;
  box-shadow: 0 4px 12px rgba(0,0,0,.12); min-width: 170px; padding: 4px 0;
}
.create-opt {
  display: block; padding: 8px 14px; font-size: 13px; color: #374151;
  text-decoration: none; white-space: nowrap;
}
.create-opt:hover { background: #f9fafb; color: #1d4ed8; text-decoration: none; }
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
