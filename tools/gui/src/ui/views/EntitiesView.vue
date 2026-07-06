<script setup lang="ts">
import { computed, inject, onMounted, onUnmounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import type { EntityList, EntityTaxonomy, GroupList } from '../../domain'
import type { RepoScope, RepoError } from '../../ports/ModelRepository'
import { modelServiceKey } from '../keys'
import { useQuery } from '../composables/useQuery'
import { usePagination } from '../composables/usePagination'
import EntitiesTreemap from '../components/EntitiesTreemap.vue'
import ArchimateTypeGlyph from '../components/ArchimateTypeGlyph.vue'
import EntityGroupNavTree from '../components/EntityGroupNavTree.vue'
import {
  friendlyEntityId,
  getEntityConnectionTotal,
  getDomainLabel,
} from '../lib/domains'

const props = defineProps<{ scope?: RepoScope }>()

type ViewMode = 'table' | 'treemap'
type SortKey = 'type' | 'in' | 'sym' | 'out' | 'total'

const PAGE_SIZE = 50
const STORAGE_KEY = 'arch_group_model-project'

const svc = inject(modelServiceKey)!
const route = useRoute()
const router = useRouter()
const entityListState = useQuery<EntityList, RepoError>()
const groupsState = useQuery<GroupList, RepoError>()
const taxonomyState = useQuery<EntityTaxonomy, RepoError>()

const isGlobal = computed(() => props.scope === 'global')
const basePath = computed(() => isGlobal.value ? '/global/entities' : '/entities')

const activeDomain = computed(() => (route.query.domain as string | undefined) ?? '')
const activeGroup = computed(() => (route.query.group as string | undefined) ?? '')
const viewMode = computed<ViewMode>(() => route.query.view === 'treemap' ? 'treemap' : 'table')
const typeFilter = ref((route.query.type as string | undefined) ?? '')
const sortKey = ref<SortKey | null>(null)
const sortOrder = ref<1 | -1>(1)
const showArchivedGroups = ref(false)

// Group view: named group selected (not 'uncategorized' or global).
// All group entities are loaded at once (limit 1000); domain/type filters are client-side.
// Non-group view: server-side domain+type filtering with PAGE_SIZE pagination.
const isGroupView = computed(() =>
  !isGlobal.value && Boolean(activeGroup.value) && activeGroup.value !== 'uncategorized'
)

const { currentPage, pageCount, hasPrev, hasNext, goNext, goPrev, reset: resetPage, offset } =
  usePagination(computed(() => entityListState.data.value?.total ?? 0), PAGE_SIZE)

const replaceQuery = (patch: Record<string, string | undefined>) =>
  void router.replace({ path: basePath.value, query: { ...route.query, ...patch } })

const setDomain = (domain: string) => replaceQuery({ domain: domain || undefined })
const setGroup = (group: string) => {
  replaceQuery({ group: group || undefined, domain: undefined })
  if (!isGlobal.value) localStorage.setItem(STORAGE_KEY, group)
}
const goToGroups = () => { localStorage.removeItem(STORAGE_KEY); void router.push('/entities/groups') }
const setViewMode = (view: ViewMode) => replaceQuery({ view: view === 'table' ? undefined : view })

const loadCurrentPage = () => entityListState.run(
  isGroupView.value
    ? svc.listEntities({ scope: props.scope, group: activeGroup.value, limit: 1000 })
    : svc.listEntities({
        scope: props.scope,
        domain: activeDomain.value || undefined,
        artifactType: typeFilter.value || undefined,
        limit: PAGE_SIZE,
        offset: offset.value,
      })
)

const load = () => { resetPage(); loadCurrentPage() }
const loadGroups = () => groupsState.run(svc.listGroups('model-project'))
const loadTaxonomy = () => taxonomyState.run(
  svc.listEntityTaxonomy({ scope: props.scope, group: activeGroup.value || undefined })
)

const goToNextPage = () => { goNext(); loadCurrentPage() }
const goToPrevPage = () => { goPrev(); loadCurrentPage() }

onMounted(() => {
  if (!isGlobal.value) {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved === null && !route.query.group && !route.query.domain) {
      void router.replace('/entities/groups')
      return
    }
    if (saved && !route.query.group) {
      void router.replace({ path: '/entities', query: { ...route.query, group: saved || undefined } })
    }
  }
  load()
  loadGroups()
  loadTaxonomy()
})

watch(() => props.scope, () => { typeFilter.value = ''; loadTaxonomy(); load() })
watch(activeGroup, () => { loadTaxonomy(); load() })
watch(activeDomain, () => { typeFilter.value = '' })
watch([activeDomain, typeFilter], () => { if (!isGroupView.value) load() })

let refreshEventSource: EventSource | null = null
onMounted(() => {
  refreshEventSource = new EventSource('/api/events')
  refreshEventSource.addEventListener('artifact_write_completed', () => { load(); loadGroups(); loadTaxonomy() })
})
onUnmounted(() => { refreshEventSource?.close() })

const groupOptions = computed(() => {
  // Counts come from the registry's whole-catalog member_count — deriving them from the loaded
  // (group-filtered, paginated) list made every non-active group read zero until clicked.
  const registryData = groupsState.data.value?.['model-projects']
  if (!registryData) return []
  const result = registryData.map(g => ({
    slug: g.slug,
    name: g.name,
    count: g.member_count ?? 0,
    archived: g.archived ?? false,
    meta_ontology: g.meta_ontology ?? '',
  }))
  return [...result].sort((a, b) => {
    if (a.archived !== b.archived) return a.archived ? 1 : -1
    if (a.slug === 'uncategorized' && b.slug !== 'uncategorized') return 1
    if (b.slug === 'uncategorized' && a.slug !== 'uncategorized') return -1
    return a.name.localeCompare(b.name)
  })
})

const activeDomainCounts = computed((): Record<string, number> | undefined => {
  const tax = taxonomyState.data.value
  if (!tax) return undefined
  return Object.fromEntries(tax.domains.map(d => [d.name, d.count]))
})

const uniqueTypes = computed(() => {
  const tax = taxonomyState.data.value
  if (tax) {
    const domains = activeDomain.value ? tax.domains.filter(d => d.name === activeDomain.value) : tax.domains
    return [...new Set(domains.flatMap(d => d.types.map(t => t.name)))].sort()
  }
  return [...new Set((entityListState.data.value?.items ?? []).map(e => e.artifact_type))].sort()
})

const compareValues = (left: number | string, right: number | string) =>
  left < right ? -1 * sortOrder.value : left > right ? 1 * sortOrder.value : 0

const sortBy = (key: SortKey) => {
  if (sortKey.value !== key) { sortKey.value = key; sortOrder.value = 1; return }
  if (sortOrder.value === 1) sortOrder.value = -1
  else { sortKey.value = null; sortOrder.value = 1 }
}

const sortedEntities = computed(() => {
  // Group view: server returns all group items, client filters by domain + type.
  // Non-group view: server already filtered; client only sorts.
  const items = isGroupView.value
    ? (entityListState.data.value?.items.filter(item =>
        (!typeFilter.value || item.artifact_type === typeFilter.value) &&
        (!activeDomain.value || item.domain === activeDomain.value)
      ) ?? [])
    : (entityListState.data.value?.items ?? [])
  if (!sortKey.value) return [...items]
  return [...items].sort((a, b) => {
    if (sortKey.value === 'type') return compareValues(a.artifact_type, b.artifact_type)
    if (sortKey.value === 'in') return compareValues(a.conn_in ?? 0, b.conn_in ?? 0)
    if (sortKey.value === 'sym') return compareValues(a.conn_sym ?? 0, b.conn_sym ?? 0)
    if (sortKey.value === 'out') return compareValues(a.conn_out ?? 0, b.conn_out ?? 0)
    return compareValues(getEntityConnectionTotal(a), getEntityConnectionTotal(b))
  })
})

const browseReturnQuery = computed(() => {
  const q: Record<string, string> = {}
  if (activeDomain.value) q.domain = activeDomain.value
  if (viewMode.value !== 'table') q.view = viewMode.value
  if (typeFilter.value) q.type = typeFilter.value
  return q
})

const pageTitle = computed(() => {
  const scope = isGlobal.value ? 'Global ' : ''
  const domainPart = activeDomain.value ? `${getDomainLabel(activeDomain.value)} ` : ''
  return `${scope}${domainPart}Entities`
})
const sortArrow = (key: SortKey) => sortKey.value === key ? (sortOrder.value === 1 ? '↑' : '↓') : ''

const displayCount = computed(() => {
  const total = entityListState.data.value?.total ?? 0
  if (isGroupView.value) return `${sortedEntities.value.length} / ${total}`
  return String(total)
})
</script>

<template>
  <div class="layout">
    <aside class="sidebar">
      <div class="sidebar-header">
        <h2 class="sidebar-title">
          Project
        </h2>
        <RouterLink
          v-if="!isGlobal"
          to="/entities/groups"
          class="manage-link"
          title="Manage projects"
        >
          ⚙
        </RouterLink>
      </div>

      <EntityGroupNavTree
        v-if="!isGlobal"
        :groups="groupOptions"
        :active-group="activeGroup"
        :active-domain="activeDomain"
        :manageable="true"
        :show-archived="showArchivedGroups"
        :domain-counts="activeDomainCounts"
        axis="model-project"
        @update:active-group="setGroup"
        @update:active-domain="setDomain"
        @update:show-archived="v => showArchivedGroups = v"
        @group-mutated="() => { load(); loadGroups(); loadTaxonomy() }"
        @navigate-to-groups="goToGroups"
      />

      <!-- Global view: flat domain list only -->
      <template v-else>
        <h2
          class="sidebar-title"
          style="margin-top:1rem"
        >
          Domain
        </h2>
        <ul class="domain-list">
          <li>
            <button
              class="domain-btn"
              :class="{ active: activeDomain === '' }"
              @click="setDomain('')"
            >
              All
            </button>
          </li>
        </ul>
      </template>
    </aside>

    <section class="content">
      <div class="content-header">
        <div>
          <h1 class="page-title">
            <span
              v-if="isGlobal"
              class="global-badge"
            >Global</span>
            {{ pageTitle }}
            <span
              v-if="entityListState.data.value"
              class="count"
            >({{ displayCount }})</span>
          </h1>
          <p class="subtitle">
            <template v-if="isGlobal">
              Read-only view of the shared global (enterprise) repository.
            </template>
            <template v-else>
              Filter by project and domain, then inspect the catalog as a sortable table or treemap.
            </template>
          </p>
        </div>
        <div class="actions">
          <div class="view-toggle">
            <button
              class="toggle-btn"
              :class="{ 'toggle-btn--active': viewMode === 'table' }"
              @click="setViewMode('table')"
            >
              Table
            </button>
            <button
              class="toggle-btn"
              :class="{ 'toggle-btn--active': viewMode === 'treemap' }"
              @click="setViewMode('treemap')"
            >
              Treemap
            </button>
          </div>
          <RouterLink
            v-if="!isGlobal"
            to="/entity/create"
            class="create-btn"
          >
            + Create Entity
          </RouterLink>
          <RouterLink
            v-if="!isGlobal"
            to="/model/wizard"
            class="wizard-link"
            title="Guided modeling — questionnaires that walk you from motivation to application"
          >
            ✨ Guided
          </RouterLink>
        </div>
      </div>

      <div class="toolbar">
        <label class="toolbar-field">
          <span>Type</span>
          <select
            v-model="typeFilter"
            class="toolbar-select"
          >
            <option value="">All</option>
            <option
              v-for="type in uniqueTypes"
              :key="type"
              :value="type"
            >{{ type }}</option>
          </select>
        </label>
      </div>

      <div
        v-if="entityListState.loading.value"
        class="state-msg"
      >
        Loading…
      </div>
      <div
        v-else-if="entityListState.errorMessage.value"
        class="state-msg state-msg--error"
      >
        {{ entityListState.errorMessage.value }}
      </div>

      <template v-else-if="entityListState.data.value">
        <div
          v-if="sortedEntities.length === 0"
          class="state-msg"
        >
          <template v-if="activeGroup">
            No entities in "{{ groupOptions.find(g => g.slug === activeGroup)?.name ?? activeGroup }}" yet.
          </template>
          <template v-else>
            No entities found{{ activeDomain ? ` in ${getDomainLabel(activeDomain)}` : '' }}{{ typeFilter ? ` of type "${typeFilter}"` : '' }}.
          </template>
        </div>

        <EntitiesTreemap
          v-else-if="viewMode === 'treemap'"
          :items="sortedEntities"
          :active-domain="activeDomain"
        />

        <template v-else>
          <table class="entity-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>
                  <button
                    class="sort-btn"
                    @click="sortBy('type')"
                  >
                    Type {{ sortArrow('type') }}
                  </button>
                </th>
                <th v-if="!activeDomain">
                  Domain
                </th>
                <th class="th-conn">
                  <button
                    class="sort-btn"
                    @click="sortBy('total')"
                  >
                    Connections {{ sortArrow('total') }}
                  </button>
                  <span class="th-conn-sub">(<button
                    class="sort-sub"
                    @click="sortBy('in')"
                  >in {{ sortArrow('in') }}</button> / <button
                    class="sort-sub"
                    @click="sortBy('sym')"
                  >sym {{ sortArrow('sym') }}</button> / <button
                    class="sort-sub"
                    @click="sortBy('out')"
                  >out {{ sortArrow('out') }}</button>)</span>
                </th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="entity in sortedEntities"
                :key="entity.artifact_id"
                :class="{ 'row--global': entity.is_global }"
              >
                <td>
                  <RouterLink :to="{ path: '/entity', query: { id: entity.artifact_id, ...browseReturnQuery } }">
                    {{ entity.name || friendlyEntityId(entity.artifact_id) }}
                  </RouterLink>
                  <span
                    v-if="entity.is_global && !isGlobal"
                    class="global-chip"
                    title="From the global repository"
                  >global</span>
                  <button
                    v-if="!activeGroup && groupOptions.length > 1 && entity.group && entity.group !== 'uncategorized'"
                    class="group-chip"
                    :title="`In group: ${entity.group}`"
                    @click="setGroup(entity.group ?? '')"
                  >
                    {{ entity.group }}
                  </button>
                </td>
                <td>
                  <span class="type-cell">
                    <ArchimateTypeGlyph
                      :type="entity.artifact_type"
                      :size="15"
                      class="type-glyph"
                    />
                    <span class="mono">{{ entity.artifact_type }}</span>
                  </span>
                </td>
                <td v-if="!activeDomain">
                  <span
                    class="domain-badge"
                    :class="`domain--${entity.domain}`"
                  >{{ entity.domain }}</span>
                </td>
                <td class="conn-counts">
                  {{ getEntityConnectionTotal(entity) }}<span class="conn-split">({{ entity.conn_in ?? 0 }} / {{ entity.conn_sym ?? 0 }} / {{ entity.conn_out ?? 0 }})</span>
                </td>
                <td>
                  <span
                    class="status-badge"
                    :class="`status--${entity.status}`"
                  >{{ entity.status }}</span>
                </td>
              </tr>
            </tbody>
          </table>

          <div
            v-if="!isGroupView && pageCount > 1"
            class="pagination"
          >
            <button
              class="page-btn"
              :disabled="!hasPrev"
              @click="goToPrevPage"
            >
              ← Prev
            </button>
            <span class="page-info">Page {{ currentPage + 1 }} of {{ pageCount }}</span>
            <button
              class="page-btn"
              :disabled="!hasNext"
              @click="goToNextPage"
            >
              Next →
            </button>
          </div>
        </template>
      </template>
    </section>
  </div>
</template>

<style scoped>
.layout { display: flex; gap: 24px; }
.sidebar { width: 190px; flex-shrink: 0; }
.sidebar-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px; }
.sidebar-title { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: .05em; color: #6b7280; }
.manage-link { font-size: 14px; color: #9ca3af; text-decoration: none; line-height: 1; }
.manage-link:hover { color: #374151; }

.domain-list { list-style: none; display: flex; flex-direction: column; gap: 2px; }
.domain-btn { width: 100%; padding: 7px 10px; border: 0; border-left: 3px solid transparent; border-radius: 6px; background: transparent; color: #374151; cursor: pointer; font-size: 13px; text-align: left; }
.domain-btn:hover { background: #f3f4f6; }
.domain-btn.active { background: #eff6ff; color: #1d4ed8; font-weight: 500; }

.content { flex: 1; min-width: 0; }
.content-header, .actions, .view-toggle, .toolbar, .toolbar-field { display: flex; align-items: center; }
.content-header { justify-content: space-between; gap: 16px; margin-bottom: 14px; }
.actions, .view-toggle { gap: 10px; }
.page-title { font-size: 22px; font-weight: 600; }
.subtitle, .count, .state-msg, .conn-split { color: #6b7280; }
.subtitle { margin-top: 2px; font-size: 13px; }
.count { margin-left: 6px; font-size: 14px; font-weight: 400; }
.toolbar { justify-content: space-between; margin-bottom: 14px; }
.toolbar-field { gap: 8px; }
.toolbar-field span { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: .05em; color: #6b7280; }
.toolbar-select, .toggle-btn { border: 1px solid #d1d5db; border-radius: 6px; background: white; color: #374151; }
.toolbar-select { min-width: 180px; padding: 7px 10px; }
.toggle-btn { padding: 7px 12px; cursor: pointer; font-size: 13px; }
.toggle-btn--active { background: #2563eb; border-color: #2563eb; color: white; }
.create-btn { padding: 8px 14px; border-radius: 6px; background: #16a34a; color: white; font-size: 13px; font-weight: 500; white-space: nowrap; }
.create-btn:hover { background: #15803d; text-decoration: none; }
.wizard-link {
  padding: 8px 12px; border-radius: 6px; border: 1px solid #bfdbfe; color: #1d4ed8;
  font-size: 13px; white-space: nowrap; background: #fff;
}
.wizard-link:hover { background: #eff6ff; text-decoration: none; }

.entity-table { width: 100%; border-collapse: collapse; background: white; border: 1px solid #e5e7eb; border-radius: 8px; overflow: hidden; }
.entity-table th, .entity-table td { padding: 10px 14px; text-align: left; }
.entity-table th { background: #f9fafb; border-bottom: 1px solid #e5e7eb; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: .05em; color: #6b7280; }
.entity-table td { border-bottom: 1px solid #f3f4f6; font-size: 13px; }
.entity-table tr:last-child td { border-bottom: 0; }
.entity-table tr:hover td { background: #f9fafb; }
.sort-btn, .sort-sub { padding: 0; border: 0; background: transparent; color: inherit; cursor: pointer; font: inherit; }
.th-conn { min-width: 170px; }
.th-conn-sub { display: block; margin-top: 2px; font-size: 9px; font-weight: 400; letter-spacing: 0; text-transform: none; color: #9ca3af; }
.type-cell { display: inline-flex; align-items: center; gap: 8px; }
.type-glyph { color: #374151; fill: none; flex: 0 0 auto; }
.mono, .conn-counts { font-family: monospace; }
.mono { font-size: 12px; color: #374151; }
.conn-counts { font-size: 12px; white-space: nowrap; }
.state-msg--error { color: #dc2626; }
.global-badge { display: inline-block; background: #fef3c7; color: #92400e; border: 1px solid #fde68a; border-radius: 4px; padding: 1px 7px; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: .05em; margin-right: 8px; vertical-align: middle; }
.global-chip { display: inline-block; margin-left: 8px; background: #fef3c7; color: #92400e; border: 1px solid #fde68a; border-radius: 3px; padding: 0 5px; font-size: 10px; font-weight: 600; vertical-align: middle; }
.group-chip { display: inline-block; margin-left: 6px; background: #e0f2fe; color: #0369a1; border: 1px solid #bae6fd; border-radius: 3px; padding: 0 5px; font-size: 10px; font-weight: 500; vertical-align: middle; cursor: pointer; }
.group-chip:hover { background: #bae6fd; }
.row--global td { background: #fffbeb; }
.row--global:hover td { background: #fef9e7; }

.pagination { display: flex; align-items: center; gap: 12px; padding: 12px 0; justify-content: center; }
.page-btn { padding: 6px 14px; border: 1px solid #d1d5db; border-radius: 6px; background: white; color: #374151; cursor: pointer; font-size: 13px; }
.page-btn:hover:not(:disabled) { background: #f3f4f6; }
.page-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.page-info { font-size: 13px; color: #6b7280; }
</style>
