<script setup lang="ts">
import { inject, onMounted, onUnmounted, watch, computed, ref, nextTick } from 'vue'
import { useRoute, useRouter, RouterLink } from 'vue-router'
import { Effect, Exit } from 'effect'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { modelServiceKey } from '../keys'
import type { DiagramContext, EntityDetail, DiagramConnection, WriteResult } from '../../domain'
import type { RepoError } from '../../ports/ModelRepository'
import type { NotFoundError } from '../../domain'
import type { MarkdownError } from '../../application/MarkdownService'
import { getDomainColor } from '../lib/domains'
import ArchimateTypeGlyph from '../components/ArchimateTypeGlyph.vue'
import DownloadMenu from '../components/DownloadMenu.vue'
import { useQuery } from '../composables/useQuery'
import { useMutation } from '../composables/useMutation'
import { toGlyphKey } from '../lib/glyphKey'

const svc = inject(modelServiceKey)!
const route = useRoute()
const router = useRouter()
const adminMode = ref(false)

const diagramId = computed(() => (route.query.id as string | undefined) ?? '')

const contextQuery = useQuery<DiagramContext, RepoError | NotFoundError>()
const svgQuery = useQuery<string, RepoError>()
const entityQuery = useQuery<EntityDetail, RepoError | NotFoundError | MarkdownError>()
const deleteMutation = useMutation<WriteResult, RepoError>()

const detail = computed(() => contextQuery.data.value?.diagram ?? null)
const diagramEntities = computed(() =>
  (contextQuery.data.value?.entities ?? [])
    .slice()
    .sort((a, b) => a.domain.localeCompare(b.domain) || a.artifact_type.localeCompare(b.artifact_type) || a.name.localeCompare(b.name))
)
const diagramConnections = computed(() => contextQuery.data.value?.connections ?? [])

const svgHtml = computed(() =>
  svgQuery.data.value
    ? DOMPurify.sanitize(svgQuery.data.value, {
        USE_PROFILES: { svg: true, svgFilters: true },
        ADD_ATTR: ['data-entity', 'data-entity-1', 'data-entity-2'],
      })
    : null
)

const matrixHtml = computed(() => {
  const body = (detail.value as Record<string, unknown> | null)?.matrix_body
  if (!body || detail.value?.diagram_type !== 'matrix') return null
  return DOMPurify.sanitize(marked.parse(body as string) as string)
})

const editPath = computed(() =>
  detail.value?.diagram_type === 'matrix' ? '/diagram/edit/matrix' : '/diagram/edit',
)

const showSource = ref(false)
const deletePreview = ref<{ content: string | null; warnings: string[] } | null>(null)
const confirmDelete = ref(false)
const isGlobalDiagram = computed(() => detail.value?.is_global ?? false)
const deleteFn = computed(() =>
  (isGlobalDiagram.value && adminMode.value) ? svc.adminDeleteDiagram : svc.deleteDiagram,
)
const deleteError = computed(() => {
  const r = deleteMutation.result.value
  if (r && !r.wrote) return r.content ?? 'Delete failed'
  return deleteMutation.errorMessage.value
})

// ── SVG rendering ─────────────────────────────────────────────────────────────

const svgContainer = ref<HTMLElement | null>(null)
const svgNodeElems = ref(new Map<string, Element>())
const prevHighlighted = ref<Element | null>(null)
const selectedConnectionGroup = ref<SVGGElement | null>(null)
let _interactivityController: AbortController | null = null
let _attachRun = 0

const load = () => {
  if (!diagramId.value) return
  contextQuery.run(svc.getDiagramContext(diagramId.value))
  svgQuery.run(svc.getDiagramSvg(diagramId.value))
}

onMounted(() => {
  void Effect.runPromiseExit(svc.getServerInfo()).then((exit) =>
    Exit.match(exit, {
      onSuccess: (info) => { adminMode.value = info.admin_mode },
      onFailure: () => {},
    }),
  )
  load()
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
    group.appendChild(hit)
  }
}

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
    if (e.display_alias) {
      aliasToId.set(e.display_alias, e.artifact_id)
      aliasToId.set(e.display_alias.replace(/[^a-zA-Z0-9_]/g, '_'), e.artifact_id)
    }
  }
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
    if (!alias && g.id.startsWith('cluster_') && aliasToId.has(g.id.slice(8))) alias = g.id.slice(8)
    if (!alias) continue

    const artifactId = aliasToId.get(alias)!
    g.setAttribute('data-entity-id', artifactId)
    svgNodeElems.value.set(artifactId, g)
    g.addEventListener('click', (ev) => { ev.stopPropagation(); selectEntity(artifactId) }, { signal })
  }

  const aliasToConnQueue = new Map<string, DiagramConnection[]>()
  const aliasToConnFallback = new Map<string, DiagramConnection>()
  for (const conn of diagramConnections.value) {
    if (!conn.source_alias || !conn.target_alias) continue
    const forwardKey = `${conn.source_alias}:${conn.target_alias}`
    const reverseKey = `${conn.target_alias}:${conn.source_alias}`
    const queue = aliasToConnQueue.get(forwardKey) ?? []
    queue.push(conn)
    aliasToConnQueue.set(forwardKey, queue)
    aliasToConnFallback.set(forwardKey, conn)
    if (!aliasToConnFallback.has(reverseKey)) aliasToConnFallback.set(reverseKey, conn)
  }

  const attachConnGroup = (g: SVGGElement, conn: DiagramConnection) => {
    if (g.hasAttribute('data-conn-id')) return
    addConnectionHitAreas(g)
    g.setAttribute('data-conn-id', conn.artifact_id)
    g.addEventListener('click', (ev) => { ev.stopPropagation(); selectConnection(conn, g) }, { signal })
  }

  // Primary: attribute-based (works when DOMPurify preserves data-entity-1/2)
  for (const g of Array.from(svgEl.querySelectorAll<SVGGElement>('g[data-entity-1]'))) {
    const a1 = g.getAttribute('data-entity-1') ?? ''
    const a2 = g.getAttribute('data-entity-2') ?? ''
    const forwardKey = `${a1}:${a2}`
    const reverseKey = `${a2}:${a1}`
    const conn = aliasToConnQueue.get(forwardKey)?.shift()
      ?? aliasToConnQueue.get(reverseKey)?.shift()
      ?? aliasToConnFallback.get(forwardKey)
      ?? aliasToConnFallback.get(reverseKey)
    if (!conn) continue
    attachConnGroup(g, conn)
  }

  // Fallback: id-based lookup via PlantUML's link_SOURCE_TARGET convention
  for (const conn of diagramConnections.value) {
    if (!conn.source_alias || !conn.target_alias) continue
    const fwdId = `link_${conn.source_alias}_${conn.target_alias}`
    const revId = `link_${conn.target_alias}_${conn.source_alias}`
    const g = (svgEl.getElementById(fwdId) ?? svgEl.getElementById(revId)) as SVGGElement | null
    if (g) attachConnGroup(g, conn)
  }
}

watch([svgHtml, diagramEntities, diagramConnections], () => { void attachInteractivity() }, { flush: 'post' })

// ── Selection ─────────────────────────────────────────────────────────────────

const selectedId = ref<string | null>(null)
const selectedConnection = ref<DiagramConnection | null>(null)

watch(selectedId, (newId) => {
  prevHighlighted.value?.classList.remove('svg-selected')
  prevHighlighted.value = null
  if (!newId) return
  const el = svgNodeElems.value.get(newId) ?? null
  el?.classList.add('svg-selected')
  prevHighlighted.value = el
})

const clearConnection = () => {
  selectedConnectionGroup.value?.classList.remove('svg-conn-selected')
  selectedConnectionGroup.value = null
  selectedConnection.value = null
}
const selectConnection = (conn: DiagramConnection, el: SVGGElement) => {
  if (selectedId.value) selectedId.value = null
  const same = selectedConnection.value?.artifact_id === conn.artifact_id
  clearConnection()
  if (!same) {
    selectedConnection.value = conn
    selectedConnectionGroup.value = el
    el.classList.add('svg-conn-selected')
  }
}
const selectEntity = (id: string) => {
  clearConnection()
  if (selectedId.value === id) {
    selectedId.value = null
    entityQuery.reset()
    return
  }
  selectedId.value = id
  entityQuery.run(svc.getEntity(id))
}


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

  let contentWidth = 0, contentHeight = 0, contentX = 0, contentY = 0
  try {
    const graphRoot = svgEl.querySelector('g')
    const bbox = (graphRoot ?? svgEl).getBBox()
    contentX = bbox.x; contentY = bbox.y
    contentWidth = bbox.width; contentHeight = bbox.height
  } catch {
    const viewBox = svgEl.viewBox?.baseVal
    if (viewBox && viewBox.width > 0 && viewBox.height > 0) {
      contentX = viewBox.x; contentY = viewBox.y
      contentWidth = viewBox.width; contentHeight = viewBox.height
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

// ── Delete ────────────────────────────────────────────────────────────────────

const previewDelete = () => {
  if (!diagramId.value) return
  confirmDelete.value = true
  deletePreview.value = null
  deleteMutation.reset()
  void deleteMutation.run(deleteFn.value({ artifact_id: diagramId.value, dry_run: true }))
    .then((exit) => Exit.match(exit, {
      onSuccess: (r) => { deletePreview.value = { content: r.content, warnings: [...r.warnings] } },
      onFailure: () => {},
    }))
}

const cancelDelete = () => {
  confirmDelete.value = false
  deletePreview.value = null
  deleteMutation.reset()
}

const executeDelete = () => {
  if (!diagramId.value) return
  void deleteMutation.run(deleteFn.value({ artifact_id: diagramId.value, dry_run: false }))
    .then((exit) => Exit.match(exit, {
      onSuccess: (r) => { if (r.wrote) void router.push(isGlobalDiagram.value ? '/global/diagrams' : '/diagrams') },
      onFailure: () => {},
    }))
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
watch(svgHtml, (svg) => { if (svg) void fitDiagramToViewport() })
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
      <RouterLink
        to="/diagrams"
        class="back"
      >
        ← Diagrams
      </RouterLink>
      <h1
        v-if="detail"
        class="pg-title"
      >
        {{ detail.name }}
      </h1>
      <DownloadMenu
        v-if="detail"
        :diagram-id="diagramId"
        :diagram-name="detail.name"
      />
      <RouterLink
        v-if="detail && !isGlobalDiagram"
        :to="{ path: '/promote', query: { diagram_id: diagramId } }"
        class="promote-btn"
      >
        ↑ Promote to Global
      </RouterLink>
      <RouterLink
        v-if="detail"
        :to="{ path: editPath, query: { id: diagramId } }"
        class="edit-btn"
      >
        Edit
      </RouterLink>
      <button
        v-if="detail && (!isGlobalDiagram || adminMode)"
        class="delete-btn"
        @click="previewDelete"
      >
        Delete{{ isGlobalDiagram && adminMode ? ' ⚠' : '' }}
      </button>
    </div>

    <div
      v-if="contextQuery.loading.value"
      class="state"
    >
      Loading…
    </div>
    <div
      v-else-if="contextQuery.errorMessage.value"
      class="state err"
    >
      {{ contextQuery.errorMessage.value }}
    </div>

    <template v-else-if="detail">
      <div class="meta">
        <span class="type-badge">{{ detail.diagram_type.replace('archimate-', '') }}</span>
        <span
          class="status-badge"
          :class="`status--${detail.status}`"
        >{{ detail.status }}</span>
        <span class="mono faded">v{{ detail.version }} · {{ detail.artifact_id }}</span>
      </div>

      <div class="main-grid">
        <!-- Matrix: rendered markdown tables -->
        <div
          v-if="detail?.diagram_type === 'matrix' && matrixHtml"
          class="matrix-view"
          v-html="matrixHtml"
        />
        <!-- ArchiMate: pan+zoom SVG canvas -->
        <div
          v-else
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
            title="Reset view"
            @click.stop="resetView"
          >
            ⊙ Reset
          </button>
          <div class="zoom-hint">
            Scroll to zoom · Drag to pan · Click entity to inspect · Double-click to reset
          </div>
        </div>

        <!-- Sidebar: entity list + inline detail -->
        <aside class="sidebar card">
          <div class="sb-hdr">
            <span class="sb-title">Entities</span>
            <span class="sb-count">{{ diagramEntities.length }}</span>
          </div>
          <ul class="ent-list">
            <li
              v-for="e in diagramEntities"
              :key="e.artifact_id"
              class="ent-item"
              :class="{ 'ent--active': selectedId === e.artifact_id }"
              @click="selectEntity(e.artifact_id)"
            >
              <span
                class="ent-glyph"
                :title="e.artifact_type"
              >
                <ArchimateTypeGlyph
                  :type="toGlyphKey(e.artifact_type)"
                  :size="13"
                />
              </span>
              <span
                class="ent-dot"
                :style="{ background: getDomainColor(e.domain) }"
              />
              <span class="ent-name">{{ e.name }}</span>
            </li>
          </ul>

          <div
            v-if="selectedConnection"
            class="ent-det"
          >
            <div class="det-hdr">
              <span class="det-name">{{ selectedConnection.conn_type }}</span>
              <button
                class="det-close"
                @click="clearConnection()"
              >
                ×
              </button>
            </div>
            <div class="conn-flow">
              {{ selectedConnection.source_name }} → {{ selectedConnection.target_name }}
            </div>
            <div
              v-if="selectedConnection.content_text?.trim()"
              class="det-content"
            >
              {{ selectedConnection.content_text }}
            </div>
          </div>
          <div
            v-if="selectedId && entityQuery.loading.value"
            class="ent-det ent-det--loading"
          >
            Loading…
          </div>
          <div
            v-if="entityQuery.data.value"
            class="ent-det"
          >
            <div class="det-hdr">
              <RouterLink
                :to="{ path: '/entity', query: { id: entityQuery.data.value.artifact_id } }"
                class="det-name"
              >
                {{ entityQuery.data.value.name }}
              </RouterLink>
              <button
                class="det-close"
                @click="selectEntity(selectedId!)"
              >
                ×
              </button>
            </div>
            <div class="det-chips">
              <span
                class="chip"
                :class="`domain--${entityQuery.data.value.domain}`"
              >{{ entityQuery.data.value.domain }}</span>
              <span
                class="chip"
                :class="`status--${entityQuery.data.value.status}`"
              >{{ entityQuery.data.value.status }}</span>
              <span class="chip chip-type">{{ entityQuery.data.value.artifact_type }}</span>
            </div>
            <div
              v-if="entityQuery.data.value.content_html"
              class="det-content markdown-body"
              v-html="entityQuery.data.value.content_html"
            />
            <RouterLink
              :to="{ path: '/graph', query: { id: entityQuery.data.value.artifact_id } }"
              class="explore-lnk"
            >
              Explore in graph →
            </RouterLink>
          </div>
        </aside>
      </div>

      <div
        v-if="confirmDelete"
        class="delete-panel"
      >
        <div class="delete-title">
          Delete Diagram
        </div>
        <div class="delete-text">
          Deletion removes the diagram source file and any rendered PNG/SVG siblings.
        </div>
        <div
          v-if="deletePreview?.warnings.length"
          class="preview-warnings"
        >
          <div
            v-for="w in deletePreview.warnings"
            :key="w"
            class="preview-warn"
          >
            {{ w }}
          </div>
        </div>
        <pre
          v-if="deletePreview?.content"
          class="delete-preview"
        >{{ deletePreview.content }}</pre>
        <pre
          v-if="deleteError"
          class="state err state-block"
        >{{ deleteError }}</pre>
        <div class="delete-actions">
          <button
            class="toggle-btn"
            :disabled="deleteMutation.running.value"
            @click="cancelDelete"
          >
            Cancel
          </button>
          <button
            class="delete-confirm-btn"
            :disabled="deleteMutation.running.value"
            @click="executeDelete"
          >
            {{ deleteMutation.running.value ? 'Deleting…' : 'Delete Diagram' }}
          </button>
        </div>
      </div>

      <div
        v-if="detail.puml_source"
        class="src-row"
      >
        <button
          class="toggle-btn"
          @click="showSource = !showSource"
        >
          {{ showSource ? 'Hide' : 'Show' }} PUML source
        </button>
        <pre
          v-if="showSource"
          class="puml-src"
        >{{ detail.puml_source }}</pre>
      </div>
    </template>
  </div>
</template>

<style scoped>
.page { max-width: 100%; }
.page-hdr { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
.back { font-size: 13px; color: #6b7280; } .back:hover { color: #374151; text-decoration: none; }
.pg-title { font-size: 20px; font-weight: 700; flex: 1; margin: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.promote-btn {
  padding: 5px 16px; background: #fef3c7; border: 1px solid #fde68a; border-radius: 6px;
  font-size: 13px; font-weight: 500; color: #92400e; text-decoration: none; flex-shrink: 0;
}
.promote-btn:hover { background: #fde68a; text-decoration: none; }
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
.svg-wrap :deep([data-conn-id]:hover) path,
.svg-wrap :deep([data-conn-id]:hover) polygon,
.svg-wrap :deep([data-conn-id]:hover) line,
.svg-wrap :deep([data-conn-id]:hover) polyline { stroke: #2563eb !important; stroke-width: 2 !important; }
.svg-wrap :deep(.svg-conn-selected) path,
.svg-wrap :deep(.svg-conn-selected) polygon,
.svg-wrap :deep(.svg-conn-selected) line,
.svg-wrap :deep(.svg-conn-selected) polyline { stroke: #2563eb !important; stroke-width: 2.5 !important; }
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
.matrix-view { overflow-x: auto; padding: 16px; background: white; border-radius: 8px; border: 1px solid #e5e7eb; }
.matrix-view :deep(th) { writing-mode: vertical-rl; transform: rotate(180deg); min-width: 2rem; padding: 8px 4px; font-size: 11px; }
.matrix-view :deep(td), .matrix-view :deep(th) { border: 1px solid #e2e8f0; padding: 4px 8px; }
.matrix-view :deep(table) { border-collapse: collapse; margin-bottom: 20px; }
.matrix-view :deep(h2) { font-size: 13px; font-weight: 700; margin: 16px 0 6px; color: #374151; }
</style>
