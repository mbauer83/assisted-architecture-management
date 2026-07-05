<script setup lang="ts">
import DOMPurify from 'dompurify'
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import AssuranceNodeDetail from './AssuranceNodeDetail.vue'
import WithheldNotice from './WithheldNotice.vue'
import { stripMarkerAttributes } from '../lib/svgHitAreas'
import {
  UCA_TYPES,
  buildAssuranceAliasMap,
  buildUcaMatrixRows,
  type AssuranceDiagramEdge,
  type AssuranceDiagramNode,
} from './AssuranceDiagramPanel.helpers'

const props = defineProps<{ diagramId: string }>()

const loading = ref(false)
const puml = ref<string | null>(null)
const svg = ref<string | null>(null)
const nodes = ref<AssuranceDiagramNode[]>([])
const edges = ref<AssuranceDiagramEdge[]>([])
const error = ref<string | null>(null)
const visibilityLimited = ref(false)
const showPuml = ref(false)
const selectedNodeId = ref<string | null>(null)
const selectedEdge = ref<AssuranceDiagramEdge | null>(null)
const svgContainer = ref<HTMLElement | null>(null)
let interactionController: AbortController | null = null

const matrixRows = computed(() => buildUcaMatrixRows(nodes.value, edges.value))
const nodeNames = computed(() => new Map(nodes.value.map((node) => [node.node_id, node.name])))
const sanitizedSvg = computed(() => svg.value
  ? DOMPurify.sanitize(svg.value, {
      USE_PROFILES: { svg: true, svgFilters: true },
      ADD_ATTR: ['data-entity', 'data-entity-1', 'data-entity-2', 'data-qualified-name'],
    })
  : null)

function selectNode(nodeId: string) {
  selectedEdge.value = null
  selectedNodeId.value = selectedNodeId.value === nodeId ? null : nodeId
}

function selectEdge(edge: AssuranceDiagramEdge) {
  selectedNodeId.value = null
  selectedEdge.value = selectedEdge.value?.edge_id === edge.edge_id ? null : edge
}

function addEdgeHitArea(group: SVGGElement) {
  for (const segment of Array.from(group.querySelectorAll<SVGElement>('path, line, polyline'))) {
    const hit = segment.cloneNode(false) as SVGElement
    stripMarkerAttributes(hit)
    hit.setAttribute('fill', 'none')
    hit.setAttribute('stroke', 'transparent')
    hit.setAttribute('stroke-width', '12')
    hit.setAttribute('pointer-events', 'stroke')
    group.appendChild(hit)
  }
}

async function attachInteractivity() {
  interactionController?.abort()
  interactionController = new AbortController()
  const { signal } = interactionController
  await nextTick()
  const svgElement = svgContainer.value?.querySelector('svg')
  if (!svgElement) return
  const aliases = buildAssuranceAliasMap(nodes.value)
  const svgIdToAlias = new Map<string, string>()

  for (const group of Array.from(svgElement.querySelectorAll<SVGGElement>('g'))) {
    const candidates = [
      group.getAttribute('data-entity'),
      group.id.startsWith('entity_') ? group.id.slice(7) : group.id,
      group.getAttribute('data-qualified-name')?.split('.').pop(),
      group.querySelector(':scope > title')?.textContent?.trim(),
    ]
    const alias = candidates.find((candidate) => candidate && aliases.has(candidate))
    if (!alias) continue
    if (group.id) svgIdToAlias.set(group.id, alias)
    group.setAttribute('data-assurance-node-id', aliases.get(alias)!)
    group.addEventListener('click', (event) => {
      event.stopPropagation()
      selectNode(aliases.get(alias)!)
    }, { signal })
  }

  const edgeByPair = new Map<string, AssuranceDiagramEdge>()
  for (const edge of edges.value) {
    const source = [...aliases].find(([, id]) => id === edge.source_id)?.[0]
    const target = [...aliases].find(([, id]) => id === edge.target_id)?.[0]
    if (!source || !target) continue
    edgeByPair.set(`${source}:${target}`, edge)
    edgeByPair.set(`${target}:${source}`, edge)
  }
  for (const group of Array.from(svgElement.querySelectorAll<SVGGElement>('g[data-entity-1]'))) {
    const rawSource = group.getAttribute('data-entity-1') ?? ''
    const rawTarget = group.getAttribute('data-entity-2') ?? ''
    const source = svgIdToAlias.get(rawSource) ?? rawSource
    const target = svgIdToAlias.get(rawTarget) ?? rawTarget
    const edge = edgeByPair.get(`${source}:${target}`)
    if (!edge) continue
    addEdgeHitArea(group)
    group.setAttribute('data-assurance-edge-id', edge.edge_id ?? `${edge.source_id}:${edge.target_id}`)
    group.addEventListener('click', (event) => {
      event.stopPropagation()
      selectEdge(edge)
    }, { signal })
  }
}

async function load() {
  loading.value = true
  puml.value = null
  svg.value = null
  nodes.value = []
  edges.value = []
  error.value = null
  visibilityLimited.value = false
  selectedNodeId.value = null
  selectedEdge.value = null
  try {
    const response = await fetch(`/api/assurance/diagrams/${encodeURIComponent(props.diagramId)}/rendered`)
    if (response.status === 423) { error.value = 'Store is locked.'; return }
    if (response.status === 404) { error.value = 'Diagram not found.'; return }
    if (!response.ok) { error.value = `HTTP ${response.status}`; return }
    const body = await response.json() as {
      puml: string | null
      svg: string | null
      nodes: AssuranceDiagramNode[]
      edges: AssuranceDiagramEdge[]
      visibility_limited: boolean
    }
    puml.value = body.puml
    svg.value = body.svg
    nodes.value = body.nodes
    edges.value = body.edges
    visibilityLimited.value = body.visibility_limited
  } catch (cause) {
    error.value = String(cause)
  } finally {
    loading.value = false
  }
}

watch(() => props.diagramId, load)
watch(sanitizedSvg, () => { void attachInteractivity() }, { flush: 'post' })
onMounted(load)
onUnmounted(() => interactionController?.abort())
</script>

<template>
  <div class="assurance-diagram-panel">
    <div
      v-if="loading"
      class="panel-state"
    >
      Loading…
    </div>
    <div
      v-else-if="error"
      class="panel-error"
    >
      {{ error }}
    </div>
    <template v-else>
      <WithheldNotice
        v-if="visibilityLimited"
        kind="diagram nodes"
      />

      <div
        class="diagram-and-detail"
        :class="{ 'diagram-and-detail--selected': selectedNodeId || selectedEdge }"
      >
        <div class="diagram-content">
          <!-- eslint-disable-next-line vue/no-v-html -->
          <div
            v-if="sanitizedSvg"
            ref="svgContainer"
            class="svg-container"
            v-html="sanitizedSvg"
          />
          <div
            v-else-if="diagramId === 'uca-matrix'"
            class="uca-matrix-wrap"
          >
            <table class="uca-matrix">
              <thead>
                <tr>
                  <th>Control action</th>
                  <th
                    v-for="ucaType in UCA_TYPES"
                    :key="ucaType"
                  >
                    {{ ucaType }}
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="row in matrixRows"
                  :key="row.controlAction.node_id"
                >
                  <th>
                    <button
                      class="node-link"
                      @click="selectNode(row.controlAction.node_id)"
                    >
                      {{ row.controlAction.name }}
                    </button>
                  </th>
                  <td
                    v-for="ucaType in UCA_TYPES"
                    :key="ucaType"
                  >
                    <button
                      v-for="node in row.cells[ucaType] ?? []"
                      :key="node.node_id"
                      class="uca-chip"
                      @click="selectNode(node.node_id)"
                    >
                      {{ node.name }}
                    </button>
                    <span
                      v-if="!(row.cells[ucaType]?.length)"
                      class="empty-cell"
                    >—</span>
                  </td>
                </tr>
                <tr v-if="matrixRows.length === 0">
                  <td
                    :colspan="UCA_TYPES.length + 1"
                    class="empty-matrix"
                  >
                    No control actions found.
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div
            v-else
            class="diagram-fallback"
          >
            <p class="fallback-note">
              Diagram rendering is unavailable. Select a store node or edge below.
            </p>
            <div class="fallback-columns">
              <section>
                <h3>Nodes</h3>
                <button
                  v-for="node in nodes"
                  :key="node.node_id"
                  class="fallback-item"
                  :class="{ 'fallback-item--selected': selectedNodeId === node.node_id }"
                  @click="selectNode(node.node_id)"
                >
                  <strong>{{ node.name }}</strong>
                  <span>{{ node.node_type }}</span>
                </button>
              </section>
              <section>
                <h3>Edges</h3>
                <button
                  v-for="edge in edges"
                  :key="edge.edge_id ?? `${edge.source_id}:${edge.target_id}`"
                  class="fallback-item"
                  :class="{ 'fallback-item--selected': selectedEdge?.edge_id === edge.edge_id }"
                  @click="selectEdge(edge)"
                >
                  <strong>{{ edge.conn_type }}</strong>
                  <span>{{ nodeNames.get(edge.source_id) }} → {{ nodeNames.get(edge.target_id) }}</span>
                </button>
              </section>
            </div>
          </div>

          <div
            v-if="puml"
            class="puml-toggle"
          >
            <button
              class="puml-toggle-btn"
              @click="showPuml = !showPuml"
            >
              {{ showPuml ? 'Hide' : 'Show' }} PUML source
            </button>
            <pre
              v-if="showPuml"
              class="puml-source"
            >{{ puml }}</pre>
          </div>
        </div>

        <aside
          v-if="selectedNodeId || selectedEdge"
          class="selection-panel"
        >
          <AssuranceNodeDetail
            v-if="selectedNodeId"
            :node-id="selectedNodeId"
            @close="selectedNodeId = null"
          />
          <RouterLink
            v-if="selectedNodeId"
            class="edit-node-link"
            :to="{ path: '/assurance/browse', query: { node_id: selectedNodeId } }"
          >
            Edit in Assurance Browse →
          </RouterLink>
          <div
            v-else-if="selectedEdge"
            class="edge-detail"
          >
            <div class="edge-detail__header">
              <strong>{{ selectedEdge.conn_type }}</strong>
              <button
                aria-label="Close"
                @click="selectedEdge = null"
              >
                ×
              </button>
            </div>
            <p>{{ nodeNames.get(selectedEdge.source_id) }} → {{ nodeNames.get(selectedEdge.target_id) }}</p>
            <p v-if="selectedEdge.label || selectedEdge.name">
              {{ selectedEdge.label || selectedEdge.name }}
            </p>
            <div class="edge-actions">
              <RouterLink :to="{ path: '/assurance/browse', query: { node_id: selectedEdge.source_id } }">
                Edit source
              </RouterLink>
              <RouterLink :to="{ path: '/assurance/browse', query: { node_id: selectedEdge.target_id } }">
                Edit target
              </RouterLink>
            </div>
          </div>
        </aside>
      </div>
    </template>
  </div>
</template>

<style scoped>
.assurance-diagram-panel { display: flex; flex-direction: column; gap: 12px; }
.panel-state { color: #64748b; font-size: 13px; }
.panel-error { color: #dc2626; font-size: 13px; }
.diagram-and-detail { display: grid; grid-template-columns: minmax(0, 1fr); gap: 16px; }
.diagram-and-detail--selected { grid-template-columns: minmax(0, 1fr) minmax(260px, 340px); }
.diagram-content { min-width: 0; }
.selection-panel { border: 1px solid #e2e8f0; border-radius: 8px; background: #fff; overflow: hidden; }
.edit-node-link { display: block; padding: 0 16px 16px; font-size: 12px; color: #1d4ed8; }
.svg-container { overflow: auto; border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px; background: #fff; }
.svg-container :deep(svg) { max-width: 100%; height: auto; }
.svg-container :deep([data-assurance-node-id]),
.svg-container :deep([data-assurance-edge-id]) { cursor: pointer; }
.svg-container :deep([data-assurance-node-id]:hover) rect,
.svg-container :deep([data-assurance-node-id]:hover) polygon,
.svg-container :deep([data-assurance-node-id]:hover) ellipse { stroke: #2563eb !important; stroke-width: 2 !important; }
.uca-matrix-wrap { overflow-x: auto; }
.uca-matrix { width: 100%; border-collapse: collapse; font-size: 12px; }
.uca-matrix th, .uca-matrix td { border: 1px solid #cbd5e1; padding: 8px; text-align: left; vertical-align: top; min-width: 130px; }
.uca-matrix thead th { background: #f1f5f9; }
.node-link { border: 0; background: none; padding: 0; color: #1d4ed8; cursor: pointer; font-weight: 600; text-align: left; }
.uca-chip { display: block; width: 100%; border: 1px solid #bfdbfe; border-radius: 5px; background: #eff6ff; color: #1e3a8a; padding: 6px; text-align: left; cursor: pointer; margin-bottom: 4px; }
.empty-cell, .empty-matrix { color: #94a3b8; }
.diagram-fallback { border: 1px solid #e2e8f0; border-radius: 6px; padding: 14px; background: #f8fafc; }
.fallback-note { margin: 0 0 12px; color: #64748b; font-size: 12px; }
.fallback-columns { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.fallback-columns h3 { margin: 0 0 8px; font-size: 12px; text-transform: uppercase; color: #475569; }
.fallback-item { display: flex; flex-direction: column; gap: 2px; width: 100%; margin-bottom: 6px; padding: 8px; border: 1px solid #cbd5e1; border-radius: 5px; background: #fff; text-align: left; cursor: pointer; }
.fallback-item span { color: #64748b; font-size: 11px; }
.fallback-item--selected { border-color: #2563eb; background: #eff6ff; }
.edge-detail { padding: 16px; font-size: 13px; }
.edge-detail__header { display: flex; justify-content: space-between; }
.edge-detail__header button { border: 0; background: none; cursor: pointer; font-size: 18px; }
.edge-actions { display: flex; gap: 12px; }
.puml-toggle { margin-top: 10px; }
.puml-toggle-btn { font-size: 12px; color: #6b7280; background: none; border: none; cursor: pointer; padding: 0; text-decoration: underline; }
.puml-source { font-size: 11px; background: #1e293b; color: #e2e8f0; padding: 12px; border-radius: 6px; overflow-x: auto; white-space: pre; margin: 8px 0 0; }
@media (max-width: 900px) {
  .diagram-and-detail--selected { grid-template-columns: 1fr; }
  .fallback-columns { grid-template-columns: 1fr; }
}
</style>
