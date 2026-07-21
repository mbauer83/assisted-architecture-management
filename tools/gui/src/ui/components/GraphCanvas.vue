<script setup lang="ts">
/**
 * Generic interactive graph canvas: SVG rendering, pan/zoom/drag, node shapes,
 * wrapped labels, multiplicity labels, and zoom controls. Domain-agnostic by
 * contract — it receives normalized nodes/edges plus presentation callbacks
 * and loading/notice state; it never imports architecture, assurance, or
 * viewpoint concepts.
 */
import { onMounted, ref, toRef } from 'vue'
import type { GraphEdge, GraphNode } from '../composables/useForceGraph'
import { useGraphPanZoom } from '../composables/useGraphPanZoom'
import {
  contrastTextColor, edgeCardPosFor, edgePathFor, nodeShapePoints, wrapLabel,
  type EdgeVisual, type NodeVisual,
} from './GraphCanvas.helpers'

const props = withDefaults(defineProps<{
  nodes: GraphNode[]
  edges: GraphEdge[]
  selectedId: string | null
  selectedEdge: GraphEdge | null
  nodeVisual: (n: GraphNode) => NodeVisual
  edgeVisual: (e: GraphEdge) => EdgeVisual
  isAnchor?: (id: string) => boolean
  showExpandBadge?: (n: GraphNode) => boolean
  clusterEdges?: boolean
  loading?: boolean
  notice?: string | null
}>(), {
  isAnchor: () => false,
  showExpandBadge: () => false,
  clusterEdges: false,
  loading: false,
  notice: null,
})

const emit = defineEmits<{
  nodeClick: [node: GraphNode]
  nodeDblclick: [node: GraphNode]
  edgeClick: [edge: GraphEdge]
  dragTick: []
  resized: [width: number, height: number]
}>()

const svgRef = ref<SVGSVGElement | null>(null)
const svgWidth = ref(800)
const svgHeight = ref(600)

const {
  viewBox, vb,
  onNodeMouseDown, onSvgMouseDown, onSvgMouseMove, onSvgMouseUp, onWheel,
  zoomBy, fitToView,
} = useGraphPanZoom(svgRef, svgWidth, svgHeight, toRef(props, 'nodes'), () => emit('dragTick'))

onMounted(() => {
  const rect = svgRef.value?.parentElement?.getBoundingClientRect()
  if (rect) {
    svgWidth.value = rect.width
    svgHeight.value = rect.height
    viewBox.value = { x: 0, y: 0, w: rect.width, h: rect.height }
    emit('resized', rect.width, rect.height)
  }
})

const centerOn = (x: number, y: number) => {
  viewBox.value.x = x - viewBox.value.w / 2
  viewBox.value.y = y - viewBox.value.h / 2
}

defineExpose({ fitToView, zoomBy, centerOn })

// Stop the edge at the target node's outer boundary so the arrowhead sits on it: anchor
// nodes carry a larger halo ring (radius 32), normal nodes a radius-24 shape.
const edgePath = (e: GraphEdge) => edgePathFor(props.nodes, e, props.clusterEdges, props.isAnchor(e.target) ? 34 : 26)

// Bounding box (node-local coords) for the below-node label, so a translucent backing rect can
// sit behind it — labels can otherwise fall in front of edges and become hard to read. Width is
// estimated from the widest line (the abbreviation + ": " prefixes the first line).
const labelBoxFor = (n: GraphNode) => {
  const lines = wrapLabel(n.label)
  const firstLen = n.type.length + 2 + (lines[0]?.length ?? 0)
  const maxLen = Math.max(firstLen, ...lines.slice(1).map((l) => l.length))
  const width = maxLen * 6 + 10
  const height = lines.length * 12 + 6
  const baseY = props.isAnchor(n.id) ? 46 : 40
  return { x: -width / 2, y: baseY - 11, width, height }
}
const edgeCardPos = (e: GraphEdge, frac: number) => edgeCardPosFor(props.nodes, e, frac)
</script>

<template>
  <div class="canvas-frame">
    <div
      v-if="notice"
      class="canvas-notice"
    >
      {{ notice }}
    </div>
    <div
      v-if="loading"
      class="canvas-loading"
    >
      Loading…
    </div>
    <div class="zoom-controls">
      <button
        type="button"
        class="zoom-btn"
        title="Zoom in"
        aria-label="Zoom in"
        @click="zoomBy(0.8)"
      >
        ＋
      </button>
      <button
        type="button"
        class="zoom-btn"
        title="Zoom out"
        aria-label="Zoom out"
        @click="zoomBy(1.25)"
      >
        －
      </button>
      <button
        type="button"
        class="zoom-btn"
        title="Fit all nodes in view"
        aria-label="Fit to view"
        @click="fitToView"
      >
        ⛶
      </button>
    </div>
    <svg
      ref="svgRef"
      class="graph-svg"
      :viewBox="vb"
      @mousedown.self="onSvgMouseDown"
      @mousemove="onSvgMouseMove"
      @mouseup="onSvgMouseUp"
      @mouseleave="onSvgMouseUp"
      @wheel.prevent="onWheel"
    >
      <defs>
        <marker
          id="arrowhead"
          markerWidth="8"
          markerHeight="6"
          refX="8"
          refY="3"
          orient="auto"
        >
          <polygon
            points="0 0, 8 3, 0 6"
            fill="#9ca3af"
          />
        </marker>
      </defs>
      <!-- Edges (wider hit area via transparent overlay) -->
      <g
        v-for="(e, i) in edges"
        :key="'e'+i"
        class="graph-edge"
        @click.stop="emit('edgeClick', e)"
      >
        <path
          :d="edgePath(e)"
          :stroke="edgeVisual(e).stroke ?? '#d1d5db'"
          :stroke-width="edgeVisual(e).strokeWidth ?? 1.5"
          :stroke-dasharray="edgeVisual(e).dashArray"
          fill="none"
          marker-end="url(#arrowhead)"
        />
        <path
          :d="edgePath(e)"
          stroke="transparent"
          stroke-width="10"
          fill="none"
          :class="{ 'edge-selected': selectedEdge === e }"
        />
      </g>
      <!-- Multiplicity labels (rendered above edges, below nodes) -->
      <template
        v-for="(e, i) in edges"
        :key="'card'+i"
      >
        <text
          v-if="e.srcMultiplicity"
          :x="edgeCardPos(e, 0.2).x"
          :y="edgeCardPos(e, 0.2).y"
          text-anchor="middle"
          font-size="8"
          fill="#374151"
          stroke="white"
          stroke-width="3"
          paint-order="stroke"
          pointer-events="none"
        >{{ e.srcMultiplicity }}</text>
        <text
          v-if="e.tgtMultiplicity"
          :x="edgeCardPos(e, 0.8).x"
          :y="edgeCardPos(e, 0.8).y"
          text-anchor="middle"
          font-size="8"
          fill="#374151"
          stroke="white"
          stroke-width="3"
          paint-order="stroke"
          pointer-events="none"
        >{{ e.tgtMultiplicity }}</text>
      </template>
      <!-- Nodes -->
      <g
        v-for="n in nodes"
        :key="n.id"
        class="graph-node"
        :transform="`translate(${n.x}, ${n.y})`"
        @mousedown="onNodeMouseDown($event, n)"
        @click.stop="emit('nodeClick', n)"
        @dblclick.stop="emit('nodeDblclick', n)"
      >
        <!-- Anchor halo: outer ring + the white main-shape stroke = double ring -->
        <polygon
          v-if="isAnchor(n.id)"
          :points="nodeShapePoints(nodeVisual(n).shape, 32)"
          fill="none"
          stroke="#1e293b"
          stroke-width="2"
        />
        <polygon
          :points="nodeShapePoints(nodeVisual(n).shape, isAnchor(n.id) ? 27 : 24)"
          :fill="nodeVisual(n).color"
          :opacity="selectedId === n.id ? 1 : 0.8"
          :stroke="selectedId === n.id ? '#1e293b' : 'white'"
          :stroke-width="selectedId === n.id ? 3 : 2"
        />
        <!-- Glyph inside the node shape; falls back to the type abbreviation when the
             consumer supplies no glyph (e.g. non-ArchiMate graphs). -->
        <svg
          v-if="nodeVisual(n).glyph"
          x="-9"
          y="-9"
          width="18"
          height="18"
          viewBox="0 0 16 16"
          fill="none"
          :stroke="contrastTextColor(nodeVisual(n).color)"
          stroke-width="1.3"
          stroke-linecap="round"
          stroke-linejoin="round"
          pointer-events="none"
        ><g v-html="nodeVisual(n).glyph" /></svg>
        <text
          v-else
          dy="4"
          text-anchor="middle"
          :fill="contrastTextColor(nodeVisual(n).color)"
          font-size="9"
          font-weight="600"
        >
          {{ n.type }}
        </text>
        <!-- Translucent backing so the label stays legible where it crosses edges. -->
        <rect
          v-bind="labelBoxFor(n)"
          rx="3"
          fill="#ffffff"
          opacity="0.6"
          pointer-events="none"
        />
        <!-- Label below the node: bolded type abbreviation, a colon, then the name (wrapped).
             Absolute y (not dy) — dy on <text> does not shift the baseline reliably once a
             child tspan sets its own x, which left the label sitting over the node. -->
        <text
          :y="isAnchor(n.id) ? 46 : 40"
          text-anchor="middle"
          :fill="isAnchor(n.id) ? '#1e293b' : '#374151'"
          font-size="10"
        >
          <title>{{ n.type }}: {{ n.label }}</title>
          <tspan
            v-for="(line, li) in wrapLabel(n.label)"
            :key="li"
            x="0"
            :dy="li === 0 ? 0 : 12"
          ><tspan
            v-if="li === 0"
            font-weight="700"
          >{{ n.type }}: </tspan>{{ line }}</tspan>
        </text>
        <text
          v-if="nodeVisual(n).iconLetter"
          x="-17"
          y="-14"
          text-anchor="middle"
          :fill="contrastTextColor(nodeVisual(n).color)"
          font-size="9"
          font-weight="bold"
          pointer-events="none"
        >{{ nodeVisual(n).iconLetter }}</text>
        <circle
          v-if="showExpandBadge(n)"
          cx="17"
          cy="-17"
          r="7"
          fill="#2563eb"
          stroke="white"
          stroke-width="1.5"
          cursor="pointer"
        />
        <text
          v-if="showExpandBadge(n)"
          x="17"
          y="-14"
          text-anchor="middle"
          fill="#252327"
          font-size="9"
          font-weight="bold"
          pointer-events="none"
        >+</text>
      </g>
    </svg>
  </div>
</template>

<style scoped>
.canvas-frame { flex: 1; display: flex; flex-direction: column; position: relative; min-height: 0; }
.canvas-notice {
  position: absolute; top: 10px; left: 50%; transform: translateX(-50%); z-index: 6;
  background: #fef3c7; border: 1px solid #f59e0b; color: #92400e;
  font-size: 12px; padding: 4px 12px; border-radius: 6px; max-width: 80%;
}
.canvas-loading {
  position: absolute; top: 10px; left: 12px; z-index: 6;
  font-size: 12px; color: #6b7280;
}
.zoom-controls {
  position: absolute; right: 12px; bottom: 12px; display: flex; flex-direction: column;
  gap: 4px; z-index: 5;
}
.zoom-btn {
  width: 30px; height: 30px; border: 1px solid #d1d5db; border-radius: 6px; background: white;
  cursor: pointer; font-size: 15px; color: #374151; line-height: 1;
  box-shadow: 0 1px 2px rgba(0,0,0,.08);
}
.zoom-btn:hover { background: #f3f4f6; }
.graph-svg { flex: 1; cursor: grab; user-select: none; }
.graph-svg:active { cursor: grabbing; }
.graph-node { cursor: pointer; }
.graph-node:hover circle:first-child { filter: brightness(1.15); }
.graph-edge { cursor: pointer; }
.graph-edge:hover path:first-child { stroke: #6b7280; }
.edge-selected { stroke: #2563eb !important; opacity: 0.3; }
</style>
