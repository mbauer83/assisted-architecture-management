<script setup lang="ts">
import { inject, onMounted, onUnmounted, watch, computed, ref, nextTick } from 'vue'
import { useRoute, useRouter, RouterLink } from 'vue-router'
import { Effect } from 'effect'
import { modelServiceKey } from '../keys'
import { useAsync } from '../composables/useAsync'
import type { DiagramDetail, EntitySummary, EntityDetail, DiagramConnection } from '../../domain'
import { getDomainColor } from '../lib/domains'
import ArchimateTypeGlyph from '../components/ArchimateTypeGlyph.vue'
import DownloadMenu from '../components/DownloadMenu.vue'

const svc = inject(modelServiceKey)!
const route = useRoute()
const router = useRouter()
const adminMode = ref(false)

const diagramId = computed(() => (route.query.id as string | undefined) ?? '')
const detail = useAsync<DiagramDetail>()
const showSource = ref(false)
const deleteBusy = ref(false)
const deleteError = ref<string | null>(null)
const deletePreview = ref<{ content: string | null; warnings: string[] } | null>(null)
const confirmDelete = ref(false)

const diagramEntities = ref<EntitySummary[]>([])
const diagramConnections = ref<DiagramConnection[]>([])
const selectedEntity = ref<EntityDetail | null>(null)
const selectedId = ref<string | null>(null)
const selectedConnection = ref<DiagramConnection | null>(null)
const isGlobalDiagram = computed(() => detail.data.value?.is_global ?? false)
const deleteFn = computed(() =>
  (isGlobalDiagram.value && adminMode.value) ? svc.adminDeleteDiagram : svc.deleteDiagram,
)

// ── SVG rendering ─────────────────────────────────────────────────────────────

const svgHtml = ref<string | null>(null)
const svgLoading = ref(false)
const svgError = ref<string | null>(null)
const svgContainer = ref<HTMLElement | null>(null)
const svgNodeElems = ref(new Map<string, Element>())
const prevHighlighted = ref<Element | null>(null)
let _interactivityController: AbortController | null = null
let _attachRun = 0

const load = () => {
  if (!diagramId.value) return
  detail.loading.value = true
  detail.error.value = null
  svgHtml.value = null; svgLoading.value = true; svgError.value = null
  Effect.runPromise(svc.getDiagramContext(diagramId.value))
    .then((context) => {
      detail.data.value = context.diagram
      detail.loading.value = false
      diagramEntities.value = context.entities
        .slice()
        .sort((a, b) => a.domain.localeCompare(b.domain) || a.artifact_type.localeCompare(b.artifact_type) || a.name.localeCompare(b.name))
      diagramConnections.value = context.connections.slice()
    })
    .catch((e) => {
      detail.error.value = String(e)
      detail.loading.value = false
      diagramEntities.value = []
      diagramConnections.value = []
    })
  Effect.runPromise(svc.getDiagramSvg(diagramId.value))
    .then((svg) => { svgHtml.value = svg; svgLoading.value = false })
    .catch((e) => { svgError.value = String(e); svgLoading.value = false })
}

onMounted(() => {
  Effect.runPromise(svc.getServerInfo())
    .then((info: any) => { adminMode.value = Boolean(info?.admin_mode) })
    .catch(() => {})
})

const addConnectionHitAreas = (group: SVGGElement) => {
  for (const oldHit of Array.from(group.querySelectorAll('[data-conn-hit]'))) oldHit.remove()

  const segments = Array.from(group.querySelectorAll<SVGElement>('path, line, polyline'))
  for (const segment of segments) {
    if (segment.closest('[data-entity-id]')) continue
    const tag = segment.tagName.toLowerCase()
    const hit = document.createElementNS('http://www.w3.org/2000/svg', tag)
    for (const attr of Array.from(segment.attributes)) {
      if (attr.name === 'id' || attr.name === 'class' || attr.name === 'style') continue
      hit.setAttribute(attr.name, attr.value)
    }
    const strokeWidth = Number(segment.getAttribute('stroke-width') ?? '')
    const hitWidth = Math.max(Number.isFinite(strokeWidth) ? strokeWidth * 4 : 0, 12)
    hit.setAttribute('data-conn-hit', 'true')
    hit.setAttribute('fill', 'none')
    hit.setAttribute('stroke', 'transparent')
    hit.setAttribute('stroke-width', String(hitWidth))
    hit.setAttribute('pointer-events', 'stroke')
    hit.setAttribute('vector-effect', 'non-scaling-stroke')
    group.insertBefore(hit, group.firstChild)
  }
}

// Build alias→artifact_id map and attach click handlers after SVG + entities load
const attachInteractivity = async () => {
  const runId = ++_attachRun
  _interactivityController?.abort()
  _interactivityController = new AbortController()
  const { signal } = _interactivityController
  svgNodeElems.value.clear()
  prevHighlighted.value = null
  await nextTick()
  await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()))
  if (runId !== _attachRun || signal.aborted) return
  const svgEl = svgContainer.value?.querySelector('svg')
  if (!svgEl || !diagramEntities.value.length) return

  const aliasToId = new Map<string, string>()
  for (const e of diagramEntities.value) {
    if (e.display_alias) aliasToId.set(e.display_alias, e.artifact_id)
  }
  if (!aliasToId.size) return

  for (const g of Array.from(svgEl.querySelectorAll<SVGGElement>('g'))) {
    let alias: string | null = null
    // Strategy 1: PlantUML >= 1.2022 sets data-entity="ALIAS" on entity groups
    const de = g.getAttribute('data-entity')
    if (de && aliasToId.has(de)) alias = de
    // Strategy 2: PlantUML id="entity_ALIAS"
    if (!alias && g.id.startsWith('entity_') && aliasToId.has(g.id.slice(7))) alias = g.id.slice(7)
    // Strategy 3: plain id match (older PlantUML or Graphviz direct alias as id)
    if (!alias && g.id && aliasToId.has(g.id)) alias = g.id
    // Strategy 4: Graphviz <title> child
    if (!alias) {
      const t = g.querySelector(':scope > title')?.textContent?.trim() ?? ''
      if (aliasToId.has(t)) alias = t
    }
    // Strategy 5: PlantUML cluster_ prefix for composite/container entity groups
    if (!alias && g.id.startsWith('cluster_') && aliasToId.has(g.id.slice(8))) alias = g.id.slice(8)
    if (!alias) continue

    const artifactId = aliasToId.get(alias)!
    g.setAttribute('data-entity-id', artifactId)
    svgNodeElems.value.set(artifactId, g)
    g.addEventListener('click', (ev) => { ev.stopPropagation(); selectEntity(artifactId) }, { signal })
  }

  // Link groups
  const aliasToConn = new Map<string, DiagramConnection>()
  for (const c of diagramConnections.value) {
    if (c.source_alias && c.target_alias) aliasToConn.set(`${c.source_alias}:${c.target_alias}`, c)
  }
  for (const g of Array.from(svgEl.querySelectorAll<SVGGElement>('g[data-entity-1]'))) {
    const a1 = g.getAttribute('data-entity-1') ?? ''
    const a2 = g.getAttribute('data-entity-2') ?? ''
    const conn = aliasToConn.get(`${a1}:${a2}`) ?? aliasToConn.get(`${a2}:${a1}`)
    if (!conn) continue
    addConnectionHitAreas(g)
    g.setAttribute('data-conn-id', conn.artifact_id)
    g.addEventListener('click', (ev) => { ev.stopPropagation(); selectConnection(conn, g) }, { signal })
  }
}

watch([svgHtml, diagramEntities, diagramConnections], () => { void attachInteractivity() }, { flush: 'post' })

// Sync sidebar selection → SVG highlight
watch(selectedId, (newId) => {
  prevHighlighted.value?.classList.remove('svg-selected')
  prevHighlighted.value = null
  if (!newId) return
  const el = svgNodeElems.value.get(newId) ?? null
  el?.classList.add('svg-selected')
  prevHighlighted.value = el
})

const clearConnection = () => {
  svgContainer.value?.querySelector('.svg-conn-selected')?.classList.remove('svg-conn-selected')
  selectedConnection.value = null
}
const selectConnection = (conn: DiagramConnection, el: SVGGElement) => {
  if (selectedId.value) selectedId.value = null
  const same = selectedConnection.value?.artifact_id === conn.artifact_id
  clearConnection()
  if (!same) { selectedConnection.value = conn; el.classList.add('svg-conn-selected') }
}
const selectEntity = (id: string) => {
  clearConnection()
  if (selectedId.value === id) { selectedId.value = null; selectedEntity.value = null; return }
  selectedId.value = id; selectedEntity.value = null
  Effect.runPromise(svc.getEntity(id)).then((d) => { selectedEntity.value = d }).catch(() => {})
}

const toGlyphKey = (t: string) => t.replace(/[A-Z]/g, (c, i) => (i > 0 ? '-' : '') + c.toLowerCase())

// ── Pan / Zoom ────────────────────────────────────────────────────────────────

const containerRef = ref<HTMLElement | null>(null)
const scale = ref(1)
const tx = ref(0)
const ty = ref(0)
const fitScale = ref(1)
const fitTx = ref(0)
const fitTy = ref(0)
let resizeObserver: ResizeObserver | null = null
let dragging = false
let drag = { x: 0, y: 0, tx: 0, ty: 0 }

const canvasStyle = computed(() => ({
  transform: `translate(${tx.value}px, ${ty.value}px) scale(${scale.value})`,
  transformOrigin: '0 0',
  willChange: 'transform',
  display: 'inline-block',
}))
const isTransformed = computed(() =>
  Math.abs(scale.value - fitScale.value) > 0.001
  || Math.abs(tx.value - fitTx.value) > 0.5
  || Math.abs(ty.value - fitTy.value) > 0.5,
)

const fitDiagramToViewport = async () => {
  await nextTick()
  const container = containerRef.value
  const svgEl = svgContainer.value?.querySelector('svg') as SVGSVGElement | null
  if (!container || !svgEl) return

  let contentWidth = 0
  let contentHeight = 0
  let contentX = 0
  let contentY = 0

  try {
    const graphRoot = svgEl.querySelector('g')
    const bbox = (graphRoot ?? svgEl).getBBox()
    contentX = bbox.x
    contentY = bbox.y
    contentWidth = bbox.width
    contentHeight = bbox.height
  } catch {
    const viewBox = svgEl.viewBox?.baseVal
    if (viewBox && viewBox.width > 0 && viewBox.height > 0) {
      contentX = viewBox.x
      contentY = viewBox.y
      contentWidth = viewBox.width
      contentHeight = viewBox.height
    } else {
      const widthAttr = Number(svgEl.getAttribute('width') ?? '')
      const heightAttr = Number(svgEl.getAttribute('height') ?? '')
      contentWidth = Number.isFinite(widthAttr) && widthAttr > 0 ? widthAttr : svgEl.clientWidth
      contentHeight = Number.isFinite(heightAttr) && heightAttr > 0 ? heightAttr : svgEl.clientHeight
    }
  }

  if (!contentWidth || !contentHeight) return

  const rect = container.getBoundingClientRect()
  const horizontalPadding = 24
  const topPadding = Math.min(Math.max(rect.height * 0.035, 16), 40)
  const bottomPadding = 24
  const availableWidth = Math.max(rect.width - horizontalPadding * 2, 80)
  const availableHeight = Math.max(rect.height - topPadding - bottomPadding, 80)
  const fittedScale = Math.min(availableWidth / contentWidth, availableHeight / contentHeight)

  if (!Number.isFinite(fittedScale) || fittedScale <= 0) return

  fitScale.value = fittedScale
  fitTx.value = (rect.width - contentWidth * fittedScale) / 2 - contentX * fittedScale
  fitTy.value = topPadding - contentY * fittedScale
  scale.value = fitScale.value
  tx.value = fitTx.value
  ty.value = fitTy.value
}

const onWheel = (e: WheelEvent) => {
  e.preventDefault()
  const factor = e.deltaY < 0 ? 1.15 : 1 / 1.15
  const ns = Math.min(8, Math.max(0.2, scale.value * factor))
  const r = ns / scale.value
  const rect = containerRef.value!.getBoundingClientRect()
  tx.value = (e.clientX - rect.left) * (1 - r) + tx.value * r
  ty.value = (e.clientY - rect.top) * (1 - r) + ty.value * r
  scale.value = ns
}

const onMouseDown = (e: MouseEvent) => {
  if ((e.target as HTMLElement).closest('[data-entity-id], [data-conn-id], button, a')) return
  dragging = true
  drag = { x: e.clientX, y: e.clientY, tx: tx.value, ty: ty.value }
  window.addEventListener('mousemove', onMouseMove)
  window.addEventListener('mouseup', onMouseUp)
}
const onMouseMove = (e: MouseEvent) => {
  if (!dragging) return
  tx.value = drag.tx + (e.clientX - drag.x)
  ty.value = drag.ty + (e.clientY - drag.y)
}
const onMouseUp = () => {
  dragging = false
  window.removeEventListener('mousemove', onMouseMove)
  window.removeEventListener('mouseup', onMouseUp)
}
const resetView = () => {
  scale.value = fitScale.value
  tx.value = fitTx.value
  ty.value = fitTy.value
}

const previewDelete = () => {
  if (!diagramId.value) return
  deleteBusy.value = true
  deleteError.value = null
  deletePreview.value = null
  confirmDelete.value = true
  Effect.runPromise(deleteFn.value({ artifact_id: diagramId.value, dry_run: true })).then((r: any) => {
    deleteBusy.value = false
    deletePreview.value = { content: r.content, warnings: [...r.warnings] }
  }).catch((e) => {
    deleteBusy.value = false
    deleteError.value = String(e)
  })
}

const cancelDelete = () => {
  confirmDelete.value = false
  deletePreview.value = null
  deleteError.value = null
}

const executeDelete = () => {
  if (!diagramId.value) return
  deleteBusy.value = true
  deleteError.value = null
  Effect.runPromise(deleteFn.value({ artifact_id: diagramId.value, dry_run: false })).then((r: any) => {
    deleteBusy.value = false
    if (r.wrote) router.push(isGlobalDiagram.value ? '/global/diagrams' : '/diagrams')
    else deleteError.value = r.content ?? 'Delete failed'
  }).catch((e) => {
    deleteBusy.value = false
    deleteError.value = String(e)
  })
}

watch(containerRef, (el, prev) => {
  prev?.removeEventListener('wheel', onWheel)
  el?.addEventListener('wheel', onWheel, { passive: false })
  resizeObserver?.disconnect()
  resizeObserver = null
  if (!el) return
  resizeObserver = new ResizeObserver(() => {
    if (!isTransformed.value) void fitDiagramToViewport()
  })
  resizeObserver.observe(el)
})
watch(() => svgHtml.value, (svg) => {
  if (svg) void fitDiagramToViewport()
})
onMounted(load)
watch(diagramId, load)
onUnmounted(() => {
  resizeObserver?.disconnect()
  containerRef.value?.removeEventListener('wheel', onWheel)
  window.removeEventListener('mousemove', onMouseMove)
  window.removeEventListener('mouseup', onMouseUp)
  _interactivityController?.abort()
})
</script>

<template>
  <div class="page">
    <div class="page-hdr">
      <RouterLink to="/diagrams" class="back">← Diagrams</RouterLink>
      <h1 v-if="detail.data.value" class="pg-title">{{ detail.data.value.name }}</h1>
      <DownloadMenu v-if="detail.data.value" :diagram-id="diagramId" :diagram-name="detail.data.value.name" />
      <RouterLink v-if="detail.data.value" :to="{ path: '/diagram/edit', query: { id: diagramId } }" class="edit-btn">Edit</RouterLink>
      <button
        v-if="detail.data.value && (!isGlobalDiagram || adminMode)"
        class="delete-btn"
        @click="previewDelete"
      >Delete{{ isGlobalDiagram && adminMode ? ' ⚠' : '' }}</button>
    </div>

    <div v-if="detail.loading.value" class="state">Loading…</div>
    <div v-else-if="detail.error.value" class="state err">{{ detail.error.value }}</div>

    <template v-else-if="detail.data.value">
      <div class="meta">
        <span class="type-badge">{{ detail.data.value.diagram_type.replace('archimate-', '') }}</span>
        <span class="status-badge" :class="`status--${detail.data.value.status}`">{{ detail.data.value.status }}</span>
        <span class="mono faded">v{{ detail.data.value.version }} · {{ detail.data.value.artifact_id }}</span>
      </div>

      <div class="main-grid">
        <!-- Diagram: pan + zoom + interactive SVG -->
        <div ref="containerRef" class="img-container" @mousedown="onMouseDown" @dblclick="resetView">
          <div :style="canvasStyle">
            <div v-if="svgLoading" class="no-img">Rendering SVG…</div>
            <div v-else-if="svgError" class="no-img err-txt">{{ svgError }}</div>
            <div v-else-if="svgHtml" ref="svgContainer" class="svg-wrap" v-html="svgHtml" />
            <div v-else class="no-img">No diagram rendered.</div>
          </div>
          <button v-if="isTransformed" class="reset-btn" @click.stop="resetView" title="Reset view">⊙ Reset</button>
          <div class="zoom-hint">Scroll to zoom · Drag to pan · Click entity to inspect · Double-click to reset</div>
        </div>

        <!-- Sidebar: entity list + inline detail -->
        <aside class="sidebar card">
          <div class="sb-hdr">
            <span class="sb-title">Entities</span>
            <span class="sb-count">{{ diagramEntities.length }}</span>
          </div>
          <ul class="ent-list">
            <li
              v-for="e in diagramEntities" :key="e.artifact_id"
              class="ent-item" :class="{ 'ent--active': selectedId === e.artifact_id }"
              @click="selectEntity(e.artifact_id)"
            >
              <span class="ent-glyph" :title="e.artifact_type">
                <ArchimateTypeGlyph :type="toGlyphKey(e.artifact_type)" :size="13" />
              </span>
              <span class="ent-dot" :style="{ background: getDomainColor(e.domain) }" />
              <span class="ent-name">{{ e.name }}</span>
            </li>
          </ul>

          <!-- Inline entity detail — no page scroll needed -->
          <div v-if="selectedConnection" class="ent-det">
            <div class="det-hdr">
              <span class="det-name">{{ selectedConnection.conn_type }}</span>
              <button class="det-close" @click="clearConnection()">×</button>
            </div>
            <div class="conn-flow">{{ selectedConnection.source_name }} → {{ selectedConnection.target_name }}</div>
            <div v-if="selectedConnection.content_text?.trim()" class="det-content">{{ selectedConnection.content_text }}</div>
          </div>
          <div v-if="selectedId && !selectedEntity" class="ent-det ent-det--loading">Loading…</div>
          <div v-if="selectedEntity" class="ent-det">
            <div class="det-hdr">
              <RouterLink
                :to="{ path: '/entity', query: { id: selectedEntity.artifact_id } }"
                class="det-name"
              >{{ selectedEntity.name }}</RouterLink>
              <button class="det-close" @click="selectEntity(selectedId!)">×</button>
            </div>
            <div class="det-chips">
              <span class="chip" :class="`domain--${selectedEntity.domain}`">{{ selectedEntity.domain }}</span>
              <span class="chip" :class="`status--${selectedEntity.status}`">{{ selectedEntity.status }}</span>
              <span class="chip chip-type">{{ selectedEntity.artifact_type }}</span>
            </div>
            <div v-if="selectedEntity.content_html" class="det-content markdown-body" v-html="selectedEntity.content_html" />
            <RouterLink
              :to="{ path: '/graph', query: { id: selectedEntity.artifact_id } }"
              class="explore-lnk"
            >Explore in graph →</RouterLink>
          </div>
        </aside>
      </div>

      <div v-if="confirmDelete" class="delete-panel">
        <div class="delete-title">Delete Diagram</div>
        <div class="delete-text">
          Deletion removes the diagram source file and any rendered PNG/SVG siblings.
        </div>
        <div v-if="deletePreview?.warnings.length" class="preview-warnings">
          <div v-for="w in deletePreview.warnings" :key="w" class="preview-warn">{{ w }}</div>
        </div>
        <pre v-if="deletePreview?.content" class="delete-preview">{{ deletePreview.content }}</pre>
        <pre v-if="deleteError" class="state err state-block">{{ deleteError }}</pre>
        <div class="delete-actions">
          <button class="toggle-btn" :disabled="deleteBusy" @click="cancelDelete">Cancel</button>
          <button class="delete-confirm-btn" :disabled="deleteBusy" @click="executeDelete">
            {{ deleteBusy ? 'Deleting…' : 'Delete Diagram' }}
          </button>
        </div>
      </div>

      <div v-if="detail.data.value.puml_source" class="src-row">
        <button class="toggle-btn" @click="showSource = !showSource">
          {{ showSource ? 'Hide' : 'Show' }} PUML source
        </button>
        <pre v-if="showSource" class="puml-src">{{ detail.data.value.puml_source }}</pre>
      </div>
    </template>
  </div>
</template>

<style scoped>
.page { max-width: 100%; }
.page-hdr { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
.back { font-size: 13px; color: #6b7280; } .back:hover { color: #374151; text-decoration: none; }
.pg-title { font-size: 20px; font-weight: 700; flex: 1; margin: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.edit-btn { padding: 5px 16px; background: #f3f4f6; border: 1px solid #d1d5db; border-radius: 6px; font-size: 13px; font-weight: 500; color: #374151; text-decoration: none; flex-shrink: 0; } .edit-btn:hover { background: #e5e7eb; }
.delete-btn { padding: 5px 16px; background: #fef2f2; border: 1px solid #fecaca; border-radius: 6px; font-size: 13px; font-weight: 600; color: #b91c1c; cursor: pointer; flex-shrink: 0; }
.delete-btn:hover { background: #fee2e2; }
.meta { display: flex; align-items: center; gap: 8px; margin-bottom: 14px; font-size: 12px; }
.faded { color: #9ca3af; } .mono { font-family: monospace; }
.state { color: #6b7280; } .err { color: #dc2626; }
.state-block { white-space: pre-wrap; overflow-x: auto; }
.type-badge { padding: 2px 8px; border-radius: 4px; font-size: 11px; background: #dbeafe; color: #1e40af; font-weight: 500; }

.main-grid { display: grid; grid-template-columns: 1fr 260px; gap: 16px; align-items: start; }
@media (max-width: 800px) { .main-grid { grid-template-columns: 1fr; } }

.img-container {
  position: relative; overflow: hidden; background: #f8fafc;
  border: 1px solid #e5e7eb; border-radius: 8px;
  min-height: 400px; height: clamp(420px, 78vh, 980px);
  cursor: grab; user-select: none;
}
@media (max-width: 800px) { .img-container { height: clamp(360px, 68vh, 820px); } }
.img-container:active { cursor: grabbing; }
.no-img { padding: 60px 40px; text-align: center; color: #9ca3af; font-size: 13px; }
.err-txt { color: #dc2626; }
.svg-wrap :deep(svg) { display: block; max-width: none; }
.svg-wrap :deep([data-entity-id]) { cursor: pointer; }
.svg-wrap :deep([data-entity-id]:hover) > :not(title) { opacity: 0.85; }
.svg-wrap :deep([data-entity-id]:hover) polygon,
.svg-wrap :deep([data-entity-id]:hover) rect,
.svg-wrap :deep([data-entity-id]:hover) polyline,
.svg-wrap :deep([data-entity-id]:hover) ellipse { stroke: #2563eb !important; stroke-width: 2 !important; }
.svg-wrap :deep(.svg-selected) polygon,
.svg-wrap :deep(.svg-selected) rect,
.svg-wrap :deep(.svg-selected) polyline,
.svg-wrap :deep(.svg-selected) ellipse { stroke: #2563eb !important; stroke-width: 2.5 !important; }
.svg-wrap :deep([data-conn-id]) { cursor: pointer; }
.svg-wrap :deep([data-conn-id]:hover) path, .svg-wrap :deep([data-conn-id]:hover) polygon { stroke: #2563eb !important; stroke-width: 2 !important; }
.svg-wrap :deep(.svg-conn-selected) path, .svg-wrap :deep(.svg-conn-selected) polygon { stroke: #2563eb !important; stroke-width: 2.5 !important; }
.reset-btn { position: absolute; top: 8px; right: 8px; padding: 4px 10px; background: rgba(255,255,255,.92); border: 1px solid #d1d5db; border-radius: 5px; font-size: 12px; cursor: pointer; color: #374151; }
.reset-btn:hover { background: white; }
.zoom-hint { position: absolute; bottom: 6px; left: 50%; transform: translateX(-50%); font-size: 11px; color: #9ca3af; background: rgba(255,255,255,.8); padding: 2px 8px; border-radius: 4px; pointer-events: none; white-space: nowrap; }

.card { background: white; border-radius: 8px; border: 1px solid #e5e7eb; }
.delete-panel { margin-top: 16px; padding: 16px; background: #fff7f7; border: 1px solid #fecaca; border-radius: 8px; }
.delete-title { font-size: 14px; font-weight: 700; color: #991b1b; margin-bottom: 6px; }
.delete-text { font-size: 13px; color: #7f1d1d; margin-bottom: 10px; }
.delete-preview {
  font-size: 11px; color: #374151; white-space: pre-wrap; max-height: 260px; overflow-y: auto;
  font-family: monospace; background: white; border: 1px solid #fecaca; border-radius: 6px; padding: 10px; margin-bottom: 10px;
}
.delete-actions { display: flex; gap: 8px; justify-content: flex-end; }
.delete-confirm-btn {
  padding: 5px 16px; background: #dc2626; border: none; border-radius: 6px; font-size: 13px; font-weight: 600; color: white; cursor: pointer;
}
.delete-confirm-btn:hover:not(:disabled) { background: #b91c1c; }
.delete-confirm-btn:disabled { opacity: .5; cursor: not-allowed; }
.sidebar { display: flex; flex-direction: column; position: sticky; top: 16px; }
.sb-hdr { display: flex; align-items: center; justify-content: space-between; padding: 10px 12px 8px; border-bottom: 1px solid #f3f4f6; }
.sb-title { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: .05em; color: #6b7280; }
.sb-count { font-size: 11px; color: #9ca3af; }
.ent-list { list-style: none; overflow-y: auto; max-height: 320px; padding: 4px 0; margin: 0; }
.ent-item { display: flex; align-items: center; gap: 5px; padding: 5px 10px; cursor: pointer; font-size: 12px; color: #374151; }
.ent-item:hover { background: #f9fafb; }
.ent--active { background: #eff6ff; color: #1d4ed8; }
.ent-glyph { display: flex; align-items: center; flex-shrink: 0; color: #6b7280; }
.ent-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
.ent-name { flex: 1; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.ent-det { padding: 10px 12px 12px; border-top: 1px solid #e5e7eb; }
.conn-flow { font-size: 12px; color: #374151; margin-bottom: 6px; }
.ent-det--loading { color: #9ca3af; font-size: 12px; }
.det-hdr { display: flex; align-items: flex-start; gap: 4px; margin-bottom: 6px; }
.det-name { font-size: 13px; font-weight: 600; color: #1e293b; flex: 1; line-height: 1.3; }
.det-name:hover { text-decoration: underline; }
.det-close { background: none; border: none; font-size: 16px; cursor: pointer; color: #9ca3af; line-height: 1; padding: 0 2px; flex-shrink: 0; } .det-close:hover { color: #374151; }
.det-chips { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 8px; }
.chip { font-size: 10px; padding: 2px 6px; border-radius: 3px; font-weight: 500; background: #f3f4f6; color: #374151; }
.det-content { font-size: 12px; line-height: 1.5; color: #374151; margin-bottom: 8px; max-height: 220px; overflow-y: auto; }
.det-content :deep(p) { margin: 0.35rem 0; }
.explore-lnk { font-size: 12px; color: #2563eb; } .explore-lnk:hover { text-decoration: underline; }
.src-row { margin-top: 16px; }
.toggle-btn { padding: 5px 14px; border-radius: 6px; border: 1px solid #d1d5db; background: white; font-size: 13px; cursor: pointer; color: #374151; margin-bottom: 8px; } .toggle-btn:hover { background: #f9fafb; }
.puml-src { background: #1e293b; color: #e2e8f0; padding: 16px; border-radius: 8px; font-size: 12px; line-height: 1.5; overflow-x: auto; white-space: pre; }
</style>
