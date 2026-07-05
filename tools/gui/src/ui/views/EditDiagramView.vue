<script setup lang="ts">
import { inject, ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Effect, Exit } from 'effect'
import { modelServiceKey, toastKey } from '../keys'
import type {
  DiagramContext, EntitySummary, DiagramConnection,
  EntityDisplayInfo, EntityContextConnection, DiagramPreviewResult, WriteResult,
  DiagramTypeUiConfig,
} from '../../domain'
import type { RepoError } from '../../ports/ModelRepository'
import type { NotFoundError } from '../../domain'
import ArchimateTypeGlyph from '../components/ArchimateTypeGlyph.vue'
import EntitySelectionList from '../components/EntitySelectionList.vue'
import EntityPickerInput from '../components/EntityPickerInput.vue'
import DiagramTypeConfigPanel from '../components/DiagramTypeConfigPanel.vue'
import PreviewViewport from '../components/PreviewViewport.vue'
import ArchimateOccurrenceControls from '../components/ArchimateOccurrenceControls.vue'
import { useQuery } from '../composables/useQuery'
import { useMutation } from '../composables/useMutation'
import { toGlyphKey } from '../lib/glyphKey'
import { isArchimateDiagramType } from '../lib/archimateOccurrences'
import { resolveElementMap, neutralizeSentinelLink } from '../lib/diagramViewerExtensions'
import { sanitizeDiagramSvg } from '../lib/svgSanitize'

const svc = inject(modelServiceKey)!
const addToast = inject(toastKey)!
const route = useRoute()
const router = useRouter()

const diagramId = computed(() => (route.query.id as string | undefined) ?? '')

const contextQuery = useQuery<DiagramContext, RepoError | NotFoundError>()
const svgQuery = useQuery<string, RepoError>()
const previewMutation = useMutation<DiagramPreviewResult, RepoError>()
const saveMutation = useMutation<WriteResult, RepoError>()

const diagramDetail = computed(() => contextQuery.data.value?.diagram ?? null)
const uiConfig = ref<DiagramTypeUiConfig | null>(null)
const baseTypeEntityData = ref<Record<string, unknown>>({})
const typeEntityPatch = ref<Record<string, unknown>>({})
const typeEntityData = computed(() => ({ ...baseTypeEntityData.value, ...typeEntityPatch.value }))
const asRecord = (value: unknown): Record<string, unknown> =>
  value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
const mergeTypeEntityData = (patch: Record<string, unknown>) => {
  typeEntityPatch.value = { ...typeEntityPatch.value, ...patch }
  previewMutation.reset()
}

const setTypeEntityData = (next: Record<string, unknown>) => {
  baseTypeEntityData.value = next
  typeEntityPatch.value = {}
  previewMutation.reset()
}

watch(diagramDetail, (d) => {
  if (d?.diagram_type === 'matrix') {
    void router.replace({ path: '/diagram/edit/matrix', query: { id: diagramId.value } })
  }
})
const svgHtml = computed(() =>
  svgQuery.data.value ? sanitizeDiagramSvg(svgQuery.data.value) : null
)
const saveError = computed(() => {
  const r = saveMutation.result.value
  if (r && !r.wrote) return r.content ?? 'Verification failed'
  return saveMutation.errorMessage.value
})

// ── Pan / Zoom ────────────────────────────────────────────────────────────────

const containerRef = ref<HTMLElement | null>(null)
const scale = ref(1); const tx = ref(0); const ty = ref(0)
let dragging = false; let drag = { x: 0, y: 0, tx: 0, ty: 0 }

const canvasStyle = computed(() => ({
  transform: `translate(${tx.value}px, ${ty.value}px) scale(${scale.value})`,
  transformOrigin: '0 0', willChange: 'transform', display: 'inline-block',
}))
const isTransformed = computed(() => scale.value !== 1 || tx.value !== 0 || ty.value !== 0)

const onWheel = (e: WheelEvent) => {
  e.preventDefault()
  const f = e.deltaY < 0 ? 1.15 : 1 / 1.15
  const ns = Math.min(8, Math.max(0.2, scale.value * f))
  const r = ns / scale.value
  const rect = containerRef.value!.getBoundingClientRect()
  tx.value = (e.clientX - rect.left) * (1 - r) + tx.value * r
  ty.value = (e.clientY - rect.top) * (1 - r) + ty.value * r
  scale.value = ns
}
const onMouseDown = (e: MouseEvent) => {
  if ((e.target as HTMLElement).closest('[data-entity-id],[data-conn-id],button,a,input,label')) return
  dragging = true
  drag = { x: e.clientX, y: e.clientY, tx: tx.value, ty: ty.value }
  window.addEventListener('mousemove', onMouseMove)
  window.addEventListener('mouseup', onMouseUp)
}
const onMouseMove = (e: MouseEvent) => {
  if (dragging) { tx.value = drag.tx + e.clientX - drag.x; ty.value = drag.ty + e.clientY - drag.y }
}
const onMouseUp = () => {
  dragging = false
  window.removeEventListener('mousemove', onMouseMove)
  window.removeEventListener('mouseup', onMouseUp)
}
const resetView = () => { scale.value = 1; tx.value = 0; ty.value = 0 }
watch(containerRef, (el, prev) => {
  prev?.removeEventListener('wheel', onWheel)
  el?.addEventListener('wheel', onWheel, { passive: false })
})

// ── Diagram entity / connection state ─────────────────────────────────────────

const diagramEntities = ref<EntitySummary[]>([])
const diagramConnections = ref<DiagramConnection[]>([])
const includedEntities = ref<EntityDisplayInfo[]>([])
const allModelConns = ref<Map<string, EntityContextConnection>>(new Map())
const includedConnIds = ref<Set<string>>(new Set())

const toRemoveEntityIds = ref<Set<string>>(new Set())
const toRemoveConnIds = ref<Set<string>>(new Set())
const entitiesToAdd = ref<EntityDisplayInfo[]>([])
const selectedNewConnIds = ref<Set<string>>(new Set())
const expandedConnectionEntityIds = ref<Set<string>>(new Set())
const expandedRelatedEntityIds = ref<Set<string>>(new Set())

const includedEntityIds = computed(() => new Set(includedEntities.value.map(e => e.artifact_id)))
const toAddEntityIds = computed(() => new Set(entitiesToAdd.value.map(e => e.artifact_id)))

const effectiveEntityIds = computed(() => {
  const s = new Set<string>()
  for (const e of includedEntities.value) if (!toRemoveEntityIds.value.has(e.artifact_id)) s.add(e.artifact_id)
  for (const e of entitiesToAdd.value) s.add(e.artifact_id)
  return s
})

const effectiveEntitiesList = computed(() => [
  ...includedEntities.value.filter(e => !toRemoveEntityIds.value.has(e.artifact_id)),
  ...entitiesToAdd.value,
])

const selectionRows = computed(() =>
  effectiveEntitiesList.value.map((entity) => {
    const isNew = toAddEntityIds.value.has(entity.artifact_id)
    return {
      entity, newInclusion: isNew,
      badgeText: isNew ? 'new' : undefined,
      actionKind: isNew ? 'remove' as const : 'mark-remove' as const,
      actionTitle: isNew ? 'Remove entity from pending additions' : 'Mark entity for removal',
    }
  }),
)

const toRemoveEntities = computed(() =>
  includedEntities.value.filter(e => toRemoveEntityIds.value.has(e.artifact_id))
)


const isConnIncluded = (connId: string): boolean =>
  (includedConnIds.value.has(connId) && !toRemoveConnIds.value.has(connId))
  || selectedNewConnIds.value.has(connId)

const finalConnIds = computed(() => [
  ...[...includedConnIds.value].filter(id => !toRemoveConnIds.value.has(id)),
  ...[...selectedNewConnIds.value],
])

const relatedEntitiesById = computed<Record<string, EntityDisplayInfo[]>>(() => {
  const related: Record<string, EntityDisplayInfo[]> = {}
  const seenByEntity = new Map<string, Set<string>>()
  for (const entity of effectiveEntitiesList.value) related[entity.artifact_id] = []
  for (const conn of allModelConns.value.values()) {
    const endpoints: Array<[string, string]> = [[conn.source, conn.target], [conn.target, conn.source]]
    for (const [ownerId, otherId] of endpoints) {
      if (!effectiveEntityIds.value.has(ownerId) || effectiveEntityIds.value.has(otherId)) continue
      if (toRemoveEntityIds.value.has(ownerId)) continue
      const name = ownerId === conn.source ? (conn.target_name ?? otherId) : (conn.source_name ?? otherId)
      const artifactType = ownerId === conn.source ? conn.target_artifact_type : conn.source_artifact_type
      const domain = ownerId === conn.source ? conn.target_domain : conn.source_domain
      const scope = ownerId === conn.source ? conn.target_scope : conn.source_scope
      const seen = seenByEntity.get(ownerId) ?? new Set<string>()
      if (seen.has(otherId)) continue
      seen.add(otherId)
      seenByEntity.set(ownerId, seen)
      related[ownerId].push({
        artifact_id: otherId, name,
        artifact_type: artifactType,
        domain,
        subdomain: '', status: scope, display_alias: '',
        element_type: artifactType, element_label: name,
      })
    }
  }
  for (const entityId of Object.keys(related)) related[entityId].sort((a, b) => a.name.localeCompare(b.name))
  return related
})

const svgEntityElems = new Map<string, Element[]>()
const svgConnElems = new Map<string, Element[]>()
const svgContainer = ref<HTMLElement | null>(null)

const updateHighlights = () => {
  for (const [id, elems] of svgEntityElems)
    for (const el of elems) el.classList.toggle('svg-remove', toRemoveEntityIds.value.has(id))
  for (const [id, elems] of svgConnElems) {
    const excl = !isConnIncluded(id) && includedConnIds.value.has(id)
    for (const el of elems) el.classList.toggle('svg-remove', excl)
  }
}

const toggleConn = (connId: string) => {
  const included = isConnIncluded(connId)
  const inIncluded = includedConnIds.value.has(connId)
  const removeItems = included
    ? [...toRemoveConnIds.value, connId]
    : [...toRemoveConnIds.value].filter(id => id !== connId)
  toRemoveConnIds.value = inIncluded ? new Set(removeItems) : toRemoveConnIds.value
  const newConnItems = included
    ? [...selectedNewConnIds.value].filter(id => id !== connId)
    : [...selectedNewConnIds.value, connId]
  selectedNewConnIds.value = !inIncluded ? new Set(newConnItems) : selectedNewConnIds.value
  updateHighlights()
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

const toggleEntityRemoval = (id: string) => {
  toRemoveEntityIds.value = toRemoveEntityIds.value.has(id)
    ? new Set([...toRemoveEntityIds.value].filter(x => x !== id))
    : new Set([...toRemoveEntityIds.value, id])
  expandedConnectionEntityIds.value = new Set([...expandedConnectionEntityIds.value].filter(x => x !== id))
  expandedRelatedEntityIds.value = new Set([...expandedRelatedEntityIds.value].filter(x => x !== id))
  updateHighlights()
  void refreshDiscovery()
}

const removeToAddEntity = (id: string) => {
  entitiesToAdd.value = entitiesToAdd.value.filter(e => e.artifact_id !== id)
  expandedConnectionEntityIds.value = new Set([...expandedConnectionEntityIds.value].filter(x => x !== id))
  expandedRelatedEntityIds.value = new Set([...expandedRelatedEntityIds.value].filter(x => x !== id))
  selectedNewConnIds.value = new Set(
    [...selectedNewConnIds.value].filter((cid) => {
      const c = allModelConns.value.get(cid)
      return !(c && (c.source === id || c.target === id))
    }),
  )
  void refreshDiscovery()
}

const handleEntityAction = (entityId: string) =>
  toAddEntityIds.value.has(entityId) ? removeToAddEntity(entityId) : toggleEntityRemoval(entityId)

const attachInteractivity = () => {
  svgEntityElems.clear(); svgConnElems.clear()
  const svgEl = svgContainer.value?.querySelector('svg')
  if (!svgEl || !diagramEntities.value.length) return

  const { nodes, edges } = resolveElementMap(diagramDetail.value?.diagram_type, svgEl, {
    entities: diagramEntities.value,
    connections: diagramConnections.value,
    diagramEntities: typeEntityData.value,
  })
  for (const [artifactId, elems] of nodes) {
    svgEntityElems.set(artifactId, elems)
    for (const el of elems) {
      if (!(el instanceof SVGGElement || el instanceof SVGAElement)) continue
      el.setAttribute('data-entity-id', artifactId)
      el.addEventListener('click', (ev) => { ev.stopPropagation(); ev.preventDefault(); toggleEntityRemoval(artifactId) })
      if (el instanceof SVGAElement) neutralizeSentinelLink(el)
    }
  }
  for (const [connArtifactId, elems] of edges) {
    for (const el of elems) {
      if (!(el instanceof SVGGElement || el instanceof SVGAElement)) continue
      el.setAttribute('data-conn-id', connArtifactId)
      el.addEventListener('click', (ev) => { ev.stopPropagation(); ev.preventDefault(); toggleConn(connArtifactId) })
      if (el instanceof SVGAElement) neutralizeSentinelLink(el)
    }
  }
  updateHighlights()
}

watch([svgHtml, diagramEntities, diagramConnections, typeEntityData], attachInteractivity, { flush: 'post' })
watch([toRemoveEntityIds, toRemoveConnIds, selectedNewConnIds], updateHighlights)

// ── Search / discovery ────────────────────────────────────────────────────────

const refreshDiscovery = async () => {
  const exit = await Effect.runPromiseExit(
    svc.discoverDiagramEntities({
      includedEntityIds: [...effectiveEntityIds.value],
      diagramType: diagramDetail.value?.diagram_type,
      maxHops: 1, limit: 20,
    }),
  )
  if (Exit.isSuccess(exit)) {
    allModelConns.value = new Map(exit.value.candidate_connections.map((conn) => [conn.artifact_id, conn]))
  }
}

const addEntity = async (entity: EntityDisplayInfo) => {
  if (includedEntityIds.value.has(entity.artifact_id) || toAddEntityIds.value.has(entity.artifact_id)) return
  entitiesToAdd.value = [...entitiesToAdd.value, entity]
  await refreshDiscovery()
  const next = new Set(selectedNewConnIds.value)
  for (const conn of allModelConns.value.values()) {
    const touchesAdded = conn.source === entity.artifact_id || conn.target === entity.artifact_id
    const other = conn.source === entity.artifact_id ? conn.target : conn.source
    if (touchesAdded && effectiveEntityIds.value.has(other)) next.add(conn.artifact_id)
  }
  selectedNewConnIds.value = next
}

// ── Load ──────────────────────────────────────────────────────────────────────

const load = async () => {
  if (!diagramId.value) return
  toRemoveEntityIds.value = new Set(); toRemoveConnIds.value = new Set()
  entitiesToAdd.value = []; selectedNewConnIds.value = new Set()
  expandedConnectionEntityIds.value = new Set(); expandedRelatedEntityIds.value = new Set()
  includedEntities.value = []; allModelConns.value = new Map(); includedConnIds.value = new Set()
  previewMutation.reset(); saveMutation.reset()

  contextQuery.run(svc.getDiagramContext(diagramId.value))
  svgQuery.run(svc.getDiagramSvg(diagramId.value))

  const exit = await Effect.runPromiseExit(svc.getDiagramContext(diagramId.value))
  Exit.match(exit, {
    onSuccess: (context) => {
      diagramEntities.value = context.entities as EntitySummary[]
      diagramConnections.value = context.connections as DiagramConnection[]
      includedEntities.value = context.entities.map(s => ({
        artifact_id: s.artifact_id, name: s.name, artifact_type: s.artifact_type,
        domain: s.domain, subdomain: s.subdomain, status: s.status,
        display_alias: s.display_alias ?? '', element_type: s.artifact_type, element_label: s.name,
      }))
      allModelConns.value = new Map(context.candidate_connections.map((conn) => [conn.artifact_id, conn]))
      const inc = new Set<string>()
      for (const cid of context.diagram.connection_ids_used ?? []) {
        if (allModelConns.value.has(cid)) inc.add(cid)
      }
      for (const conn of context.connections) inc.add(conn.artifact_id)
      includedConnIds.value = inc
      baseTypeEntityData.value = asRecord(context.diagram.diagram_entities)
      typeEntityPatch.value = {}
      void Effect.runPromise(svc.getDiagramTypeUiConfig(context.diagram.diagram_type))
        .then((config) => { uiConfig.value = config })
        .catch(() => { uiConfig.value = null })
      void refreshDiscovery()
    },
    onFailure: () => {},
  })
}

onMounted(load)
watch(diagramId, load)

// ── Preview / Save ────────────────────────────────────────────────────────────

const showPuml = ref(false)

const finalEntityIds = computed(() => {
  const base = [
    ...includedEntities.value.filter(e => !toRemoveEntityIds.value.has(e.artifact_id)).map(e => e.artifact_id),
    ...entitiesToAdd.value.map(e => e.artifact_id),
  ]
  const mapped = (typeEntityData.value.entity_ids_mapped as string[] | undefined) ?? []
  return [...new Set([...base, ...mapped])]
})

const doPreview = () => {
  if (!diagramDetail.value) return
  void previewMutation.run(svc.previewDiagram({
    diagram_type: diagramDetail.value.diagram_type,
    name: diagramDetail.value.name,
    entity_ids: finalEntityIds.value,
    connection_ids: finalConnIds.value,
    diagram_entities: typeEntityData.value,
  }))
}

const doSave = async () => {
  if (!diagramDetail.value) return
  const exit = await saveMutation.run(svc.editDiagram({
    artifact_id: diagramId.value,
    diagram_type: diagramDetail.value.diagram_type,
    name: diagramDetail.value.name,
    entity_ids: finalEntityIds.value,
    connection_ids: finalConnIds.value,
    diagram_entities: typeEntityData.value,
    dry_run: false,
  }))
  if (!Exit.isSuccess(exit) || !exit.value.wrote) return
  addToast('Diagram saved')
  void router.push({ path: '/diagram', query: { id: diagramId.value } })
}

onUnmounted(() => {
  containerRef.value?.removeEventListener('wheel', onWheel)
  window.removeEventListener('mousemove', onMouseMove)
  window.removeEventListener('mouseup', onMouseUp)
})
</script>

<template>
  <div class="page">
    <div class="page-hdr">
      <button
        class="back-link"
        @click="router.push({ path: '/diagram', query: { id: diagramId } })"
      >
        ← Back
      </button>
      <div class="hdr-info">
        <h1 class="pg-title">
          <span
            v-if="contextQuery.loading.value"
            class="faded"
          >Loading…</span>
          <span v-else-if="diagramDetail">{{ diagramDetail.name }}</span>
        </h1>
        <span
          v-if="diagramDetail"
          class="type-badge"
        >
          {{ diagramDetail.diagram_type.replace('archimate-', '') }}
        </span>
      </div>
      <div class="hdr-actions">
        <button
          class="btn-preview"
          :disabled="previewMutation.running.value || !diagramDetail"
          @click="doPreview"
        >
          {{ previewMutation.running.value ? 'Rendering…' : 'Preview' }}
        </button>
        <button
          class="btn-save"
          :disabled="saveMutation.running.value || !previewMutation.result.value || !diagramDetail"
          :title="!previewMutation.result.value ? 'Run Preview first' : ''"
          @click="doSave"
        >
          {{ saveMutation.running.value ? 'Saving…' : 'Save Changes' }}
        </button>
      </div>
    </div>

    <div class="main-grid">
      <div
        ref="containerRef"
        class="img-container"
        @mousedown="onMouseDown"
        @dblclick="resetView"
      >
        <div :style="canvasStyle">
          <div
            v-if="svgQuery.loading.value"
            class="no-img"
          >
            Rendering SVG…
          </div>
          <div
            v-else-if="svgQuery.errorMessage.value"
            class="no-img err-txt"
          >
            {{ svgQuery.errorMessage.value }}
          </div>
          <div
            v-else-if="svgHtml"
            ref="svgContainer"
            class="svg-wrap"
            v-html="svgHtml"
          />
          <div
            v-else
            class="no-img"
          >
            No diagram rendered.
          </div>
        </div>
        <button
          v-if="isTransformed"
          class="reset-btn"
          @click.stop="resetView"
        >
          ⊙ Reset
        </button>
        <div class="zoom-hint">
          Click entity to mark for removal · Click connection to toggle · Scroll/drag to navigate
        </div>
      </div>

      <aside class="sidebar card">
        <div
          v-if="uiConfig?.entity_search_filter !== false"
          class="sb-search"
        >
          <EntityPickerInput
            :excluded-ids="effectiveEntityIds"
            :diagram-type="diagramDetail?.diagram_type"
            @select="addEntity"
          />
        </div>

        <div class="sb-scroll">
          <DiagramTypeConfigPanel
            :ui-config="uiConfig"
            :diagram-entities="typeEntityData"
            :entities="effectiveEntitiesList"
            :diagram-connections="diagramConnections"
            :diagram-id="diagramId"
            @diagram-entities-change="mergeTypeEntityData"
            @diagram-connections-change="diagramConnections = $event"
          />

          <div
            v-if="isArchimateDiagramType(diagramDetail?.diagram_type) && effectiveEntitiesList.length"
            class="sb-section sb-section--pad"
          >
            <ArchimateOccurrenceControls
              :diagram-entities="typeEntityData"
              :entities="effectiveEntitiesList"
              @change="setTypeEntityData"
            />
          </div>

          <div
            v-if="uiConfig?.entity_search_filter !== false && effectiveEntitiesList.length"
            class="sb-section"
          >
            <div class="sb-sec-hdr">
              Included Entities <span class="sb-count">{{ effectiveEntitiesList.length }}</span>
            </div>
            <div class="entity-section">
              <EntitySelectionList
                :rows="selectionRows"
                :candidate-connections="[...allModelConns.values()]"
                :included-entity-ids="[...effectiveEntityIds]"
                :included-connection-ids="finalConnIds"
                :related-entities-by-id="relatedEntitiesById"
                :expanded-connection-entity-ids="[...expandedConnectionEntityIds]"
                :expanded-related-entity-ids="[...expandedRelatedEntityIds]"
                @toggle-connections="toggleConnections"
                @toggle-related="toggleRelated"
                @toggle-connection="toggleConn"
                @add-related-entity="addEntity"
                @entity-action="handleEntityAction"
              />
            </div>
          </div>

          <div
            v-if="toRemoveEntities.length"
            class="sb-section"
          >
            <div class="sb-sec-hdr sb-sec-hdr--rm">
              For removal <span class="sb-count">{{ toRemoveEntities.length }}</span>
            </div>
            <div
              v-for="entity in toRemoveEntities"
              :key="entity.artifact_id"
              class="rm-row"
            >
              <span class="dd-glyph rm-glyph"><ArchimateTypeGlyph
                :type="toGlyphKey(entity.element_type || entity.artifact_type)"
                :size="13"
              /></span>
              <span class="rm-name">{{ entity.name }}</span>
              <button
                class="undo-btn"
                title="Restore"
                @click="toggleEntityRemoval(entity.artifact_id)"
              >
                ↩
              </button>
            </div>
          </div>

          <div
            v-if="!effectiveEntitiesList.length && !toRemoveEntities.length"
            class="sb-hint"
          >
            Loading diagram entities…
          </div>

          <div class="sb-actions">
            <button
              class="btn-preview"
              :disabled="previewMutation.running.value || !diagramDetail"
              @click="doPreview"
            >
              {{ previewMutation.running.value ? 'Rendering…' : 'Preview' }}
            </button>
            <button
              class="btn-save"
              :disabled="saveMutation.running.value || !previewMutation.result.value || !diagramDetail"
              :title="!previewMutation.result.value ? 'Run Preview first' : ''"
              @click="doSave"
            >
              {{ saveMutation.running.value ? 'Saving…' : 'Save Changes' }}
            </button>
            <div
              v-if="saveError"
              class="save-err"
            >
              {{ saveError }}
            </div>
          </div>
        </div>
      </aside>
    </div>

    <div
      v-if="previewMutation.result.value || previewMutation.running.value || previewMutation.errorMessage.value"
      class="preview-row"
    >
      <div
        v-if="previewMutation.running.value"
        class="state-msg"
      >
        Rendering preview…
      </div>
      <div
        v-if="previewMutation.errorMessage.value"
        class="state-err"
      >
        {{ previewMutation.errorMessage.value }}
      </div>
      <template v-if="previewMutation.result.value">
        <div
          v-for="w in previewMutation.result.value.warnings"
          :key="w"
          class="warn-msg"
        >
          {{ w }}
        </div>
        <PreviewViewport
          v-if="previewMutation.result.value.image"
          :reset-signal="previewMutation.result.value"
        >
          <img
            :src="previewMutation.result.value.image"
            class="preview-img"
            alt="Preview"
            draggable="false"
          >
        </PreviewViewport>
        <div
          v-else
          class="state-msg"
        >
          No image rendered.
        </div>
        <button
          class="toggle-src"
          @click="showPuml = !showPuml"
        >
          {{ showPuml ? 'Hide' : 'Show' }} PUML
        </button>
        <pre
          v-if="showPuml"
          class="puml-src"
        >{{ previewMutation.result.value.puml }}</pre>
      </template>
    </div>
  </div>
</template>

<style scoped>
.page { max-width: 100%; }
.page-hdr { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
.hdr-actions { display: flex; gap: 8px; margin-left: auto; }
.back-link { font-size: 13px; color: #6b7280; background: none; border: none; cursor: pointer; padding: 0; flex-shrink: 0; }
.back-link:hover { color: #374151; }
.hdr-info { display: flex; align-items: center; gap: 10px; flex: 1; min-width: 0; }
.pg-title { font-size: 20px; font-weight: 700; margin: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.faded { color: #9ca3af; font-weight: 400; }
.type-badge { padding: 2px 8px; border-radius: 4px; font-size: 11px; background: #dbeafe; color: #1e40af; font-weight: 500; flex-shrink: 0; }

.main-grid { display: grid; grid-template-columns: 1fr 50%; gap: 16px; align-items: start; }
@media (max-width: 860px) { .main-grid { grid-template-columns: 1fr; } }

.img-container {
  position: relative; overflow: hidden; background: #f8fafc;
  border: 1px solid #e5e7eb; border-radius: 8px; min-height: 500px;
  cursor: grab; user-select: none;
}
.img-container:active { cursor: grabbing; }
.no-img { padding: 60px 40px; text-align: center; color: #9ca3af; font-size: 13px; }
.err-txt { color: #dc2626; }

.svg-wrap :deep(svg) { display: block; max-width: none; }
.svg-wrap :deep([data-entity-id]) { cursor: pointer; }
.svg-wrap :deep([data-entity-id]:hover) polygon,
.svg-wrap :deep([data-entity-id]:hover) rect { stroke: #ef4444 !important; stroke-width: 2 !important; }
.svg-wrap :deep(a[data-entity-id]:hover) text { fill: #ef4444 !important; }
.svg-wrap :deep(.svg-remove) { opacity: 0.4; }
.svg-wrap :deep(.svg-remove) polygon,
.svg-wrap :deep(.svg-remove) rect,
.svg-wrap :deep(.svg-remove) path { stroke: #ef4444 !important; stroke-width: 2.5 !important; }
.svg-wrap :deep([data-conn-id]) { cursor: pointer; }
.svg-wrap :deep([data-conn-id]:hover) path,
.svg-wrap :deep([data-conn-id]:hover) polygon { stroke: #6366f1 !important; stroke-width: 2 !important; }

.reset-btn { position: absolute; top: 8px; right: 8px; padding: 4px 10px; background: rgba(255,255,255,.92); border: 1px solid #d1d5db; border-radius: 5px; font-size: 12px; cursor: pointer; color: #374151; }
.reset-btn:hover { background: white; }
.zoom-hint { position: absolute; bottom: 6px; left: 50%; transform: translateX(-50%); font-size: 11px; color: #9ca3af; background: rgba(255,255,255,.8); padding: 2px 8px; border-radius: 4px; pointer-events: none; white-space: nowrap; }

.card { background: white; border-radius: 8px; border: 1px solid #e5e7eb; }
.sidebar { display: flex; flex-direction: column; position: sticky; top: 16px; max-height: calc(100vh - 80px); overflow: hidden; }
.sb-search { padding: 10px; border-bottom: 1px solid #f3f4f6; flex-shrink: 0; position: relative; z-index: 10; }
.inp { width: 100%; padding: 7px 10px; border-radius: 6px; border: 1px solid #d1d5db; font-size: 13px; outline: none; box-sizing: border-box; }
.inp:focus { border-color: #6366f1; }
.sb-scroll { flex: 1; overflow-y: auto; display: flex; flex-direction: column; min-height: 0; }
.sb-section { border-bottom: 1px solid #f3f4f6; }
.sb-section--pad { padding: 10px; }
.sb-sec-hdr { display: flex; align-items: center; gap: 5px; padding: 8px 10px 6px; font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: .06em; color: #6b7280; }
.sb-sec-hdr--rm { color: #dc2626; }
.sb-count { font-size: 10px; font-weight: 400; color: #9ca3af; }
.entity-section { padding: 0 10px 10px; }

.rm-row { display: flex; align-items: center; gap: 5px; padding: 4px 10px; font-size: 12px; }
.rm-glyph { color: #dc2626; opacity: 0.7; }
.rm-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #374151; }
.undo-btn { background: none; border: none; cursor: pointer; color: #9ca3af; font-size: 13px; padding: 0 2px; flex-shrink: 0; }
.undo-btn:hover { color: #374151; }

.sb-hint { padding: 12px 10px; font-size: 11px; color: #9ca3af; }
.sb-actions { padding: 10px; display: flex; flex-direction: column; gap: 6px; margin-top: auto; border-top: 1px solid #f3f4f6; flex-shrink: 0; }
.btn-preview { width: 100%; padding: 7px 12px; background: #f3f4f6; color: #1d4ed8; border: 1px solid #bfdbfe; border-radius: 6px; font-size: 13px; cursor: pointer; font-weight: 500; }
.btn-preview:hover:not(:disabled) { background: #eff6ff; }
.btn-save { width: 100%; padding: 7px 12px; background: #2563eb; color: white; border: none; border-radius: 6px; font-size: 13px; font-weight: 500; cursor: pointer; }
.btn-save:hover:not(:disabled) { background: #1d4ed8; }
.btn-preview:disabled, .btn-save:disabled { opacity: .5; cursor: not-allowed; }
.save-err { font-size: 12px; color: #dc2626; }

.preview-row { margin-top: 16px; }
.state-msg { font-size: 13px; color: #6b7280; }
.state-err { font-size: 13px; color: #dc2626; margin-top: 6px; }
.warn-msg { font-size: 12px; color: #b45309; margin-bottom: 4px; }
.preview-img { max-width: none; display: block; }
.toggle-src { margin-top: 10px; font-size: 12px; color: #2563eb; background: none; border: none; cursor: pointer; padding: 0; }
.puml-src { font-size: 11px; font-family: monospace; white-space: pre-wrap; margin-top: 8px; background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 6px; padding: 10px; max-height: 400px; overflow-y: auto; }
</style>
