<script setup lang="ts">
import { ref, computed } from 'vue'

interface NodeSummary {
  node_id: string
  node_type: string
  name: string
}

const props = defineProps<{
  sourceId: string
  loading?: boolean
}>()

const emit = defineEmits<{
  submit: [data: { source_id: string; target_id: string; conn_type: string }]
  cancel: []
}>()

const CONN_TYPES = [
  'issues', 'acts-on', 'feedback', 'concerns', 'by-controller', 'violates',
  'leads-to', 'explains', 'derives', 'refines', 'satisfied-by', 'accountable-to',
  'responsible-of', 'evidenced-by', 'assesses', 'treated-by', 'complies-with',
  'cites', 'binds-to', 'investigates',
]

const connType = ref('')
const targetQuery = ref('')
const targetId = ref('')
const searchResults = ref<NodeSummary[]>([])
const searching = ref(false)
const searchError = ref<string | null>(null)

const canSubmit = computed(() =>
  connType.value !== ''
  && targetId.value !== ''
  && !props.loading
)

async function searchNodes() {
  const q = targetQuery.value.trim()
  if (!q) {
    searchResults.value = []
    return
  }
  searching.value = true
  searchError.value = null
  try {
    const resp = await fetch(`/api/assurance/nodes?status=`)
    if (!resp.ok) {
      searchError.value = `Search failed (HTTP ${resp.status})`
      return
    }
    const body = await resp.json() as { nodes: NodeSummary[] }
    const lq = q.toLowerCase()
    searchResults.value = (body.nodes ?? [])
      .filter(n =>
        n.name.toLowerCase().includes(lq)
        || n.node_type.toLowerCase().includes(lq)
        || n.node_id.toLowerCase().includes(lq)
      )
      .slice(0, 15)
  } catch (e) {
    searchError.value = String(e)
  } finally {
    searching.value = false
  }
}

function selectTarget(node: NodeSummary) {
  targetId.value = node.node_id
  targetQuery.value = `${node.name} (${node.node_type})`
  searchResults.value = []
}

function handleSubmit() {
  if (!canSubmit.value) return
  emit('submit', {
    source_id: props.sourceId,
    target_id: targetId.value,
    conn_type: connType.value,
  })
}
</script>

<template>
  <form
    class="edge-picker"
    @submit.prevent="handleSubmit"
  >
    <div class="form-row">
      <label class="form-label">Connection type <span class="required">*</span></label>
      <select
        v-model="connType"
        class="form-control"
        required
      >
        <option value="">
          — select —
        </option>
        <option
          v-for="t in CONN_TYPES"
          :key="t"
          :value="t"
        >
          {{ t }}
        </option>
      </select>
    </div>

    <div class="form-row">
      <label class="form-label">Target node <span class="required">*</span></label>
      <div class="search-box">
        <input
          v-model="targetQuery"
          type="text"
          class="form-control"
          placeholder="Search by name, type, or ID…"
          @input="searchNodes"
        >
        <div
          v-if="searching"
          class="search-hint"
        >
          Searching…
        </div>
        <div
          v-else-if="searchError"
          class="search-error"
        >
          {{ searchError }}
        </div>
        <ul
          v-else-if="searchResults.length > 0"
          class="search-results"
        >
          <li
            v-for="n in searchResults"
            :key="n.node_id"
            class="search-result-item"
            @click="selectTarget(n)"
          >
            <span class="result-badge">{{ n.node_type }}</span>
            <span class="result-name">{{ n.name }}</span>
            <span class="result-id">{{ n.node_id }}</span>
          </li>
        </ul>
      </div>
      <div
        v-if="targetId"
        class="target-selected"
      >
        Selected: <code>{{ targetId }}</code>
      </div>
    </div>

    <div class="form-actions">
      <button
        type="submit"
        class="btn-primary"
        :disabled="!canSubmit"
      >
        {{ loading ? 'Adding…' : 'Add edge' }}
      </button>
      <button
        type="button"
        class="btn-secondary"
        @click="emit('cancel')"
      >
        Cancel
      </button>
    </div>
  </form>
</template>

<style scoped>
.edge-picker { display: flex; flex-direction: column; gap: 14px; }
.form-row { display: flex; flex-direction: column; gap: 4px; }
.form-label { font-size: 12px; font-weight: 600; color: #374151; }
.required { color: #dc2626; }
.form-control {
  font-size: 13px;
  padding: 6px 10px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  background: #fff;
  color: #111827;
  width: 100%;
  box-sizing: border-box;
}
.form-control:focus { outline: 2px solid #2563eb; border-color: transparent; }
.search-box { position: relative; }
.search-hint, .search-error { font-size: 12px; color: #6b7280; padding: 4px 0; }
.search-error { color: #b91c1c; }
.search-results {
  list-style: none;
  margin: 4px 0 0;
  padding: 0;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  background: #fff;
  max-height: 180px;
  overflow-y: auto;
}
.search-result-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 10px;
  cursor: pointer;
  font-size: 13px;
  border-bottom: 1px solid #f1f5f9;
}
.search-result-item:hover { background: #f0f9ff; }
.search-result-item:last-child { border-bottom: none; }
.result-badge {
  font-size: 10px;
  font-weight: 600;
  background: #dbeafe;
  color: #1d4ed8;
  padding: 1px 6px;
  border-radius: 3px;
  flex-shrink: 0;
  white-space: nowrap;
}
.result-name { flex: 1; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.result-id { font-size: 10px; color: #9ca3af; white-space: nowrap; }
.target-selected { font-size: 12px; color: #15803d; }
.target-selected code { font-size: 11px; background: #f0fdf4; padding: 1px 4px; border-radius: 3px; }
.form-actions { display: flex; gap: 10px; }
.btn-primary {
  padding: 7px 18px;
  background: #2563eb;
  color: #fff;
  border: none;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}
.btn-primary:hover:not(:disabled) { background: #1d4ed8; }
.btn-primary:disabled { opacity: 0.5; cursor: default; }
.btn-secondary {
  padding: 7px 18px;
  background: #f3f4f6;
  color: #374151;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
}
.btn-secondary:hover { background: #e5e7eb; }
</style>
