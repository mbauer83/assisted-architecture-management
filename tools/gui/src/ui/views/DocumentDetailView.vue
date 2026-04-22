<script setup lang="ts">
import { computed, inject, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Effect } from 'effect'
import { modelServiceKey } from '../keys'
import MarkdownEditor from '../components/MarkdownEditor.vue'
import ArtifactReferenceInput from '../components/ArtifactReferenceInput.vue'
import type { DocumentDetail } from '../../domain'

const svc = inject(modelServiceKey)!
const route = useRoute()
const router = useRouter()

const documentId = computed(() => route.params.id as string)
const detail = ref<DocumentDetail | null>(null)
const loading = ref(false)
const saving = ref(false)
const deleting = ref(false)
const error = ref<string | null>(null)
const verificationIssues = ref<string[]>([])
const showReferencePicker = ref(false)
const editorRef = ref<InstanceType<typeof MarkdownEditor> | null>(null)

const title = ref('')
const status = ref('draft')
const keywords = ref('')
const body = ref('')
const titleTouched = ref(false)
const saveAttempted = ref(false)
const titleError = computed(() =>
  (!title.value.trim() && (titleTouched.value || saveAttempted.value))
    ? 'Title is required.'
    : null,
)

const collectVerificationIssues = (verification: unknown): string[] => {
  if (!verification || typeof verification !== 'object') return []
  const issues = (verification as { issues?: unknown }).issues
  if (!Array.isArray(issues)) return []
  return issues
    .map((issue) => {
      if (!issue || typeof issue !== 'object') return null
      const code = typeof (issue as { code?: unknown }).code === 'string' ? (issue as { code: string }).code : ''
      const message = typeof (issue as { message?: unknown }).message === 'string' ? (issue as { message: string }).message : ''
      if (!code && !message) return null
      return code ? `${code}: ${message}` : message
    })
    .filter((issue): issue is string => Boolean(issue))
}

const load = () => {
  loading.value = true
  error.value = null
  verificationIssues.value = []
  Effect.runPromise(svc.getDocument(documentId.value)).then((doc) => {
    detail.value = doc
    title.value = doc.title
    status.value = doc.status
    keywords.value = (doc.keywords ?? []).join(', ')
    body.value = doc.content_text ?? ''
    loading.value = false
  }).catch((e) => {
    error.value = String(e)
    loading.value = false
  })
}

onMounted(load)
watch(documentId, load)

const save = () => {
  saveAttempted.value = true
  titleTouched.value = true
  verificationIssues.value = []
  if (titleError.value) return
  saving.value = true
  error.value = null
  Effect.runPromise(svc.editDocument(documentId.value, {
    title: title.value,
    status: status.value,
    keywords: keywords.value.split(',').map((value) => value.trim()).filter(Boolean),
    body: body.value,
    dry_run: false,
  })).then((result) => {
    if (!result.wrote) {
      verificationIssues.value = collectVerificationIssues(result.verification)
      error.value = verificationIssues.value.length
        ? 'Document could not be saved until the validation issues are fixed.'
        : 'Document could not be saved.'
      saving.value = false
      return
    }
    saving.value = false
    load()
  }).catch((e) => {
    error.value = String(e)
    saving.value = false
  })
}

const remove = () => {
  if (!window.confirm(`Delete document ${documentId.value}?`)) return
  deleting.value = true
  error.value = null
  Effect.runPromise(svc.deleteDocument(documentId.value, false)).then(() => {
    deleting.value = false
    router.push('/documents')
  }).catch((e) => {
    error.value = String(e)
    deleting.value = false
  })
}

const insertReference = (markdownLink: string) => {
  editorRef.value?.insertAtCursor(markdownLink)
}
</script>

<template>
  <div class="detail-page">
    <div class="page-header">
      <button class="back-link" type="button" @click="router.push('/documents')">← Documents</button>
      <div class="page-actions">
        <button class="secondary-btn" type="button" @click="showReferencePicker = true">Insert Reference</button>
        <button class="primary-btn" type="button" :disabled="saving || loading" @click="save">Save</button>
        <button class="danger-btn" type="button" :disabled="deleting || loading" @click="remove">Delete</button>
      </div>
    </div>

    <div v-if="loading" class="state-msg">Loading…</div>
    <div v-else-if="error && !detail" class="state-msg state-msg--error">{{ error }}</div>

    <div v-else-if="detail" class="card">
      <div class="meta-grid">
        <label class="form-field form-field--wide">
          <span>Title *</span>
          <input
            v-model="title"
            class="form-control"
            :class="{ 'form-control--invalid': titleError }"
            type="text"
            @blur="titleTouched = true"
          />
          <div v-if="titleError" class="field-error">{{ titleError }}</div>
        </label>

        <div class="form-field">
          <span>Type</span>
          <div class="readonly-pill">{{ detail.doc_type }}</div>
        </div>

        <label class="form-field">
          <span>Status</span>
          <select v-model="status" class="form-control">
            <option value="draft">draft</option>
            <option value="accepted">accepted</option>
            <option value="rejected">rejected</option>
            <option value="superseded">superseded</option>
          </select>
        </label>
      </div>

      <label class="form-field">
        <span>Keywords</span>
        <input v-model="keywords" class="form-control" type="text" />
      </label>

      <div class="form-field">
        <span>Body</span>
        <div class="editor-toolbar">
          <button class="secondary-btn" type="button" @click="showReferencePicker = true">Insert Reference</button>
        </div>
        <MarkdownEditor
          ref="editorRef"
          v-model="body"
          min-height="420px"
          placeholder="Document markdown..."
        />
      </div>

      <div class="artifact-meta">
        <code>{{ detail.artifact_id }}</code>
        <code>{{ detail.path }}</code>
      </div>

      <div v-if="error" class="state-msg state-msg--error">{{ error }}</div>
      <ul v-if="verificationIssues.length" class="issue-list">
        <li v-for="issue in verificationIssues" :key="issue">{{ issue }}</li>
      </ul>
    </div>

    <div v-if="showReferencePicker" class="overlay" @click.self="showReferencePicker = false">
      <ArtifactReferenceInput
        :current-path="detail?.path"
        @insert="insertReference"
        @close="showReferencePicker = false"
      />
    </div>
  </div>
</template>

<style scoped>
.detail-page { max-width: 1100px; margin: 0 auto; }
.page-header { display: flex; justify-content: space-between; align-items: center; gap: 16px; margin-bottom: 20px; }
.back-link { border: 0; background: transparent; color: #64748b; cursor: pointer; padding: 0; font-size: 13px; }
.page-actions { display: flex; gap: 10px; flex-wrap: wrap; }
.card { background: white; border: 1px solid #e5e7eb; border-radius: 10px; padding: 20px; }
.meta-grid { display: grid; grid-template-columns: 2fr 1fr 1fr; gap: 14px; }
.form-field { display: flex; flex-direction: column; gap: 6px; margin-bottom: 14px; }
.form-field--wide { grid-column: span 1; }
.form-field span { font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; color: #64748b; font-weight: 700; }
.form-control {
  padding: 9px 11px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  font-size: 13px;
}
.form-control--invalid {
  border-color: #dc2626;
  background: #fef2f2;
}
.field-error {
  color: #dc2626;
  font-size: 12px;
}
.readonly-pill {
  display: inline-flex;
  align-items: center;
  min-height: 39px;
  padding: 0 11px;
  border-radius: 8px;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 13px;
  font-weight: 600;
}
.editor-toolbar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 8px;
}
.artifact-meta {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 14px;
  color: #64748b;
  font-size: 12px;
}
.primary-btn, .secondary-btn, .danger-btn {
  border: 0;
  border-radius: 8px;
  padding: 9px 14px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}
.primary-btn { background: #2563eb; color: white; }
.secondary-btn { background: #e2e8f0; color: #0f172a; }
.danger-btn { background: #fee2e2; color: #991b1b; }
.state-msg { color: #64748b; }
.state-msg--error { color: #dc2626; margin-top: 10px; }
.issue-list {
  margin: 10px 0 0;
  padding-left: 18px;
  color: #991b1b;
  font-size: 13px;
}
.overlay {
  position: fixed;
  inset: 0;
  display: grid;
  place-items: center;
  background: rgba(15, 23, 42, 0.3);
  padding: 16px;
}
@media (max-width: 760px) { .meta-grid { grid-template-columns: 1fr; } }
</style>
