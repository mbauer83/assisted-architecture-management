<script setup lang="ts">
import { inject, onMounted, watch, computed } from 'vue'
import { useRoute, RouterLink } from 'vue-router'
import { modelServiceKey } from '../keys'
import { useAsync } from '../composables/useAsync'
import ConnectionsPanel from '../components/ConnectionsPanel.vue'
import type { EntityDetail, ConnectionList } from '../../domain'

const svc = inject(modelServiceKey)!
const route = useRoute()

const entityId = computed(() => (route.query.id as string | undefined) ?? '')

const detail = useAsync<EntityDetail>()
const outbound = useAsync<ConnectionList>()
const inbound = useAsync<ConnectionList>()

const load = () => {
  if (!entityId.value) return
  detail.run(svc.getEntity(entityId.value))
  loadConnections()
}

const loadConnections = () => {
  if (!entityId.value) return
  outbound.run(svc.getConnections(entityId.value, 'outbound'))
  inbound.run(svc.getConnections(entityId.value, 'inbound'))
}

onMounted(load)
watch(entityId, load)
</script>

<template>
  <div>
    <div class="top-bar">
      <RouterLink to="/entities" class="back-link">← Browse entities</RouterLink>
      <RouterLink
        v-if="entityId"
        :to="{ path: '/graph', query: { id: entityId } }"
        class="graph-btn"
      >Explore graph</RouterLink>
    </div>

    <div v-if="detail.loading.value" class="state-msg">Loading...</div>
    <div v-else-if="detail.error.value" class="state-msg state-msg--error">{{ detail.error.value }}</div>

    <template v-else-if="detail.data.value">
      <div class="entity-header">
        <div class="entity-title-row">
          <h1 class="entity-name">{{ detail.data.value.name }}</h1>
          <span class="status-badge" :class="`status--${detail.data.value.status}`">{{ detail.data.value.status }}</span>
        </div>
        <div class="meta-row">
          <span class="meta-item mono">{{ detail.data.value.artifact_type }}</span>
          <span class="sep">·</span>
          <span class="domain-badge" :class="`domain--${detail.data.value.domain}`">{{ detail.data.value.domain }}</span>
          <span v-if="detail.data.value.subdomain" class="sep">/ {{ detail.data.value.subdomain }}</span>
          <span class="sep">·</span>
          <span class="meta-item">v{{ detail.data.value.version }}</span>
        </div>
        <div class="artifact-id mono">{{ detail.data.value.artifact_id }}</div>
      </div>

      <div v-if="detail.data.value?.content_html" class="card content-card">
        <div class="markdown-body" v-html="detail.data.value.content_html"></div>
      </div>

      <div class="connections-section">
        <ConnectionsPanel
          :entity-id="entityId"
          :connections="outbound.data.value ?? []"
          direction="outbound"
          :loading="outbound.loading.value"
          :error="outbound.error.value"
          @refresh="loadConnections"
        />
        <ConnectionsPanel
          :entity-id="entityId"
          :connections="inbound.data.value ?? []"
          direction="inbound"
          :loading="inbound.loading.value"
          :error="inbound.error.value"
          @refresh="loadConnections"
        />
      </div>
    </template>
  </div>
</template>

<style scoped>
.top-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.back-link { font-size: 13px; color: #6b7280; }
.back-link:hover { color: #374151; }

.graph-btn {
  padding: 6px 14px; border-radius: 6px; background: #1e293b; color: #f8fafc;
  font-size: 13px; font-weight: 500;
}
.graph-btn:hover { background: #334155; text-decoration: none; }

.state-msg { color: #6b7280; padding: 4px 0; }
.state-msg--error { color: #dc2626; }

.entity-header { margin-bottom: 20px; }
.entity-title-row { display: flex; align-items: center; gap: 12px; margin-bottom: 8px; }
.entity-name { font-size: 22px; font-weight: 700; }

.meta-row { display: flex; align-items: center; gap: 8px; font-size: 13px; color: #374151; margin-bottom: 6px; }
.sep { color: #9ca3af; }
.artifact-id { font-size: 11px; color: #9ca3af; }
.mono { font-family: monospace; }

.card { background: white; border-radius: 8px; border: 1px solid #e5e7eb; }
.content-card { padding: 16px 20px; margin-bottom: 24px; overflow-x: auto; }

.markdown-body :deep(p) { margin: 1rem 0 1.7rem 0; }
.markdown-body :deep(ul) { padding-left: 1.5rem; }
.markdown-body :deep(table) { inline-size: 100%; border-collapse: collapse; margin-block: 2rem; min-inline-size: max-content; }
.markdown-body :deep(th), .markdown-body :deep(td) { padding-inline: 1.25rem; padding-block: 0.75rem; text-align: start; border-bottom: 1px solid var(--border-color, #eee); }

.connections-section { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
@media (max-width: 700px) { .connections-section { grid-template-columns: 1fr; } }

.domain-badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 500; }
.domain--motivation { background: #fef3c7; color: #92400e; }
.domain--strategy   { background: #d1fae5; color: #065f46; }
.domain--business   { background: #fef9c3; color: #713f12; }
.domain--common     { background: #f5f0eb; color: #57534e; }
.domain--application{ background: #dbeafe; color: #1e40af; }
.domain--technology { background: #dcfce7; color: #14532d; }

.status-badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 500; }
.status--draft      { background: #f3f4f6; color: #6b7280; }
.status--active     { background: #dcfce7; color: #166534; }
.status--deprecated { background: #fee2e2; color: #991b1b; }
</style>
