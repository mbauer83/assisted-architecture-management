<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AssuranceNodeDetail from '../components/AssuranceNodeDetail.vue'
import AssuranceNodeForm from './AssuranceNodeForm.vue'
import type { AssuranceNodeFormData } from './AssuranceNodeForm.vue'
import AssuranceEdgePicker from '../components/AssuranceEdgePicker.vue'
import AssuranceAnalysisPicker from '../components/AssuranceAnalysisPicker.vue'
import { nodesUrlForAnalysis } from '../components/AssuranceAnalysisPicker.helpers'

interface AssuranceNode {
  node_id: string
  node_type: string
  name: string
  status?: string
  tlp?: string
  concern_class?: string
  binding_status?: string
}

interface NodesResponse {
  nodes: AssuranceNode[]
  count: number
  visibility_limited?: boolean
}

const route = useRoute()
const router = useRouter()

const nodes = ref<AssuranceNode[]>([])
const loading = ref(false)
const error = ref<string | null>(null)
const visibilityLimited = ref(false)

// Analysis scope: null = all analyses; otherwise restrict the node list.
const analysisId = ref<string | null>(null)

// Filters
const filterType = ref('')
const filterStatus = ref('')
const filterConcern = ref('')
const filterTlp = ref('')
const filterBinding = ref('')

// Selected node for detail / edit panels
const selectedNodeId = ref<string | null>(null)
const selectedNode = computed(() =>
  nodes.value.find(n => n.node_id === selectedNodeId.value) ?? null
)

// Panel mode: 'detail' | 'create' | 'edit' | 'add-edge'
const panelMode = ref<'detail' | 'create' | 'edit' | 'add-edge'>('detail')
const formLoading = ref(false)
const formError = ref<string | null>(null)

// Derived: unique filter options from loaded nodes
const nodeTypes = computed(() => [...new Set(nodes.value.map(n => n.node_type))].sort())
const statuses = computed(() => [...new Set(nodes.value.map(n => n.status ?? '').filter(Boolean))].sort())
const concerns = computed(() => [...new Set(nodes.value.map(n => n.concern_class ?? '').filter(Boolean))].sort())
const tlpValues = computed(() => [...new Set(nodes.value.map(n => n.tlp ?? '').filter(Boolean))].sort())
const bindingValues = computed(() => [...new Set(nodes.value.map(n => n.binding_status ?? '').filter(Boolean))].sort())

const filtered = computed(() => nodes.value.filter(n => {
  if (filterType.value && n.node_type !== filterType.value) return false
  if (filterStatus.value && n.status !== filterStatus.value) return false
  if (filterConcern.value && n.concern_class !== filterConcern.value) return false
  if (filterTlp.value && n.tlp !== filterTlp.value) return false
  if (filterBinding.value && n.binding_status !== filterBinding.value) return false
  return true
}))

async function loadNodes() {
  loading.value = true
  error.value = null
  try {
    const resp = await fetch(nodesUrlForAnalysis(analysisId.value))
    if (resp.status === 423) {
      error.value = 'The assurance store is locked. Run `arch-assurance unlock` and restart the backend.'
      return
    }
    if (!resp.ok) {
      error.value = `Failed to load nodes (HTTP ${resp.status})`
      return
    }
    const body = await resp.json() as NodesResponse
    nodes.value = body.nodes
    visibilityLimited.value = body.visibility_limited ?? false
  } catch (e) {
    error.value = String(e)
  } finally {
    loading.value = false
  }
}

function selectNode(node: AssuranceNode) {
  selectedNodeId.value = node.node_id
  panelMode.value = 'detail'
  void router.replace({ path: '/assurance/browse', query: { node_id: node.node_id } })
}

function closePanel() {
  selectedNodeId.value = null
  panelMode.value = 'detail'
  formError.value = null
  void router.replace({ path: '/assurance/browse' })
}

function openCreate() {
  selectedNodeId.value = null
  panelMode.value = 'create'
  formError.value = null
}

function openEdit() {
  if (!selectedNodeId.value) return
  panelMode.value = 'edit'
  formError.value = null
}

function openAddEdge() {
  if (!selectedNodeId.value) return
  panelMode.value = 'add-edge'
  formError.value = null
}

function backToDetail() {
  panelMode.value = 'detail'
  formError.value = null
}

async function handleCreate(data: AssuranceNodeFormData) {
  formLoading.value = true
  formError.value = null
  try {
    const resp = await fetch('/api/assurance/nodes', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    })
    if (resp.status === 423) { formError.value = 'Store is locked.'; return }
    if (!resp.ok) {
      const body = await resp.json().catch(() => ({})) as Record<string, unknown>
      formError.value = typeof body['error'] === 'string' ? body['error'] : `HTTP ${resp.status}`
      return
    }
    await loadNodes()
    panelMode.value = 'detail'
  } catch (e) {
    formError.value = String(e)
  } finally {
    formLoading.value = false
  }
}

async function handleEdit(data: AssuranceNodeFormData) {
  if (!selectedNodeId.value) return
  formLoading.value = true
  formError.value = null
  try {
    const resp = await fetch(`/api/assurance/nodes/${selectedNodeId.value}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    })
    if (resp.status === 423) { formError.value = 'Store is locked.'; return }
    if (!resp.ok) {
      const body = await resp.json().catch(() => ({})) as Record<string, unknown>
      formError.value = typeof body['error'] === 'string' ? body['error'] : `HTTP ${resp.status}`
      return
    }
    await loadNodes()
    panelMode.value = 'detail'
  } catch (e) {
    formError.value = String(e)
  } finally {
    formLoading.value = false
  }
}

async function handleDelete() {
  if (!selectedNodeId.value) return
  if (!confirm('Delete this node and all its edges? This cannot be undone.')) return
  formLoading.value = true
  formError.value = null
  try {
    const resp = await fetch(`/api/assurance/nodes/${selectedNodeId.value}`, { method: 'DELETE' })
    if (resp.status === 423) { formError.value = 'Store is locked.'; return }
    if (!resp.ok) {
      const body = await resp.json().catch(() => ({})) as Record<string, unknown>
      formError.value = typeof body['error'] === 'string' ? body['error'] : `HTTP ${resp.status}`
      return
    }
    closePanel()
    await loadNodes()
  } catch (e) {
    formError.value = String(e)
  } finally {
    formLoading.value = false
  }
}

async function handleAddEdge(data: { source_id: string; target_id: string; conn_type: string }) {
  formLoading.value = true
  formError.value = null
  try {
    const resp = await fetch('/api/assurance/edges', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    })
    if (resp.status === 423) { formError.value = 'Store is locked.'; return }
    if (!resp.ok) {
      const body = await resp.json().catch(() => ({})) as Record<string, unknown>
      formError.value = typeof body['error'] === 'string' ? body['error'] : `HTTP ${resp.status}`
      return
    }
    panelMode.value = 'detail'
  } catch (e) {
    formError.value = String(e)
  } finally {
    formLoading.value = false
  }
}

// Initial data for the edit form from the selected node
const editInitialData = computed((): Partial<AssuranceNodeFormData> => {
  const n = selectedNode.value
  if (!n) return {}
  return {
    node_type: n.node_type,
    name: n.name,
    status: n.status ?? 'draft',
    tlp: n.tlp ?? 'TLP:WHITE',
    concern_class: n.concern_class ?? '',
    binding_status: n.binding_status ?? '',
  }
})

const showPanel = computed(() =>
  selectedNodeId.value !== null || panelMode.value === 'create'
)

onMounted(() => {
  void loadNodes()
  const qNodeId = route.query['node_id']
  if (typeof qNodeId === 'string' && qNodeId) {
    selectedNodeId.value = qNodeId
  }
})

watch(() => route.query['node_id'], (val) => {
  selectedNodeId.value = typeof val === 'string' && val ? val : null
})

// Reload the node list whenever the analysis scope changes.
watch(analysisId, () => { void loadNodes() })
</script>

<template>
  <div class="browse-page">
    <div class="browse-header">
      <div class="browse-title-row">
        <h1 class="browse-title">
          Assurance nodes
        </h1>
        <div class="browse-header-actions">
          <button
            class="btn-create"
            type="button"
            @click="openCreate"
          >
            + New node
          </button>
          <button
            class="reload-btn"
            type="button"
            :disabled="loading"
            @click="loadNodes"
          >
            {{ loading ? 'Loading…' : '↺ Refresh' }}
          </button>
        </div>
      </div>
      <div class="browse-analysis-row">
        <AssuranceAnalysisPicker v-model="analysisId" />
      </div>
      <p
        v-if="visibilityLimited"
        class="visibility-note"
      >
        Some nodes are withheld by classification policy.
      </p>
    </div>

    <div
      v-if="error"
      class="browse-error"
    >
      {{ error }}
    </div>

    <div
      v-else
      class="browse-body"
      :class="{ 'browse-body--split': showPanel }"
    >
      <!-- Filter + list panel -->
      <div class="browse-list-panel">
        <div class="filter-bar">
          <select
            v-model="filterType"
            class="filter-select"
            aria-label="Filter by type"
          >
            <option value="">
              All types
            </option>
            <option
              v-for="t in nodeTypes"
              :key="t"
              :value="t"
            >
              {{ t }}
            </option>
          </select>
          <select
            v-model="filterStatus"
            class="filter-select"
            aria-label="Filter by status"
          >
            <option value="">
              All statuses
            </option>
            <option
              v-for="s in statuses"
              :key="s"
              :value="s"
            >
              {{ s }}
            </option>
          </select>
          <select
            v-model="filterConcern"
            class="filter-select"
            aria-label="Filter by concern class"
          >
            <option value="">
              All concerns
            </option>
            <option
              v-for="c in concerns"
              :key="c"
              :value="c"
            >
              {{ c }}
            </option>
          </select>
          <select
            v-model="filterTlp"
            class="filter-select"
            aria-label="Filter by TLP"
          >
            <option value="">
              All TLP
            </option>
            <option
              v-for="t in tlpValues"
              :key="t"
              :value="t"
            >
              {{ t }}
            </option>
          </select>
          <select
            v-model="filterBinding"
            class="filter-select"
            aria-label="Filter by binding status"
          >
            <option value="">
              All binding
            </option>
            <option
              v-for="b in bindingValues"
              :key="b"
              :value="b"
            >
              {{ b }}
            </option>
          </select>
        </div>

        <div class="list-count">
          {{ filtered.length }} node{{ filtered.length === 1 ? '' : 's' }}
        </div>

        <div
          v-if="loading"
          class="list-loading"
        >
          Loading nodes…
        </div>
        <ul
          v-else
          class="node-list"
        >
          <li
            v-for="node in filtered"
            :key="node.node_id"
            class="node-item"
            :class="{ 'node-item--selected': node.node_id === selectedNodeId }"
            @click="selectNode(node)"
          >
            <span class="node-type-badge">{{ node.node_type }}</span>
            <span class="node-name">{{ node.name }}</span>
            <span
              v-if="node.tlp && node.tlp !== 'TLP:WHITE'"
              class="node-tlp"
            >{{ node.tlp }}</span>
            <span
              v-if="node.binding_status"
              class="node-binding"
              :class="`node-binding--${node.binding_status}`"
            >{{ node.binding_status }}</span>
          </li>
          <li
            v-if="!loading && filtered.length === 0"
            class="node-empty"
          >
            {{ nodes.length === 0 ? 'No assurance nodes in the store.' : 'No nodes match the current filters.' }}
          </li>
        </ul>
      </div>

      <!-- Right panel: detail / create / edit / add-edge -->
      <div
        v-if="showPanel"
        class="browse-detail-panel"
      >
        <!-- Shared form error banner -->
        <div
          v-if="formError"
          class="panel-error"
        >
          {{ formError }}
        </div>

        <!-- CREATE -->
        <div
          v-if="panelMode === 'create'"
          class="panel-section"
        >
          <div class="panel-header">
            <h2 class="panel-title">
              New assurance node
            </h2>
            <button
              class="panel-close"
              type="button"
              aria-label="Close"
              @click="closePanel"
            >
              ×
            </button>
          </div>
          <div class="panel-body">
            <AssuranceNodeForm
              :loading="formLoading"
              @submit="handleCreate"
              @cancel="closePanel"
            />
          </div>
        </div>

        <!-- EDIT -->
        <div
          v-else-if="panelMode === 'edit' && selectedNode"
          class="panel-section"
        >
          <div class="panel-header">
            <h2 class="panel-title">
              Edit node
            </h2>
            <button
              class="panel-close"
              type="button"
              aria-label="Close"
              @click="backToDetail"
            >
              ×
            </button>
          </div>
          <div class="panel-body">
            <AssuranceNodeForm
              :initial-data="editInitialData"
              :locked-node-type="selectedNode.node_type"
              :loading="formLoading"
              @submit="handleEdit"
              @cancel="backToDetail"
            />
          </div>
        </div>

        <!-- ADD EDGE -->
        <div
          v-else-if="panelMode === 'add-edge' && selectedNodeId"
          class="panel-section"
        >
          <div class="panel-header">
            <h2 class="panel-title">
              Add edge from node
            </h2>
            <button
              class="panel-close"
              type="button"
              aria-label="Close"
              @click="backToDetail"
            >
              ×
            </button>
          </div>
          <div class="panel-body">
            <AssuranceEdgePicker
              :source-id="selectedNodeId"
              :loading="formLoading"
              @submit="handleAddEdge"
              @cancel="backToDetail"
            />
          </div>
        </div>

        <!-- DETAIL -->
        <div
          v-else-if="selectedNodeId"
          class="panel-section"
        >
          <div class="panel-header">
            <div class="panel-detail-actions">
              <button
                class="btn-edit"
                type="button"
                @click="openEdit"
              >
                Edit
              </button>
              <button
                class="btn-add-edge"
                type="button"
                @click="openAddEdge"
              >
                Add edge
              </button>
              <button
                class="btn-delete"
                type="button"
                :disabled="formLoading"
                @click="handleDelete"
              >
                Delete
              </button>
            </div>
            <button
              class="panel-close"
              type="button"
              aria-label="Close"
              @click="closePanel"
            >
              ×
            </button>
          </div>
          <AssuranceNodeDetail
            :node-id="selectedNodeId"
            @close="closePanel"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.browse-page {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}
.browse-header {
  padding: 20px 24px 16px;
  border-bottom: 1px solid #e2e8f0;
  flex-shrink: 0;
}
.browse-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}
.browse-title { font-size: 20px; font-weight: 700; margin: 0; }
.browse-header-actions { display: flex; gap: 8px; }
.btn-create {
  padding: 6px 14px;
  background: #2563eb;
  color: #fff;
  border: none;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}
.btn-create:hover { background: #1d4ed8; }
.reload-btn {
  padding: 5px 12px;
  border-radius: 6px;
  background: #f3f4f6;
  color: #374151;
  border: 1px solid #d1d5db;
  font-size: 13px;
  cursor: pointer;
}
.reload-btn:hover:not(:disabled) { background: #e5e7eb; }
.reload-btn:disabled { opacity: 0.5; cursor: default; }
.browse-analysis-row { margin-top: 10px; }
.visibility-note { font-size: 12px; color: #9ca3af; margin: 6px 0 0; }
.browse-error {
  padding: 24px;
  color: #b91c1c;
  background: #fef2f2;
  border-radius: 8px;
  margin: 16px 24px;
  font-size: 14px;
}
.browse-body { display: flex; flex: 1; overflow: hidden; }
.browse-list-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-right: 1px solid #e2e8f0;
  min-width: 0;
}
.browse-body--split .browse-list-panel { max-width: 400px; }
.browse-detail-panel { flex: 1; overflow: hidden; min-width: 0; display: flex; flex-direction: column; }
.panel-error {
  padding: 8px 16px;
  background: #fef2f2;
  color: #b91c1c;
  font-size: 13px;
  border-bottom: 1px solid #fca5a5;
  flex-shrink: 0;
}
.panel-section { display: flex; flex-direction: column; height: 100%; overflow: hidden; }
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid #e2e8f0;
  flex-shrink: 0;
}
.panel-title { font-size: 15px; font-weight: 600; margin: 0; }
.panel-body { flex: 1; overflow-y: auto; padding: 16px; }
.panel-close {
  background: none;
  border: none;
  font-size: 18px;
  color: #9ca3af;
  cursor: pointer;
  padding: 2px 6px;
  line-height: 1;
}
.panel-close:hover { color: #374151; }
.panel-detail-actions { display: flex; gap: 8px; }
.btn-edit, .btn-add-edge, .btn-delete {
  padding: 5px 12px;
  border-radius: 5px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  border: 1px solid;
}
.btn-edit { background: #f0f9ff; color: #0369a1; border-color: #bae6fd; }
.btn-edit:hover { background: #e0f2fe; }
.btn-add-edge { background: #f0fdf4; color: #15803d; border-color: #bbf7d0; }
.btn-add-edge:hover { background: #dcfce7; }
.btn-delete { background: #fef2f2; color: #b91c1c; border-color: #fca5a5; }
.btn-delete:hover:not(:disabled) { background: #fee2e2; }
.btn-delete:disabled { opacity: 0.5; cursor: default; }
.filter-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 12px 16px;
  border-bottom: 1px solid #e2e8f0;
  background: #f8fafc;
  flex-shrink: 0;
}
.filter-select {
  font-size: 12px;
  padding: 4px 8px;
  border: 1px solid #d1d5db;
  border-radius: 4px;
  background: #fff;
  color: #374151;
  flex: 1;
  min-width: 100px;
  max-width: 150px;
}
.list-count { padding: 6px 16px; font-size: 12px; color: #6b7280; border-bottom: 1px solid #f1f5f9; flex-shrink: 0; }
.list-loading { padding: 24px 16px; color: #6b7280; font-size: 14px; }
.node-list { list-style: none; margin: 0; padding: 0; overflow-y: auto; flex: 1; }
.node-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  cursor: pointer;
  border-bottom: 1px solid #f1f5f9;
  font-size: 13px;
}
.node-item:hover { background: #f0f9ff; }
.node-item--selected { background: #eff6ff; border-left: 3px solid #2563eb; }
.node-type-badge {
  font-size: 11px;
  font-weight: 500;
  background: #dbeafe;
  color: #1d4ed8;
  padding: 2px 7px;
  border-radius: 4px;
  white-space: nowrap;
  flex-shrink: 0;
}
.node-name { flex: 1; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.node-tlp { font-size: 11px; color: #dc2626; font-weight: 600; flex-shrink: 0; }
.node-binding { font-size: 11px; padding: 1px 6px; border-radius: 3px; flex-shrink: 0; }
.node-binding--bound { background: #dcfce7; color: #15803d; }
.node-binding--unbound { background: #fee2e2; color: #b91c1c; }
.node-empty { padding: 24px 16px; color: #9ca3af; font-size: 13px; }
</style>
