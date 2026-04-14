<script setup lang="ts">
import { computed, inject, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { Effect } from 'effect'
import { modelServiceKey } from '../keys'
import type { ConnectionRecord, ConnectionList, DiagramRefs } from '../../domain'
import EntitySearchInput from './EntitySearchInput.vue'

const props = defineProps<{
  entityId: string
  connections: ConnectionList
  direction: 'outbound' | 'inbound'
  loading: boolean
  error: string | null
}>()

const emit = defineEmits<{
  refresh: []
}>()

const svc = inject(modelServiceKey)!

// Group connections by the artifact_type of the connected entity
const grouped = computed(() => {
  const groups: Record<string, ConnectionRecord[]> = {}
  for (const c of props.connections) {
    const otherId = props.direction === 'outbound' ? c.target : c.source
    const typePart = otherId.split('@')[0] ?? 'unknown'
    if (!groups[typePart]) groups[typePart] = []
    groups[typePart].push({ ...c })
  }
  return Object.entries(groups).sort(([a], [b]) => a.localeCompare(b))
})

const friendlyName = (id: string) => {
  const parts = id.split('.')
  return parts.length > 2 ? parts.slice(2).join(' ').replace(/-/g, ' ') : id
}

const otherEnd = (c: ConnectionList[number]) =>
  props.direction === 'outbound' ? c.target : c.source

// ── Add connection ───────────────────────────────────────────────────────────

const addingFor = ref<string | null>(null) // entity-type group key
const selectedTarget = ref<{ id: string; name: string } | null>(null)
const connTypeInput = ref('')
const addError = ref<string | null>(null)
const addBusy = ref(false)

const startAdd = (typeKey: string) => {
  addingFor.value = addingFor.value === typeKey ? null : typeKey
  selectedTarget.value = null
  connTypeInput.value = ''
  addError.value = null
}

const onSelectTarget = (id: string, name: string) => {
  selectedTarget.value = { id, name }
}

const confirmAdd = () => {
  if (!selectedTarget.value || !connTypeInput.value.trim()) return
  addBusy.value = true
  addError.value = null
  const source = props.direction === 'outbound' ? props.entityId : selectedTarget.value.id
  const target = props.direction === 'outbound' ? selectedTarget.value.id : props.entityId
  Effect.runPromise(
    svc.addConnection({
      source_entity: source,
      connection_type: connTypeInput.value.trim(),
      target_entity: target,
      dry_run: false,
    }),
  ).then((r) => {
    addBusy.value = false
    if (r.wrote) {
      addingFor.value = null
      selectedTarget.value = null
      connTypeInput.value = ''
      emit('refresh')
    } else {
      addError.value = r.content ?? 'Verification failed'
    }
  }).catch((e) => {
    addBusy.value = false
    addError.value = String(e)
  })
}

// ── Remove connection ────────────────────────────────────────────────────────

const removingConn = ref<ConnectionList[number] | null>(null)
const diagramRefs = ref<DiagramRefs>([])
const diagramRefsLoading = ref(false)
const removeBusy = ref(false)
const removeError = ref<string | null>(null)

const startRemove = (c: ConnectionList[number]) => {
  removingConn.value = c
  removeError.value = null
  diagramRefsLoading.value = true
  Effect.runPromise(svc.getDiagramRefs(c.source, c.target)).then((refs) => {
    diagramRefs.value = refs
    diagramRefsLoading.value = false
  }).catch(() => {
    diagramRefs.value = []
    diagramRefsLoading.value = false
  })
}

const cancelRemove = () => { removingConn.value = null }

const confirmRemove = () => {
  if (!removingConn.value) return
  removeBusy.value = true
  removeError.value = null
  const c = removingConn.value
  Effect.runPromise(
    svc.removeConnection({
      source_entity: c.source,
      connection_type: c.conn_type,
      target_entity: c.target,
      dry_run: false,
    }),
  ).then((r) => {
    removeBusy.value = false
    if (r.wrote) { removingConn.value = null; emit('refresh') }
    else { removeError.value = r.content ?? 'Verification failed' }
  }).catch((e) => {
    removeBusy.value = false
    removeError.value = String(e)
  })
}
</script>

<template>
  <div class="conn-panel">
    <h2 class="conn-title">{{ direction === 'outbound' ? 'Outbound' : 'Inbound' }} connections</h2>

    <div v-if="loading" class="state-msg">Loading...</div>
    <div v-else-if="error" class="state-msg state-msg--error">{{ error }}</div>
    <div v-else-if="!connections.length" class="state-msg">None</div>

    <template v-else>
      <div v-for="[typeKey, conns] in grouped" :key="typeKey" class="type-group">
        <div class="group-header">
          <span class="group-type-badge">{{ typeKey }}</span>
          <span class="group-count">{{ conns.length }}</span>
          <button class="icon-btn add-btn" title="Add connection" @click="startAdd(typeKey)">+</button>
        </div>

        <ul class="conn-list">
          <li v-for="c in conns" :key="c.artifact_id" class="conn-item">
            <span class="conn-type-badge">{{ c.conn_type.replace('archimate-', '') }}</span>
            <RouterLink
              :to="{ path: '/entity', query: { id: otherEnd(c) } }"
              class="conn-target"
            >{{ friendlyName(otherEnd(c)) }}</RouterLink>
            <button class="icon-btn remove-btn" title="Remove connection" @click="startRemove(c)">×</button>
          </li>
        </ul>

        <!-- Add connection form -->
        <div v-if="addingFor === typeKey" class="add-form">
          <div class="add-row">
            <input
              v-model="connTypeInput"
              class="conn-type-input"
              placeholder="Connection type (e.g. archimate-realization)"
            />
          </div>
          <div class="add-row">
            <EntitySearchInput
              :type-prefix="addingFor !== '_new' ? addingFor ?? undefined : undefined"
              placeholder="Search target entity..." @select="onSelectTarget"
            />
            <button
              class="add-confirm-btn"
              :disabled="!selectedTarget || !connTypeInput.trim() || addBusy"
              @click="confirmAdd"
            >Add</button>
          </div>
          <div v-if="selectedTarget" class="selected-target">
            Selected: <strong>{{ selectedTarget.name }}</strong>
          </div>
          <div v-if="addError" class="state-msg state-msg--error">{{ addError }}</div>
        </div>
      </div>
    </template>

    <!-- "Add" button when no connections exist for new group -->
    <div v-if="!loading && !error" class="add-new-group">
      <button class="icon-btn add-btn" title="Add connection" @click="startAdd('_new')">+</button>
      <div v-if="addingFor === '_new'" class="add-form">
        <div class="add-row">
          <input
            v-model="connTypeInput"
            class="conn-type-input"
            placeholder="Connection type (e.g. archimate-realization)"
          />
        </div>
        <div class="add-row">
          <EntitySearchInput placeholder="Search target entity..." @select="onSelectTarget" />
          <button
            class="add-confirm-btn"
            :disabled="!selectedTarget || !connTypeInput.trim() || addBusy"
            @click="confirmAdd"
          >Add</button>
        </div>
        <div v-if="selectedTarget" class="selected-target">
          Selected: <strong>{{ selectedTarget.name }}</strong>
        </div>
        <div v-if="addError" class="state-msg state-msg--error">{{ addError }}</div>
      </div>
    </div>

    <!-- Remove confirmation dialog -->
    <div v-if="removingConn" class="modal-overlay" @click.self="cancelRemove">
      <div class="modal">
        <h3 class="modal-title">Remove connection?</h3>
        <p class="modal-desc">
          <strong>{{ removingConn.conn_type.replace('archimate-', '') }}</strong>
          {{ removingConn.source }} → {{ removingConn.target }}
        </p>
        <div v-if="diagramRefsLoading" class="state-msg">Checking diagram references...</div>
        <template v-else-if="diagramRefs.length">
          <p class="modal-warn">This connection is referenced in {{ diagramRefs.length }} diagram(s):</p>
          <ul class="diagram-ref-list">
            <li v-for="d in diagramRefs" :key="d.artifact_id">{{ d.name }}</li>
          </ul>
          <p class="modal-warn">Those diagram references will become dangling.</p>
        </template>
        <div v-if="removeError" class="state-msg state-msg--error">{{ removeError }}</div>
        <div class="modal-actions">
          <button class="modal-btn modal-btn--cancel" @click="cancelRemove">Cancel</button>
          <button
            class="modal-btn modal-btn--danger"
            :disabled="removeBusy || diagramRefsLoading"
            @click="confirmRemove"
          >Remove</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.conn-panel { background: white; border-radius: 8px; border: 1px solid #e5e7eb; padding: 16px; }
.conn-title {
  font-size: 13px; font-weight: 600; color: #374151; margin-bottom: 12px;
  text-transform: uppercase; letter-spacing: .05em;
}

.state-msg { color: #6b7280; padding: 4px 0; font-size: 13px; }
.state-msg--error { color: #dc2626; }

.type-group { margin-bottom: 12px; }
.group-header { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.group-type-badge {
  padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600;
  background: #f0f0f0; color: #374151; text-transform: uppercase;
}
.group-count { font-size: 11px; color: #9ca3af; }

.conn-list { list-style: none; display: flex; flex-direction: column; gap: 4px; }
.conn-item { display: flex; align-items: baseline; gap: 8px; font-size: 13px; }
.conn-type-badge {
  padding: 1px 6px; border-radius: 4px; font-size: 11px;
  background: #f3f4f6; color: #374151; white-space: nowrap;
}
.conn-target { font-weight: 500; }

.icon-btn {
  width: 22px; height: 22px; border-radius: 4px; border: 1px solid #d1d5db;
  background: white; cursor: pointer; font-size: 14px; line-height: 1;
  display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.icon-btn:hover { background: #f3f4f6; }
.add-btn { color: #16a34a; border-color: #bbf7d0; }
.add-btn:hover { background: #f0fdf4; }
.remove-btn { color: #dc2626; border-color: #fecaca; margin-left: auto; }
.remove-btn:hover { background: #fef2f2; }

.add-form { margin-top: 8px; padding: 10px; background: #f9fafb; border-radius: 6px; }
.add-row { display: flex; gap: 6px; margin-bottom: 6px; align-items: center; }
.conn-type-input {
  flex: 1; padding: 6px 10px; border-radius: 6px; border: 1px solid #d1d5db;
  font-size: 12px; outline: none;
}
.conn-type-input:focus { border-color: #2563eb; }
.add-confirm-btn {
  padding: 6px 14px; background: #2563eb; color: white; border: none;
  border-radius: 6px; font-size: 13px; font-weight: 500; cursor: pointer; white-space: nowrap;
}
.add-confirm-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.add-confirm-btn:hover:not(:disabled) { background: #1d4ed8; }
.selected-target { font-size: 12px; color: #374151; margin-top: 4px; }
.add-new-group { margin-top: 8px; }

/* Remove modal */
.modal-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,.4); z-index: 100;
  display: flex; align-items: center; justify-content: center;
}
.modal {
  background: white; border-radius: 10px; padding: 24px; max-width: 480px;
  width: 90%; box-shadow: 0 8px 24px rgba(0,0,0,.2);
}
.modal-title { font-size: 16px; font-weight: 600; margin-bottom: 8px; }
.modal-desc { font-size: 13px; color: #374151; margin-bottom: 12px; word-break: break-all; }
.modal-warn { font-size: 13px; color: #b45309; margin-bottom: 8px; }
.diagram-ref-list { list-style: disc; padding-left: 20px; font-size: 13px; margin-bottom: 12px; }
.modal-actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 16px; }
.modal-btn {
  padding: 8px 16px; border-radius: 6px; font-size: 13px; font-weight: 500;
  cursor: pointer; border: none;
}
.modal-btn--cancel { background: #f3f4f6; color: #374151; }
.modal-btn--cancel:hover { background: #e5e7eb; }
.modal-btn--danger { background: #dc2626; color: white; }
.modal-btn--danger:hover:not(:disabled) { background: #b91c1c; }
.modal-btn--danger:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
