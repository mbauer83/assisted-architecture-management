<script setup lang="ts">
import { computed, inject, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import type { EntityList } from '../../domain'
import type { RepoScope, RepoError } from '../../ports/ModelRepository'
import { modelServiceKey } from '../keys'
import { useQuery } from '../composables/useQuery'
import EntitiesTreemap from '../components/EntitiesTreemap.vue'
import ArchimateTypeGlyph from '../components/ArchimateTypeGlyph.vue'
import {
  DOMAIN_OPTIONS,
  friendlyEntityId,
  getEntityConnectionTotal,
  getDomainLabel,
} from '../lib/domains'

const props = defineProps<{ scope?: RepoScope }>()

type ViewMode = 'table' | 'treemap'
type SortKey = 'type' | 'in' | 'sym' | 'out' | 'total'

const svc = inject(modelServiceKey)!
const route = useRoute()
const router = useRouter()
const entityListState = useQuery<EntityList, RepoError>()

const isGlobal = computed(() => props.scope === 'global')
const basePath = computed(() => isGlobal.value ? '/global/entities' : '/entities')

const activeDomain = computed(() => (route.query.domain as string | undefined) ?? '')
const viewMode = computed<ViewMode>(() => route.query.view === 'treemap' ? 'treemap' : 'table')
const typeFilter = ref((route.query.type as string | undefined) ?? '')
const sortKey = ref<SortKey | null>(null)
const sortOrder = ref<1 | -1>(1)

const replaceQuery = (patch: Record<string, string | undefined>) =>
  void router.replace({ path: basePath.value, query: { ...route.query, ...patch } })

const setDomain = (domain: string) => replaceQuery({ domain: domain || undefined })
const setViewMode = (view: ViewMode) => replaceQuery({ view: view === 'table' ? undefined : view })
const load = () => entityListState.run(svc.listEntities({
  ...(activeDomain.value ? { domain: activeDomain.value } : {}),
  scope: props.scope,
}))

onMounted(load)
watch([activeDomain, () => props.scope], () => {
  typeFilter.value = ''
  load()
})

const uniqueTypes = computed(() => {
  const types = entityListState.data.value?.items.map(item => item.artifact_type) ?? []
  return [...new Set(types)].sort()
})

const compareValues = (left: number | string, right: number | string) =>
  left < right ? -1 * sortOrder.value : left > right ? 1 * sortOrder.value : 0

const sortBy = (key: SortKey) => {
  if (sortKey.value !== key) {
    sortKey.value = key
    sortOrder.value = 1
    return
  }
  if (sortOrder.value === 1) sortOrder.value = -1
  else {
    sortKey.value = null
    sortOrder.value = 1
  }
}

const sortedEntities = computed(() => {
  const items = entityListState.data.value?.items.filter(item =>
    !typeFilter.value || item.artifact_type === typeFilter.value,
  ) ?? []
  if (!sortKey.value) return items
  return [...items].sort((a, b) => {
    if (sortKey.value === 'type') return compareValues(a.artifact_type, b.artifact_type)
    if (sortKey.value === 'in') return compareValues(a.conn_in ?? 0, b.conn_in ?? 0)
    if (sortKey.value === 'sym') return compareValues(a.conn_sym ?? 0, b.conn_sym ?? 0)
    if (sortKey.value === 'out') return compareValues(a.conn_out ?? 0, b.conn_out ?? 0)
    return compareValues(getEntityConnectionTotal(a), getEntityConnectionTotal(b))
  })
})

const hierarchicalEntities = computed(() => {
  const items = sortedEntities.value
  const byId = new Map(items.map((item) => [item.artifact_id, item]))

  type ChildEntry = { entity: typeof items[number]; relationType: string | undefined }
  const children = new Map<string, ChildEntry[]>()

  for (const item of items) {
    const rawParents = item.all_parents?.length
      ? item.all_parents
      : item.parent_entity_id
        ? [{ parent_id: item.parent_entity_id, relation_type: item.hierarchy_relation_type ?? '' }]
        : []
    for (const p of rawParents.filter((p) => byId.has(p.parent_id))) {
      const bucket = children.get(p.parent_id) ?? []
      bucket.push({ entity: item, relationType: p.relation_type || undefined })
      children.set(p.parent_id, bucket)
    }
  }

  const hasParent = new Set<string>()
  for (const entries of children.values()) for (const { entity } of entries) hasParent.add(entity.artifact_id)
  const roots = items.filter((item) => !hasParent.has(item.artifact_id))

  const ordered: typeof items = []
  const visited = new Set<string>()
  const currentPath = new Set<string>()

  // parentKey is the full ancestry key of the parent node, propagated down so that
  // each (entity, ancestor-path) combination gets a unique visit key.  This lets
  // grandchildren appear once per each copy of their parent, not just once globally.
  const visit = (item: typeof items[number], depth: number, parentId: string | null, relationType: string | null, parentKey: string) => {
    if (currentPath.has(item.artifact_id)) return  // cycle guard
    const key = `${item.artifact_id}::${parentKey}`
    if (visited.has(key)) return
    visited.add(key)
    ordered.push(
      parentId !== null
        ? { ...item, parent_entity_id: parentId, hierarchy_relation_type: relationType ?? undefined, hierarchy_depth: depth, specialization_depth: depth }
        : { ...item, hierarchy_depth: depth, specialization_depth: depth },
    )
    currentPath.add(item.artifact_id)
    for (const { entity: child, relationType: rt } of children.get(item.artifact_id) ?? []) {
      visit(child, depth + 1, item.artifact_id, rt ?? null, key)
    }
    currentPath.delete(item.artifact_id)
  }

  for (const root of roots) visit(root, 0, null, null, '')
  return ordered
})

const hierarchyMarker = (relationType?: string) => {
  if (relationType === 'composition') return '◆'
  if (relationType === 'aggregation') return '◇'
  return '↳'
}

const browseReturnQuery = computed(() => {
  const q: Record<string, string> = {}
  if (activeDomain.value) q.domain = activeDomain.value
  if (viewMode.value !== 'table') q.view = viewMode.value
  if (typeFilter.value) q.type = typeFilter.value
  return q
})

const pageTitle = computed(() => {
  const scope = isGlobal.value ? 'Global ' : ''
  return activeDomain.value ? `${scope}${getDomainLabel(activeDomain.value)} Entities` : `${scope}Entities`
})
const sortArrow = (key: SortKey) => sortKey.value === key ? (sortOrder.value === 1 ? '↑' : '↓') : ''
</script>

<template>
  <div class="layout">
    <aside class="sidebar">
      <h2 class="sidebar-title">
        Domain
      </h2>
      <ul class="domain-list">
        <li
          v-for="domain in DOMAIN_OPTIONS"
          :key="domain.key"
        >
          <button
            class="domain-btn"
            :class="{ active: activeDomain === domain.key, [`domain-border--${domain.key || 'all'}`]: true }"
            @click="setDomain(domain.key)"
          >
            {{ domain.label }}
          </button>
        </li>
      </ul>
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
            >
              ({{ hierarchicalEntities.length }}<template v-if="typeFilter"> / {{ entityListState.data.value.total }}</template>)
            </span>
          </h1>
          <p class="subtitle">
            <template v-if="isGlobal">
              Read-only view of the shared global (enterprise) repository.
            </template>
            <template v-else>
              Filter by domain, then inspect the catalog as a sortable table or a connection-weighted treemap.
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
          v-if="hierarchicalEntities.length === 0"
          class="state-msg"
        >
          No entities found{{ activeDomain ? ` in ${getDomainLabel(activeDomain)}` : '' }}{{ typeFilter ? ` of type "${typeFilter}"` : '' }}.
        </div>

        <EntitiesTreemap
          v-else-if="viewMode === 'treemap'"
          :items="sortedEntities"
          :active-domain="activeDomain"
        />

        <table
          v-else
          class="entity-table"
        >
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
                <span class="th-conn-sub">
                  (<button
                    class="sort-sub"
                    @click="sortBy('in')"
                  >in {{ sortArrow('in') }}</button> /
                  <button
                    class="sort-sub"
                    @click="sortBy('sym')"
                  >sym {{ sortArrow('sym') }}</button> /
                  <button
                    class="sort-sub"
                    @click="sortBy('out')"
                  >out {{ sortArrow('out') }}</button>)
                </span>
              </th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="entity in hierarchicalEntities"
              :key="`${entity.artifact_id}::${entity.parent_entity_id ?? ''}`"
              :class="{ 'row--global': entity.is_global }"
            >
              <td>
                <div
                  class="name-cell"
                  :style="{ paddingLeft: `${(entity.hierarchy_depth ?? entity.specialization_depth ?? 0) * 18}px` }"
                >
                  <span
                    v-if="(entity.hierarchy_depth ?? entity.specialization_depth)"
                    class="spec-marker"
                  >
                    {{ hierarchyMarker(entity.hierarchy_relation_type) }}
                  </span>
                  <RouterLink :to="{ path: '/entity', query: { id: entity.artifact_id, ...browseReturnQuery } }">
                    {{ entity.name || friendlyEntityId(entity.artifact_id) }}
                  </RouterLink>
                </div>
                <span
                  v-if="entity.is_global && !isGlobal"
                  class="global-chip"
                  title="From the global repository"
                >global</span>
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
                {{ getEntityConnectionTotal(entity) }}
                <span class="conn-split">({{ entity.conn_in ?? 0 }} / {{ entity.conn_sym ?? 0 }} / {{ entity.conn_out ?? 0 }})</span>
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
      </template>
    </section>
  </div>
</template>

<style scoped>
.layout { display: flex; gap: 24px; }
.sidebar { width: 160px; flex-shrink: 0; }
.sidebar-title, .toolbar-field span, .entity-table th {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: .05em;
  color: #6b7280;
}

.domain-list { list-style: none; display: flex; flex-direction: column; gap: 2px; }
.domain-btn {
  width: 100%;
  padding: 7px 10px;
  border: 0;
  border-left: 3px solid transparent;
  border-radius: 6px;
  background: transparent;
  color: #374151;
  cursor: pointer;
  font-size: 13px;
  text-align: left;
}
.domain-btn:hover { background: #f3f4f6; }
.domain-btn.active { background: #eff6ff; color: #1d4ed8; font-weight: 500; }
.domain-border--motivation.active { border-left-color: var(--domain-motivation); }
.domain-border--strategy.active { border-left-color: var(--domain-strategy); }
.domain-border--common.active { border-left-color: var(--domain-common); }
.domain-border--business.active { border-left-color: var(--domain-business); }
.domain-border--application.active { border-left-color: var(--domain-application); }
.domain-border--technology.active { border-left-color: var(--domain-technology); }

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

.toolbar-select, .toggle-btn {
  border: 1px solid #d1d5db;
  border-radius: 6px;
  background: white;
  color: #374151;
}
.toolbar-select { min-width: 180px; padding: 7px 10px; }
.toggle-btn { padding: 7px 12px; cursor: pointer; font-size: 13px; }
.toggle-btn--active { background: #2563eb; border-color: #2563eb; color: white; }

.create-btn {
  padding: 8px 14px;
  border-radius: 6px;
  background: #16a34a;
  color: white;
  font-size: 13px;
  font-weight: 500;
  white-space: nowrap;
}
.create-btn:hover { background: #15803d; text-decoration: none; }

.entity-table {
  width: 100%;
  border-collapse: collapse;
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  overflow: hidden;
}
.entity-table th, .entity-table td { padding: 10px 14px; text-align: left; }
.entity-table th { background: #f9fafb; border-bottom: 1px solid #e5e7eb; }
.entity-table td { border-bottom: 1px solid #f3f4f6; font-size: 13px; }
.entity-table tr:last-child td { border-bottom: 0; }
.entity-table tr:hover td { background: #f9fafb; }

.sort-btn, .sort-sub {
  padding: 0;
  border: 0;
  background: transparent;
  color: inherit;
  cursor: pointer;
  font: inherit;
}
.th-conn { min-width: 170px; }
.th-conn-sub { display: block; margin-top: 2px; font-size: 9px; font-weight: 400; letter-spacing: 0; text-transform: none; color: #9ca3af; }
.type-cell { display: inline-flex; align-items: center; gap: 8px; }
.name-cell { display: inline-flex; align-items: center; gap: 6px; }
.spec-marker { color: #9ca3af; font-size: 12px; }
.type-glyph { color: #374151; fill: none; flex: 0 0 auto; }
.mono, .conn-counts { font-family: monospace; }
.mono { font-size: 12px; color: #374151; }
.conn-counts { font-size: 12px; white-space: nowrap; }
.state-msg--error { color: #dc2626; }

.global-badge {
  display: inline-block;
  background: #fef3c7;
  color: #92400e;
  border: 1px solid #fde68a;
  border-radius: 4px;
  padding: 1px 7px;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .05em;
  margin-right: 8px;
  vertical-align: middle;
}

.global-chip {
  display: inline-block;
  margin-left: 8px;
  background: #fef3c7;
  color: #92400e;
  border: 1px solid #fde68a;
  border-radius: 3px;
  padding: 0 5px;
  font-size: 10px;
  font-weight: 600;
  vertical-align: middle;
}

.row--global td { background: #fffbeb; }
.row--global:hover td { background: #fef9e7; }
</style>
