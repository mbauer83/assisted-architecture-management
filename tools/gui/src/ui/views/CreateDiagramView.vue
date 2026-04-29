<script setup lang="ts">
import { inject, ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Effect } from 'effect'
import { modelServiceKey } from '../keys'
import type { EntityDisplayInfo, EntityContextConnection, DiagramPreviewResult } from '../../domain'
import EntitySelectionList from '../components/EntitySelectionList.vue'
import EntityPickerInput from '../components/EntityPickerInput.vue'

const svc = inject(modelServiceKey)!
const router = useRouter()

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


const includedEntities = ref<EntityDisplayInfo[]>([])
const highlightedEntityIds = ref<Set<string>>(new Set())
const expandedConnectionEntityIds = ref<Set<string>>(new Set())
const expandedRelatedEntityIds = ref<Set<string>>(new Set())
const includedEntityIds = computed(() => new Set(includedEntities.value.map((e) => e.artifact_id)))

const allModelConns = ref<Map<string, EntityContextConnection>>(new Map())
const includedConnIds = ref<Set<string>>(new Set())

const selectionRows = computed(() =>
  includedEntities.value.map((entity) => ({
    entity,
    newInclusion: highlightedEntityIds.value.has(entity.artifact_id),
    badgeText: highlightedEntityIds.value.has(entity.artifact_id) ? 'new' : undefined,
    actionKind: 'remove' as const,
    actionTitle: 'Remove entity from diagram',
  })),
)

const relatedEntitiesById = computed<Record<string, EntityDisplayInfo[]>>(() => {
  const related: Record<string, EntityDisplayInfo[]> = {}
  const seenByEntity = new Map<string, Set<string>>()
  for (const entity of includedEntities.value) related[entity.artifact_id] = []
  for (const conn of allModelConns.value.values()) {
    const endpoints: Array<[string, string]> = [
      [conn.source, conn.target],
      [conn.target, conn.source],
    ]
    for (const [ownerId, otherId] of endpoints) {
      if (!includedEntityIds.value.has(ownerId) || includedEntityIds.value.has(otherId)) continue
      const name = ownerId === conn.source ? (conn.target_name ?? otherId) : (conn.source_name ?? otherId)
      const artifactType = ownerId === conn.source ? conn.target_artifact_type : conn.source_artifact_type
      const domain = ownerId === conn.source ? conn.target_domain : conn.source_domain
      const scope = ownerId === conn.source ? conn.target_scope : conn.source_scope
      const seen = seenByEntity.get(ownerId) ?? new Set<string>()
      if (seen.has(otherId)) continue
      seen.add(otherId)
      seenByEntity.set(ownerId, seen)
      related[ownerId].push({
        artifact_id: otherId,
        name,
        artifact_type: artifactType,
        domain,
        subdomain: '',
        status: scope,
        display_alias: '',
        element_type: artifactType,
        element_label: name,
      })
    }
  }
  for (const entityId of Object.keys(related)) {
    related[entityId].sort((a, b) => a.name.localeCompare(b.name))
  }
  return related
})

const refreshDiscovery = async () => {
  const discovery = await Effect.runPromise(
    svc.discoverDiagramEntities({
      includedEntityIds: includedEntities.value.map((e) => e.artifact_id),
      maxHops: 1,
      limit: 20,
    }),
  ).catch(() => null)
  if (!discovery) return
  allModelConns.value = new Map(discovery.candidate_connections.map((conn) => [conn.artifact_id, conn]))
}

const addEntity = async (entity: EntityDisplayInfo) => {
  if (includedEntityIds.value.has(entity.artifact_id)) return
  includedEntities.value.push(entity)
  highlightedEntityIds.value = new Set(highlightedEntityIds.value).add(entity.artifact_id)
  expandedRelatedEntityIds.value = new Set(expandedRelatedEntityIds.value)
  await refreshDiscovery()
  const nextConnIds = new Set(includedConnIds.value)
  for (const conn of allModelConns.value.values()) {
    const otherId = conn.source === entity.artifact_id ? conn.target : conn.source
    if ((conn.source === entity.artifact_id || conn.target === entity.artifact_id) && includedEntityIds.value.has(otherId)) {
      nextConnIds.add(conn.artifact_id)
    }
  }
  includedConnIds.value = nextConnIds
}

const removeEntity = (artifactId: string) => {
  includedEntities.value = includedEntities.value.filter((e) => e.artifact_id !== artifactId)
  const nextHighlighted = new Set(highlightedEntityIds.value)
  nextHighlighted.delete(artifactId)
  highlightedEntityIds.value = nextHighlighted
  const nextExpandedConns = new Set(expandedConnectionEntityIds.value)
  nextExpandedConns.delete(artifactId)
  expandedConnectionEntityIds.value = nextExpandedConns
  const nextExpandedRelated = new Set(expandedRelatedEntityIds.value)
  nextExpandedRelated.delete(artifactId)
  expandedRelatedEntityIds.value = nextExpandedRelated
  const nextConnIds = new Set(includedConnIds.value)
  for (const id of [...nextConnIds]) {
    const c = allModelConns.value.get(id)
    if (c && (c.source === artifactId || c.target === artifactId)) nextConnIds.delete(id)
  }
  includedConnIds.value = nextConnIds
  void refreshDiscovery()
}

const toggleConnections = (entityId: string) => {
  const next = new Set(expandedConnectionEntityIds.value)
  if (next.has(entityId)) next.delete(entityId)
  else next.add(entityId)
  expandedConnectionEntityIds.value = next
}

const toggleRelated = (entityId: string) => {
  const next = new Set(expandedRelatedEntityIds.value)
  if (next.has(entityId)) next.delete(entityId)
  else next.add(entityId)
  expandedRelatedEntityIds.value = next
}

const toggleConnection = (id: string) => {
  const next = new Set(includedConnIds.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  includedConnIds.value = next
}

watch(name, () => {
  preview.value = null
  previewClean.value = false
})

const preview = ref<DiagramPreviewResult | null>(null)
const previewBusy = ref(false)
const previewError = ref<string | null>(null)
const previewClean = ref(false)
const previewIssues = ref<string[]>([])
const showPuml = ref(false)

// ── Preview pan+zoom ─────────────────────────────────────────────────────────
const prevContainerRef = ref<HTMLElement | null>(null)
const prevScale = ref(1); const prevTx = ref(0); const prevTy = ref(0)
let prevDragging = false; let prevDrag = { x: 0, y: 0, tx: 0, ty: 0 }

const prevCanvasStyle = computed(() => ({
  transform: `translate(${prevTx.value}px, ${prevTy.value}px) scale(${prevScale.value})`,
  transformOrigin: '0 0', willChange: 'transform', display: 'inline-block',
}))
const prevIsTransformed = computed(() => prevScale.value !== 1 || prevTx.value !== 0 || prevTy.value !== 0)

const prevOnWheel = (e: WheelEvent) => {
  e.preventDefault()
  const f = e.deltaY < 0 ? 1.15 : 1 / 1.15
  const ns = Math.min(8, Math.max(0.2, prevScale.value * f))
  const r = ns / prevScale.value
  const rect = prevContainerRef.value!.getBoundingClientRect()
  prevTx.value = (e.clientX - rect.left) * (1 - r) + prevTx.value * r
  prevTy.value = (e.clientY - rect.top) * (1 - r) + prevTy.value * r
  prevScale.value = ns
}
const prevOnMouseDown = (e: MouseEvent) => {
  e.preventDefault()
  prevDragging = true
  prevDrag = { x: e.clientX, y: e.clientY, tx: prevTx.value, ty: prevTy.value }
  window.addEventListener('mousemove', prevOnMouseMove)
  window.addEventListener('mouseup', prevOnMouseUp)
}
const prevOnMouseMove = (e: MouseEvent) => {
  if (prevDragging) { prevTx.value = prevDrag.tx + e.clientX - prevDrag.x; prevTy.value = prevDrag.ty + e.clientY - prevDrag.y }
}
const prevOnMouseUp = () => {
  prevDragging = false
  window.removeEventListener('mousemove', prevOnMouseMove)
  window.removeEventListener('mouseup', prevOnMouseUp)
}
const prevResetView = () => { prevScale.value = 1; prevTx.value = 0; prevTy.value = 0 }
watch(prevContainerRef, (el, old) => {
  old?.removeEventListener('wheel', prevOnWheel)
  el?.addEventListener('wheel', prevOnWheel, { passive: false })
})
watch(preview, () => prevResetView())

onUnmounted(() => {
  prevContainerRef.value?.removeEventListener('wheel', prevOnWheel)
  window.removeEventListener('mousemove', prevOnMouseMove)
  window.removeEventListener('mouseup', prevOnMouseUp)
})

const doPreview = () => {
  previewBusy.value = true
  previewError.value = null
  previewIssues.value = []
  void Effect.runPromise(
    svc.previewDiagram({
      diagram_type: diagramType.value,
      name: name.value,
      entity_ids: includedEntities.value.map((e) => e.artifact_id),
      connection_ids: [...includedConnIds.value],
    }),
  )
    .then((r) => {
      preview.value = r
      previewClean.value = true
      previewIssues.value = []
      previewBusy.value = false
    })
    .catch((e) => { previewError.value = String(e); previewBusy.value = false })
}

const createBusy = ref(false)
const createError = ref<string | null>(null)

const doCreate = () => {
  createBusy.value = true
  createError.value = null
  void Effect.runPromise(
    svc.createDiagram({
      diagram_type: diagramType.value,
      name: name.value,
      entity_ids: includedEntities.value.map((e) => e.artifact_id),
      connection_ids: [...includedConnIds.value],
      dry_run: false,
    }),
  )
    .then((r) => {
      createBusy.value = false
      if (r.wrote) void router.push({ path: '/diagram', query: { id: r.artifact_id } })
      else createError.value = r.content ?? 'Verification failed — check warnings'
    })
    .catch((e) => { createBusy.value = false; createError.value = String(e) })
}


onMounted(() => { void refreshDiscovery() })
</script>

<template>
  <div class="layout">
    <div class="page-header">
      <button
        class="back-link"
        @click="router.back()"
      >
        ← Back
      </button>
      <h1 class="page-title">
        Create Diagram
      </h1>
    </div>

    <div class="columns">
      <section class="card form-col">
        <div class="form-row">
          <label class="lbl">Name <span class="req">*</span></label>
          <input
            v-model="name"
            class="inp"
            placeholder="Diagram name"
          >
        </div>

        <div class="form-row">
          <label class="lbl">Diagram Type</label>
          <select
            v-model="diagramType"
            class="inp"
          >
            <option
              v-for="dt in DIAGRAM_TYPES"
              :key="dt.key"
              :value="dt.key"
            >
              {{ dt.label }}
            </option>
          </select>
        </div>

        <div class="form-row">
          <label class="lbl">Add Entities</label>
          <EntityPickerInput
            :excluded-ids="includedEntityIds"
            @select="addEntity"
          />
        </div>

        <div
          v-if="includedEntities.length"
          class="form-row"
        >
          <label class="lbl">Included Entities ({{ includedEntities.length }})</label>
          <EntitySelectionList
            :rows="selectionRows"
            :candidate-connections="[...allModelConns.values()]"
            :included-entity-ids="[...includedEntityIds]"
            :included-connection-ids="[...includedConnIds]"
            :related-entities-by-id="relatedEntitiesById"
            :expanded-connection-entity-ids="[...expandedConnectionEntityIds]"
            :expanded-related-entity-ids="[...expandedRelatedEntityIds]"
            @toggle-connections="toggleConnections"
            @toggle-related="toggleRelated"
            @toggle-connection="toggleConnection"
            @add-related-entity="addEntity"
            @entity-action="removeEntity"
          />
        </div>

        <div
          v-if="createError"
          class="state-err"
        >
          {{ createError }}
        </div>

        <div class="actions">
          <button
            class="btn-preview"
            :disabled="previewBusy || !name.trim() || !includedEntities.length"
            @click="doPreview"
          >
            {{ previewBusy ? 'Rendering…' : 'Preview' }}
          </button>
          <button
            class="btn-create"
            :disabled="createBusy || !previewClean"
            :title="!previewClean ? 'Run preview first to enable create' : ''"
            @click="doCreate"
          >
            {{ createBusy ? 'Creating…' : 'Create Diagram' }}
          </button>
        </div>
      </section>

      <section class="card preview-col">
        <div
          v-if="!preview && !previewBusy && !previewError"
          class="preview-hint"
        >
          Select entities and connections, then click <strong>Preview</strong>.
        </div>
        <div
          v-if="previewBusy"
          class="state-msg"
        >
          Rendering…
        </div>
        <div
          v-if="previewError"
          class="state-err"
        >
          {{ previewError }}
        </div>

        <template v-if="preview">
          <div
            v-if="!previewClean"
            class="state-err"
          >
            <strong>Verification issues found:</strong>
            <ul style="margin-top: 4px; font-size: 12px; margin-bottom: 0; padding-left: 18px;">
              <li
                v-for="issue in previewIssues"
                :key="issue"
              >
                {{ issue }}
              </li>
            </ul>
          </div>
          <div
            v-else
            class="state-msg"
          >
            Verification passed.
          </div>
          <div
            v-if="preview.image"
            ref="prevContainerRef"
            class="prev-container"
            @mousedown="prevOnMouseDown"
            @dblclick="prevResetView"
          >
            <div :style="prevCanvasStyle">
              <img
                :src="preview.image"
                class="preview-img"
                alt="Diagram preview"
                draggable="false"
              >
            </div>
            <button
              v-if="prevIsTransformed"
              class="reset-btn"
              @click.stop="prevResetView"
            >
              ⊙ Reset
            </button>
            <div class="zoom-hint">
              Scroll to zoom · Drag to pan · Double-click to reset
            </div>
          </div>
          <div
            v-else
            class="state-msg"
          >
            No image could be rendered.
          </div>
          <button
            class="toggle-src"
            @click="showPuml = !showPuml"
          >
            {{ showPuml ? 'Hide' : 'Show' }} PUML source
          </button>
          <pre
            v-if="showPuml"
            class="puml-src"
          >{{ preview.puml }}</pre>
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

.columns { display: grid; grid-template-columns: 480px 1fr; gap: 20px; align-items: start; }
@media (max-width: 860px) { .columns { grid-template-columns: 1fr; } }

.card { background: white; border-radius: 8px; border: 1px solid #e5e7eb; padding: 20px; }
.form-row { margin-bottom: 14px; }
.lbl { display: block; font-size: 11px; font-weight: 700; color: #374151; margin-bottom: 4px; text-transform: uppercase; letter-spacing: .05em; }
.req { color: #dc2626; }
.inp { width: 100%; padding: 7px 10px; border-radius: 6px; border: 1px solid #d1d5db; font-size: 13px; outline: none; box-sizing: border-box; background: white; }
.inp:focus { border-color: #2563eb; }

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
.prev-container {
  position: relative; overflow: hidden; cursor: grab; user-select: none;
  background: #f8fafc; border: 1px solid #e5e7eb; border-radius: 6px; min-height: 200px;
}
.prev-container:active { cursor: grabbing; }
.preview-img { max-width: none; display: block; }
.reset-btn { position: absolute; top: 8px; right: 8px; padding: 4px 10px; background: rgba(255,255,255,.92); border: 1px solid #d1d5db; border-radius: 5px; font-size: 12px; cursor: pointer; color: #374151; }
.reset-btn:hover { background: white; }
.zoom-hint { position: absolute; bottom: 6px; left: 50%; transform: translateX(-50%); font-size: 11px; color: #9ca3af; background: rgba(255,255,255,.8); padding: 2px 8px; border-radius: 4px; pointer-events: none; white-space: nowrap; }
.toggle-src { margin-top: 10px; font-size: 12px; color: #2563eb; background: none; border: none; cursor: pointer; padding: 0; }
.toggle-src:hover { text-decoration: underline; }
.puml-src { font-size: 11px; font-family: monospace; white-space: pre-wrap; margin-top: 8px; background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 6px; padding: 10px; max-height: 400px; overflow-y: auto; }
</style>
