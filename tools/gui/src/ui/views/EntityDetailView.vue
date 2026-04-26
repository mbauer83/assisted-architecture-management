<script setup lang="ts">
import { inject, onMounted, ref, watch, computed } from 'vue'
import { useRoute, useRouter, RouterLink } from 'vue-router'
import { Effect } from 'effect'
import { modelServiceKey, toastKey } from '../keys'
import { useQuery } from '../composables/useQuery'
import ConnectionsPanel from '../components/ConnectionsPanel.vue'
import ArchimateTypeGlyph from '../components/ArchimateTypeGlyph.vue'
import ArtifactReferenceInput from '../components/ArtifactReferenceInput.vue'
import type { EntityContext, WriteResult } from '../../domain'
import type { NotFoundError } from '../../domain'
import type { MarkdownError } from '../../application/MarkdownService'
import type { RepoError } from '../../ports/ModelRepository'
import { readErrorMessage } from '../lib/errors'

const svc = inject(modelServiceKey)!
const addToast = inject(toastKey)!
const router = useRouter()
const adminMode = ref(false)
onMounted(() => {
  void Effect.runPromise(svc.getServerInfo())
    .then((info) => { adminMode.value = info.admin_mode })
    .catch((reason: unknown) => {
      editError.value = readErrorMessage(reason)
    })
})
const route = useRoute()

const entityId = computed(() => (route.query.id as string | undefined) ?? '')

const context = useQuery<EntityContext, RepoError | NotFoundError | MarkdownError>()
const detail = computed(() => context.data.value?.entity ?? null)
const outgoing = computed(() => context.data.value?.connections.outbound ?? [])
const incoming = computed(() => context.data.value?.connections.inbound ?? [])
const symmetric = computed(() => context.data.value?.connections.symmetric ?? [])

const load = () => {
  if (!entityId.value) return
  context.run(svc.getEntityContext(entityId.value))
}

onMounted(load)
watch(entityId, load)

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
const showReferencePicker = ref(false)
const activeReferenceField = ref<'summary' | 'notes'>('summary')
const summaryTextareaRef = ref<HTMLTextAreaElement | null>(null)
const notesTextareaRef = ref<HTMLTextAreaElement | null>(null)

const startEdit = () => {
  if (!detail.value) return
  const d = detail.value
  if (!d) return
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
    properties: props,
    notes: editNotes.value || undefined,
    dry_run: dryRun,
  }
}

const isGlobalEntity = computed(() => detail.value?.is_global ?? false)
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
  void Effect.runPromise(editFn.value(buildEditBody(true))).then((r) => {
    editBusy.value = false
    editPreview.value = { content: r.content, warnings: [...r.warnings] }
  }).catch((reason: unknown) => {
    editBusy.value = false
    editError.value = readErrorMessage(reason)
  })
}

const saveEdit = () => {
  editBusy.value = true
  editError.value = null
  void Effect.runPromise(editFn.value(buildEditBody(false))).then((r) => {
    editBusy.value = false
    if (r.wrote) {
      addToast('Entity saved')
      editing.value = false
      editPreview.value = null
      if (r.artifact_id && r.artifact_id !== entityId.value) {
        void router.replace({ path: '/entity', query: { id: r.artifact_id } })
      } else {
        load()
      }
    } else {
      editError.value = r.content ?? 'Verification failed'
    }
  }).catch((reason: unknown) => {
    editBusy.value = false
    editError.value = readErrorMessage(reason)
  })
}

const previewDelete = () => {
  if (!entityId.value) return
  deleteBusy.value = true
  deleteError.value = null
  deletePreview.value = null
  confirmDelete.value = true
  void Effect.runPromise(deleteFn.value({ artifact_id: entityId.value, dry_run: true })).then((r: WriteResult) => {
    deleteBusy.value = false
    deletePreview.value = { content: r.content, warnings: [...r.warnings] }
  }).catch((reason: unknown) => {
    deleteBusy.value = false
    deleteError.value = readErrorMessage(reason)
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
  void Effect.runPromise(deleteFn.value({ artifact_id: entityId.value, dry_run: false })).then((r: WriteResult) => {
    deleteBusy.value = false
    if (r.wrote) {
      void router.push(detail.value?.is_global ? '/global/entities' : '/entities')
    } else {
      deleteError.value = r.content ?? 'Delete failed'
    }
  }).catch((reason: unknown) => {
    deleteBusy.value = false
    deleteError.value = readErrorMessage(reason)
  })
}

const openReferencePicker = (field: 'summary' | 'notes') => {
  activeReferenceField.value = field
  showReferencePicker.value = true
}

const insertReference = (markdownLink: string) => {
  const textarea = activeReferenceField.value === 'summary'
    ? summaryTextareaRef.value
    : notesTextareaRef.value
  if (!textarea) return
  const start = textarea.selectionStart ?? textarea.value.length
  const end = textarea.selectionEnd ?? start
  const currentValue = activeReferenceField.value === 'summary' ? editSummary.value : editNotes.value
  const nextValue = `${currentValue.slice(0, start)}${markdownLink}${currentValue.slice(end)}`
  if (activeReferenceField.value === 'summary') editSummary.value = nextValue
  else editNotes.value = nextValue
  requestAnimationFrame(() => {
    textarea.focus()
    const cursor = start + markdownLink.length
    textarea.setSelectionRange(cursor, cursor)
  })
}
</script>

<template>
  <div>
    <div class="top-bar">
      <RouterLink
        :to="detail?.is_global ? '/global/entities' : '/entities'"
        class="back-link"
      >
        ← Browse entities
      </RouterLink>
      <div class="top-actions">
        <span
          v-if="detail?.is_global"
          class="global-badge"
          title="From the global (enterprise) repository"
        >Global</span>
        <RouterLink
          v-if="entityId"
          :to="{ path: '/graph', query: { id: entityId } }"
          class="graph-btn"
        >
          Explore graph
        </RouterLink>
        <RouterLink
          v-if="detail && !detail.is_global && !editing"
          :to="{ path: '/promote', query: { entity_id: entityId } }"
          class="promote-btn"
          title="Promote this entity to the global repository"
        >
          ↑ Promote to Global
        </RouterLink>
        <button
          v-if="detail && !editing && (!detail.is_global || adminMode)"
          class="edit-btn"
          :class="{ 'edit-btn--admin': detail.is_global && adminMode }"
          :title="detail.is_global && adminMode ? 'Edit global entity (admin mode)' : undefined"
          @click="startEdit"
        >
          Edit{{ detail.is_global && adminMode ? ' ⚠' : '' }}
        </button>
        <button
          v-if="detail && !editing && (!detail.is_global || adminMode)"
          class="delete-btn"
          :title="detail.is_global && adminMode ? 'Delete global entity (admin mode)' : undefined"
          @click="previewDelete"
        >
          Delete{{ detail.is_global && adminMode ? ' ⚠' : '' }}
        </button>
        <button
          v-if="editing"
          class="cancel-btn"
          :disabled="editBusy"
          @click="cancelEdit"
        >
          Cancel
        </button>
        <button
          v-if="editing"
          class="preview-btn"
          :disabled="editBusy"
          @click="previewEdit"
        >
          Preview
        </button>
        <button
          v-if="editing"
          class="save-btn"
          :disabled="editBusy"
          @click="saveEdit"
        >
          Save
        </button>
      </div>
    </div>

    <div
      v-if="context.loading.value"
      class="state-msg"
    >
      Loading...
    </div>
    <div
      v-else-if="context.errorMessage.value"
      class="state-msg state-msg--error"
    >
      {{ context.errorMessage.value }}
    </div>

    <template v-else-if="detail">
      <div class="entity-header">
        <div class="entity-title-row">
          <h1
            v-if="!editing"
            class="entity-name"
          >
            {{ detail.name }}
          </h1>
          <input
            v-else
            v-model="editName"
            class="edit-name-input"
          >
          <span
            v-if="!editing"
            class="status-badge"
            :class="`status--${detail.status}`"
          >{{ detail.status }}</span>
          <select
            v-else
            v-model="editStatus"
            class="edit-status-select"
          >
            <option value="draft">
              draft
            </option>
            <option value="active">
              active
            </option>
            <option value="deprecated">
              deprecated
            </option>
          </select>
        </div>
        <div class="meta-row">
          <span class="meta-type">
            <ArchimateTypeGlyph
              :type="detail.artifact_type"
              :size="16"
              class="meta-glyph"
            />
            <span class="meta-item mono">{{ detail.artifact_type }}</span>
          </span>
          <span class="sep">·</span>
          <span
            class="domain-badge"
            :class="`domain--${detail.domain}`"
          >{{ detail.domain }}</span>
          <span
            v-if="detail.subdomain"
            class="sep"
          >/ {{ detail.subdomain }}</span>
          <span class="sep">·</span>
          <span class="meta-item">v{{ detail.version }}</span>
        </div>
        <div class="artifact-id mono">
          {{ detail.artifact_id }}
        </div>
      </div>

      <!-- Edit form -->
      <div
        v-if="editing"
        class="edit-form card"
      >
        <div class="form-row">
          <label class="form-label">Summary</label>
          <div class="field-tools">
            <button
              class="insert-ref-btn"
              type="button"
              @click="openReferencePicker('summary')"
            >
              Insert Reference
            </button>
          </div>
          <textarea
            ref="summaryTextareaRef"
            v-model="editSummary"
            class="edit-textarea"
            rows="3"
          />
        </div>
        <div class="form-row">
          <label class="form-label">Keywords <span class="form-hint">(comma-separated)</span></label>
          <input
            v-model="editKeywords"
            class="edit-input"
            placeholder="e.g. model, tooling, automation"
          >
        </div>
        <div class="form-row">
          <label class="form-label">Notes</label>
          <div class="field-tools">
            <button
              class="insert-ref-btn"
              type="button"
              @click="openReferencePicker('notes')"
            >
              Insert Reference
            </button>
          </div>
          <textarea
            ref="notesTextareaRef"
            v-model="editNotes"
            class="edit-textarea"
            rows="3"
          />
        </div>
        <div class="form-row">
          <label class="form-label">Properties</label>
          <div
            v-for="(row, i) in editProperties"
            :key="i"
            class="prop-row"
          >
            <input
              v-model="row.key"
              class="prop-key"
              placeholder="key"
            >
            <input
              v-model="row.value"
              class="prop-value"
              placeholder="value"
            >
            <button
              class="icon-btn remove-prop-btn"
              @click="removePropertyRow(i)"
            >
              ×
            </button>
          </div>
          <button
            class="add-prop-btn"
            @click="addPropertyRow"
          >
            + Add property
          </button>
        </div>

        <!-- Preview -->
        <div
          v-if="editPreview"
          class="preview-box"
        >
          <div class="preview-header">
            Dry-run preview
          </div>
          <div
            v-if="editPreview.warnings.length"
            class="preview-warnings"
          >
            <div
              v-for="w in editPreview.warnings"
              :key="w"
              class="preview-warn"
            >
              {{ w }}
            </div>
          </div>
          <pre
            v-if="editPreview.content"
            class="preview-content"
          >{{ editPreview.content }}</pre>
        </div>

        <div
          v-if="editError"
          class="state-msg state-msg--error"
        >
          {{ editError }}
        </div>

        <div class="edit-actions">
          <button
            class="cancel-btn"
            :disabled="editBusy"
            @click="cancelEdit"
          >
            Cancel
          </button>
          <button
            class="preview-btn"
            :disabled="editBusy"
            @click="previewEdit"
          >
            Preview
          </button>
          <button
            class="save-btn"
            :disabled="editBusy"
            @click="saveEdit"
          >
            Save
          </button>
        </div>
      </div>

      <!-- Content -->
      <div
        v-else-if="detail?.content_html"
        class="card content-card"
      >
        <div
          class="markdown-body"
          v-html="detail.content_html"
        />
      </div>

      <div
        v-if="confirmDelete"
        class="delete-panel card"
      >
        <div class="delete-title">
          Delete Entity
        </div>
        <div class="delete-text">
          Deletion removes the entity artifact and its owned outgoing file. It is blocked while
          other connections, diagrams, or global references still depend on the entity.
        </div>
        <div
          v-if="deletePreview?.warnings.length"
          class="preview-warnings"
        >
          <div
            v-for="w in deletePreview.warnings"
            :key="w"
            class="preview-warn"
          >
            {{ w }}
          </div>
        </div>
        <pre
          v-if="deletePreview?.content"
          class="delete-preview"
        >{{ deletePreview.content }}</pre>
        <pre
          v-if="deleteError"
          class="state-msg state-msg--error state-msg--block"
        >{{ deleteError }}</pre>
        <div class="edit-actions">
          <button
            class="cancel-btn"
            :disabled="deleteBusy"
            @click="cancelDelete"
          >
            Cancel
          </button>
          <button
            class="delete-confirm-btn"
            :disabled="deleteBusy"
            @click="executeDelete"
          >
            {{ deleteBusy ? 'Deleting…' : 'Delete Entity' }}
          </button>
        </div>
      </div>

      <!-- Connections: [INCOMING] [SYMMETRIC] [OUTGOING] on wide screens -->
      <div class="connections-section">
        <ConnectionsPanel
          :entity-id="entityId"
          :entity-type="detail.artifact_type"
          :connections="incoming"
          direction="incoming"
          :loading="context.loading.value"
          :error="context.errorMessage.value"
          :readonly="isGlobalEntity && !adminMode"
          :admin-mode="isGlobalEntity && adminMode"
          @refresh="load"
        />
        <ConnectionsPanel
          :entity-id="entityId"
          :entity-type="detail.artifact_type"
          :connections="symmetric"
          direction="symmetric"
          :loading="context.loading.value"
          :error="context.errorMessage.value"
          :readonly="isGlobalEntity && !adminMode"
          :admin-mode="isGlobalEntity && adminMode"
          @refresh="load"
        />
        <ConnectionsPanel
          :entity-id="entityId"
          :entity-type="detail.artifact_type"
          :connections="outgoing"
          direction="outgoing"
          :loading="context.loading.value"
          :error="context.errorMessage.value"
          :readonly="isGlobalEntity && !adminMode"
          :admin-mode="isGlobalEntity && adminMode"
          @refresh="load"
        />
      </div>

      <div
        v-if="showReferencePicker"
        class="overlay"
        @click.self="showReferencePicker = false"
      >
        <ArtifactReferenceInput
          :current-path="detail?.path"
          :fixed-kinds="['diagram', 'document']"
          @insert="insertReference"
          @close="showReferencePicker = false"
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
.field-tools { display: flex; justify-content: flex-end; margin-bottom: 6px; }
.insert-ref-btn {
  padding: 4px 10px; border-radius: 6px; border: 1px solid #d1d5db;
  background: #f8fafc; color: #374151; font-size: 12px; cursor: pointer;
}
.insert-ref-btn:hover { background: #f1f5f9; }
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
.connections-section { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px; }
@media (max-width: 1000px) { .connections-section { grid-template-columns: 1fr 1fr; } }
@media (max-width: 700px) { .connections-section { grid-template-columns: 1fr; } }
.overlay {
  position: fixed; inset: 0; background: rgba(15, 23, 42, 0.48);
  display: flex; align-items: center; justify-content: center; padding: 24px; z-index: 50;
}

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
