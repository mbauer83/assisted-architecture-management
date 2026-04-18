<script setup lang="ts">
import { computed, inject, onMounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { Effect } from 'effect'
import { modelServiceKey } from '../keys'
import type { ConnectionRecord, ConnectionList, DiagramRefs, OntologyClassification } from '../../domain'
import EntitySearchInput from './EntitySearchInput.vue'

const props = defineProps<{
  entityId: string
  entityType: string
  connections: ConnectionList
  direction: 'outgoing' | 'incoming' | 'symmetric'
  loading: boolean
  error: string | null
  readonly?: boolean
  adminMode?: boolean
}>()

const emit = defineEmits<{
  refresh: []
}>()

const svc = inject(modelServiceKey)!

// ── Ontology ──────────────────────────────────────────────────────────────────

const ontology = ref<OntologyClassification | null>(null)

onMounted(() => {
  Effect.runPromise(svc.getOntologyClassification(props.entityType))
    .then((o) => { ontology.value = o })
    .catch(() => { /* silently degrade — sections built from existing connections */ })
})

watch(() => props.entityType, () => {
  ontology.value = null
  Effect.runPromise(svc.getOntologyClassification(props.entityType))
    .then((o) => { ontology.value = o })
    .catch(() => {})
})

// Permissible target types for this direction from the ontology
const permissibleTypes = computed((): string[] => {
  if (!ontology.value) return []
  const map = ontology.value[props.direction] as Record<string, string[]>
  return Object.keys(map).sort()
})

// Symmetric connection types derived from ontology
const symmetricConnTypes = computed((): Set<string> => {
  if (!ontology.value) return new Set()
  const types = new Set<string>()
  for (const conns of Object.values(ontology.value.symmetric)) {
    for (const ct of conns) types.add(ct)
  }
  return types
})

// ── Grouping ──────────────────────────────────────────────────────────────────

// Group existing connections by the artifact_type-prefix of the connected entity,
// filtering to only show connections matching this panel's direction.
const grouped = computed(() => {
  const groups: Record<string, ConnectionRecord[]> = {}
  const symTypes = symmetricConnTypes.value
  for (const c of props.connections) {
    const isSym = symTypes.has(c.conn_type)
    if (props.direction === 'symmetric' && !isSym) continue
    if (props.direction !== 'symmetric' && isSym) continue
    const otherId = props.direction === 'incoming' ? c.source : c.target
    const typePart = otherId.split('@')[0] ?? 'unknown'
    if (!groups[typePart]) groups[typePart] = []
    groups[typePart].push({ ...c })
  }
  return groups
})

// All section keys: union of ontology permissible types + types found in existing connections
const sectionKeys = computed((): string[] => {
  const all = new Set([...permissibleTypes.value, ...Object.keys(grouped.value)])
  return Array.from(all).sort()
})

const friendlyName = (id: string) => {
  const parts = id.split('.')
  return parts.length > 2 ? parts.slice(2).join(' ').replace(/-/g, ' ') : id
}

const otherEnd = (c: ConnectionRecord) =>
  props.direction === 'incoming' ? c.source : c.target

const titleLabel = computed(() => {
  if (props.direction === 'outgoing') return 'Outgoing'
  if (props.direction === 'incoming') return 'Incoming'
  return 'Symmetric'
})

// ── Add connection ─────────────────────────────────────────────────────────────

const addingFor = ref<string | null>(null)
const selectedTarget = ref<{ id: string; name: string } | null>(null)
const connTypeOptions = ref<string[]>([])
const connTypeSelected = ref('')
const descInput = ref('')
const addError = ref<string | null>(null)
const addBusy = ref(false)

const startAdd = (typeKey: string) => {
  if (addingFor.value === typeKey) {
    addingFor.value = null
    return
  }
  addingFor.value = typeKey
  selectedTarget.value = null
  connTypeOptions.value = []
  connTypeSelected.value = ''
  descInput.value = ''
  addError.value = null
  // Fetch permissible connection types for this source→target pair
  Effect.runPromise(svc.getOntologyPair(props.entityType, typeKey))
    .then((pair) => {
      const types = props.direction === 'symmetric'
        ? pair.connection_types.filter(ct => symmetricConnTypes.value.has(ct))
        : [...pair.connection_types]
      connTypeOptions.value = types
      if (types.length === 1) connTypeSelected.value = types[0]
      else if (props.direction === 'symmetric') connTypeSelected.value = 'archimate-association'
    })
    .catch(() => {
      connTypeOptions.value = []
    })
}

const cancelAdd = () => {
  addingFor.value = null
  selectedTarget.value = null
}

const onSelectTarget = (id: string, name: string) => {
  selectedTarget.value = { id, name }
}

const confirmAdd = () => {
  if (!selectedTarget.value || !connTypeSelected.value) return
  addBusy.value = true
  addError.value = null
  const isIncoming = props.direction === 'incoming'
  const source = isIncoming ? selectedTarget.value.id : props.entityId
  const target = isIncoming ? props.entityId : selectedTarget.value.id
  const addFn = props.adminMode ? svc.adminAddConnection : svc.addConnection
  Effect.runPromise(
    addFn({
      source_entity: source,
      connection_type: connTypeSelected.value,
      target_entity: target,
      description: descInput.value.trim() || undefined,
      dry_run: false,
    }),
  ).then((r) => {
    addBusy.value = false
    if (r.wrote) {
      addingFor.value = null
      selectedTarget.value = null
      emit('refresh')
    } else {
      addError.value = r.content ?? 'Verification failed'
    }
  }).catch((e) => {
    addBusy.value = false
    addError.value = String(e)
  })
}

// ── Remove connection ──────────────────────────────────────────────────────────

const removingConn = ref<ConnectionRecord | null>(null)
const diagramRefs = ref<DiagramRefs>([])
const diagramRefsLoading = ref(false)
const removeBusy = ref(false)
const removeError = ref<string | null>(null)

const startRemove = (c: ConnectionRecord) => {
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
  const removeFn = props.adminMode ? svc.adminRemoveConnection : svc.removeConnection
  Effect.runPromise(
    removeFn({
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
    <h2 class="conn-title">{{ titleLabel }} connections</h2>

    <div v-if="loading" class="state-msg">Loading...</div>
    <div v-else-if="error" class="state-msg state-msg--error">{{ error }}</div>

    <template v-else>
      <template v-if="sectionKeys.length">
        <div v-for="typeKey in sectionKeys" :key="typeKey" class="type-group">
          <div class="group-header">
            <span class="group-type-badge">{{ typeKey }}</span>
            <span class="group-count">{{ (grouped[typeKey] ?? []).length }}</span>
            <button v-if="!readonly" class="icon-btn add-btn" title="Add connection" @click="startAdd(typeKey)">+</button>
          </div>

          <ul v-if="grouped[typeKey]?.length" class="conn-list">
            <li v-for="c in grouped[typeKey]" :key="c.artifact_id" class="conn-item">
              <span class="conn-type-badge">{{ c.conn_type.replace('archimate-', '') }}</span>
              <RouterLink
                :to="{ path: '/entity', query: { id: otherEnd(c) } }"
                class="conn-target"
              >{{ friendlyName(otherEnd(c)) }}</RouterLink>
              <span v-if="c.content_text?.trim()" class="conn-info-wrap">
                <span class="conn-info-btn" tabindex="0">ⓘ</span>
                <span class="conn-info-tip">{{ c.content_text.trim() }}</span>
              </span>
              <button v-if="!readonly" class="icon-btn remove-btn" title="Remove connection" @click="startRemove(c)">×</button>
            </li>
          </ul>

          <!-- Add form for this type group -->
          <div v-if="addingFor === typeKey" class="add-form">
            <div v-if="connTypeOptions.length" class="add-row">
              <select v-model="connTypeSelected" class="conn-type-select">
                <option value="" disabled>Select connection type...</option>
                <option v-for="ct in connTypeOptions" :key="ct" :value="ct">
                  {{ ct.replace('archimate-', '') }}
                </option>
              </select>
            </div>
            <div v-else class="state-msg">Loading connection types...</div>
            <div class="add-row">
              <EntitySearchInput
                :artifact-type="typeKey"
                placeholder="Search target entity..."
                @select="onSelectTarget"
              />
            </div>
            <div v-if="selectedTarget" class="selected-target">
              Selected: <strong>{{ selectedTarget.name }}</strong>
            </div>
            <div class="add-row">
              <input
                v-model="descInput"
                class="desc-input"
                placeholder="Description (optional)"
              />
            </div>
            <div class="add-actions">
              <button class="cancel-btn" @click="cancelAdd">Cancel</button>
              <button
                class="add-confirm-btn"
                :disabled="!selectedTarget || !connTypeSelected || addBusy"
                @click="confirmAdd"
              >Add</button>
            </div>
            <div v-if="addError" class="state-msg state-msg--error">{{ addError }}</div>
          </div>
        </div>
      </template>

      <!-- Fallback when no ontology data yet and no connections -->
      <div v-else class="state-msg">None</div>
    </template>

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

.conn-info-wrap {
  position: relative; display: inline-flex; align-items: center; margin-left: 2px;
}
.conn-info-btn {
  font-size: 12px; color: #6b7280; cursor: default; user-select: none; line-height: 1;
}
.conn-info-tip {
  display: none; position: absolute; left: 100%; top: 50%; transform: translateY(-50%);
  margin-left: 6px; background: #1e293b; color: #f1f5f9; font-size: 11px; line-height: 1.4;
  padding: 6px 10px; border-radius: 6px; white-space: pre-wrap; max-width: 280px;
  z-index: 60; pointer-events: none; box-shadow: 0 4px 12px rgba(0,0,0,.3);
}
.conn-info-wrap:hover .conn-info-tip,
.conn-info-wrap:focus-within .conn-info-tip { display: block; }

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
.conn-type-select {
  flex: 1; padding: 6px 10px; border-radius: 6px; border: 1px solid #d1d5db;
  font-size: 12px; outline: none; background: white;
}
.conn-type-select:focus { border-color: #2563eb; }
.desc-input {
  flex: 1; padding: 6px 10px; border-radius: 6px; border: 1px solid #d1d5db;
  font-size: 12px; outline: none;
}
.desc-input:focus { border-color: #2563eb; }
.add-actions { display: flex; gap: 6px; justify-content: flex-end; margin-top: 4px; }
.add-confirm-btn {
  padding: 6px 14px; background: #2563eb; color: white; border: none;
  border-radius: 6px; font-size: 13px; font-weight: 500; cursor: pointer; white-space: nowrap;
}
.add-confirm-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.add-confirm-btn:hover:not(:disabled) { background: #1d4ed8; }
.cancel-btn {
  padding: 6px 14px; background: #f3f4f6; color: #374151; border: 1px solid #d1d5db;
  border-radius: 6px; font-size: 13px; cursor: pointer;
}
.cancel-btn:hover { background: #e5e7eb; }
.selected-target { font-size: 12px; color: #374151; margin-bottom: 4px; }

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
