<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { hierarchy, treemap, type HierarchyRectangularNode } from 'd3-hierarchy'
import type { EntitySummary } from '../../domain'
import ArchimateTypeGlyph from './ArchimateTypeGlyph.vue'
import { friendlyEntityId, getDomainColor, getDomainLabel, getEntityConnectionTotal } from '../lib/domains'

type TreeGroup = { name: string; color: string; children: TreeLeaf[] }
type TreeLeaf = { entity: EntitySummary; value: number; color: string }
type Pan = { x: number; y: number }
type Point = { x: number; y: number }

const props = defineProps<{ items: EntitySummary[]; activeDomain: string }>()

const router = useRouter()
const hostRef = ref<HTMLElement | null>(null)
const svgRef = ref<SVGSVGElement | null>(null)
const size = ref({ width: 960, height: 620 })
const zoom = ref(1)
const pan = ref<Pan>({ x: 0, y: 0 })
const panning = ref(false)
const dragStart = ref<Point>({ x: 0, y: 0 })
const panOrigin = ref<Pan>({ x: 0, y: 0 })
const movedDuringGesture = ref(false)
const pressedLeafId = ref<string | null>(null)
const tooltipLeaf = ref<EntitySummary | null>(null)
const tooltipPos = ref<Point>({ x: 0, y: 0 })
let observer: ResizeObserver | null = null
let hoverTimer: ReturnType<typeof setTimeout> | null = null
const TOOLTIP_WIDTH = 260
const TOOLTIP_HEIGHT = 120
const TOOLTIP_GAP = 12

const groupMode = computed(() => (props.activeDomain ? 'subdomain' : 'domain'))
const domainColor = computed(() => getDomainColor(props.activeDomain))
const viewBox = computed(() => `0 0 ${size.value.width} ${size.value.height}`)
const transform = computed(() => `translate(${pan.value.x}, ${pan.value.y}) scale(${zoom.value})`)

const treeData = computed<TreeGroup[]>(() => {
  const groups = new Map<string, TreeLeaf[]>()
  for (const entity of props.items) {
    const name = groupMode.value === 'domain' ? getDomainLabel(entity.domain) : entity.subdomain || 'General'
    const list = groups.get(name) ?? []
    list.push({
      entity,
      value: getEntityConnectionTotal(entity),
      color: groupMode.value === 'domain' ? getDomainColor(entity.domain) : domainColor.value,
    })
    groups.set(name, list)
  }
  return [...groups.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([name, children]) => ({
    name,
    color: groupMode.value === 'domain' ? getDomainColor(children[0]?.entity.domain) : domainColor.value,
    children: children.sort((a, b) => b.value - a.value || (a.entity.name || a.entity.artifact_id).localeCompare(b.entity.name || b.entity.artifact_id)),
  }))
})

const layout = computed(() => {
  const root = hierarchy<{ children: TreeGroup[] } | TreeGroup | TreeLeaf>({ children: treeData.value }, node =>
    'children' in node ? node.children : undefined,
  ).sum(node => ('value' in node ? Math.max(node.value, 0.25) : 0))
  return treemap<{ children: TreeGroup[] } | TreeGroup | TreeLeaf>()
    .size([Math.max(size.value.width, 320), Math.max(size.value.height, 320)])
    .paddingOuter(10)
    .paddingTop(node => (node.depth === 1 ? 26 : 3))
    .paddingInner(4)
    .round(true)(root)
})

const scaled = (value: number) => value * zoom.value
const fits = (width: number, height: number, minW: number, minH: number) =>
  scaled(width) >= minW && scaled(height) >= minH

const clamp = (value: number, min: number, max: number) =>
  Math.max(min, Math.min(max, value))

const fitText = (text: string, width: number, fontSize: number) => {
  const maxChars = Math.max(3, Math.floor(width / Math.max(fontSize * 0.62, 1)))
  return text.length > maxChars ? `${text.slice(0, maxChars - 1)}…` : text
}

const groupFontSize = (width: number, height: number) =>
  clamp(Math.min(width / 10, height * 0.4), 8, 12)

const leafVisuals = (leaf: HierarchyRectangularNode<TreeLeaf>) => {
  const width = leaf.x1 - leaf.x0
  const height = leaf.y1 - leaf.y0
  const iconSize = clamp(Math.min(width * 0.18, height * 0.46), 8, 14)
  const gap = clamp(iconSize * 0.45, 4, 8)
  const left = 8
  const textX = left + iconSize + gap
  const textWidth = Math.max(0, width - textX - 6)
  const nameSize = clamp(Math.min(height * 0.24, textWidth / 7.2), 7, 12)
  const metaSize = clamp(Math.min(height * 0.18, textWidth / 13), 6, 10)
  const showIcon = fits(width, height, 24, 20)
  const showName = textWidth > 18 && fits(width, height, 62, 30)
  const showMeta = textWidth > 30 && fits(width, height, 88, 44)
  const label = fitText(leaf.data.entity.name || leaf.data.entity.artifact_id, textWidth, nameSize)
  return {
    iconSize,
    left,
    textX,
    nameSize,
    metaSize,
    label,
    showIcon,
    showName,
    showMeta,
  }
}

const groups = computed(() =>
  ((layout.value.children ?? []) as HierarchyRectangularNode<TreeGroup>[]).map(group => ({
    key: group.data.name,
    name: group.data.name,
    color: group.data.color,
    x: group.x0,
    y: group.y0,
    width: group.x1 - group.x0,
    height: group.y1 - group.y0,
    showLabel: fits(group.x1 - group.x0, group.y1 - group.y0, 110, 42),
    fontSize: groupFontSize(group.x1 - group.x0, group.y1 - group.y0),
  })),
)

const leaves = computed(() =>
  (layout.value.leaves() as HierarchyRectangularNode<TreeLeaf>[]).map(leaf => ({
    key: leaf.data.entity.artifact_id,
    entity: leaf.data.entity,
    value: leaf.data.value,
    color: leaf.data.color,
    x: leaf.x0,
    y: leaf.y0,
    width: leaf.x1 - leaf.x0,
    height: leaf.y1 - leaf.y0,
    ...leafVisuals(leaf),
  })),
)

const clampZoom = (next: number) => Math.min(12, Math.max(1, next))
const openEntity = (id: string) => router.push({ path: '/entity', query: { id } })
const resetView = () => { zoom.value = 1; pan.value = { x: 0, y: 0 } }
const clearTooltip = () => {
  if (hoverTimer) clearTimeout(hoverTimer)
  hoverTimer = null
  tooltipLeaf.value = null
}
const updateSize = () => {
  const rect = hostRef.value?.getBoundingClientRect()
  if (!rect) return
  size.value = { width: rect.width, height: Math.max(rect.height, 540) }
}

const queueTooltip = (entity: EntitySummary, clientX: number, clientY: number) => {
  clearTooltip()
  const rect = hostRef.value?.getBoundingClientRect()
  if (!rect || panning.value) return
  const localX = clientX - rect.left
  const localY = clientY - rect.top
  const roomRight = rect.width - localX
  const roomBottom = rect.height - localY
  tooltipPos.value = {
    x: clamp(roomRight > TOOLTIP_WIDTH + TOOLTIP_GAP ? localX + 120 : localX - TOOLTIP_WIDTH + 380, 8, rect.width + 400 - 8),
    y: clamp(roomBottom > TOOLTIP_HEIGHT + TOOLTIP_GAP ? localY + TOOLTIP_GAP : localY - TOOLTIP_HEIGHT - TOOLTIP_GAP, 8, rect.height - TOOLTIP_HEIGHT - 8),
  }
  hoverTimer = setTimeout(() => {
    tooltipLeaf.value = entity
    hoverTimer = null
  }, 250)
}

const zoomAround = (clientX: number, clientY: number, nextZoom: number) => {
  const svgRect = svgRef.value?.getBoundingClientRect()
  if (!svgRect) return
  const targetZoom = clampZoom(nextZoom)
  const px = clientX - svgRect.left
  const py = clientY - svgRect.top
  const wx = (px - pan.value.x) / zoom.value
  const wy = (py - pan.value.y) / zoom.value
  zoom.value = targetZoom
  pan.value = { x: px - wx * targetZoom, y: py - wy * targetZoom }
}

const zoomByButton = (delta: number) => {
  const rect = svgRef.value?.getBoundingClientRect()
  if (!rect) return
  zoomAround(rect.left + rect.width / 2, rect.top + rect.height / 2, zoom.value + delta)
}

const onWheel = (event: WheelEvent) => {
  event.preventDefault()
  clearTooltip()
  zoomAround(event.clientX, event.clientY, zoom.value * (event.deltaY > 0 ? 0.9 : 1.12))
}

const startPan = (event: MouseEvent) => {
  if (event.button !== 0) return
  clearTooltip()
  panning.value = true
  dragStart.value = { x: event.clientX, y: event.clientY }
  panOrigin.value = { ...pan.value }
  movedDuringGesture.value = false
  const leaf = (event.target as Element | null)?.closest<SVGElement>('[data-leaf-id]')
  pressedLeafId.value = leaf?.dataset.leafId ?? null
}

const onMove = (event: MouseEvent) => {
  if (!panning.value) return
  if (Math.hypot(event.clientX - dragStart.value.x, event.clientY - dragStart.value.y) > 4) {
    movedDuringGesture.value = true
  }
  clearTooltip()
  pan.value = {
    x: panOrigin.value.x + event.clientX - dragStart.value.x,
    y: panOrigin.value.y + event.clientY - dragStart.value.y,
  }
}

const stopPan = () => {
  if (panning.value && pressedLeafId.value && !movedDuringGesture.value) {
    void openEntity(pressedLeafId.value)
  }
  panning.value = false
  movedDuringGesture.value = false
  pressedLeafId.value = null
}

onMounted(() => {
  updateSize()
  observer = new ResizeObserver(updateSize)
  if (hostRef.value) observer.observe(hostRef.value)
  window.addEventListener('mousemove', onMove)
  window.addEventListener('mouseup', stopPan)
})

onBeforeUnmount(() => {
  clearTooltip()
  observer?.disconnect()
  window.removeEventListener('mousemove', onMove)
  window.removeEventListener('mouseup', stopPan)
})

watch(() => props.items, resetView)
</script>

<template>
  <div
    ref="hostRef"
    class="treemap-card"
  >
    <div class="treemap-topbar">
      <div class="treemap-note">
        Sized by total connections. Drag to pan, wheel to zoom.
        <span v-if="groupMode === 'domain'">Grouped by domain.</span>
        <span v-else>Grouped by subdomain.</span>
      </div>
      <div class="treemap-controls">
        <button
          class="control-btn"
          title="Zoom out"
          @click="zoomByButton(-0.35)"
        >
          −
        </button>
        <button
          class="control-btn"
          title="Reset zoom and pan"
          @click="resetView"
        >
          {{ zoom.toFixed(1) }}x
        </button>
        <button
          class="control-btn"
          title="Zoom in"
          @click="zoomByButton(0.35)"
        >
          +
        </button>
      </div>
    </div>
    <svg
      ref="svgRef"
      class="treemap-svg"
      :viewBox="viewBox"
      preserveAspectRatio="xMidYMid meet"
      @wheel.prevent="onWheel"
      @mousedown="startPan"
    >
      <rect
        class="interaction-bg"
        x="0"
        y="0"
        :width="size.width"
        :height="size.height"
      />
      <g :transform="transform">
        <g
          v-for="group in groups"
          :key="group.key"
        >
          <rect
            class="group-shell"
            :x="group.x"
            :y="group.y"
            :width="group.width"
            :height="group.height"
            :fill="group.color"
            fill-opacity="0.16"
            :stroke="group.color"
          />
          <text
            v-if="group.showLabel"
            class="group-label"
            :x="group.x + 10"
            :y="group.y + group.fontSize + 5"
            :font-size="group.fontSize"
          >{{ group.name }}</text>
        </g>
        <g
          v-for="leaf in leaves"
          :key="leaf.key"
          :data-leaf-id="leaf.key"
          @mouseenter="queueTooltip(leaf.entity, $event.clientX, $event.clientY)"
          @mousemove="queueTooltip(leaf.entity, $event.clientX, $event.clientY)"
          @mouseleave="clearTooltip"
        >
          <rect
            class="leaf-block"
            :x="leaf.x"
            :y="leaf.y"
            :width="leaf.width"
            :height="leaf.height"
            :fill="leaf.color"
          />
          <g
            v-if="leaf.showIcon"
            class="leaf-copy"
          >
            <ArchimateTypeGlyph
              :type="leaf.entity.artifact_type"
              :x="leaf.x + leaf.left"
              :y="leaf.y + Math.max(6, (leaf.height - leaf.iconSize) / 2 - (leaf.showName ? 5 : 0))"
              :size="leaf.iconSize"
              class="leaf-glyph"
            />
            <text
              v-if="leaf.showName"
              class="leaf-name"
              :x="leaf.x + leaf.textX"
              :y="leaf.y + 8 + leaf.nameSize"
              :font-size="leaf.nameSize"
            >{{ leaf.label }}</text>
            <text
              v-if="leaf.showMeta"
              class="leaf-meta"
              :x="leaf.x + leaf.textX"
              :y="leaf.y + 10 + leaf.nameSize + leaf.metaSize + 4"
              :font-size="leaf.metaSize"
            >{{ leaf.value }} connections</text>
          </g>
        </g>
      </g>
    </svg>
    <div
      v-if="tooltipLeaf"
      class="leaf-tooltip"
      :style="{ left: `${tooltipPos.x}px`, top: `${tooltipPos.y}px` }"
    >
      <div class="tooltip-head">
        <ArchimateTypeGlyph
          :type="tooltipLeaf.artifact_type"
          :size="18"
          class="tooltip-glyph"
        />
        <div>
          <div class="tooltip-name">
            {{ tooltipLeaf.name || friendlyEntityId(tooltipLeaf.artifact_id) }}
          </div>
          <div class="tooltip-type">
            {{ tooltipLeaf.artifact_type }}
          </div>
        </div>
      </div>
      <div class="tooltip-id">
        {{ tooltipLeaf.artifact_id }}
      </div>
    </div>
  </div>
</template>

<style scoped>
.treemap-card { background: white; border: 1px solid #e5e7eb; border-radius: 10px; overflow: hidden; min-height: 620px; }
.treemap-topbar, .treemap-controls { display: flex; align-items: center; }
.treemap-topbar { justify-content: space-between; gap: 14px; padding: 10px 14px; border-bottom: 1px solid #e5e7eb; background: #f8fafc; }
.treemap-note { font-size: 12px; color: #6b7280; }
.treemap-controls { gap: 6px; }
.control-btn {
  min-width: 34px; padding: 6px 9px; border: 1px solid #d1d5db; border-radius: 6px;
  background: white; color: #374151; cursor: pointer; font-size: 12px;
}
.control-btn:hover { background: #f3f4f6; }
.treemap-svg { display: block; width: 100%; height: 620px; cursor: grab; }
.treemap-svg:active { cursor: grabbing; }
.interaction-bg { fill: #fff; }
.group-shell { stroke-width: 1.5; rx: 10; }
.group-label { font-weight: 700; letter-spacing: .02em; pointer-events: none; }
.leaf-block { cursor: pointer; stroke: rgba(255, 255, 255, 0.9); stroke-width: 1.5; }
.leaf-block:hover { filter: brightness(0.98) saturate(1.08); }
.leaf-copy { cursor: pointer; pointer-events: none; }
.leaf-glyph { color: #1f2937; fill: none; }
.leaf-name, .leaf-meta { fill: #1f2937; }
.leaf-name { font-weight: 600; }
.leaf-meta { opacity: .8; }
.leaf-tooltip {
  position: absolute;
  z-index: 2;
  min-width: 220px;
  max-width: 260px;
  padding: 10px 12px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.98);
  box-shadow: 0 10px 30px rgba(15, 23, 42, 0.14);
  pointer-events: none;
}
.tooltip-head { display: flex; gap: 10px; align-items: center; margin-bottom: 6px; }
.tooltip-glyph { color: #1f2937; fill: none; flex: 0 0 auto; }
.tooltip-name { font-size: 13px; font-weight: 600; color: #111827; }
.tooltip-type { font-size: 11px; color: #6b7280; }
.tooltip-id { font-size: 11px; color: #6b7280; font-family: monospace; word-break: break-all; }
</style>
