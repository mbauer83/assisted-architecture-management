<script setup lang="ts">
import { inject, onMounted, ref, watch, computed } from 'vue'
import { useRoute, useRouter, RouterLink } from 'vue-router'
import { Effect } from 'effect'
import { modelServiceKey } from '../keys'
import { useAsync } from '../composables/useAsync'
import ConnectionsPanel from '../components/ConnectionsPanel.vue'
import ArchimateTypeGlyph from '../components/ArchimateTypeGlyph.vue'
import type { EntityDetail, ConnectionList, OntologyClassification } from '../../domain'

const svc = inject(modelServiceKey)!
const router = useRouter()
const adminMode = ref(false)
onMounted(() => {
  Effect.runPromise(svc.getServerInfo())
    .then((info: any) => { adminMode.value = Boolean(info?.admin_mode) })
    .catch(() => {})
})
const route = useRoute()

const entityId = computed(() => (route.query.id as string | undefined) ?? '')

const detail = useAsync<EntityDetail>()
const outgoing = useAsync<ConnectionList>()
const incoming = useAsync<ConnectionList>()
const symmetric = useAsync<ConnectionList>()

// Whether the symmetric panel should be shown (based on ontology)
const ontology = ref<OntologyClassification | null>(null)
const hasSymmetric = computed(() =>
  ontology.value ? Object.keys(ontology.value.symmetric).length > 0 : false,
)

const load = () => {
  if (!entityId.value) return
  detail.run(svc.getEntity(entityId.value))
  loadConnections()
}

const loadConnections = () => {
  if (!entityId.value) return
  outgoing.run(svc.getConnections(entityId.value, 'outbound'))
  incoming.run(svc.getConnections(entityId.value, 'inbound'))
  // Symmetric connections share both directions; we show ones where this entity is source
  symmetric.run(svc.getConnections(entityId.value, 'outbound'))
}

onMounted(load)
watch(entityId, load)

watch(() => detail.data.value?.artifact_type, (newType) => {
  if (!newType) return
  Effect.runPromise(svc.getOntologyClassification(newType))
    .then((o) => { ontology.value = o })
    .catch(() => {})
})

// ── Edit mode ─────────────────────────────────────────────────────────────────

const editing = ref(false)
const editName = ref('')
const editSummary = ref('')
const editKeywords = ref('')
const editStatus = ref('')
const editProperties = ref<{ key: string; value: string }[]>([])
const editNotes = ref('')
const editBusy = ref(false)
const editError = ref<string | null>(null)
const editPreview = ref<{ content: string | null; warnings: string[] } | null>(null)
const deleteBusy = ref(false)
const deleteError = ref<string | null>(null)
const deletePreview = ref<{ content: string | null; warnings: string[] } | null>(null)
const confirmDelete = ref(false)

const startEdit = () => {
  if (!detail.data.value) return
  const d = detail.data.value
  editName.value = d.name
  editSummary.value = d.summary ?? ''
  editKeywords.value = (d.keywords ?? []).join(', ')
  editStatus.value = d.status
  editNotes.value = d.notes ?? ''
  editProperties.value = Object.entries(d.properties ?? {}).map(([key, value]) => ({ key, value }))
  editPreview.value = null
  editError.value = null
  editing.value = true
}

const cancelEdit = () => {
  editing.value = false
  editPreview.value = null
  editError.value = null
}

const addPropertyRow = () => {
  editProperties.value.push({ key: '', value: '' })
}

const removePropertyRow = (i: number) => {
  editProperties.value.splice(i, 1)
}

const buildEditBody = (dryRun: boolean) => {
  const props: Record<string, string> = {}
  for (const row of editProperties.value) {
    if (row.key.trim()) props[row.key.trim()] = row.value
  }
  const kws = editKeywords.value.split(',').map(k => k.trim()).filter(Boolean)
  return {
    artifact_id: entityId.value,
    name: editName.value || undefined,
    summary: editSummary.value || undefined,
    keywords: kws.length ? kws : undefined,
    status: editStatus.value || undefined,
    properties: Object.keys(props).length ? props : undefined,
    notes: editNotes.value || undefined,
    dry_run: dryRun,
  }
}

const isGlobalEntity = computed(() => detail.data.value?.is_global ?? false)
// Use admin endpoint when editing a global entity in admin mode
const editFn = computed(() =>
  (isGlobalEntity.value && adminMode.value) ? svc.adminEditEntity : svc.editEntity
)
const deleteFn = computed(() =>
  (isGlobalEntity.value && adminMode.value) ? svc.adminDeleteEntity : svc.deleteEntity
)

const previewEdit = () => {
  editBusy.value = true
  editError.value = null
  editPreview.value = null
  Effect.runPromise(editFn.value(buildEditBody(true))).then((r) => {
    editBusy.value = false
    editPreview.value = { content: r.content, warnings: [...r.warnings] }
  }).catch((e) => {
    editBusy.value = false
    editError.value = String(e)
  })
}

const saveEdit = () => {
  editBusy.value = true
  editError.value = null
  Effect.runPromise(editFn.value(buildEditBody(false))).then((r) => {
    editBusy.value = false
    if (r.wrote) {
      editing.value = false
      editPreview.value = null
      load()
    } else {
      editError.value = r.content ?? 'Verification failed'
    }
  }).catch((e) => {
    editBusy.value = false
    editError.value = String(e)
  })
}

const previewDelete = () => {
  if (!entityId.value) return
  deleteBusy.value = true
  deleteError.value = null
  deletePreview.value = null
  confirmDelete.value = true
  Effect.runPromise(deleteFn.value({ artifact_id: entityId.value, dry_run: true })).then((r: any) => {
    deleteBusy.value = false
    deletePreview.value = { content: r.content, warnings: [...r.warnings] }
  }).catch((e) => {
    deleteBusy.value = false
    if (typeof e === 'object' && e !== null) {
      if ('detail' in e) {
        deleteError.value = String((e as any).detail)
      } else if ('message' in e) {
        // check if message is JSON with "detail" field
        try {
          const json = JSON.parse(String((e as any).message))
          if ('detail' in json) {
            deleteError.value = String(json.detail)
          } else {
            deleteError.value = String((e as any).message)
          }
        } catch (e) {
          deleteError.value = String((e as any).message)
        }
      } else {
        deleteError.value = JSON.stringify(e)
      }
    } else {
      deleteError.value = String(e)
    }
  })
}

const cancelDelete = () => {
  confirmDelete.value = false
  deletePreview.value = null
  deleteError.value = null
}

const executeDelete = () => {
  if (!entityId.value) return
  deleteBusy.value = true
  deleteError.value = null
  Effect.runPromise(deleteFn.value({ artifact_id: entityId.value, dry_run: false })).then((r: any) => {
    deleteBusy.value = false
    if (r.wrote) {
      console.log('Delete successful')
      router.push(detail.data.value?.is_global ? '/global/entities' : '/entities')
    } else {
      console.error('Delete failed', r)
      deleteError.value = r.content ?? 'Delete failed'
    }
  }).catch((e) => {
    deleteBusy.value = false
    // See if we can extract JSON with a "detail" field from the error message
    console.error('Delete failed', e)
    if (typeof e === 'object' && e !== null) {
      if ('detail' in e) {
        deleteError.value = String((e as any).detail)
      } else if ('message' in e) {
        deleteError.value = String((e as any).message)
      } else {
        deleteError.value = JSON.stringify(e)
      }
    } else {
      deleteError.value = String(e)
    }
  })
}
</script>

<template>
  <div>
    <div class="top-bar">
      <RouterLink
        :to="detail.data.value?.is_global ? '/global/entities' : '/entities'"
        class="back-link"
      >← Browse entities</RouterLink>
      <div class="top-actions">
        <span v-if="detail.data.value?.is_global" class="global-badge" title="From the global (enterprise) repository">Global</span>
        <RouterLink
          v-if="entityId"
          :to="{ path: '/graph', query: { id: entityId } }"
          class="graph-btn"
        >Explore graph</RouterLink>
        <RouterLink
          v-if="detail.data.value && !detail.data.value.is_global && !editing"
          :to="{ path: '/promote', query: { entity_id: entityId } }"
          class="promote-btn"
          title="Promote this entity to the global repository"
        >↑ Promote to Global</RouterLink>
        <button
          v-if="detail.data.value && !editing && (!detail.data.value.is_global || adminMode)"
          class="edit-btn"
          :class="{ 'edit-btn--admin': detail.data.value.is_global && adminMode }"
          :title="detail.data.value.is_global && adminMode ? 'Edit global entity (admin mode)' : undefined"
          @click="startEdit"
        >Edit{{ detail.data.value.is_global && adminMode ? ' ⚠' : '' }}</button>
        <button
          v-if="detail.data.value && !editing && (!detail.data.value.is_global || adminMode)"
          class="delete-btn"
          :title="detail.data.value.is_global && adminMode ? 'Delete global entity (admin mode)' : undefined"
          @click="previewDelete"
        >Delete{{ detail.data.value.is_global && adminMode ? ' ⚠' : '' }}</button>
      </div>
    </div>

    <div v-if="detail.loading.value" class="state-msg">Loading...</div>
    <div v-else-if="detail.error.value" class="state-msg state-msg--error">{{ detail.error.value }}</div>

    <template v-else-if="detail.data.value">
      <div class="entity-header">
        <div class="entity-title-row">
          <h1 v-if="!editing" class="entity-name">{{ detail.data.value.name }}</h1>
          <input v-else v-model="editName" class="edit-name-input" />
          <span v-if="!editing" class="status-badge" :class="`status--${detail.data.value.status}`">{{ detail.data.value.status }}</span>
          <select v-else v-model="editStatus" class="edit-status-select">
            <option value="draft">draft</option>
            <option value="active">active</option>
            <option value="deprecated">deprecated</option>
          </select>
        </div>
        <div class="meta-row">
          <span class="meta-type">
            <ArchimateTypeGlyph :type="detail.data.value.artifact_type" :size="16" class="meta-glyph" />
            <span class="meta-item mono">{{ detail.data.value.artifact_type }}</span>
          </span>
          <span class="sep">·</span>
          <span class="domain-badge" :class="`domain--${detail.data.value.domain}`">{{ detail.data.value.domain }}</span>
          <span v-if="detail.data.value.subdomain" class="sep">/ {{ detail.data.value.subdomain }}</span>
          <span class="sep">·</span>
          <span class="meta-item">v{{ detail.data.value.version }}</span>
        </div>
        <div class="artifact-id mono">{{ detail.data.value.artifact_id }}</div>
      </div>

      <!-- Edit form -->
      <div v-if="editing" class="edit-form card">
        <div class="form-row">
          <label class="form-label">Summary</label>
          <textarea v-model="editSummary" class="edit-textarea" rows="3" />
        </div>
        <div class="form-row">
          <label class="form-label">Keywords <span class="form-hint">(comma-separated)</span></label>
          <input v-model="editKeywords" class="edit-input" placeholder="e.g. model, tooling, automation" />
        </div>
        <div class="form-row">
          <label class="form-label">Notes</label>
          <textarea v-model="editNotes" class="edit-textarea" rows="3" />
        </div>
        <div class="form-row">
          <label class="form-label">Properties</label>
          <div v-for="(row, i) in editProperties" :key="i" class="prop-row">
            <input v-model="row.key" class="prop-key" placeholder="key" />
            <input v-model="row.value" class="prop-value" placeholder="value" />
            <button class="icon-btn remove-prop-btn" @click="removePropertyRow(i)">×</button>
          </div>
          <button class="add-prop-btn" @click="addPropertyRow">+ Add property</button>
        </div>

        <!-- Preview -->
        <div v-if="editPreview" class="preview-box">
          <div class="preview-header">Dry-run preview</div>
          <div v-if="editPreview.warnings.length" class="preview-warnings">
            <div v-for="w in editPreview.warnings" :key="w" class="preview-warn">{{ w }}</div>
          </div>
          <pre v-if="editPreview.content" class="preview-content">{{ editPreview.content }}</pre>
        </div>

        <div v-if="editError" class="state-msg state-msg--error">{{ editError }}</div>

        <div class="edit-actions">
          <button class="cancel-btn" :disabled="editBusy" @click="cancelEdit">Cancel</button>
          <button class="preview-btn" :disabled="editBusy" @click="previewEdit">Preview</button>
          <button class="save-btn" :disabled="editBusy" @click="saveEdit">Save</button>
        </div>
      </div>

      <!-- Content -->
      <div v-else-if="detail.data.value?.content_html" class="card content-card">
        <div class="markdown-body" v-html="detail.data.value.content_html"></div>
      </div>

      <div v-if="confirmDelete" class="delete-panel card">
        <div class="delete-title">Delete Entity</div>
        <div class="delete-text">
          Deletion removes the entity artifact and its owned outgoing file. It is blocked while
          other connections, diagrams, or global references still depend on the entity.
        </div>
        <div v-if="deletePreview?.warnings.length" class="preview-warnings">
          <div v-for="w in deletePreview.warnings" :key="w" class="preview-warn">{{ w }}</div>
        </div>
        <pre v-if="deletePreview?.content" class="delete-preview">{{ deletePreview.content }}</pre>
        <pre v-if="deleteError" class="state-msg state-msg--error state-msg--block">{{ deleteError }}</pre>
        <div class="edit-actions">
          <button class="cancel-btn" :disabled="deleteBusy" @click="cancelDelete">Cancel</button>
          <button class="delete-confirm-btn" :disabled="deleteBusy" @click="executeDelete">
            {{ deleteBusy ? 'Deleting…' : 'Delete Entity' }}
          </button>
        </div>
      </div>

      <!-- Connections: [INCOMING] [SYMMETRIC] [OUTGOING] on wide screens -->
      <div class="connections-section" :class="{ 'has-symmetric': hasSymmetric }">
        <ConnectionsPanel
          :entity-id="entityId"
          :entity-type="detail.data.value.artifact_type"
          :connections="incoming.data.value ?? []"
          direction="incoming"
          :loading="incoming.loading.value"
          :error="incoming.error.value"
          :readonly="isGlobalEntity && !adminMode"
          :admin-mode="isGlobalEntity && adminMode"
          @refresh="loadConnections"
        />
        <ConnectionsPanel
          v-if="hasSymmetric"
          :entity-id="entityId"
          :entity-type="detail.data.value.artifact_type"
          :connections="symmetric.data.value ?? []"
          direction="symmetric"
          :loading="symmetric.loading.value"
          :error="symmetric.error.value"
          :readonly="isGlobalEntity && !adminMode"
          :admin-mode="isGlobalEntity && adminMode"
          @refresh="loadConnections"
        />
        <ConnectionsPanel
          :entity-id="entityId"
          :entity-type="detail.data.value.artifact_type"
          :connections="outgoing.data.value ?? []"
          direction="outgoing"
          :loading="outgoing.loading.value"
          :error="outgoing.error.value"
          :readonly="isGlobalEntity && !adminMode"
          :admin-mode="isGlobalEntity && adminMode"
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
.top-actions { display: flex; gap: 8px; align-items: center; }

.graph-btn {
  padding: 6px 14px; border-radius: 6px; background: #1e293b; color: #f8fafc;
  font-size: 13px; font-weight: 500;
}
.graph-btn:hover { background: #334155; text-decoration: none; }

.edit-btn {
  padding: 6px 14px; border-radius: 6px; background: #f3f4f6; color: #374151;
  border: 1px solid #d1d5db; font-size: 13px; font-weight: 500; cursor: pointer;
}
.edit-btn:hover { background: #e5e7eb; }
.delete-btn {
  padding: 6px 14px; border-radius: 6px; background: #fef2f2; color: #b91c1c;
  border: 1px solid #fecaca; font-size: 13px; font-weight: 500; cursor: pointer;
}
.delete-btn:hover { background: #fee2e2; }

.promote-btn {
  padding: 6px 14px; border-radius: 6px; background: #fef3c7; color: #92400e;
  border: 1px solid #fde68a; font-size: 13px; font-weight: 500;
}
.promote-btn:hover { background: #fde68a; text-decoration: none; }

.edit-btn--admin {
  background: #7c2d12; color: #fed7aa; border-color: #ea580c;
}
.edit-btn--admin:hover { background: #9a3412; }

.global-badge {
  display: inline-block;
  background: #fef3c7; color: #92400e;
  border: 1px solid #fde68a; border-radius: 4px;
  padding: 2px 8px; font-size: 11px; font-weight: 700;
  text-transform: uppercase; letter-spacing: .05em;
}

.state-msg { color: #6b7280; padding: 4px 0; }
.state-msg--error { color: #dc2626; }
.state-msg--block { white-space: pre-wrap; overflow-x: auto; }

.entity-header { margin-bottom: 20px; }
.entity-title-row { display: flex; align-items: center; gap: 12px; margin-bottom: 8px; flex-wrap: wrap; }
.entity-name { font-size: 22px; font-weight: 700; }
.edit-name-input {
  font-size: 20px; font-weight: 600; border: 1px solid #d1d5db; border-radius: 6px;
  padding: 4px 10px; outline: none; flex: 1;
}
.edit-name-input:focus { border-color: #2563eb; }
.edit-status-select {
  padding: 3px 8px; border-radius: 6px; border: 1px solid #d1d5db; font-size: 12px; outline: none;
}

.meta-row { display: flex; align-items: center; gap: 8px; font-size: 13px; color: #374151; margin-bottom: 6px; }
.meta-type { display: inline-flex; align-items: center; gap: 8px; }
.meta-glyph { color: #374151; fill: none; flex: 0 0 auto; }
.sep { color: #9ca3af; }
.artifact-id { font-size: 11px; color: #9ca3af; }
.mono { font-family: monospace; }

.card { background: white; border-radius: 8px; border: 1px solid #e5e7eb; }
.content-card { padding: 16px 20px; margin-bottom: 24px; overflow-x: auto; }

.markdown-body :deep(p) { margin: 1rem 0 1.7rem 0; }
.markdown-body :deep(ul) { padding-left: 1.5rem; }
.markdown-body :deep(table) { inline-size: 100%; border-collapse: collapse; margin-block: 2rem; min-inline-size: max-content; }
.markdown-body :deep(th), .markdown-body :deep(td) { padding-inline: 1.25rem; padding-block: 0.75rem; text-align: start; border-bottom: 1px solid var(--border-color, #eee); }

/* Edit form */
.edit-form { padding: 20px; margin-bottom: 24px; }
.form-row { margin-bottom: 14px; }
.form-label { display: block; font-size: 12px; font-weight: 600; color: #374151; margin-bottom: 4px; text-transform: uppercase; letter-spacing: .04em; }
.form-hint { font-weight: 400; text-transform: none; color: #9ca3af; }
.edit-input {
  width: 100%; padding: 7px 10px; border-radius: 6px; border: 1px solid #d1d5db;
  font-size: 13px; outline: none; box-sizing: border-box;
}
.edit-input:focus { border-color: #2563eb; }
.edit-textarea {
  width: 100%; padding: 7px 10px; border-radius: 6px; border: 1px solid #d1d5db;
  font-size: 13px; outline: none; resize: vertical; box-sizing: border-box; font-family: inherit;
}
.edit-textarea:focus { border-color: #2563eb; }

.prop-row { display: flex; gap: 6px; margin-bottom: 6px; align-items: center; }
.prop-key { flex: 1; padding: 6px 8px; border-radius: 6px; border: 1px solid #d1d5db; font-size: 12px; outline: none; }
.prop-value { flex: 2; padding: 6px 8px; border-radius: 6px; border: 1px solid #d1d5db; font-size: 12px; outline: none; }
.add-prop-btn {
  font-size: 12px; color: #2563eb; background: none; border: none; cursor: pointer; padding: 4px 0;
}
.add-prop-btn:hover { text-decoration: underline; }
.remove-prop-btn {
  width: 22px; height: 22px; border-radius: 4px; border: 1px solid #fecaca;
  background: white; cursor: pointer; color: #dc2626; font-size: 14px;
  display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.remove-prop-btn:hover { background: #fef2f2; }

.preview-box { background: #f9fafb; border-radius: 6px; padding: 12px; margin-bottom: 12px; }
.preview-header { font-size: 11px; font-weight: 600; text-transform: uppercase; color: #6b7280; margin-bottom: 8px; }
.preview-warnings { margin-bottom: 8px; }
.preview-warn { font-size: 12px; color: #b45309; }
.preview-content { font-size: 11px; color: #374151; white-space: pre-wrap; max-height: 200px; overflow-y: auto; font-family: monospace; }
.delete-panel { padding: 16px; margin-bottom: 24px; border-color: #fecaca; background: #fff7f7; }
.delete-title { font-size: 14px; font-weight: 700; color: #991b1b; margin-bottom: 6px; }
.delete-text { font-size: 13px; color: #7f1d1d; margin-bottom: 10px; }
.delete-preview {
  font-size: 11px; color: #374151; white-space: pre-wrap; max-height: 260px; overflow-y: auto;
  font-family: monospace; background: #fff; border: 1px solid #fecaca; border-radius: 6px; padding: 10px;
}

.edit-actions { display: flex; gap: 8px; justify-content: flex-end; padding-top: 4px; }
.cancel-btn {
  padding: 7px 16px; background: #f3f4f6; color: #374151; border: 1px solid #d1d5db;
  border-radius: 6px; font-size: 13px; cursor: pointer;
}
.cancel-btn:hover:not(:disabled) { background: #e5e7eb; }
.preview-btn {
  padding: 7px 16px; background: #f3f4f6; color: #1d4ed8; border: 1px solid #bfdbfe;
  border-radius: 6px; font-size: 13px; cursor: pointer; font-weight: 500;
}
.preview-btn:hover:not(:disabled) { background: #eff6ff; }
.save-btn {
  padding: 7px 16px; background: #2563eb; color: white; border: none;
  border-radius: 6px; font-size: 13px; font-weight: 500; cursor: pointer;
}
.save-btn:hover:not(:disabled) { background: #1d4ed8; }
.delete-confirm-btn {
  padding: 7px 16px; background: #dc2626; color: white; border: none;
  border-radius: 6px; font-size: 13px; font-weight: 600; cursor: pointer;
}
.delete-confirm-btn:hover:not(:disabled) { background: #b91c1c; }
.cancel-btn:disabled, .preview-btn:disabled, .save-btn:disabled, .delete-confirm-btn:disabled { opacity: 0.5; cursor: not-allowed; }

/* Connections — [INCOMING] [SYMMETRIC] [OUTGOING] */
.connections-section { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.connections-section.has-symmetric { grid-template-columns: 1fr 1fr 1fr; }
@media (max-width: 1000px) { .connections-section.has-symmetric { grid-template-columns: 1fr 1fr; } }
@media (max-width: 700px) { .connections-section, .connections-section.has-symmetric { grid-template-columns: 1fr; } }

.domain-badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 500; }
.domain--motivation { background: #d8c1e4; color: #252327; }
.domain--strategy   { background: #efbd5d; color: #252327; }
.domain--business   { background: #f4de7f; color: #252327; }
.domain--common     { background: #e8e5d3; color: #252327; }
.domain--application{ background: #b6d7e1; color: #252327; }
.domain--technology { background: #c3e1b4; color: #252327; }

.status-badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 500; }
.status--draft      { background: #f3f4f6; color: #6b7280; }
.status--active     { background: #dcfce7; color: #166534; }
.status--deprecated { background: #fee2e2; color: #991b1b; }
</style>
