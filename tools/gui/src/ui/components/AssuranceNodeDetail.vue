<script setup lang="ts">
import { ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import ModelThisPanel from './ModelThisPanel.vue'
import { isUnboundControlNode } from './ModelThisPanel.helpers'
import { tlpColor } from './tlp'

const props = defineProps<{ nodeId: string | null }>()
const emit = defineEmits<{ close: [] }>()

interface ArchRef {
  arch_artifact_id: string
  relationship_type?: string
  notes?: string
}

interface Edge {
  edge_id?: string
  source_id: string
  target_id: string
  conn_type: string
  label?: string
}

interface NodeDetail {
  node_id: string
  node_type: string
  name: string
  status?: string
  tlp?: string
  concern_class?: string
  disposition?: string
  uca_type?: string
  binding_status?: string
  node_role?: string
  content_text?: string
  attributes?: Record<string, unknown>
}

interface NodeResponse {
  node: NodeDetail
  outgoing_edges: Edge[]
  incoming_edges: Edge[]
  arch_refs: ArchRef[]
}

const data = ref<NodeResponse | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)

async function load(nodeId: string | null) {
  if (!nodeId) { data.value = null; return }
  loading.value = true
  error.value = null
  try {
    const resp = await fetch(`/api/assurance/nodes/${encodeURIComponent(nodeId)}`)
    if (resp.status === 423) { error.value = 'Store locked'; return }
    if (resp.status === 404) { error.value = 'Node not found'; return }
    if (!resp.ok) { error.value = `HTTP ${resp.status}`; return }
    data.value = await resp.json() as NodeResponse
  } catch (e) {
    error.value = String(e)
  } finally {
    loading.value = false
  }
}

watch(() => props.nodeId, load, { immediate: true })

function archEntityPath(ref: ArchRef): string {
  return `/entity?id=${encodeURIComponent(ref.arch_artifact_id)}`
}
</script>

<template>
  <div class="node-detail">
    <div class="detail-hdr">
      <span class="detail-title">Node detail</span>
      <button
        class="close-btn"
        type="button"
        aria-label="Close"
        @click="emit('close')"
      >
        ×
      </button>
    </div>

    <div
      v-if="loading"
      class="detail-loading"
    >
      Loading…
    </div>
    <div
      v-else-if="error"
      class="detail-error"
    >
      {{ error }}
    </div>
    <template v-else-if="data">
      <!-- Identity -->
      <div class="detail-section">
        <div class="detail-row">
          <span class="detail-label">Name</span>
          <span class="detail-value">{{ data.node.name }}</span>
        </div>
        <div class="detail-row">
          <span class="detail-label">Type</span>
          <span class="detail-badge">{{ data.node.node_type }}</span>
        </div>
        <div
          v-if="data.node.status"
          class="detail-row"
        >
          <span class="detail-label">Status</span>
          <span class="detail-value">{{ data.node.status }}</span>
        </div>
        <div
          v-if="data.node.tlp"
          class="detail-row"
        >
          <span class="detail-label">TLP</span>
          <span
            class="detail-value tlp-value"
            :style="{ color: tlpColor(data.node.tlp) }"
          >{{ data.node.tlp }}</span>
        </div>
        <div
          v-if="data.node.concern_class"
          class="detail-row"
        >
          <span class="detail-label">Concern</span>
          <span class="detail-value">{{ data.node.concern_class }}</span>
        </div>
        <div
          v-if="data.node.disposition"
          class="detail-row"
        >
          <span class="detail-label">Disposition</span>
          <span class="detail-value">{{ data.node.disposition }}</span>
        </div>
        <div
          v-if="data.node.binding_status"
          class="detail-row"
        >
          <span class="detail-label">Binding</span>
          <span class="detail-value">{{ data.node.binding_status }}</span>
        </div>
        <div
          v-if="data.node.uca_type"
          class="detail-row"
        >
          <span class="detail-label">UCA type</span>
          <span class="detail-value">{{ data.node.uca_type }}</span>
        </div>
      </div>

      <!-- Modelling gap: model-this affordance for unbound control-structure nodes -->
      <div
        v-if="isUnboundControlNode(data.node.node_type, data.node.binding_status)"
        class="detail-section"
      >
        <ModelThisPanel
          :node-id="data.node.node_id"
          :node-name="data.node.name"
          @bound="load(props.nodeId)"
        />
      </div>

      <!-- Content -->
      <div
        v-if="data.node.content_text"
        class="detail-section"
      >
        <p class="detail-content">
          {{ data.node.content_text }}
        </p>
      </div>

      <!-- Architecture references -->
      <div
        v-if="data.arch_refs.length > 0"
        class="detail-section"
      >
        <div class="section-label">
          Architecture references
        </div>
        <ul class="ref-list">
          <li
            v-for="archRef in data.arch_refs"
            :key="archRef.arch_artifact_id"
            class="ref-item"
          >
            <RouterLink
              :to="archEntityPath(archRef)"
              class="ref-link"
            >
              <span class="ref-icon">↗</span>
              <span class="ref-id">{{ archRef.arch_artifact_id }}</span>
            </RouterLink>
            <span
              v-if="archRef.relationship_type"
              class="ref-rel"
            >{{ archRef.relationship_type }}</span>
          </li>
        </ul>
      </div>

      <!-- Edges -->
      <div
        v-if="data.outgoing_edges.length > 0"
        class="detail-section"
      >
        <div class="section-label">
          Outgoing ({{ data.outgoing_edges.length }})
        </div>
        <ul class="edge-list">
          <li
            v-for="edge in data.outgoing_edges"
            :key="edge.edge_id ?? edge.target_id"
            class="edge-item"
          >
            <span class="edge-type">{{ edge.conn_type }}</span>
            <span class="edge-arrow">→</span>
            <span class="edge-target">{{ edge.target_id }}</span>
          </li>
        </ul>
      </div>

      <div
        v-if="data.incoming_edges.length > 0"
        class="detail-section"
      >
        <div class="section-label">
          Incoming ({{ data.incoming_edges.length }})
        </div>
        <ul class="edge-list">
          <li
            v-for="edge in data.incoming_edges"
            :key="edge.edge_id ?? edge.source_id"
            class="edge-item"
          >
            <span class="edge-source">{{ edge.source_id }}</span>
            <span class="edge-arrow">→</span>
            <span class="edge-type">{{ edge.conn_type }}</span>
          </li>
        </ul>
      </div>
    </template>
  </div>
</template>

<style scoped>
.node-detail {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow-y: auto;
}
.detail-hdr {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid #e2e8f0;
  background: #f8fafc;
  position: sticky;
  top: 0;
  z-index: 1;
}
.detail-title { font-weight: 600; font-size: 14px; }
.close-btn {
  background: none;
  border: none;
  font-size: 18px;
  cursor: pointer;
  color: #6b7280;
  line-height: 1;
  padding: 2px 4px;
}
.close-btn:hover { color: #111827; }
.detail-loading, .detail-error {
  padding: 16px;
  color: #6b7280;
  font-size: 14px;
}
.detail-section {
  padding: 12px 16px;
  border-bottom: 1px solid #f1f5f9;
}
.detail-row {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 6px;
  font-size: 13px;
}
.detail-label {
  font-size: 11px;
  color: #9ca3af;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  width: 70px;
  flex-shrink: 0;
}
.detail-value { color: #111827; }
.detail-badge {
  font-size: 11px;
  font-weight: 500;
  background: #dbeafe;
  color: #1d4ed8;
  padding: 2px 7px;
  border-radius: 4px;
}
.tlp-value { font-weight: 600; }
.detail-content {
  font-size: 13px;
  color: #374151;
  line-height: 1.6;
  margin: 0;
}
.section-label {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: #6b7280;
  margin-bottom: 8px;
}
.ref-list, .edge-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.ref-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}
.ref-link {
  display: flex;
  align-items: center;
  gap: 4px;
  color: #2563eb;
  text-decoration: none;
  font-family: monospace;
  font-size: 12px;
}
.ref-link:hover { text-decoration: underline; }
.ref-icon { font-size: 10px; }
.ref-id { max-width: 200px; overflow: hidden; text-overflow: ellipsis; }
.ref-rel { font-size: 11px; color: #9ca3af; }
.edge-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-family: monospace;
  color: #374151;
}
.edge-type {
  font-size: 11px;
  font-weight: 500;
  background: #f1f5f9;
  padding: 1px 5px;
  border-radius: 3px;
  color: #475569;
}
.edge-arrow { color: #9ca3af; }
.edge-target, .edge-source {
  max-width: 130px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
