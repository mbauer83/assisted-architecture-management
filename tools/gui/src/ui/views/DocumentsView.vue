<script setup lang="ts">
import { computed, inject, onMounted, ref } from 'vue'
import { Effect } from 'effect'
import { RouterLink, useRouter } from 'vue-router'
import { modelServiceKey } from '../keys'
import type { DocumentList, DocumentType } from '../../domain'

const svc = inject(modelServiceKey)!
const router = useRouter()

const documentTypes = ref<DocumentType[]>([])
const documentList = ref<DocumentList | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const docTypeFilter = ref('')
const titleFilter = ref('')

const load = () => {
  loading.value = true
  error.value = null
  Promise.all([
    Effect.runPromise(svc.listDocumentTypes()),
    Effect.runPromise(svc.listDocuments(docTypeFilter.value ? { doc_type: docTypeFilter.value } : {})),
  ]).then(([types, docs]) => {
    documentTypes.value = types
    documentList.value = docs
    loading.value = false
  }).catch((e) => {
    error.value = String(e)
    loading.value = false
  })
}

onMounted(load)

const filteredItems = computed(() => {
  const lc = titleFilter.value.trim().toLowerCase()
  const items = documentList.value?.items ?? []
  if (!lc) return items
  return items.filter((item) => item.title.toLowerCase().includes(lc))
})
</script>

<template>
  <div class="documents-page">
    <div class="page-header">
      <div>
        <h1 class="page-title">
          Documents
        </h1>
      </div>
      <button
        class="create-btn"
        type="button"
        @click="router.push('/documents/new')"
      >
        + New Document
      </button>
    </div>

    <div class="toolbar card">
      <label class="toolbar-field">
        <span>Type</span>
        <select
          v-model="docTypeFilter"
          class="toolbar-select"
          @change="load"
        >
          <option value="">All</option>
          <option
            v-for="type in documentTypes"
            :key="type.doc_type"
            :value="type.doc_type"
          >{{ type.name }}</option>
        </select>
      </label>
      <label class="toolbar-field toolbar-field--grow">
        <span>Title</span>
        <input
          v-model="titleFilter"
          class="toolbar-input"
          type="text"
          placeholder="Filter by title..."
        >
      </label>
    </div>

    <div
      v-if="loading"
      class="state-msg"
    >
      Loading…
    </div>
    <div
      v-else-if="error"
      class="state-msg state-msg--error"
    >
      {{ error }}
    </div>

    <div
      v-else
      class="card table-card"
    >
      <div class="result-count">
        {{ filteredItems.length }} document{{ filteredItems.length === 1 ? '' : 's' }}
      </div>
      <table class="documents-table">
        <thead>
          <tr>
            <th>Title</th>
            <th>Type</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="doc in filteredItems"
            :key="doc.artifact_id"
          >
            <td>
              <RouterLink :to="`/documents/${doc.artifact_id}`">
                {{ doc.title }}
              </RouterLink>
            </td>
            <td><span class="doc-type">{{ doc.doc_type }}</span></td>
            <td>
              <span
                class="status-badge"
                :class="`status--${doc.status}`"
              >{{ doc.status }}</span>
            </td>
          </tr>
          <tr v-if="!filteredItems.length">
            <td
              colspan="3"
              class="empty-row"
            >
              No documents found.
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.documents-page { max-width: 1100px; margin: 0 auto; }
.page-header { display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; margin-bottom: 20px; }
.page-title { font-size: 22px; font-weight: 600; margin-bottom: 4px; }
.page-subtitle { color: #64748b; font-size: 13px; max-width: 720px; }
.card { background: white; border: 1px solid #e5e7eb; border-radius: 10px; }
.toolbar { display: flex; gap: 12px; padding: 16px; margin-bottom: 16px; flex-wrap: wrap; }
.toolbar-field { display: flex; flex-direction: column; gap: 6px; min-width: 180px; }
.toolbar-field--grow { flex: 1; }
.toolbar-field span { font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; color: #64748b; font-weight: 700; }
.toolbar-select, .toolbar-input {
  padding: 8px 10px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  font-size: 13px;
}
.create-btn {
  border: 0;
  border-radius: 8px;
  background: #2563eb;
  color: white;
  padding: 9px 14px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}
.table-card { padding: 16px; }
.result-count { color: #64748b; font-size: 13px; margin-bottom: 12px; }
.documents-table { width: 100%; border-collapse: collapse; }
.documents-table th {
  text-align: left;
  font-size: 11px;
  text-transform: uppercase;
  color: #64748b;
  letter-spacing: 0.05em;
  padding-bottom: 10px;
}
.documents-table td {
  padding: 12px 0;
  border-top: 1px solid #eef2f7;
}
.doc-type {
  display: inline-flex;
  padding: 3px 8px;
  border-radius: 999px;
  background: #e0f2fe;
  color: #075985;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
}
.status-badge { padding: 3px 8px; border-radius: 999px; font-size: 11px; font-weight: 600; }
.status--draft { background: #f1f5f9; color: #475569; }
.status--accepted { background: #dcfce7; color: #166534; }
.status--rejected { background: #fee2e2; color: #991b1b; }
.status--superseded { background: #fef3c7; color: #92400e; }
.empty-row, .state-msg { color: #64748b; }
.state-msg--error { color: #dc2626; }
</style>
