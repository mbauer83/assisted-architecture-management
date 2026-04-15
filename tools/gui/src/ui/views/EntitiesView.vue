<script setup lang="ts">
import { inject, onMounted, watch, computed } from 'vue'
import { useRoute, useRouter, RouterLink } from 'vue-router'
import { modelServiceKey } from '../keys'
import { useAsync } from '../composables/useAsync'
import type { EntityList } from '../../domain'

const svc = inject(modelServiceKey)!
const route = useRoute()
const router = useRouter()

const { data: entityList, error, loading, run } = useAsync<EntityList>()

const DOMAINS = [
  { key: '', label: 'All' },
  { key: 'motivation', label: 'Motivation' },
  { key: 'strategy', label: 'Strategy' },
  { key: 'common', label: 'Common' },
  { key: 'business', label: 'Business' },
  { key: 'application', label: 'Application' },
  { key: 'technology', label: 'Technology' },
]

const activeDomain = computed(() => (route.query.domain as string | undefined) ?? '')

const setDomain = (domain: string) =>
  domain
    ? router.replace({ path: '/entities', query: { domain } })
    : router.replace({ path: '/entities' })

const load = () =>
  run(svc.listEntities(activeDomain.value ? { domain: activeDomain.value } : {}))

onMounted(load)
watch(activeDomain, load)

const friendlyId = (id: string) => {
  const parts = id.split('.')
  return parts.length > 2 ? parts.slice(2).join('.') : id
}
</script>

<template>
  <div class="layout">
    <aside class="sidebar">
      <h2 class="sidebar-title">Domain</h2>
      <ul class="domain-list">
        <li v-for="d in DOMAINS" :key="d.key">
          <button
            class="domain-btn"
            :class="{ active: activeDomain === d.key, [`domain--${d.key || 'all'}`]: true }"
            @click="setDomain(d.key)"
          >
            {{ d.label }}
          </button>
        </li>
      </ul>
    </aside>

    <section class="content">
      <div class="content-header">
        <h1 class="page-title">
          {{ activeDomain ? activeDomain.charAt(0).toUpperCase() + activeDomain.slice(1) : 'All Entities' }}
          <span v-if="entityList" class="count">({{ entityList.total }})</span>
        </h1>
        <RouterLink to="/entity/create" class="create-btn">+ Create Entity</RouterLink>
      </div>

      <div v-if="loading" class="state-msg">Loading…</div>
      <div v-else-if="error" class="state-msg state-msg--error">{{ error }}</div>

      <table v-else-if="entityList" class="entity-table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Type</th>
            <th v-if="!activeDomain">Domain</th>
            <th class="th-conn">Connections<br><span class="th-conn-sub">(in / symm. / out)</span></th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="e in entityList.items" :key="e.artifact_id">
            <td>
              <RouterLink :to="{ path: '/entity', query: { id: e.artifact_id } }">
                {{ e.name || friendlyId(e.artifact_id) }}
              </RouterLink>
            </td>
            <td class="mono">{{ e.artifact_type }}</td>
            <td v-if="!activeDomain">
              <span class="domain-badge" :class="`domain--${e.domain}`">{{ e.domain }}</span>
            </td>
            <td class="conn-counts">({{ e.conn_in ?? 0 }} / {{ e.conn_sym ?? 0 }} / {{ e.conn_out ?? 0 }})</td>
            <td><span class="status-badge" :class="`status--${e.status}`">{{ e.status }}</span></td>
          </tr>
        </tbody>
      </table>
    </section>
  </div>
</template>

<style scoped>
.layout { display: flex; gap: 24px; }

.sidebar { width: 160px; flex-shrink: 0; }
.sidebar-title { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: .05em; color: #6b7280; margin-bottom: 8px; }
.domain-list { list-style: none; display: flex; flex-direction: column; gap: 2px; }
.domain-btn {
  width: 100%;
  text-align: left;
  padding: 6px 10px;
  border-radius: 6px;
  border: none;
  background: transparent;
  cursor: pointer;
  font-size: 13px;
  color: #374151;
  border-left: 3px solid transparent;
}
.domain-btn:hover { background: #f3f4f6; }
.domain-btn.active { background: #eff6ff; color: #1d4ed8; font-weight: 500; }

.domain--motivation.active { border-left-color: #d8c1e4; }
.domain--strategy.active   { border-left-color: #efbd5d; }
.domain--business.active   { border-left-color: #f4de7f; }
.domain--common.active     { border-left-color: #e8e5d3; }
.domain--application.active{ border-left-color: #b6d7e1; }
.domain--technology.active { border-left-color: #c3e1b4; }

.content { flex: 1; min-width: 0; }

.content-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.page-title { font-size: 20px; font-weight: 600; margin-bottom: 0; }

.create-btn {
  padding: 7px 14px; background: #16a34a; color: white; border-radius: 6px;
  font-size: 13px; font-weight: 500; white-space: nowrap;
}
.create-btn:hover { background: #15803d; text-decoration: none; }
.count { font-size: 14px; font-weight: 400; color: #6b7280; margin-left: 6px; }

.state-msg { color: #6b7280; }
.state-msg--error { color: #dc2626; }

.entity-table { width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; border: 1px solid #e5e7eb; }
.entity-table th { text-align: left; padding: 10px 14px; font-size: 11px; text-transform: uppercase; letter-spacing: .05em; color: #6b7280; background: #f9fafb; border-bottom: 1px solid #e5e7eb; }
.entity-table td { padding: 9px 14px; border-bottom: 1px solid #f3f4f6; font-size: 13px; }
.entity-table tr:last-child td { border-bottom: none; }
.entity-table tr:hover td { background: #f9fafb; }
.mono { font-family: monospace; font-size: 12px; color: #374151; }
.conn-counts { font-family: monospace; font-size: 12px; color: #6b7280; white-space: nowrap; }
.th-conn { line-height: 1.3; }
.th-conn-sub { font-size: 9px; font-weight: 400; letter-spacing: 0; text-transform: none; color: #9ca3af; }

.domain-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
  background: #f3f4f6;
  color: #374151;
}
.domain-badge.domain--motivation { background: #d8c1e4; color: #252327; }
.domain-badge.domain--strategy   { background: #efbd5d; color: #252327; }
.domain-badge.domain--business   { background: #f4de7f; color: #252327; }
.domain-badge.domain--common     { background: #e8e5d3; color: #252327; }
.domain-badge.domain--application{ background: #b6d7e1; color: #252327; }
.domain-badge.domain--technology { background: #c3e1b4; color: #252327; }

.status-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
}
.status--draft      { background: #f3f4f6; color: #6b7280; }
.status--active     { background: #dcfce7; color: #166534; }
.status--deprecated { background: #fee2e2; color: #991b1b; }
</style>
