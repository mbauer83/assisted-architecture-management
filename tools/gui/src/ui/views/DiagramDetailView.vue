<script setup lang="ts">
import { inject, onMounted, watch, computed, ref } from 'vue'
import { useRoute, RouterLink } from 'vue-router'
import { Effect } from 'effect'
import { modelServiceKey } from '../keys'
import { useAsync } from '../composables/useAsync'
import type { DiagramDetail, EntitySummary, EntityDetail } from '../../domain'

const svc = inject(modelServiceKey)!
const route = useRoute()

const diagramId = computed(() => (route.query.id as string | undefined) ?? '')
const detail = useAsync<DiagramDetail>()
const showSource = ref(false)

// Entity list for this diagram
const diagramEntities = ref<EntitySummary[]>([])
const selectedEntity = ref<EntityDetail | null>(null)
const selectedEntityId = ref<string | null>(null)
const selectedEntityHtml = ref<string | null>(null)

const DOMAIN_COLORS: Record<string, string> = {
  motivation: '#d8c1e4', strategy: '#efbd5d', business: '#f4de7f',
  common: '#e8e5d3', application: '#b6d7e1', technology: '#c3e1b4',
}

const load = () => {
  if (!diagramId.value) return
  detail.run(svc.getDiagram(diagramId.value))
  Effect.runPromise(svc.getDiagramEntities(diagramId.value))
    .then((ents) => { diagramEntities.value = ents })
    .catch(() => { diagramEntities.value = [] })
}

onMounted(load)
watch(diagramId, load)

const imageUrl = computed(() => {
  const d = detail.data.value
  if (!d?.rendered_filename) return null
  return svc.diagramImageUrl(d.rendered_filename)
})

const selectDiagramEntity = (id: string) => {
  if (selectedEntityId.value === id) { selectedEntityId.value = null; selectedEntity.value = null; selectedEntityHtml.value = null; return }
  selectedEntityId.value = id
  selectedEntity.value = null
  selectedEntityHtml.value = null
  Effect.runPromise(svc.getEntity(id)).then((d) => {
    selectedEntity.value = d
    selectedEntityHtml.value = d.content_html ?? null
  }).catch(() => {})
}
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

      <!-- Diagram image + entity list side by side -->
      <div class="diagram-main">
        <div class="diagram-image-col">
          <div v-if="imageUrl" class="rendered-card card">
            <img :src="imageUrl" :alt="detail.data.value.name" class="rendered-img" />
          </div>
          <div v-else class="card no-render"><p>No rendered image available.</p></div>
        </div>

        <aside v-if="diagramEntities.length" class="entity-list card">
          <h2 class="entity-list-title">Entities</h2>
          <ul class="entity-list-items">
            <li
              v-for="e in diagramEntities" :key="e.artifact_id"
              class="entity-list-item"
              :class="{ 'entity-list-item--active': selectedEntityId === e.artifact_id }"
              @click="selectDiagramEntity(e.artifact_id)"
            >
              <span class="entity-domain-dot" :style="{ background: DOMAIN_COLORS[e.domain] ?? '#9ca3af' }" />
              <span class="entity-list-name">{{ e.name }}</span>
              <span class="entity-list-type">{{ e.artifact_type }}</span>
            </li>
          </ul>
        </aside>
      </div>

      <!-- Selected entity detail (same fields/order as graph sidebar) -->
      <div v-if="selectedEntity" class="selected-entity card">
        <div class="se-field">
          <label>Name</label>
          <RouterLink :to="{ path: '/entity', query: { id: selectedEntity.artifact_id } }" class="se-link">{{ selectedEntity.name }}</RouterLink>
        </div>
        <div class="se-field"><label>Type</label><span class="se-value mono">{{ selectedEntity.artifact_type }}</span></div>
        <div class="se-field"><label>Domain</label><span class="se-value domain-badge" :class="`domain--${selectedEntity.domain}`">{{ selectedEntity.domain }}</span></div>
        <div class="se-field"><label>Status</label><span class="se-value status-badge" :class="`status--${selectedEntity.status}`">{{ selectedEntity.status }}</span></div>
        <div class="se-field"><label>Version</label><span class="se-value">{{ selectedEntity.version }}</span></div>
        <div class="se-field"><label>Artifact ID</label><span class="se-value mono id-value">{{ selectedEntity.artifact_id }}</span></div>
        <div v-if="selectedEntityHtml" class="se-content markdown-body" v-html="selectedEntityHtml" />
        <div class="se-field se-explore">
          <RouterLink :to="{ path: '/graph', query: { id: selectedEntity.artifact_id } }" class="se-link">Explore graph →</RouterLink>
        </div>
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

.diagram-main { display: flex; gap: 16px; align-items: flex-start; margin-bottom: 16px; }
.diagram-image-col { flex: 1; min-width: 0; }
.entity-list { width: 240px; flex-shrink: 0; padding: 12px; }
.entity-list-title { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: .05em; color: #6b7280; margin-bottom: 8px; }
.entity-list-items { list-style: none; }
.entity-list-item {
  display: flex; align-items: center; gap: 6px; padding: 5px 6px;
  border-radius: 4px; cursor: pointer; font-size: 12px; color: #374151;
}
.entity-list-item:hover { background: #f3f4f6; }
.entity-list-item--active { background: #eff6ff; color: #1d4ed8; }
.entity-domain-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.entity-list-name { flex: 1; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.entity-list-type { font-size: 10px; color: #9ca3af; white-space: nowrap; }

.selected-entity { padding: 16px; margin-bottom: 16px; }
.se-field { margin-bottom: 10px; }
.se-field label { display: block; font-size: 11px; color: #6b7280; text-transform: uppercase; letter-spacing: .05em; margin-bottom: 2px; }
.se-value { font-size: 13px; color: #1e293b; }
.se-link { font-size: 13px; font-weight: 600; color: #1e293b; }
.se-explore { margin-top: 8px; }
.se-explore .se-link { color: #2563eb; font-size: 12px; }
.id-value { font-size: 11px; color: #9ca3af; font-family: monospace; word-break: break-all; }
.mono { font-family: monospace; }
.se-content { font-size: 13px; line-height: 1.5; color: #374151; margin-top: 8px; }
.se-content :deep(p) { margin: 0.5rem 0; }
.domain-badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 500; }
.domain--motivation { background: #d8c1e4; color: #252327; }
.domain--strategy   { background: #efbd5d; color: #252327; }
.domain--business   { background: #f4de7f; color: #252327; }
.domain--common     { background: #e8e5d3; color: #252327; }
.domain--application{ background: #b6d7e1; color: #252327; }
.domain--technology { background: #c3e1b4; color: #252327; }

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
