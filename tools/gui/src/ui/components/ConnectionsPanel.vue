<script setup lang="ts">
import { computed, inject, onMounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { Effect } from 'effect'
import { modelServiceKey } from '../keys'
import type {
  ConnectionRecord,
  ConnectionList,
  DiagramRefs,
  OntologyClassification,
  WriteHelp,
} from '../../domain'
import EntitySearchInput from './EntitySearchInput.vue'
import { readErrorMessage } from '../lib/errors'

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

// Helper to resolve entity name from id via loaded connections or prefix
const friendlyName = (id: string) => {
  const parts = id.split('.')
  return parts.length > 2 ? parts.slice(2).join(' ').replace(/-/g, ' ') : id
}

const emit = defineEmits<{
  refresh: []
}>()

const svc = inject(modelServiceKey)!

// ── Ontology ──────────────────────────────────────────────────────────────────

const ontology = ref<OntologyClassification | null>(null)
const prefixToType = ref<Record<string, string>>({})

const loadTypeCatalog = () => {
  void Effect.runPromise(svc.getWriteHelp())
    .then((help: WriteHelp) => {
      const catalog = help.entity_type_catalog
      if (!catalog) return
      const next: Record<string, string> = {}
      for (const [artifactType, info] of Object.entries(catalog)) {
        if (info.prefix) {
          next[info.prefix] = artifactType
        }
      }
      prefixToType.value = next
    })
    .catch((error: unknown) => {
      console.error('Failed to load write help', readErrorMessage(error))
    })
}

onMounted(() => {
  loadTypeCatalog()
  void Effect.runPromise(svc.getOntologyClassification(props.entityType))
    .then((o) => { ontology.value = o })
    .catch((error: unknown) => {
      console.error('Failed to load ontology classification', readErrorMessage(error))
    })
})

watch(() => props.entityType, () => {
  ontology.value = null
  void Effect.runPromise(svc.getOntologyClassification(props.entityType))
    .then((o) => { ontology.value = o })
    .catch((error: unknown) => {
      console.error('Failed to refresh ontology classification', readErrorMessage(error))
    })
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

const artifactTypeFromId = (artifactId: string) => {
  const prefix = artifactId.split('@')[0] ?? ''
  return prefixToType.value[prefix] ?? prefix.toLowerCase()
}

// Group existing connections by the artifact_type-prefix of the connected entity,
// filtering to only show connections matching this panel's direction.
const otherArtifactId = (c: ConnectionRecord) => {
  if (props.direction === 'incoming') return c.source
  if (props.direction === 'symmetric') return c.source === props.entityId ? c.target : c.source
  return c.target
}

const grouped = computed(() => {
  const groups: Record<string, ConnectionRecord[]> = {}
  const symTypes = symmetricConnTypes.value
  for (const c of props.connections) {
    const isSym = symTypes.has(c.conn_type)
    if (props.direction === 'symmetric' && !isSym) continue
    if (props.direction !== 'symmetric' && isSym) continue
    const otherId = otherArtifactId(c)
    const typePart = artifactTypeFromId(otherId)
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

const otherEnd = (c: ConnectionRecord) => otherArtifactId(c)

const otherEndName = (c: ConnectionRecord) => {
  if (props.direction === 'incoming') return c.source_name || friendlyName(c.source)
  if (props.direction === 'symmetric') {
    const otherId = otherEnd(c)
    if (otherId === c.source) return c.source_name || friendlyName(c.source)
    return c.target_name || friendlyName(c.target)
  }
  return c.target_name || friendlyName(c.target)
}

const titleLabel = computed(() => {
  if (props.direction === 'outgoing') return 'Outgoing'
  if (props.direction === 'incoming') return 'Incoming'
  return 'Symmetric'
})

// ── Association expand/edit ───────────────────────────────────────────────────

const expandedAssoc = ref<Set<string>>(new Set())
const assocAddTarget = ref<Record<string, { id: string; name: string } | null>>({})
const assocBusy = ref<Record<string, boolean>>({})
const assocError = ref<Record<string, string | null>>({})

const toggleAssoc = (connId: string) => {
  const next = new Set(expandedAssoc.value)
  if (next.has(connId)) next.delete(connId)
  else next.add(connId)
  expandedAssoc.value = next
}

const onAssocTargetSelect = (connId: string, id: string, name: string) => {
  assocAddTarget.value = { ...assocAddTarget.value, [connId]: { id, name } }
}

const addAssociation = (c: ConnectionRecord) => {
  const picked = assocAddTarget.value[c.artifact_id]
  if (!picked) return
  assocBusy.value = { ...assocBusy.value, [c.artifact_id]: true }
  assocError.value = { ...assocError.value, [c.artifact_id]: null }
  Effect.runPromise(
    svc.manageConnectionAssociations({
      source_entity: c.source, connection_type: c.conn_type, target_entity: c.target,
      add_entities: [picked.id], dry_run: false,
    }),
  ).then((r) => {
    assocBusy.value = { ...assocBusy.value, [c.artifact_id]: false }
    if (r.wrote) {
      assocAddTarget.value = { ...assocAddTarget.value, [c.artifact_id]: null }
      emit('refresh')
    } else {
      assocError.value = { ...assocError.value, [c.artifact_id]: r.content ?? 'Failed' }
    }
  }).catch((e) => {
    assocBusy.value = { ...assocBusy.value, [c.artifact_id]: false }
    assocError.value = { ...assocError.value, [c.artifact_id]: String(e) }
  })
}

const removeAssociation = (c: ConnectionRecord, entityId: string) => {
  assocBusy.value = { ...assocBusy.value, [c.artifact_id]: true }
  Effect.runPromise(
    svc.manageConnectionAssociations({
      source_entity: c.source, connection_type: c.conn_type, target_entity: c.target,
      remove_entities: [entityId], dry_run: false,
    }),
  ).then((r) => {
    assocBusy.value = { ...assocBusy.value, [c.artifact_id]: false }
    if (r.wrote) emit('refresh')
  }).catch(() => {
    assocBusy.value = { ...assocBusy.value, [c.artifact_id]: false }
  })
}

// ── Add connection ─────────────────────────────────────────────────────────────

const addingFor = ref<string | null>(null)
const selectedTarget = ref<{ id: string; name: string } | null>(null)
const connTypeOptions = ref<string[]>([])
const connTypeSelected = ref('')
const descInput = ref('')
const srcCardInput = ref('')
const tgtCardInput = ref('')
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
  srcCardInput.value = ''
  tgtCardInput.value = ''
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
      src_cardinality: srcCardInput.value.trim() || undefined,
      tgt_cardinality: tgtCardInput.value.trim() || undefined,
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
    <h2 class="conn-title">
      {{ titleLabel }} connections
    </h2>

    <div
      v-if="loading"
      class="state-msg"
    >
      Loading...
    </div>
    <div
      v-else-if="error"
      class="state-msg state-msg--error"
    >
      {{ error }}
    </div>

    <template v-else>
      <template v-if="sectionKeys.length">
        <div
          v-for="typeKey in sectionKeys"
          :key="typeKey"
          class="type-group"
        >
          <div class="group-header">
            <span class="group-type-badge">{{ typeKey }}</span>
            <span class="group-count">{{ (grouped[typeKey] ?? []).length }}</span>
            <button
              v-if="!readonly"
              class="icon-btn add-btn"
              title="Add connection"
              @click="startAdd(typeKey)"
            >
              +
            </button>
          </div>

          <ul
            v-if="grouped[typeKey]?.length"
            class="conn-list"
          >
            <li
              v-for="c in grouped[typeKey]"
              :key="c.artifact_id"
              class="conn-item-wrap"
            >
              <div class="conn-item">
                <span class="conn-type-badge">{{ c.conn_type.replace('archimate-', '') }}</span>
                <span
                  v-if="c.src_cardinality || c.tgt_cardinality"
                  class="conn-card-badge"
                >
                  {{ c.src_cardinality || '·' }}..{{ c.tgt_cardinality || '·' }}
                </span>
                <RouterLink
                  :to="{ path: '/entity', query: { id: otherEnd(c) } }"
                  class="conn-target"
                >
                  {{ otherEndName(c) }}
                </RouterLink>
                <span
                  v-if="c.content_text?.trim()"
                  class="conn-info-wrap"
                >
                  <span
                    class="conn-info-btn"
                    tabindex="0"
                  >ⓘ</span>
                  <span class="conn-info-tip">{{ c.content_text.trim() }}</span>
                </span>
                <button
                  v-if="!readonly"
                  class="icon-btn assoc-btn"
                  :class="{ 'assoc-btn--active': expandedAssoc.has(c.artifact_id) }"
                  :title="expandedAssoc.has(c.artifact_id) ? 'Hide associations' : 'Associations'"
                  @click="toggleAssoc(c.artifact_id)"
                >
                  {{ (c.associated_entities?.length ?? 0) > 0 ? `⊕${c.associated_entities!.length}` : '⊕' }}
                </button>
                <button
                  v-if="!readonly"
                  class="icon-btn remove-btn"
                  title="Remove connection"
                  @click="startRemove(c)"
                >
                  ×
                </button>
              </div>

              <!-- Second-order associations panel -->
              <div
                v-if="!readonly && expandedAssoc.has(c.artifact_id)"
                class="assoc-panel"
              >
                <div class="assoc-chips">
                  <span
                    v-for="eid in (c.associated_entities ?? [])"
                    :key="eid"
                    class="assoc-chip"
                  >
                    <RouterLink
                      :to="{ path: '/entity', query: { id: eid } }"
                      class="assoc-chip-link"
                    >{{ friendlyName(eid) }}</RouterLink>
                    <button
                      class="assoc-chip-remove"
                      :disabled="assocBusy[c.artifact_id]"
                      @click="removeAssociation(c, eid)"
                    >×</button>
                  </span>
                  <span
                    v-if="!(c.associated_entities?.length)"
                    class="assoc-empty"
                  >No associations</span>
                </div>
                <div class="assoc-add-row">
                  <EntitySearchInput
                    placeholder="Associate entity..."
                    @select="(id, name) => onAssocTargetSelect(c.artifact_id, id, name)"
                  />
                  <button
                    class="assoc-add-btn"
                    :disabled="!assocAddTarget[c.artifact_id] || assocBusy[c.artifact_id]"
                    @click="addAssociation(c)"
                  >
                    +
                  </button>
                </div>
                <div
                  v-if="assocError[c.artifact_id]"
                  class="state-msg state-msg--error"
                >
                  {{ assocError[c.artifact_id] }}
                </div>
              </div>
            </li>
          </ul>

          <!-- Add form for this type group -->
          <div
            v-if="addingFor === typeKey"
            class="add-form"
          >
            <div
              v-if="connTypeOptions.length"
              class="add-row"
            >
              <select
                v-model="connTypeSelected"
                class="conn-type-select"
              >
                <option
                  value=""
                  disabled
                >
                  Select connection type...
                </option>
                <option
                  v-for="ct in connTypeOptions"
                  :key="ct"
                  :value="ct"
                >
                  {{ ct.replace('archimate-', '') }}
                </option>
              </select>
            </div>
            <div
              v-else
              class="state-msg"
            >
              Loading connection types...
            </div>
            <div class="add-row">
              <EntitySearchInput
                :artifact-type="typeKey"
                placeholder="Search target entity..."
                @select="onSelectTarget"
              />
            </div>
            <div
              v-if="selectedTarget"
              class="selected-target"
            >
              Selected: <strong>{{ selectedTarget.name }}</strong>
            </div>
            <div class="add-row">
              <input
                v-model="descInput"
                class="desc-input"
                placeholder="Description (optional)"
              >
            </div>
            <div class="add-row add-row--card">
              <label class="card-label">src</label>
              <input
                v-model="srcCardInput"
                class="card-input"
                placeholder="e.g. 1"
                maxlength="8"
              >
              <span class="card-sep">→</span>
              <label class="card-label">tgt</label>
              <input
                v-model="tgtCardInput"
                class="card-input"
                placeholder="e.g. *"
                maxlength="8"
              >
              <span class="card-hint">cardinality (optional)</span>
            </div>
            <div class="add-actions">
              <button
                class="cancel-btn"
                @click="cancelAdd"
              >
                Cancel
              </button>
              <button
                class="add-confirm-btn"
                :disabled="!selectedTarget || !connTypeSelected || addBusy"
                @click="confirmAdd"
              >
                Add
              </button>
            </div>
            <div
              v-if="addError"
              class="state-msg state-msg--error"
            >
              {{ addError }}
            </div>
          </div>
        </div>
      </template>

      <!-- Fallback when no ontology data yet and no connections -->
      <div
        v-else
        class="state-msg"
      >
        None
      </div>
    </template>

    <!-- Remove confirmation dialog -->
    <div
      v-if="removingConn"
      class="modal-overlay"
      @click.self="cancelRemove"
    >
      <div class="modal">
        <h3 class="modal-title">
          Remove connection?
        </h3>
        <p class="modal-desc">
          <strong>{{ removingConn.conn_type.replace('archimate-', '') }}</strong>
          {{ removingConn.source }} → {{ removingConn.target }}
        </p>
        <div
          v-if="diagramRefsLoading"
          class="state-msg"
        >
          Checking diagram references...
        </div>
        <template v-else-if="diagramRefs.length">
          <p class="modal-warn">
            This connection is referenced in {{ diagramRefs.length }} diagram(s):
          </p>
          <ul class="diagram-ref-list">
            <li
              v-for="d in diagramRefs"
              :key="d.artifact_id"
            >
              {{ d.name }}
            </li>
          </ul>
          <p class="modal-warn">
            Those diagram references will become dangling.
          </p>
        </template>
        <div
          v-if="removeError"
          class="state-msg state-msg--error"
        >
          {{ removeError }}
        </div>
        <div class="modal-actions">
          <button
            class="modal-btn modal-btn--cancel"
            @click="cancelRemove"
          >
            Cancel
          </button>
          <button
            class="modal-btn modal-btn--danger"
            :disabled="removeBusy || diagramRefsLoading"
            @click="confirmRemove"
          >
            Remove
          </button>
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
.conn-item-wrap { display: flex; flex-direction: column; gap: 2px; }
.conn-item { display: flex; align-items: center; gap: 6px; font-size: 13px; }
.conn-type-badge {
  padding: 1px 6px; border-radius: 4px; font-size: 11px;
  background: #f3f4f6; color: #374151; white-space: nowrap;
}
.conn-target { font-weight: 500; }
.conn-card-badge {
  font-size: 10px; color: #6b7280; font-family: monospace; white-space: nowrap;
  background: #f3f4f6; padding: 1px 4px; border-radius: 3px;
}

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
.assoc-btn {
  color: #2563eb; border-color: #bfdbfe; font-size: 10px; font-weight: 600;
}
.assoc-btn:hover { background: #eff6ff; }
.assoc-btn--active { background: #eff6ff; }

/* Association panel */
.assoc-panel {
  margin-left: 12px; padding: 6px 10px; background: #f0f9ff;
  border-radius: 6px; border: 1px solid #bae6fd; font-size: 12px;
}
.assoc-chips { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 6px; align-items: center; }
.assoc-chip {
  display: inline-flex; align-items: center; gap: 2px;
  background: #dbeafe; border: 1px solid #93c5fd; border-radius: 12px;
  padding: 1px 6px; font-size: 11px;
}
.assoc-chip-link { color: #1d4ed8; text-decoration: none; }
.assoc-chip-link:hover { text-decoration: underline; }
.assoc-chip-remove {
  background: none; border: none; color: #64748b; cursor: pointer;
  padding: 0 1px; font-size: 12px; line-height: 1;
}
.assoc-chip-remove:hover { color: #dc2626; }
.assoc-empty { color: #94a3b8; font-style: italic; }
.assoc-add-row { display: flex; gap: 4px; align-items: center; }
.assoc-add-btn {
  padding: 4px 8px; background: #2563eb; color: white; border: none;
  border-radius: 4px; font-size: 12px; cursor: pointer; flex-shrink: 0;
}
.assoc-add-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.assoc-add-btn:hover:not(:disabled) { background: #1d4ed8; }

/* Cardinality row in add form */
.add-row--card { align-items: center; gap: 4px; }
.card-label { font-size: 11px; color: #6b7280; white-space: nowrap; }
.card-input {
  width: 52px; padding: 4px 6px; border-radius: 4px; border: 1px solid #d1d5db;
  font-size: 11px; font-family: monospace; outline: none;
}
.card-input:focus { border-color: #2563eb; }
.card-sep { color: #9ca3af; font-size: 11px; margin: 0 2px; }
.card-hint { font-size: 10px; color: #9ca3af; margin-left: 4px; }

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
