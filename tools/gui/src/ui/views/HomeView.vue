<script setup lang="ts">
import { inject, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { modelServiceKey } from '../keys'
import { useAsync } from '../composables/useAsync'
import type { Stats } from '../../domain'
import { DOMAIN_OPTIONS } from '../lib/domains'

const svc = inject(modelServiceKey)!
const { data: stats, error, loading, run } = useAsync<Stats>()

onMounted(() => run(svc.getStats()))
</script>

<template>
  <div>
    <h1 class="page-title">Model Overview</h1>

    <div v-if="loading" class="state-msg">Loading…</div>
    <div v-else-if="error" class="state-msg state-msg--error">{{ error }}</div>

    <template v-else-if="stats">
      <div class="summary-cards">
        <div class="card card--stat">
          <span class="stat-num">{{ stats.entities }}</span>
          <span class="stat-label">Entities</span>
        </div>
        <div class="card card--stat">
          <span class="stat-num">{{ stats.connections }}</span>
          <span class="stat-label">Connections</span>
        </div>
        <div class="card card--stat">
          <span class="stat-num">{{ stats.diagrams }}</span>
          <span class="stat-label">Diagrams</span>
        </div>
      </div>

      <h2 class="section-title">Entities by Domain</h2>
      <div class="domain-grid">
        <RouterLink
          v-for="d in DOMAIN_OPTIONS.filter(option => option.key)"
          :key="d.key"
          :to="{ path: '/entities', query: { domain: d.key } }"
          class="card card--domain"
          :class="`domain--${d.key}`"
        >
          <span class="domain-name">{{ d.label }}</span>
          <span class="domain-count">{{ stats.entities_by_domain[d.key] ?? 0 }}</span>
        </RouterLink>
      </div>

      <h2 class="section-title">Connections by Type</h2>
      <table class="conn-table">
        <tbody>
          <tr v-for="(count, type) in stats.connections_by_type" :key="type">
            <td class="conn-type">{{ type }}</td>
            <td class="conn-count">{{ count }}</td>
          </tr>
        </tbody>
      </table>
    </template>
  </div>
</template>

<style scoped>
.page-title { font-size: 22px; font-weight: 600; margin-bottom: 20px; }
.section-title { font-size: 16px; font-weight: 600; margin: 28px 0 12px; color: #374151; }

.state-msg { color: #6b7280; padding: 12px 0; }
.state-msg--error { color: #dc2626; }

.summary-cards {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}

.card {
  background: white;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
  padding: 16px 20px;
}

.card--stat {
  display: flex;
  flex-direction: column;
  min-width: 110px;
}
.stat-num { font-size: 28px; font-weight: 700; color: #1e293b; }
.stat-label { font-size: 12px; color: #6b7280; text-transform: uppercase; letter-spacing: 0.05em; }

.domain-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 12px;
}

.card--domain {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-left: 4px solid;
  padding: 12px 16px;
  color: inherit;
}
.card--domain:hover { text-decoration: none; box-shadow: 0 2px 8px rgba(0,0,0,.08); }
.domain-name { font-weight: 500; font-size: 13px; }
.domain-count { font-size: 20px; font-weight: 700; }

.domain--motivation  { border-left-color: #d8c1e4; }
.domain--strategy    { border-left-color: #efbd5d; }
.domain--business    { border-left-color: #f4de7f; }
.domain--common      { border-left-color: #e8e5d3; }
.domain--application { border-left-color: #b6d7e1; }
.domain--technology  { border-left-color: #c3e1b4; }

.conn-table { border-collapse: collapse; }
.conn-type { padding: 4px 16px 4px 0; font-family: monospace; font-size: 12px; color: #374151; }
.conn-count { padding: 4px 8px; font-weight: 600; color: #1e293b; }
</style>
