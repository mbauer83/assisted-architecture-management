<script setup lang="ts">
import { inject, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Effect } from 'effect'
import { modelServiceKey } from '../keys'
import type { WriteResult } from '../../domain'

const svc = inject(modelServiceKey)!
const router = useRouter()

// ── Write-help data ───────────────────────────────────────────────────────────

type WriteHelp = { entity_types_by_domain: Record<string, string[]> }
const writeHelp = ref<WriteHelp | null>(null)

onMounted(() => {
  Effect.runPromise(svc.getWriteHelp()).then((h) => {
    writeHelp.value = h as WriteHelp
  }).catch(() => {})
})

// ── Form state ────────────────────────────────────────────────────────────────

const artifactType = ref('')
const name = ref('')
const summary = ref('')
const keywords = ref('')
const status = ref('draft')
const version = ref('0.1.0')
const properties = ref<{ key: string; value: string }[]>([])
const notes = ref('')

const busy = ref(false)
const formError = ref<string | null>(null)
const preview = ref<WriteResult | null>(null)
const previewClean = ref(false)

// ── Property rows ─────────────────────────────────────────────────────────────

const addPropRow = () => properties.value.push({ key: '', value: '' })
const removePropRow = (i: number) => properties.value.splice(i, 1)

// ── Build body ────────────────────────────────────────────────────────────────

const buildBody = (dryRun: boolean) => {
  const props: Record<string, string> = {}
  for (const row of properties.value) {
    if (row.key.trim()) props[row.key.trim()] = row.value
  }
  const kws = keywords.value.split(',').map(k => k.trim()).filter(Boolean)
  return {
    artifact_type: artifactType.value,
    name: name.value,
    summary: summary.value || undefined,
    keywords: kws.length ? kws : undefined,
    status: status.value,
    version: version.value,
    properties: Object.keys(props).length ? props : undefined,
    notes: notes.value || undefined,
    dry_run: dryRun,
  }
}

// ── Preview ───────────────────────────────────────────────────────────────────

const doPreview = () => {
  if (!artifactType.value || !name.value.trim()) {
    formError.value = 'Artifact type and name are required.'
    return
  }
  busy.value = true
  formError.value = null
  preview.value = null
  previewClean.value = false
  Effect.runPromise(svc.createEntity(buildBody(true))).then((r) => {
    busy.value = false
    preview.value = r
    previewClean.value = !r.verification || (
      Array.isArray((r.verification as { errors?: unknown[] })?.errors)
        ? (r.verification as { errors: unknown[] }).errors.length === 0
        : true
    )
  }).catch((e) => {
    busy.value = false
    formError.value = String(e)
  })
}

// ── Create ────────────────────────────────────────────────────────────────────

const doCreate = () => {
  busy.value = true
  formError.value = null
  Effect.runPromise(svc.createEntity(buildBody(false))).then((r) => {
    busy.value = false
    if (r.wrote) {
      router.push({ path: '/entity', query: { id: r.artifact_id } })
    } else {
      formError.value = r.content ?? 'Verification failed'
    }
  }).catch((e) => {
    busy.value = false
    formError.value = String(e)
  })
}
</script>

<template>
  <div class="create-layout">
    <div class="page-header">
      <button class="back-link" @click="router.back()">← Back</button>
      <h1 class="page-title">Create Entity</h1>
    </div>

    <div class="form-and-preview">
      <!-- Form -->
      <section class="form-section card">
        <div class="form-row">
          <label class="form-label">Artifact Type <span class="required">*</span></label>
          <select v-model="artifactType" class="form-select">
            <option value="" disabled>Select type...</option>
            <template v-if="writeHelp">
              <optgroup
                v-for="(types, domain) in writeHelp.entity_types_by_domain"
                :key="domain"
                :label="domain"
              >
                <option v-for="t in types" :key="t" :value="t">{{ t }}</option>
              </optgroup>
            </template>
          </select>
        </div>

        <div class="form-row">
          <label class="form-label">Name <span class="required">*</span></label>
          <input v-model="name" class="form-input" placeholder="Human-readable name" />
        </div>

        <div class="form-row">
          <label class="form-label">Summary</label>
          <textarea v-model="summary" class="form-textarea" rows="3" placeholder="Short description..." />
        </div>

        <div class="form-row">
          <label class="form-label">Keywords <span class="form-hint">(comma-separated)</span></label>
          <input v-model="keywords" class="form-input" placeholder="e.g. model, tooling, automation" />
        </div>

        <div class="form-row two-col">
          <div>
            <label class="form-label">Status</label>
            <select v-model="status" class="form-select">
              <option value="draft">draft</option>
              <option value="active">active</option>
              <option value="deprecated">deprecated</option>
            </select>
          </div>
          <div>
            <label class="form-label">Version</label>
            <input v-model="version" class="form-input" placeholder="0.1.0" />
          </div>
        </div>

        <div class="form-row">
          <label class="form-label">Properties</label>
          <div v-for="(row, i) in properties" :key="i" class="prop-row">
            <input v-model="row.key" class="prop-key" placeholder="key" />
            <input v-model="row.value" class="prop-value" placeholder="value" />
            <button class="remove-prop-btn icon-btn" @click="removePropRow(i)">×</button>
          </div>
          <button class="add-prop-btn" @click="addPropRow">+ Add property</button>
        </div>

        <div class="form-row">
          <label class="form-label">Notes</label>
          <textarea v-model="notes" class="form-textarea" rows="3" placeholder="Additional notes..." />
        </div>

        <div v-if="formError" class="state-msg state-msg--error">{{ formError }}</div>

        <div class="form-actions">
          <button class="preview-btn" :disabled="busy" @click="doPreview">Preview</button>
          <button
            class="create-btn"
            :disabled="busy || !previewClean"
            :title="!previewClean ? 'Run preview first to enable create' : ''"
            @click="doCreate"
          >Create</button>
        </div>
      </section>

      <!-- Preview pane -->
      <section v-if="preview" class="preview-section card">
        <h2 class="preview-title">Dry-run preview</h2>
        <div class="preview-meta">
          <span class="mono">{{ preview.artifact_id }}</span>
          <span class="preview-path mono">→ {{ preview.path }}</span>
        </div>

        <div v-if="preview.warnings.length" class="preview-warnings">
          <div v-for="w in preview.warnings" :key="w" class="preview-warn">{{ w }}</div>
        </div>

        <div v-if="!previewClean" class="state-msg state-msg--error">
          Verification issues found — fix them before creating.
        </div>
        <div v-else class="state-msg state-msg--ok">Verification passed.</div>

        <pre v-if="preview.content" class="preview-content">{{ preview.content }}</pre>
      </section>
    </div>
  </div>
</template>

<style scoped>
.create-layout { max-width: 960px; }

.page-header { display: flex; align-items: center; gap: 16px; margin-bottom: 24px; }
.back-link { font-size: 13px; color: #6b7280; background: none; border: none; cursor: pointer; padding: 0; }
.back-link:hover { color: #374151; }
.page-title { font-size: 20px; font-weight: 600; }

.form-and-preview { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; align-items: start; }
@media (max-width: 800px) { .form-and-preview { grid-template-columns: 1fr; } }

.card { background: white; border-radius: 8px; border: 1px solid #e5e7eb; padding: 20px; }

.form-row { margin-bottom: 14px; }
.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.form-label {
  display: block; font-size: 12px; font-weight: 600; color: #374151;
  margin-bottom: 4px; text-transform: uppercase; letter-spacing: .04em;
}
.required { color: #dc2626; }
.form-hint { font-weight: 400; text-transform: none; color: #9ca3af; }
.form-input {
  width: 100%; padding: 7px 10px; border-radius: 6px; border: 1px solid #d1d5db;
  font-size: 13px; outline: none; box-sizing: border-box;
}
.form-input:focus { border-color: #2563eb; }
.form-textarea {
  width: 100%; padding: 7px 10px; border-radius: 6px; border: 1px solid #d1d5db;
  font-size: 13px; outline: none; resize: vertical; box-sizing: border-box; font-family: inherit;
}
.form-textarea:focus { border-color: #2563eb; }
.form-select {
  width: 100%; padding: 7px 10px; border-radius: 6px; border: 1px solid #d1d5db;
  font-size: 13px; outline: none; background: white; box-sizing: border-box;
}
.form-select:focus { border-color: #2563eb; }

.prop-row { display: flex; gap: 6px; margin-bottom: 6px; align-items: center; }
.prop-key { flex: 1; padding: 6px 8px; border-radius: 6px; border: 1px solid #d1d5db; font-size: 12px; outline: none; }
.prop-value { flex: 2; padding: 6px 8px; border-radius: 6px; border: 1px solid #d1d5db; font-size: 12px; outline: none; }
.icon-btn {
  width: 22px; height: 22px; border-radius: 4px; border: 1px solid #d1d5db;
  background: white; cursor: pointer; font-size: 14px; line-height: 1;
  display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.remove-prop-btn { border-color: #fecaca; color: #dc2626; }
.remove-prop-btn:hover { background: #fef2f2; }
.add-prop-btn {
  font-size: 12px; color: #2563eb; background: none; border: none; cursor: pointer; padding: 4px 0;
}
.add-prop-btn:hover { text-decoration: underline; }

.state-msg { font-size: 13px; color: #6b7280; padding: 4px 0; }
.state-msg--error { color: #dc2626; }
.state-msg--ok { color: #16a34a; }

.form-actions { display: flex; gap: 8px; justify-content: flex-end; padding-top: 4px; }
.preview-btn {
  padding: 7px 16px; background: #f3f4f6; color: #1d4ed8; border: 1px solid #bfdbfe;
  border-radius: 6px; font-size: 13px; cursor: pointer; font-weight: 500;
}
.preview-btn:hover:not(:disabled) { background: #eff6ff; }
.create-btn {
  padding: 7px 16px; background: #16a34a; color: white; border: none;
  border-radius: 6px; font-size: 13px; font-weight: 500; cursor: pointer;
}
.create-btn:hover:not(:disabled) { background: #15803d; }
.preview-btn:disabled, .create-btn:disabled { opacity: 0.5; cursor: not-allowed; }

/* Preview pane */
.preview-section { }
.preview-title {
  font-size: 13px; font-weight: 600; text-transform: uppercase; letter-spacing: .05em;
  color: #374151; margin-bottom: 12px;
}
.preview-meta { font-size: 12px; color: #6b7280; margin-bottom: 8px; display: flex; flex-direction: column; gap: 2px; }
.preview-path { color: #9ca3af; }
.mono { font-family: monospace; }
.preview-warnings { margin-bottom: 8px; }
.preview-warn { font-size: 12px; color: #b45309; }
.preview-content {
  font-size: 11px; color: #374151; white-space: pre-wrap; max-height: 400px; overflow-y: auto;
  font-family: monospace; margin-top: 12px; background: #f9fafb; border-radius: 6px; padding: 10px;
}
</style>
