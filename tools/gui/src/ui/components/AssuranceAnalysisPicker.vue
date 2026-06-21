<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import {
  ANALYSIS_METHODS,
  buildAnalysisOptions,
  emptyNewAnalysisForm,
  newAnalysisBody,
  validateNewAnalysis,
  type AnalysisMethod,
  type AnalysisSummary,
} from './AssuranceAnalysisPicker.helpers'

const props = withDefaults(
  defineProps<{ modelValue: string | null; defaultMethod?: AnalysisMethod }>(),
  { defaultMethod: 'STPA' },
)
const emit = defineEmits<{
  'update:modelValue': [value: string | null]
  created: [analysisId: string]
}>()

const analyses = ref<AnalysisSummary[]>([])
const loading = ref(false)
const error = ref<string | null>(null)

const creating = ref(false)
const form = ref(emptyNewAnalysisForm())
const formError = ref<string | null>(null)
const submitting = ref(false)

const options = computed(() => buildAnalysisOptions(analyses.value))

async function load() {
  loading.value = true
  error.value = null
  try {
    const resp = await fetch('/api/assurance/analyses')
    if (resp.status === 423) { error.value = 'locked'; return }
    if (!resp.ok) { error.value = `HTTP ${resp.status}`; return }
    const body = await resp.json() as { analyses: AnalysisSummary[] }
    analyses.value = body.analyses
  } catch (e) {
    error.value = String(e)
  } finally {
    loading.value = false
  }
}

function onSelect(event: Event) {
  const value = (event.target as HTMLSelectElement).value
  emit('update:modelValue', value || null)
}

function openCreate() {
  creating.value = true
  form.value = emptyNewAnalysisForm(props.defaultMethod)
  formError.value = null
}

function cancelCreate() {
  creating.value = false
  formError.value = null
}

async function submitCreate() {
  const validation = validateNewAnalysis(form.value)
  if (validation) { formError.value = validation; return }
  submitting.value = true
  formError.value = null
  try {
    const resp = await fetch('/api/assurance/analyses', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(newAnalysisBody(form.value)),
    })
    const body = await resp.json().catch(() => ({})) as Record<string, unknown>
    if (!resp.ok) {
      formError.value = typeof body['message'] === 'string'
        ? body['message']
        : `HTTP ${resp.status}`
      return
    }
    await load()
    creating.value = false
    const newId = typeof body['analysis_id'] === 'string' ? body['analysis_id'] : null
    if (newId) {
      emit('update:modelValue', newId)
      emit('created', newId)
    }
  } catch (e) {
    formError.value = String(e)
  } finally {
    submitting.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="analysis-picker">
    <label class="ap-label">Analysis</label>
    <select
      class="ap-select"
      :value="props.modelValue ?? ''"
      :disabled="loading"
      aria-label="Scope to an analysis"
      @change="onSelect"
    >
      <option value="">
        All analyses
      </option>
      <option
        v-for="opt in options"
        :key="opt.value"
        :value="opt.value"
      >
        {{ opt.label }}
      </option>
    </select>
    <button
      v-if="!creating"
      class="ap-new-btn"
      type="button"
      @click="openCreate"
    >
      + New analysis
    </button>

    <form
      v-if="creating"
      class="ap-form"
      @submit.prevent="submitCreate"
    >
      <input
        v-model="form.name"
        class="ap-input"
        placeholder="Analysis name"
        aria-label="Analysis name"
      >
      <select
        v-model="form.method"
        class="ap-input"
        aria-label="Method"
      >
        <option
          v-for="m in ANALYSIS_METHODS"
          :key="m"
          :value="m"
        >
          {{ m }}
        </option>
      </select>
      <input
        v-model="form.architecture_anchor_id"
        class="ap-input"
        placeholder="Architecture anchor id (optional)"
        aria-label="Architecture anchor id"
      >
      <div class="ap-form-actions">
        <button
          class="ap-submit"
          type="submit"
          :disabled="submitting"
        >
          {{ submitting ? 'Creating…' : 'Create' }}
        </button>
        <button
          class="ap-cancel"
          type="button"
          @click="cancelCreate"
        >
          Cancel
        </button>
      </div>
      <p
        v-if="formError"
        class="ap-error"
      >
        {{ formError }}
      </p>
    </form>
  </div>
</template>

<style scoped>
.analysis-picker { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }
.ap-label { font-size: 12px; font-weight: 600; color: #475569; }
.ap-select {
  font-size: 13px;
  padding: 5px 10px;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  background: #fff;
  color: #1e293b;
  min-width: 200px;
}
.ap-new-btn {
  font-size: 12px;
  padding: 5px 10px;
  border: 1px dashed #93c5fd;
  border-radius: 6px;
  background: #eff6ff;
  color: #1d4ed8;
  cursor: pointer;
}
.ap-new-btn:hover { background: #dbeafe; }
.ap-form {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  width: 100%;
  margin-top: 6px;
  padding: 8px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
}
.ap-input {
  font-size: 12px;
  padding: 5px 8px;
  border: 1px solid #cbd5e1;
  border-radius: 5px;
}
.ap-form-actions { display: flex; gap: 6px; }
.ap-submit {
  font-size: 12px;
  padding: 5px 12px;
  border: none;
  border-radius: 5px;
  background: #2563eb;
  color: #fff;
  font-weight: 600;
  cursor: pointer;
}
.ap-submit:disabled { opacity: 0.5; cursor: default; }
.ap-cancel {
  font-size: 12px;
  padding: 5px 12px;
  border: 1px solid #d1d5db;
  border-radius: 5px;
  background: #fff;
  color: #374151;
  cursor: pointer;
}
.ap-error { font-size: 12px; color: #b91c1c; width: 100%; margin: 4px 0 0; }
</style>
