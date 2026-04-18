<script setup lang="ts">
import { inject, ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Effect } from 'effect'
import { modelServiceKey } from '../keys'
import { useAsync } from '../composables/useAsync'
import type {
  DiagramDetail, EntitySummary, DiagramConnection,
  EntityDisplayInfo, ConnectionRecord, DiagramPreviewResult,
} from '../../domain'
import ArchimateTypeGlyph from '../components/ArchimateTypeGlyph.vue'

const svc = inject(modelServiceKey)!
const route = useRoute()
const router = useRouter()

const diagramId = computed(() => (route.query.id as string | undefined) ?? '')
const diagramDetail = useAsync<DiagramDetail>()

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

// ── SVG ───────────────────────────────────────────────────────────────────────

const svgHtml = ref<string | null>(null)
const svgLoading = ref(false)
const svgError = ref<string | null>(null)
const svgContainer = ref<HTMLElement | null>(null)

const svgEntityElems = new Map<string, Element>()
const svgConnElems = new Map<string, Element>()

// ── Diagram state ─────────────────────────────────────────────────────────────

const diagramEntities = ref<EntitySummary[]>([])
const diagramConnections = ref<DiagramConnection[]>([])

// Entities currently in diagram (loaded from backend)
const includedEntities = ref<EntityDisplayInfo[]>([])
// All known connections (fetched for all entities)
const allModelConns = ref<Map<string, ConnectionRecord>>(new Map())
// Connections that were originally in the diagram
const includedConnIds = ref<Set<string>>(new Set())

// Entities selected for removal via SVG click
const toRemoveEntityIds = ref<Set<string>>(new Set())
// Connections manually excluded (originally included but removed)
const toRemoveConnIds = ref<Set<string>>(new Set())
// New entities to add
const entitiesToAdd = ref<EntityDisplayInfo[]>([])
// New connections to include (for newly added entities)
const selectedNewConnIds = ref<Set<string>>(new Set())
// Expanded state for entity list entries
const expandedEntityIds = ref<Set<string>>(new Set())

const includedEntityIds = computed(() => new Set(includedEntities.value.map(e => e.artifact_id)))
const toAddEntityIds = computed(() => new Set(entitiesToAdd.value.map(e => e.artifact_id)))

// All entities that will be in the final diagram (existing - removed + to-add)
const effectiveEntityIds = computed(() => {
  const s = new Set<string>()
  for (const e of includedEntities.value) if (!toRemoveEntityIds.value.has(e.artifact_id)) s.add(e.artifact_id)
  for (const e of entitiesToAdd.value) s.add(e.artifact_id)
  return s
})

// Entity list for sidebar: non-removed existing + to-be-added
const effectiveEntitiesList = computed(() => [
  ...includedEntities.value.filter(e => !toRemoveEntityIds.value.has(e.artifact_id)),
  ...entitiesToAdd.value,
])

const toRemoveEntities = computed(() =>
  includedEntities.value.filter(e => toRemoveEntityIds.value.has(e.artifact_id))
)

const nameOf = (id: string) =>
  includedEntities.value.find(e => e.artifact_id === id)?.name ??
  entitiesToAdd.value.find(e => e.artifact_id === id)?.name ?? id

const toGlyphKey = (t: string) => t.replace(/[A-Z]/g, (c, i) => (i > 0 ? '-' : '') + c.toLowerCase())

const isToAdd = (id: string) => toAddEntityIds.value.has(id)

// ── Connection state ──────────────────────────────────────────────────────────

const isConnIncluded = (connId: string): boolean =>
  (includedConnIds.value.has(connId) && !toRemoveConnIds.value.has(connId))
  || selectedNewConnIds.value.has(connId)

const toggleConn = (connId: string) => {
  if (isConnIncluded(connId)) {
    if (includedConnIds.value.has(connId)) {
      const next = new Set(toRemoveConnIds.value); next.add(connId); toRemoveConnIds.value = next
    } else {
      const next = new Set(selectedNewConnIds.value); next.delete(connId); selectedNewConnIds.value = next
    }
  } else {
    if (includedConnIds.value.has(connId)) {
      const next = new Set(toRemoveConnIds.value); next.delete(connId); toRemoveConnIds.value = next
    } else {
      const next = new Set(selectedNewConnIds.value); next.add(connId); selectedNewConnIds.value = next
    }
  }
  updateHighlights()
}

// ── Connection table per entity ───────────────────────────────────────────────

interface ConnEntry { conn: ConnectionRecord; direction: 'out' | 'in'; otherName: string; otherId: string }
interface ConnTypeGroup { included: ConnEntry[]; excluded: ConnEntry[] }

const getConnsByType = (entityId: string): Map<string, ConnTypeGroup> => {
  const byType = new Map<string, ConnTypeGroup>()
  for (const conn of allModelConns.value.values()) {
    const isOut = conn.source === entityId
    const isIn = conn.target === entityId
    if (!isOut && !isIn) continue
    const otherId = isOut ? conn.target : conn.source
    if (!effectiveEntityIds.value.has(otherId)) continue
    const inc = isConnIncluded(conn.artifact_id)
    const entry: ConnEntry = {
      conn, direction: isOut ? 'out' : 'in', otherName: nameOf(otherId), otherId,
    }
    if (!byType.has(conn.conn_type)) byType.set(conn.conn_type, { included: [], excluded: [] })
    const g = byType.get(conn.conn_type)!
    if (inc) g.included.push(entry); else g.excluded.push(entry)
  }
  return byType
}

const toggleExpand = (id: string) => {
  const next = new Set(expandedEntityIds.value)
  if (next.has(id)) next.delete(id); else next.add(id)
  expandedEntityIds.value = next
}

// ── SVG interaction ───────────────────────────────────────────────────────────

const updateHighlights = () => {
  for (const [id, el] of svgEntityElems) el.classList.toggle('svg-remove', toRemoveEntityIds.value.has(id))
  for (const [id, el] of svgConnElems) {
    const excl = !isConnIncluded(id) && includedConnIds.value.has(id)
    el.classList.toggle('svg-remove', excl)
  }
}

const toggleEntityRemoval = (id: string) => {
  const nextE = new Set(toRemoveEntityIds.value)
  if (nextE.has(id)) {
    nextE.delete(id)
  } else {
    nextE.add(id)
    // Collapse expansion when entity is removed
    const nextExp = new Set(expandedEntityIds.value); nextExp.delete(id); expandedEntityIds.value = nextExp
  }
  toRemoveEntityIds.value = nextE
  updateHighlights()
}

const attachInteractivity = () => {
  svgEntityElems.clear(); svgConnElems.clear()
  const svgEl = svgContainer.value?.querySelector('svg')
  if (!svgEl || !diagramEntities.value.length) return

  const aliasToId = new Map<string, string>()
  for (const e of diagramEntities.value) if (e.display_alias) aliasToId.set(e.display_alias, e.artifact_id)
  if (!aliasToId.size) return

  for (const g of Array.from(svgEl.querySelectorAll<SVGGElement>('g'))) {
    let alias: string | null = null
    const de = g.getAttribute('data-entity')
    if (de && aliasToId.has(de)) alias = de
    if (!alias && g.id.startsWith('entity_') && aliasToId.has(g.id.slice(7))) alias = g.id.slice(7)
    if (!alias && g.id && aliasToId.has(g.id)) alias = g.id
    if (!alias) {
      const t = g.querySelector(':scope > title')?.textContent?.trim() ?? ''
      if (aliasToId.has(t)) alias = t
    }
    if (!alias) continue
    const artifactId = aliasToId.get(alias)!
    g.setAttribute('data-entity-id', artifactId)
    svgEntityElems.set(artifactId, g)
    g.addEventListener('click', (ev) => { ev.stopPropagation(); toggleEntityRemoval(artifactId) })
  }

  const aliasToConn = new Map<string, DiagramConnection>()
  for (const c of diagramConnections.value)
    if (c.source_alias && c.target_alias) aliasToConn.set(`${c.source_alias}:${c.target_alias}`, c)
  for (const g of Array.from(svgEl.querySelectorAll<SVGGElement>('g[data-entity-1]'))) {
    const a1 = g.getAttribute('data-entity-1') ?? ''; const a2 = g.getAttribute('data-entity-2') ?? ''
    const conn = aliasToConn.get(`${a1}:${a2}`) ?? aliasToConn.get(`${a2}:${a1}`)
    if (!conn) continue
    g.setAttribute('data-conn-id', conn.artifact_id)
    svgConnElems.set(conn.artifact_id, g)
    g.addEventListener('click', (ev) => { ev.stopPropagation(); toggleConn(conn.artifact_id) })
  }
  updateHighlights()
}

watch([svgHtml, diagramEntities, diagramConnections], attachInteractivity, { flush: 'post' })
// Re-run highlights when connection state changes
watch([toRemoveEntityIds, toRemoveConnIds, selectedNewConnIds], updateHighlights)

// ── Search / add ──────────────────────────────────────────────────────────────

const searchQuery = ref(''); const searchResults = ref<EntityDisplayInfo[]>([]); const showDropdown = ref(false)
let searchTimer: ReturnType<typeof setTimeout> | null = null

const onSearchInput = () => {
  if (searchTimer) clearTimeout(searchTimer)
  const q = searchQuery.value.trim()
  if (!q) { searchResults.value = []; showDropdown.value = false; return }
  searchTimer = setTimeout(() => {
    Effect.runPromise(svc.searchEntityDisplay(q, 20)).then(res => {
      searchResults.value = res.filter(r => !includedEntityIds.value.has(r.artifact_id) && !toAddEntityIds.value.has(r.artifact_id))
      showDropdown.value = searchResults.value.length > 0
    }).catch(() => {})
  }, 280)
}
const closeDropdown = () => { setTimeout(() => { showDropdown.value = false }, 150) }

const addEntity = async (entity: EntityDisplayInfo) => {
  if (includedEntityIds.value.has(entity.artifact_id) || toAddEntityIds.value.has(entity.artifact_id)) return
  entitiesToAdd.value = [...entitiesToAdd.value, entity]
  showDropdown.value = false; searchQuery.value = ''
  const conns = await Effect.runPromise(svc.getConnections(entity.artifact_id, 'any')).catch(() => [] as ConnectionRecord[])
  const map = new Map(allModelConns.value)
  const next = new Set(selectedNewConnIds.value)
  for (const conn of conns) {
    map.set(conn.artifact_id, conn)
    // Auto-include connections to existing (non-removed, non-to-add) entities
    const other = conn.source === entity.artifact_id ? conn.target : conn.source
    if (effectiveEntityIds.value.has(other) && !toAddEntityIds.value.has(other)) next.add(conn.artifact_id)
  }
  allModelConns.value = map; selectedNewConnIds.value = next
}

const removeToAddEntity = (id: string) => {
  entitiesToAdd.value = entitiesToAdd.value.filter(e => e.artifact_id !== id)
  const ne = new Set(expandedEntityIds.value); ne.delete(id); expandedEntityIds.value = ne
  const nc = new Set(selectedNewConnIds.value)
  for (const [cid, c] of allModelConns.value) if (c.source === id || c.target === id) nc.delete(cid)
  selectedNewConnIds.value = nc
}

// ── Load ──────────────────────────────────────────────────────────────────────

const load = async () => {
  if (!diagramId.value) return
  diagramDetail.run(svc.getDiagram(diagramId.value))
  svgHtml.value = null; svgLoading.value = true; svgError.value = null
  toRemoveEntityIds.value = new Set(); toRemoveConnIds.value = new Set()
  entitiesToAdd.value = []; selectedNewConnIds.value = new Set()
  expandedEntityIds.value = new Set()
  includedEntities.value = []; allModelConns.value = new Map(); includedConnIds.value = new Set()

  const [summaries, dconns, svg] = await Promise.all([
    Effect.runPromise(svc.getDiagramEntities(diagramId.value)).catch(() => [] as EntitySummary[]),
    Effect.runPromise(svc.getDiagramConnections(diagramId.value)).catch(() => [] as DiagramConnection[]),
    Effect.runPromise(svc.getDiagramSvg(diagramId.value)).catch((e) => { svgError.value = String(e); return null as null }),
  ])

  svgHtml.value = svg; svgLoading.value = false
  diagramEntities.value = summaries; diagramConnections.value = dconns

  const entityIdSet = new Set(summaries.map(s => s.artifact_id))
  includedEntities.value = summaries.map(s => ({
    artifact_id: s.artifact_id, name: s.name, artifact_type: s.artifact_type,
    domain: s.domain, subdomain: s.subdomain, status: s.status,
    display_alias: s.display_alias ?? '', element_type: s.artifact_type, element_label: s.name,
  }))

  const connArrays = await Promise.all(
    summaries.map(s => Effect.runPromise(svc.getConnections(s.artifact_id, 'any')).catch(() => [] as ConnectionRecord[]))
  )
  const map = new Map<string, ConnectionRecord>()
  const inc = new Set<string>()
  for (const cs of connArrays) for (const c of cs) {
    map.set(c.artifact_id, c)
    if (entityIdSet.has(c.source) && entityIdSet.has(c.target)) inc.add(c.artifact_id)
  }
  allModelConns.value = map; includedConnIds.value = inc
}

onMounted(load)

// ── Preview + Save ────────────────────────────────────────────────────────────

const preview = ref<DiagramPreviewResult | null>(null)
const previewBusy = ref(false)
const previewError = ref<string | null>(null)
const showPuml = ref(false)
const saveError = ref<string | null>(null)
const saveBusy = ref(false)

const finalEntityIds = computed(() => [
  ...includedEntities.value.filter(e => !toRemoveEntityIds.value.has(e.artifact_id)).map(e => e.artifact_id),
  ...entitiesToAdd.value.map(e => e.artifact_id),
])
const finalConnIds = computed(() => [
  ...[...includedConnIds.value].filter(id => !toRemoveConnIds.value.has(id)),
  ...[...selectedNewConnIds.value],
])

const doPreview = () => {
  if (!diagramDetail.data.value) return
  previewBusy.value = true; previewError.value = null; preview.value = null
  Effect.runPromise(svc.previewDiagram({
    diagram_type: diagramDetail.data.value.diagram_type,
    name: diagramDetail.data.value.name,
    entity_ids: finalEntityIds.value,
    connection_ids: finalConnIds.value,
  }))
    .then(r => { preview.value = r; previewBusy.value = false })
    .catch(e => { previewError.value = String(e); previewBusy.value = false })
}

const doSave = () => {
  if (!diagramDetail.data.value) return
  saveBusy.value = true; saveError.value = null
  Effect.runPromise(svc.editDiagram({
    artifact_id: diagramId.value,
    diagram_type: diagramDetail.data.value.diagram_type,
    name: diagramDetail.data.value.name,
    entity_ids: finalEntityIds.value,
    connection_ids: finalConnIds.value,
    dry_run: false,
  }))
    .then(r => {
      saveBusy.value = false
      if (r.wrote) router.push({ path: '/diagram', query: { id: diagramId.value } })
      else saveError.value = r.content ?? 'Verification failed'
    })
    .catch(e => { saveBusy.value = false; saveError.value = String(e) })
}

onUnmounted(() => {
  if (searchTimer) clearTimeout(searchTimer)
  containerRef.value?.removeEventListener('wheel', onWheel)
  window.removeEventListener('mousemove', onMouseMove)
  window.removeEventListener('mouseup', onMouseUp)
})
</script>

<template>
  <div class="page">
    <div class="page-hdr">
      <button class="back-link" @click="router.push({ path: '/diagram', query: { id: diagramId } })">← Back</button>
      <div class="hdr-info">
        <h1 class="pg-title">
          <span v-if="diagramDetail.loading.value" class="faded">Loading…</span>
          <span v-else-if="diagramDetail.data.value">{{ diagramDetail.data.value.name }}</span>
        </h1>
        <span v-if="diagramDetail.data.value" class="type-badge">
          {{ diagramDetail.data.value.diagram_type.replace('archimate-', '') }}
        </span>
      </div>
    </div>

    <div class="main-grid">
      <!-- SVG canvas -->
      <div ref="containerRef" class="img-container" @mousedown="onMouseDown" @dblclick="resetView">
        <div :style="canvasStyle">
          <div v-if="svgLoading" class="no-img">Rendering SVG…</div>
          <div v-else-if="svgError" class="no-img err-txt">{{ svgError }}</div>
          <div v-else-if="svgHtml" ref="svgContainer" class="svg-wrap" v-html="svgHtml" />
          <div v-else class="no-img">No diagram rendered.</div>
        </div>
        <button v-if="isTransformed" class="reset-btn" @click.stop="resetView">⊙ Reset</button>
        <div class="zoom-hint">Click entity to mark for removal · Click connection to toggle · Scroll/drag to navigate</div>
      </div>

      <!-- Sidebar -->
      <aside class="sidebar card">
        <!-- Search (always visible) -->
        <div class="sb-search">
          <div class="search-wrap">
            <input
              v-model="searchQuery" class="inp" placeholder="Search entities to add…"
              @input="onSearchInput" @blur="closeDropdown"
              @focus="() => { if (searchResults.length) showDropdown = true }"
            />
            <div v-if="showDropdown" class="dropdown">
              <button
                v-for="r in searchResults" :key="r.artifact_id"
                class="dd-item" @mousedown.prevent="addEntity(r)"
              >
                <span class="dd-glyph"><ArchimateTypeGlyph :type="toGlyphKey(r.element_type || r.artifact_type)" :size="14" /></span>
                <span class="dd-name">{{ r.name }}</span>
                <span class="dd-domain">{{ r.domain }}</span>
              </button>
            </div>
          </div>
        </div>

        <!-- Scrollable content -->
        <div class="sb-scroll">

          <!-- Entity list (non-removed existing + to-add) -->
          <div v-if="effectiveEntitiesList.length" class="sb-section">
            <div class="sb-sec-hdr">
              Entities <span class="sb-count">{{ effectiveEntitiesList.length }}</span>
            </div>

            <div v-for="entity in effectiveEntitiesList" :key="entity.artifact_id" class="ent-block">
              <!-- Entity row -->
              <div
                class="ent-row"
                :class="{ 'ent-row--new': isToAdd(entity.artifact_id) }"
                 @click="toggleExpand(entity.artifact_id)"
                 title="Expand connections"
              >
                <div
                  class="expand-indicator"
                  :class="{ expanded: expandedEntityIds.has(entity.artifact_id) }"
                >▶</div>
                <span class="dd-glyph"><ArchimateTypeGlyph :type="toGlyphKey(entity.element_type || entity.artifact_type)" :size="13" /></span>
                <span class="ent-name">{{ entity.name }}</span>
                <span v-if="isToAdd(entity.artifact_id)" class="new-tag">new</span>
                <button
                  v-if="isToAdd(entity.artifact_id)"
                  class="rm-btn" @click="removeToAddEntity(entity.artifact_id)" title="Remove"
                >×</button>
                <button
                  v-else
                  class="rm-btn rm-btn--entity" @click="toggleEntityRemoval(entity.artifact_id)" title="Mark for removal"
                >−</button>
              </div>

              <!-- Connection expansion -->
              <div class="list-entity" :class="{ 'is-expanded': expandedEntityIds.has(entity.artifact_id) }">
                <template v-for="[connsByType] in [[getConnsByType(entity.artifact_id)]]" :key="'ct-'+entity.artifact_id">
                  <div v-if="!connsByType.size" class="no-conns">No connections to diagram entities.</div>
                  <div v-for="[connType, group] in connsByType" :key="connType" class="conn-type-block">
                    <div class="conn-type-lbl">{{ connType }}</div>
                    <div class="conn-cols">
                      <div class="conn-col conn-col--inc">
                        <div class="col-hdr">Included</div>
                        <div
                          v-for="entry in group.included" :key="entry.conn.artifact_id"
                          class="conn-entry conn-entry--inc"
                          @click="toggleConn(entry.conn.artifact_id)"
                          title="Click to exclude"
                        >
                          <span class="dir-arrow">{{ entry.direction === 'out' ? '→' : '←' }}</span>
                          <span class="other-name">{{ entry.otherName }}</span>
                        </div>
                        <div v-if="!group.included.length" class="col-empty">—</div>
                      </div>
                      <div class="conn-col conn-col--excl">
                        <div class="col-hdr">Excluded</div>
                        <div
                          v-for="entry in group.excluded" :key="entry.conn.artifact_id"
                          class="conn-entry conn-entry--excl"
                          @click="toggleConn(entry.conn.artifact_id)"
                          title="Click to include"
                        >
                          <span class="dir-arrow">{{ entry.direction === 'out' ? '→' : '←' }}</span>
                          <span class="other-name">{{ entry.otherName }}</span>
                        </div>
                        <div v-if="!group.excluded.length" class="col-empty">—</div>
                      </div>
                    </div>
                  </div>
                </template>
              </div>
            </div>
          </div>

          <!-- For removal (entities only) -->
          <div v-if="toRemoveEntities.length" class="sb-section">
            <div class="sb-sec-hdr sb-sec-hdr--rm">
              For removal <span class="sb-count">{{ toRemoveEntities.length }}</span>
            </div>
            <div v-for="entity in toRemoveEntities" :key="entity.artifact_id" class="rm-row">
              <span class="dd-glyph rm-glyph"><ArchimateTypeGlyph :type="toGlyphKey(entity.element_type || entity.artifact_type)" :size="13" /></span>
              <span class="rm-name">{{ entity.name }}</span>
              <button class="undo-btn" @click="toggleEntityRemoval(entity.artifact_id)" title="Restore">↩</button>
            </div>
          </div>

          <div v-if="!effectiveEntitiesList.length && !toRemoveEntities.length" class="sb-hint">
            Loading diagram entities…
          </div>

          <!-- Actions -->
          <div class="sb-actions">
            <button class="btn-preview" :disabled="previewBusy || !diagramDetail.data.value" @click="doPreview">
              {{ previewBusy ? 'Rendering…' : 'Preview' }}
            </button>
            <button
              class="btn-save"
              :disabled="saveBusy || !preview || !diagramDetail.data.value"
              :title="!preview ? 'Run Preview first' : ''"
              @click="doSave"
            >
              {{ saveBusy ? 'Saving…' : 'Save Changes' }}
            </button>
            <div v-if="saveError" class="save-err">{{ saveError }}</div>
          </div>
        </div>
      </aside>
    </div>

    <!-- Preview (below) -->
    <div v-if="preview || previewBusy || previewError" class="preview-row">
      <div v-if="previewBusy" class="state-msg">Rendering preview…</div>
      <div v-if="previewError" class="state-err">{{ previewError }}</div>
      <template v-if="preview">
        <div v-for="w in preview.warnings" :key="w" class="warn-msg">{{ w }}</div>
        <img v-if="preview.image" :src="preview.image" class="preview-img" alt="Preview" />
        <div v-else class="state-msg">No image rendered.</div>
        <button class="toggle-src" @click="showPuml = !showPuml">{{ showPuml ? 'Hide' : 'Show' }} PUML</button>
        <pre v-if="showPuml" class="puml-src">{{ preview.puml }}</pre>
      </template>
    </div>
  </div>
</template>

<style scoped>
.page { max-width: 100%; }
.page-hdr { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
.back-link { font-size: 13px; color: #6b7280; background: none; border: none; cursor: pointer; padding: 0; flex-shrink: 0; }
.back-link:hover { color: #374151; }
.hdr-info { display: flex; align-items: center; gap: 10px; flex: 1; min-width: 0; }
.pg-title { font-size: 20px; font-weight: 700; margin: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.faded { color: #9ca3af; font-weight: 400; }
.type-badge { padding: 2px 8px; border-radius: 4px; font-size: 11px; background: #dbeafe; color: #1e40af; font-weight: 500; flex-shrink: 0; }

.main-grid { display: grid; grid-template-columns: 1fr 50%; gap: 16px; align-items: start; }
@media (max-width: 860px) { .main-grid { grid-template-columns: 1fr; } }

/* SVG canvas */
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

/* Sidebar */
.card { background: white; border-radius: 8px; border: 1px solid #e5e7eb; }
.sidebar { display: flex; flex-direction: column; position: sticky; top: 16px; max-height: calc(100vh - 80px); overflow: hidden; }

.sb-search { padding: 10px; border-bottom: 1px solid #f3f4f6; flex-shrink: 0; position: relative; z-index: 10; }
.search-wrap { position: relative; }
.inp { width: 100%; padding: 7px 10px; border-radius: 6px; border: 1px solid #d1d5db; font-size: 13px; outline: none; box-sizing: border-box; }
.inp:focus { border-color: #6366f1; }
.dropdown { position: absolute; top: calc(100% + 3px); left: 0; right: 0; background: white; border: 1px solid #d1d5db; border-radius: 6px; box-shadow: 0 4px 12px rgba(0,0,0,.12); z-index: 100; max-height: 240px; overflow-y: auto; }
.dd-item { display: flex; align-items: center; gap: 6px; width: 100%; text-align: left; padding: 7px 10px; background: none; border: none; border-bottom: 1px solid #f3f4f6; cursor: pointer; font-size: 13px; }
.dd-item:last-child { border-bottom: none; }
.dd-item:hover { background: #f0f7ff; }
.dd-glyph { display: flex; align-items: center; flex-shrink: 0; color: #4b5563; }
.dd-name { font-weight: 500; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dd-domain { font-size: 11px; color: #9ca3af; white-space: nowrap; }

.sb-scroll { flex: 1; overflow-y: auto; display: flex; flex-direction: column; min-height: 0; }

.sb-section { border-bottom: 1px solid #f3f4f6; }
.sb-sec-hdr { display: flex; align-items: center; gap: 5px; padding: 6px 10px 4px; font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: .06em; color: #6b7280; }
.sb-sec-hdr--rm { color: #dc2626; }
.sb-count { font-size: 10px; font-weight: 400; color: #9ca3af; }

/* Entity rows */
.ent-block { }
.ent-row { display: flex; align-items: center; gap: 4px; padding: 3px 8px; cursor: pointer; }
.ent-row:hover { background: #f9fafb; }
.ent-row--new { opacity: 0.75; }
.ent-row--new:hover { background: #f0fdf4; }
.list-entity { display: none; }
.list-entity.is-expanded { display: block; }
.ent-block:has(.conn-entry--excl) .ent-row { background: #ffcbcb; }
.expand-indicator { background: none; border: none; font-size: 9px; color: #9ca3af; padding: 1px 2px; transition: transform 0.12s; flex-shrink: 0; line-height: 1; }
.expand-indicator:hover { color: #6b7280; }
.expand-indicator.expanded { transform: rotate(90deg); }
.ent-name { font-size: 12px; font-weight: 500; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #374151; }
.new-tag { font-size: 9px; font-weight: 600; color: #059669; background: #d1fae5; padding: 1px 4px; border-radius: 3px; white-space: nowrap; flex-shrink: 0; }
.rm-btn { background: none; border: none; cursor: pointer; color: #d1d5db; font-size: 14px; padding: 0 2px; line-height: 1; flex-shrink: 0; }
.rm-btn:hover { color: #dc2626; }
.rm-btn--entity:hover { color: #ef4444; }

/* Connection type expansion */
.conn-type-block { padding: 4px 8px 4px 20px; border-top: 1px solid #f9fafb; }
.conn-type-lbl { font-size: 10px; font-weight: 700; color: #6366f1; text-transform: uppercase; letter-spacing: .04em; margin-bottom: 3px; }
.conn-cols { display: grid; grid-template-columns: 1fr 1fr; gap: 4px; }
.conn-col { display: flex; flex-direction: column; gap: 1px; }
.col-hdr { font-size: 9px; font-weight: 700; text-transform: uppercase; letter-spacing: .04em; padding: 1px 3px; margin-bottom: 1px; }
.conn-col--inc .col-hdr { color: #059669; }
.conn-col--excl .col-hdr { color: #9ca3af; }
.conn-entry { display: flex; align-items: center; gap: 3px; padding: 2px 4px; border-radius: 3px; cursor: pointer; font-size: 11px; overflow: hidden; }
.conn-entry--inc { background: #f0fdf4; color: #374151; }
.conn-entry--inc:hover { background: #dcfce7; }
.conn-entry--excl { background: #f9fafb; color: #9ca3af; }
.conn-entry--excl:hover { background: #f3f4f6; color: #374151; }
.dir-arrow { font-size: 10px; flex-shrink: 0; color: #6b7280; }
.other-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.col-empty { font-size: 10px; color: #e5e7eb; padding: 2px 4px; }
.no-conns { font-size: 11px; color: #9ca3af; padding: 4px 8px 4px 20px; }

/* For removal */
.rm-row { display: flex; align-items: center; gap: 5px; padding: 4px 10px; font-size: 12px; }
.rm-glyph { color: #dc2626; opacity: 0.7; }
.rm-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #374151; }
.undo-btn { background: none; border: none; cursor: pointer; color: #9ca3af; font-size: 13px; padding: 0 2px; flex-shrink: 0; }
.undo-btn:hover { color: #374151; }

.sb-hint { padding: 12px 10px; font-size: 11px; color: #9ca3af; }

/* Actions */
.sb-actions { padding: 10px; display: flex; flex-direction: column; gap: 6px; margin-top: auto; border-top: 1px solid #f3f4f6; flex-shrink: 0; }
.btn-preview { width: 100%; padding: 7px 12px; background: #f3f4f6; color: #1d4ed8; border: 1px solid #bfdbfe; border-radius: 6px; font-size: 13px; cursor: pointer; font-weight: 500; }
.btn-preview:hover:not(:disabled) { background: #eff6ff; }
.btn-save { width: 100%; padding: 7px 12px; background: #2563eb; color: white; border: none; border-radius: 6px; font-size: 13px; font-weight: 500; cursor: pointer; }
.btn-save:hover:not(:disabled) { background: #1d4ed8; }
.btn-preview:disabled, .btn-save:disabled { opacity: .5; cursor: not-allowed; }
.save-err { font-size: 12px; color: #dc2626; }

/* Preview */
.preview-row { margin-top: 16px; }
.state-msg { font-size: 13px; color: #6b7280; }
.state-err { font-size: 13px; color: #dc2626; margin-top: 6px; }
.warn-msg { font-size: 12px; color: #b45309; margin-bottom: 4px; }
.preview-img { max-width: 100%; border-radius: 6px; border: 1px solid #e5e7eb; display: block; margin-top: 8px; }
.toggle-src { margin-top: 10px; font-size: 12px; color: #2563eb; background: none; border: none; cursor: pointer; padding: 0; }
.toggle-src:hover { text-decoration: underline; }
.puml-src { font-size: 11px; font-family: monospace; white-space: pre-wrap; margin-top: 8px; background: #1e293b; color: #e2e8f0; border-radius: 6px; padding: 10px; max-height: 400px; overflow-y: auto; }
</style>
