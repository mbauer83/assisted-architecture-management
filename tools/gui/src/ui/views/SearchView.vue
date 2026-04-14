<script setup lang="ts">
import { inject, ref, watch } from 'vue'
import { useRoute, useRouter, RouterLink } from 'vue-router'
import { modelServiceKey } from '../keys'
import { useAsync } from '../composables/useAsync'
import type { SearchResult } from '../../domain'

const svc = inject(modelServiceKey)!
const route = useRoute()
const router = useRouter()

const { data: result, error, loading, run } = useAsync<SearchResult>()

const query = ref((route.query.q as string | undefined) ?? '')

const submit = () => {
  if (!query.value.trim()) return
  router.replace({ path: '/search', query: { q: query.value } })
  run(svc.search(query.value.trim()))
}

// Run search if navigated to with ?q=
if (query.value) run(svc.search(query.value.trim()))

watch(() => route.query.q, (q) => {
  query.value = (q as string | undefined) ?? ''
  if (query.value) run(svc.search(query.value.trim()))
})

const friendlyName = (id: string) => {
  const parts = id.split('.')
  return parts.length > 2 ? parts.slice(2).join(' ').replace(/-/g, ' ') : id
}
</script>

<template>
  <div>
    <h1 class="page-title">Search</h1>

    <form class="search-form" @submit.prevent="submit">
      <input
        v-model="query"
        class="search-input"
        type="text"
        placeholder="Search entities, connections, diagrams…"
        autofocus
      />
      <button type="submit" class="search-btn">Search</button>
    </form>

    <div v-if="loading" class="state-msg">Searching…</div>
    <div v-else-if="error" class="state-msg state-msg--error">{{ error }}</div>

    <template v-else-if="result">
      <p class="result-count">{{ result.hits.length }} result{{ result.hits.length !== 1 ? 's' : '' }} for "{{ result.query }}"</p>

      <div v-if="!result.hits.length" class="state-msg">No results found.</div>

      <ul class="result-list">
        <li v-for="h in result.hits" :key="h.artifact_id" class="result-item card">
          <div class="result-top">
            <RouterLink
              v-if="h.record_type === 'entity'"
              :to="{ path: '/entity', query: { id: h.artifact_id } }"
              class="result-name"
            >
              {{ h.name || friendlyName(h.artifact_id) }}
            </RouterLink>
            <span v-else class="result-name">{{ h.name || friendlyName(h.artifact_id) }}</span>
            <span class="score">{{ h.score.toFixed(1) }}</span>
          </div>
          <div class="result-meta">
            <span class="mono result-type">{{ h.artifact_type }}</span>
            <span v-if="h.domain" class="domain-badge" :class="`domain--${h.domain}`">{{ h.domain }}</span>
            <span class="status-badge" :class="`status--${h.status}`">{{ h.status }}</span>
          </div>
          <div class="result-id mono">{{ h.artifact_id }}</div>
        </li>
      </ul>
    </template>
  </div>
</template>

<style scoped>
.page-title { font-size: 22px; font-weight: 600; margin-bottom: 20px; }

.search-form { display: flex; gap: 8px; margin-bottom: 20px; }
.search-input {
  flex: 1;
  padding: 9px 14px;
  border-radius: 6px;
  border: 1px solid #d1d5db;
  font-size: 14px;
  outline: none;
}
.search-input:focus { border-color: #2563eb; box-shadow: 0 0 0 3px rgba(37,99,235,.15); }
.search-btn {
  padding: 9px 20px;
  background: #2563eb;
  color: white;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
}
.search-btn:hover { background: #1d4ed8; }

.state-msg { color: #6b7280; }
.state-msg--error { color: #dc2626; }

.result-count { font-size: 13px; color: #6b7280; margin-bottom: 12px; }

.result-list { list-style: none; display: flex; flex-direction: column; gap: 8px; }

.card { background: white; border-radius: 8px; border: 1px solid #e5e7eb; padding: 14px 16px; }

.result-top { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 6px; }
.result-name { font-weight: 600; font-size: 14px; }
.score { font-size: 11px; color: #9ca3af; font-family: monospace; }

.result-meta { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; flex-wrap: wrap; }
.result-type { font-size: 12px; color: #374151; }
.result-id { font-size: 11px; color: #9ca3af; }
.mono { font-family: monospace; }

.domain-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
}
.domain--motivation { background: #fef3c7; color: #92400e; }
.domain--strategy   { background: #d1fae5; color: #065f46; }
.domain--business   { background: #fef9c3; color: #713f12; }
.domain--common     { background: #f5f0eb; color: #57534e; }
.domain--application{ background: #dbeafe; color: #1e40af; }
.domain--technology { background: #dcfce7; color: #14532d; }

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
