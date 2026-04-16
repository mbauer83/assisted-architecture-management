<script setup lang="ts">
import { inject, onMounted, onUnmounted, watch, computed, ref } from 'vue'
import { useRoute, RouterLink } from 'vue-router'
import { Effect } from 'effect'
import { modelServiceKey } from '../keys'
import { useAsync } from '../composables/useAsync'
import type { DiagramDetail, EntitySummary, EntityDetail } from '../../domain'
import { getDomainColor } from '../lib/domains'
import ArchimateTypeGlyph from '../components/ArchimateTypeGlyph.vue'

const svc = inject(modelServiceKey)!
const route = useRoute()

const diagramId = computed(() => (route.query.id as string | undefined) ?? '')
const detail = useAsync<DiagramDetail>()
const showSource = ref(false)

const diagramEntities = ref<EntitySummary[]>([])
const selectedEntity = ref<EntityDetail | null>(null)
const selectedId = ref<string | null>(null)

const imageUrl = computed(() => {
  const d = detail.data.value
  return d?.rendered_filename ? svc.diagramImageUrl(d.rendered_filename) : null
})

const load = () => {
  if (!diagramId.value) return
  detail.run(svc.getDiagram(diagramId.value))
  Effect.runPromise(svc.getDiagramEntities(diagramId.value))
    .then((ents) => { diagramEntities.value = ents })
    .catch(() => { diagramEntities.value = [] })
}

const selectEntity = (id: string) => {
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
let dragging = false
let drag = { x: 0, y: 0, tx: 0, ty: 0 }

const canvasStyle = computed(() => ({
  transform: `translate(${tx.value}px, ${ty.value}px) scale(${scale.value})`,
  transformOrigin: '0 0',
  willChange: 'transform',
  display: 'inline-block',
}))
const isTransformed = computed(() => scale.value !== 1 || tx.value !== 0 || ty.value !== 0)

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
  if ((e.target as HTMLElement).closest('button, a')) return
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
const resetView = () => { scale.value = 1; tx.value = 0; ty.value = 0 }

onMounted(load)
watch(diagramId, load)

// containerRef lives inside v-else-if, so it's null until data loads — watch it
watch(containerRef, (el, prev) => {
  prev?.removeEventListener('wheel', onWheel)
  el?.addEventListener('wheel', onWheel, { passive: false })
})

onUnmounted(() => {
  containerRef.value?.removeEventListener('wheel', onWheel)
  window.removeEventListener('mousemove', onMouseMove)
  window.removeEventListener('mouseup', onMouseUp)
})
</script>

<template>
  <div class="page">
    <div class="page-hdr">
      <RouterLink to="/diagrams" class="back">← Diagrams</RouterLink>
      <h1 v-if="detail.data.value" class="pg-title">{{ detail.data.value.name }}</h1>
      <RouterLink
        v-if="detail.data.value"
        :to="{ path: '/diagram/edit', query: { id: diagramId } }"
        class="edit-btn"
      >Edit</RouterLink>
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
        <!-- Diagram image with pan + zoom -->
        <div ref="containerRef" class="img-container" @mousedown="onMouseDown" @dblclick="resetView">
          <div :style="canvasStyle">
            <img
              v-if="imageUrl" :src="imageUrl" :alt="detail.data.value.name"
              draggable="false" class="diag-img"
            />
            <div v-else class="no-img">No rendered image available.</div>
          </div>
          <button v-if="isTransformed" class="reset-btn" @click.stop="resetView" title="Reset view">⊙ Reset</button>
          <div class="zoom-hint">Scroll to zoom · Drag to pan · Double-click to reset</div>
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
            <div
              v-if="selectedEntity.content_html"
              class="det-content markdown-body"
              v-html="selectedEntity.content_html"
            />
            <RouterLink
              :to="{ path: '/graph', query: { id: selectedEntity.artifact_id } }"
              class="explore-lnk"
            >Explore in graph →</RouterLink>
          </div>
        </aside>
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
.back { font-size: 13px; color: #6b7280; }
.back:hover { color: #374151; text-decoration: none; }
.pg-title { font-size: 20px; font-weight: 700; flex: 1; margin: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.edit-btn { padding: 5px 16px; background: #f3f4f6; border: 1px solid #d1d5db; border-radius: 6px; font-size: 13px; font-weight: 500; color: #374151; text-decoration: none; flex-shrink: 0; }
.edit-btn:hover { background: #e5e7eb; text-decoration: none; }
.meta { display: flex; align-items: center; gap: 8px; margin-bottom: 14px; font-size: 12px; }
.faded { color: #9ca3af; } .mono { font-family: monospace; }
.state { color: #6b7280; } .err { color: #dc2626; }
.type-badge { padding: 2px 8px; border-radius: 4px; font-size: 11px; background: #dbeafe; color: #1e40af; font-weight: 500; }

.main-grid { display: grid; grid-template-columns: 1fr 260px; gap: 16px; align-items: start; }
@media (max-width: 800px) { .main-grid { grid-template-columns: 1fr; } }

.img-container {
  position: relative; overflow: hidden; background: #f8fafc;
  border: 1px solid #e5e7eb; border-radius: 8px; min-height: 400px;
  cursor: grab; user-select: none;
}
.img-container:active { cursor: grabbing; }
.diag-img { display: block; max-width: none; pointer-events: none; }
.no-img { padding: 60px 40px; text-align: center; color: #9ca3af; font-size: 13px; }
.reset-btn { position: absolute; top: 8px; right: 8px; padding: 4px 10px; background: rgba(255,255,255,.92); border: 1px solid #d1d5db; border-radius: 5px; font-size: 12px; cursor: pointer; color: #374151; }
.reset-btn:hover { background: white; }
.zoom-hint { position: absolute; bottom: 6px; left: 50%; transform: translateX(-50%); font-size: 11px; color: #9ca3af; background: rgba(255,255,255,.8); padding: 2px 8px; border-radius: 4px; pointer-events: none; white-space: nowrap; }

.card { background: white; border-radius: 8px; border: 1px solid #e5e7eb; }
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
.ent-det--loading { color: #9ca3af; font-size: 12px; }
.det-hdr { display: flex; align-items: flex-start; gap: 4px; margin-bottom: 6px; }
.det-name { font-size: 13px; font-weight: 600; color: #1e293b; flex: 1; line-height: 1.3; }
.det-name:hover { text-decoration: underline; }
.det-close { background: none; border: none; font-size: 16px; cursor: pointer; color: #9ca3af; line-height: 1; padding: 0 2px; flex-shrink: 0; }
.det-close:hover { color: #374151; }
.det-chips { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 8px; }
.chip { font-size: 10px; padding: 2px 6px; border-radius: 3px; font-weight: 500; background: #f3f4f6; color: #374151; }
.chip-type { background: #f3f4f6; color: #374151; }
.det-content { font-size: 12px; line-height: 1.5; color: #374151; margin-bottom: 8px; max-height: 220px; overflow-y: auto; }
.det-content :deep(p) { margin: 0.35rem 0; }
.explore-lnk { font-size: 12px; color: #2563eb; }
.explore-lnk:hover { text-decoration: underline; }

.src-row { margin-top: 16px; }
.toggle-btn { padding: 5px 14px; border-radius: 6px; border: 1px solid #d1d5db; background: white; font-size: 13px; cursor: pointer; color: #374151; margin-bottom: 8px; }
.toggle-btn:hover { background: #f9fafb; }
.puml-src { background: #1e293b; color: #e2e8f0; padding: 16px; border-radius: 8px; font-size: 12px; line-height: 1.5; overflow-x: auto; white-space: pre; }
</style>
