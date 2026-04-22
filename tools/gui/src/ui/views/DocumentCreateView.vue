<script setup lang="ts">
import { computed, inject, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Effect } from 'effect'
import { modelServiceKey } from '../keys'
import MarkdownEditor from '../components/MarkdownEditor.vue'
import ArtifactReferenceInput from '../components/ArtifactReferenceInput.vue'
import { draftDocumentPath } from '../lib/referenceLinks.js'
import type { DocumentType } from '../../domain'

const svc = inject(modelServiceKey)!
const router = useRouter()

const documentTypes = ref<DocumentType[]>([])
const docType = ref('')
const title = ref('')
const status = ref('draft')
const keywords = ref('')
const body = ref('')
const loading = ref(false)
const saving = ref(false)
const error = ref<string | null>(null)
const verificationIssues = ref<string[]>([])
const showReferencePicker = ref(false)
const editorRef = ref<InstanceType<typeof MarkdownEditor> | null>(null)
const lastAutoBody = ref('')
const bodyWasManuallyEdited = ref(false)
const syncingAutoBody = ref(false)
const titleTouched = ref(false)
const submitAttempted = ref(false)

const placeholderBody = (requiredSections: readonly string[]) =>
  requiredSections.map((section) => `## ${section}\n\n`).join('\n')

const selectedType = computed(() =>
  documentTypes.value.find((type) => type.doc_type === docType.value) ?? null,
)
const draftPath = computed(() => draftDocumentPath(docType.value, selectedType.value?.subdirectory))
const titleError = computed(() =>
  (!title.value.trim() && (titleTouched.value || submitAttempted.value))
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

onMounted(() => {
  loading.value = true
  Effect.runPromise(svc.listDocumentTypes()).then((types) => {
    documentTypes.value = types
    if (!docType.value && types.length > 0) docType.value = types[0].doc_type
    loading.value = false
  }).catch((e) => {
    error.value = String(e)
    loading.value = false
  })
})

watch(body, (nextValue) => {
  if (syncingAutoBody.value) return
  bodyWasManuallyEdited.value = nextValue !== lastAutoBody.value
})

watch(selectedType, (type) => {
  if (!type) return
  const nextPlaceholder = placeholderBody(type.required_sections)
  if (!bodyWasManuallyEdited.value || body.value === lastAutoBody.value || !body.value.trim()) {
    syncingAutoBody.value = true
    body.value = nextPlaceholder
    lastAutoBody.value = nextPlaceholder
    bodyWasManuallyEdited.value = false
    syncingAutoBody.value = false
  }
})

const submit = () => {
  submitAttempted.value = true
  titleTouched.value = true
  verificationIssues.value = []
  if (titleError.value) return
  error.value = null
  saving.value = true
  Effect.runPromise(svc.createDocument({
    doc_type: docType.value,
    title: title.value,
    body: body.value,
    keywords: keywords.value.split(',').map((value) => value.trim()).filter(Boolean),
    status: status.value,
    dry_run: false,
  })).then((result) => {
    if (!result.wrote) {
      verificationIssues.value = collectVerificationIssues(result.verification)
      error.value = verificationIssues.value.length
        ? 'Document could not be created until the validation issues are fixed.'
        : 'Document could not be created.'
      saving.value = false
      return
    }
    saving.value = false
    router.push(`/documents/${result.artifact_id}`)
  }).catch((e) => {
    error.value = String(e)
    saving.value = false
  })
}

const insertReference = (markdownLink: string) => {
  editorRef.value?.insertAtCursor(markdownLink)
}
</script>

<template>
  <div class="create-page">
    <div class="page-header">
      <button class="back-link" type="button" @click="router.push('/documents')">← Documents</button>
      <h1 class="page-title">New Document</h1>
    </div>

    <div v-if="loading" class="state-msg">Loading…</div>
    <div v-else class="card">
      <div class="form-grid">
        <label class="form-field">
          <span>Document Type</span>
          <select v-model="docType" class="form-control">
            <option v-for="type in documentTypes" :key="type.doc_type" :value="type.doc_type">{{ type.name }}</option>
          </select>
        </label>

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
        <span>Title *</span>
        <input
          v-model="title"
          class="form-control"
          :class="{ 'form-control--invalid': titleError }"
          type="text"
          placeholder="Use concise, decision-oriented wording"
          @blur="titleTouched = true"
        />
        <div v-if="titleError" class="field-error">{{ titleError }}</div>
      </label>

      <label class="form-field">
        <span>Keywords</span>
        <input v-model="keywords" class="form-control" type="text" placeholder="Comma-separated terms" />
      </label>

      <div class="form-field">
        <span>Body</span>
        <div class="editor-toolbar">
          <button class="secondary-btn" type="button" @click="showReferencePicker = true">Insert Reference</button>
        </div>
        <MarkdownEditor
          ref="editorRef"
          v-model="body"
          min-height="360px"
          placeholder="Write markdown content..."
        />
      </div>

      <div v-if="error" class="state-msg state-msg--error">{{ error }}</div>
      <ul v-if="verificationIssues.length" class="issue-list">
        <li v-for="issue in verificationIssues" :key="issue">{{ issue }}</li>
      </ul>

      <div class="actions">
        <button class="submit-btn" type="button" :disabled="saving || !docType" @click="submit">Create Document</button>
      </div>
    </div>

    <div v-if="showReferencePicker" class="overlay" @click.self="showReferencePicker = false">
      <ArtifactReferenceInput
        :current-path="draftPath"
        @insert="insertReference"
        @close="showReferencePicker = false"
      />
    </div>
  </div>
</template>

<style scoped>
.create-page { max-width: 980px; margin: 0 auto; }
.page-header { display: flex; gap: 16px; align-items: center; margin-bottom: 20px; }
.back-link { border: 0; background: transparent; color: #64748b; cursor: pointer; padding: 0; font-size: 13px; }
.page-title { font-size: 22px; font-weight: 600; }
.card { background: white; border: 1px solid #e5e7eb; border-radius: 10px; padding: 20px; }
.form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
.form-field { display: flex; flex-direction: column; gap: 6px; margin-bottom: 14px; }
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
.editor-toolbar { display: flex; justify-content: flex-end; margin-bottom: 8px; }
.secondary-btn {
  border: 0;
  background: #e2e8f0;
  color: #0f172a;
  border-radius: 8px;
  padding: 8px 12px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}
.actions { display: flex; justify-content: flex-end; }
.submit-btn {
  border: 0;
  background: #2563eb;
  color: white;
  border-radius: 8px;
  padding: 10px 16px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}
.state-msg { color: #64748b; margin-bottom: 12px; }
.state-msg--error { color: #dc2626; }
.issue-list {
  margin: 0 0 12px;
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
@media (max-width: 700px) { .form-grid { grid-template-columns: 1fr; } }
</style>
