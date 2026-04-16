<script setup lang="ts">
import { inject, ref, computed, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { Effect } from 'effect'
import { modelServiceKey } from '../keys'
import type { EntityDisplayInfo, ConnectionRecord, DiagramPreviewResult } from '../../domain'
import ArchimateTypeGlyph from '../components/ArchimateTypeGlyph.vue'

const toGlyphKey = (t: string) => t.replace(/[A-Z]/g, (c, i) => (i > 0 ? '-' : '') + c.toLowerCase())

const svc = inject(modelServiceKey)!
const router = useRouter()

// ── Form ──────────────────────────────────────────────────────────────────────

const name = ref('')
const diagramType = ref('archimate-business')

const DIAGRAM_TYPES = [
  { key: 'archimate-motivation', label: 'Motivation' },
  { key: 'archimate-strategy', label: 'Strategy' },
  { key: 'archimate-business', label: 'Business' },
  { key: 'archimate-application', label: 'Application' },
  { key: 'archimate-technology', label: 'Technology' },
  { key: 'archimate-layered', label: 'Layered' },
]

// ── Entity search ─────────────────────────────────────────────────────────────

const searchQuery = ref('')
const searchResults = ref<EntityDisplayInfo[]>([])
const showDropdown = ref(false)
let searchTimer: ReturnType<typeof setTimeout> | null = null

const includedEntities = ref<EntityDisplayInfo[]>([])
const includedEntityIds = computed(() => new Set(includedEntities.value.map((e) => e.artifact_id)))

const onSearchInput = () => {
  if (searchTimer) clearTimeout(searchTimer)
  const q = searchQuery.value.trim()
  if (!q) { searchResults.value = []; showDropdown.value = false; return }
  searchTimer = setTimeout(() => {
    Effect.runPromise(svc.searchEntityDisplay(q, 20)).then((res) => {
      searchResults.value = res.filter((r) => !includedEntityIds.value.has(r.artifact_id))
      showDropdown.value = searchResults.value.length > 0
    }).catch(() => {})
  }, 280)
}

const closeDropdown = () => { setTimeout(() => { showDropdown.value = false }, 150) }

// ── Connection management ─────────────────────────────────────────────────────

// All model connections fetched for included entities, keyed by artifact_id
const allModelConns = ref<Map<string, ConnectionRecord>>(new Map())
// artifact_ids of connections selected for diagram inclusion
const includedConnIds = ref<Set<string>>(new Set())

const includedConns = computed(() =>
  [...allModelConns.value.values()].filter(
    (c) =>
      includedConnIds.value.has(c.artifact_id) &&
      includedEntityIds.value.has(c.source) &&
      includedEntityIds.value.has(c.target),
  ),
)

const availableConns = computed(() =>
  [...allModelConns.value.values()].filter(
    (c) =>
      !includedConnIds.value.has(c.artifact_id) &&
      includedEntityIds.value.has(c.source) &&
      includedEntityIds.value.has(c.target),
  ),
)

const nameOf = (id: string) =>
  includedEntities.value.find((e) => e.artifact_id === id)?.name ?? id

const addEntity = async (entity: EntityDisplayInfo) => {
  if (includedEntityIds.value.has(entity.artifact_id)) return
  includedEntities.value.push(entity)
  showDropdown.value = false
  searchQuery.value = ''
  const conns = await Effect.runPromise(svc.getConnections(entity.artifact_id, 'any')).catch(() => [])
  for (const conn of conns) {
    allModelConns.value.set(conn.artifact_id, conn)
    const otherId = conn.source === entity.artifact_id ? conn.target : conn.source
    if (includedEntityIds.value.has(otherId)) {
      includedConnIds.value.add(conn.artifact_id)
    }
  }
}

const removeEntity = (artifactId: string) => {
  includedEntities.value = includedEntities.value.filter((e) => e.artifact_id !== artifactId)
  for (const id of [...includedConnIds.value]) {
    const c = allModelConns.value.get(id)
    if (c && (c.source === artifactId || c.target === artifactId)) {
      includedConnIds.value.delete(id)
    }
  }
}

const removeConn = (id: string) => includedConnIds.value.delete(id)
const addConn = (id: string) => includedConnIds.value.add(id)

// ── Preview ───────────────────────────────────────────────────────────────────

const preview = ref<DiagramPreviewResult | null>(null)
const previewBusy = ref(false)
const previewError = ref<string | null>(null)
const showPuml = ref(false)

const doPreview = () => {
  previewBusy.value = true
  previewError.value = null
  Effect.runPromise(
    svc.previewDiagram({
      diagram_type: diagramType.value,
      name: name.value,
      entity_ids: includedEntities.value.map((e) => e.artifact_id),
      connection_ids: includedConns.value.map((c) => c.artifact_id),
    }),
  )
    .then((r) => { preview.value = r; previewBusy.value = false })
    .catch((e) => { previewError.value = String(e); previewBusy.value = false })
}

// ── Create ────────────────────────────────────────────────────────────────────

const createBusy = ref(false)
const createError = ref<string | null>(null)

const doCreate = () => {
  createBusy.value = true
  createError.value = null
  Effect.runPromise(
    svc.createDiagram({
      diagram_type: diagramType.value,
      name: name.value,
      entity_ids: includedEntities.value.map((e) => e.artifact_id),
      connection_ids: includedConns.value.map((c) => c.artifact_id),
      dry_run: false,
    }),
  )
    .then((r) => {
      createBusy.value = false
      if (r.wrote) router.push({ path: '/diagram', query: { id: r.artifact_id } })
      else createError.value = r.content ?? 'Verification failed — check warnings'
    })
    .catch((e) => { createBusy.value = false; createError.value = String(e) })
}

onUnmounted(() => { if (searchTimer) clearTimeout(searchTimer) })
</script>

<template>
  <div class="layout">
    <div class="page-header">
      <button class="back-link" @click="router.back()">← Back</button>
      <h1 class="page-title">Create Diagram</h1>
    </div>

    <div class="columns">
      <!-- ── Left: form ─────────────────────────────────────────────────── -->
      <section class="card form-col">
        <div class="form-row">
          <label class="lbl">Name <span class="req">*</span></label>
          <input v-model="name" class="inp" placeholder="Diagram name" />
        </div>

        <div class="form-row">
          <label class="lbl">Diagram Type</label>
          <select v-model="diagramType" class="inp">
            <option v-for="dt in DIAGRAM_TYPES" :key="dt.key" :value="dt.key">{{ dt.label }}</option>
          </select>
        </div>

        <!-- Entity search -->
        <div class="form-row">
          <label class="lbl">Add Entities</label>
          <div class="search-wrap">
            <input
              v-model="searchQuery"
              class="inp"
              placeholder="Search by name, type, domain…"
              @input="onSearchInput"
              @blur="closeDropdown"
              @focus="() => { if (searchResults.length) showDropdown = true }"
            />
            <div v-if="showDropdown" class="dropdown">
              <button
                v-for="r in searchResults"
                :key="r.artifact_id"
                class="dd-item"
                @mousedown.prevent="addEntity(r)"
              >
                <span class="dd-glyph" :title="r.element_type || r.artifact_type"><ArchimateTypeGlyph :type="toGlyphKey(r.element_type || r.artifact_type)" :size="16" /></span>
                <span class="dd-name">{{ r.name }}</span>
                <span class="dd-domain">{{ r.domain }}</span>
              </button>
            </div>
          </div>
        </div>

        <!-- Included entities -->
        <div v-if="includedEntities.length" class="form-row">
          <label class="lbl">Entities ({{ includedEntities.length }})</label>
          <div class="chips">
            <div v-for="e in includedEntities" :key="e.artifact_id" class="chip">
              <span class="dd-glyph" :title="e.element_type || e.artifact_type"><ArchimateTypeGlyph :type="toGlyphKey(e.element_type || e.artifact_type)" :size="16" /></span>
              <span class="chip-name">{{ e.name }}</span>
              <button class="chip-rm" @click="removeEntity(e.artifact_id)" title="Remove">×</button>
            </div>
          </div>
        </div>

        <!-- Connections panel -->
        <div v-if="includedEntities.length >= 2" class="form-row">
          <label class="lbl">Connections</label>
          <div v-if="!includedConns.length && !availableConns.length" class="empty-msg">
            No model connections found between included entities.
          </div>

          <!-- Included -->
          <div v-for="c in includedConns" :key="c.artifact_id" class="conn-row conn-row--in">
            <span class="conn-label">
              {{ nameOf(c.source) }}
              <em> {{ c.conn_type }} </em>
              {{ nameOf(c.target) }}
            </span>
            <button class="conn-btn conn-rm" @click="removeConn(c.artifact_id)" title="Remove from diagram">−</button>
          </div>

          <!-- Available (not yet included) -->
          <div v-if="availableConns.length" class="avail-header">Available from model:</div>
          <div v-for="c in availableConns" :key="c.artifact_id" class="conn-row conn-row--avail">
            <span class="conn-label">
              {{ nameOf(c.source) }}
              <em> {{ c.conn_type }} </em>
              {{ nameOf(c.target) }}
            </span>
            <button class="conn-btn conn-add" @click="addConn(c.artifact_id)" title="Add to diagram">+</button>
          </div>
        </div>

        <div v-if="createError" class="state-err">{{ createError }}</div>

        <div class="actions">
          <button
            class="btn-preview"
            :disabled="previewBusy || !name.trim() || !includedEntities.length"
            @click="doPreview"
          >{{ previewBusy ? 'Rendering…' : 'Preview' }}</button>
          <button
            class="btn-create"
            :disabled="createBusy || !preview"
            :title="!preview ? 'Run Preview first' : ''"
            @click="doCreate"
          >{{ createBusy ? 'Creating…' : 'Create Diagram' }}</button>
        </div>
      </section>

      <!-- ── Right: preview ────────────────────────────────────────────── -->
      <section class="card preview-col">
        <div v-if="!preview && !previewBusy && !previewError" class="preview-hint">
          Select entities and connections, then click <strong>Preview</strong>.
        </div>
        <div v-if="previewBusy" class="state-msg">Rendering…</div>
        <div v-if="previewError" class="state-err">{{ previewError }}</div>

        <template v-if="preview">
          <div v-for="w in preview.warnings" :key="w" class="warn">{{ w }}</div>
          <img v-if="preview.image" :src="preview.image" class="preview-img" alt="Diagram preview" />
          <div v-else class="state-msg">No image could be rendered.</div>
          <button class="toggle-src" @click="showPuml = !showPuml">
            {{ showPuml ? 'Hide' : 'Show' }} PUML source
          </button>
          <pre v-if="showPuml" class="puml-src">{{ preview.puml }}</pre>
        </template>
      </section>
    </div>
  </div>
</template>

<style scoped>
.layout { max-width: 1200px; margin: 0 auto; }
.page-header { display: flex; align-items: center; gap: 16px; margin-bottom: 24px; }
.back-link { font-size: 13px; color: #6b7280; background: none; border: none; cursor: pointer; padding: 0; }
.back-link:hover { color: #374151; }
.page-title { font-size: 20px; font-weight: 600; margin: 0; }

.columns { display: grid; grid-template-columns: 420px 1fr; gap: 20px; align-items: start; }
@media (max-width: 860px) { .columns { grid-template-columns: 1fr; } }

.card { background: white; border-radius: 8px; border: 1px solid #e5e7eb; padding: 20px; }
.form-row { margin-bottom: 14px; }
.lbl { display: block; font-size: 11px; font-weight: 700; color: #374151; margin-bottom: 4px; text-transform: uppercase; letter-spacing: .05em; }
.req { color: #dc2626; }
.inp { width: 100%; padding: 7px 10px; border-radius: 6px; border: 1px solid #d1d5db; font-size: 13px; outline: none; box-sizing: border-box; background: white; }
.inp:focus { border-color: #2563eb; }

.search-wrap { position: relative; }
.dropdown { position: absolute; top: calc(100% + 3px); left: 0; right: 0; background: white; border: 1px solid #d1d5db; border-radius: 6px; box-shadow: 0 4px 12px rgba(0,0,0,.1); z-index: 100; max-height: 260px; overflow-y: auto; }
.dd-item { display: flex; align-items: center; gap: 6px; width: 100%; text-align: left; padding: 8px 10px; background: none; border: none; border-bottom: 1px solid #f3f4f6; cursor: pointer; font-size: 13px; }
.dd-item:last-child { border-bottom: none; }
.dd-item:hover { background: #f0f7ff; }
.dd-glyph { display: flex; align-items: center; flex-shrink: 0; color: #4b5563; }
.dd-name { font-weight: 500; flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dd-domain { font-size: 11px; color: #9ca3af; white-space: nowrap; }
.chips { display: flex; flex-direction: column; gap: 5px; }
.chip { display: flex; align-items: center; gap: 6px; padding: 5px 8px; background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 6px; }
.chip-name { font-size: 13px; font-weight: 500; flex: 1; }
.chip-rm { margin-left: auto; width: 20px; height: 20px; border-radius: 4px; border: 1px solid #fca5a5; background: white; color: #dc2626; cursor: pointer; font-size: 14px; line-height: 1; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.chip-rm:hover { background: #fef2f2; }
.empty-msg { font-size: 12px; color: #9ca3af; padding: 4px 0; }
.conn-row { display: flex; align-items: center; gap: 6px; padding: 5px 8px; border-radius: 6px; margin-bottom: 4px; font-size: 12px; }
.conn-row--in { background: #f0fdf4; border: 1px solid #bbf7d0; }
.conn-row--avail { background: #f9fafb; border: 1px solid #e5e7eb; }
.conn-label { flex: 1; line-height: 1.4; }
.conn-label em { font-style: normal; font-weight: 600; color: #6b7280; }
.conn-btn { width: 22px; height: 22px; border-radius: 4px; border: none; cursor: pointer; font-size: 16px; line-height: 1; display: flex; align-items: center; justify-content: center; flex-shrink: 0; font-weight: 700; }
.conn-rm { background: #fee2e2; color: #dc2626; }
.conn-rm:hover { background: #fecaca; }
.conn-add { background: #dcfce7; color: #16a34a; }
.conn-add:hover { background: #bbf7d0; }
.avail-header { font-size: 11px; font-weight: 700; color: #9ca3af; text-transform: uppercase; letter-spacing: .04em; margin: 8px 0 4px; }
.actions { display: flex; gap: 8px; justify-content: flex-end; padding-top: 8px; }
.btn-preview { padding: 7px 16px; background: #f3f4f6; color: #1d4ed8; border: 1px solid #bfdbfe; border-radius: 6px; font-size: 13px; cursor: pointer; font-weight: 500; }
.btn-preview:hover:not(:disabled) { background: #eff6ff; }
.btn-create { padding: 7px 16px; background: #16a34a; color: white; border: none; border-radius: 6px; font-size: 13px; font-weight: 500; cursor: pointer; }
.btn-create:hover:not(:disabled) { background: #15803d; }
.btn-preview:disabled, .btn-create:disabled { opacity: .5; cursor: not-allowed; }
.state-msg { font-size: 13px; color: #6b7280; }
.state-err { font-size: 13px; color: #dc2626; margin-top: 6px; }
.warn { font-size: 12px; color: #b45309; margin-bottom: 4px; }
.preview-hint { font-size: 13px; color: #9ca3af; }
.preview-img { max-width: 100%; border-radius: 6px; border: 1px solid #e5e7eb; display: block; }
.toggle-src { margin-top: 10px; font-size: 12px; color: #2563eb; background: none; border: none; cursor: pointer; padding: 0; }
.toggle-src:hover { text-decoration: underline; }
.puml-src { font-size: 11px; font-family: monospace; white-space: pre-wrap; margin-top: 8px; background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 6px; padding: 10px; max-height: 400px; overflow-y: auto; }
</style>
