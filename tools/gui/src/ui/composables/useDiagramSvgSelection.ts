import { nextTick, ref, watch, type Ref } from 'vue'
import type { Router } from 'vue-router'
import { Exit } from 'effect'
import type { ModelService } from '../../application/ModelService'
import type { DiagramConnection, EntityDetail, EntitySummary } from '../../domain'
import { useQuery } from './useQuery'
import { useMutation } from './useMutation'
import type { WriteResult } from '../../domain'
import type { RepoError } from '../../ports/ModelRepository'
import type { NotFoundError } from '../../domain'
import type { MarkdownError } from '../../application/MarkdownService'
import { lookupViewerExtension, resolveElementMap, neutralizeSentinelLink } from '../lib/diagramViewerExtensions'
import { SVG_MARKER_ATTRIBUTES } from '../lib/svgHitAreas'

/** The only two `DiagramContext['diagram']` fields this composable actually reads — a real
 * persisted diagram's full detail record satisfies this structurally, but so does an
 * ephemeral, never-persisted rendering (a viewpoint's ad-hoc `diagram` execution) that has
 * no artifact id/version/status of its own to report. */
export interface DiagramSvgSelectionDetail {
  diagram_type: string
  diagram_entities?: unknown
}

/**
 * Wires click-to-select interactivity into a rendered diagram SVG (entities, connections,
 * diagram-type-specific sub-parts, C4 drill-down badges) and owns the resulting selection
 * state (which entity/connection/sub-part is selected, the inline edge-label editor).
 * Re-attaches whenever the SVG or the entity/connection lists it needs to match against
 * change. Delegates all type-specific node matching to the diagram type's viewer extension
 * (`resolveElementMap`) — this composable only knows about the generic click/select contract.
 */
export function useDiagramSvgSelection(options: {
  svc: ModelService
  router: Router
  svgHtml: Ref<string | null>
  detail: Ref<DiagramSvgSelectionDetail | null>
  diagramEntities: Ref<readonly EntitySummary[]>
  diagramConnections: Ref<readonly DiagramConnection[]>
  drilldownByEntityId: Ref<Record<string, string>>
  diagramId: Ref<string>
  reload: () => void
}) {
  const { svc, router, svgHtml, detail, diagramEntities, diagramConnections, drilldownByEntityId, diagramId, reload } = options

  const viewerExtension = ref(lookupViewerExtension(detail.value?.diagram_type))
  watch(detail, (d) => { viewerExtension.value = lookupViewerExtension(d?.diagram_type) })

  const svgContainer = ref<HTMLElement | null>(null)
  const svgNodeElems = ref(new Map<string, Element[]>())
  const prevHighlighted = ref<Element[]>([])
  const selectedConnectionGroup = ref<SVGGElement | null>(null)
  let interactivityController: AbortController | null = null
  let attachRun = 0

  const selectedId = ref<string | null>(null)
  const selectedConnection = ref<DiagramConnection | null>(null)
  // Opaque payload from the diagram type's viewer extension; rendered by its detailComponent.
  const selectedSubPart = ref<unknown>(null)
  let selectedSubPartEls: Element[] = []
  const entityQuery = useQuery<EntityDetail, RepoError | NotFoundError | MarkdownError>()

  const edgeLabelInput = ref('')
  const edgeLabelMutation = useMutation<WriteResult, RepoError>()
  watch(selectedConnection, (conn) => { edgeLabelInput.value = conn?.edge_label_override ?? '' })

  watch(selectedId, (newId) => {
    for (const el of prevHighlighted.value) el.classList.remove('svg-selected')
    prevHighlighted.value = []
    if (!newId) return
    const els = svgNodeElems.value.get(newId) ?? []
    for (const el of els) el.classList.add('svg-selected')
    prevHighlighted.value = els
  })

  const clearConnection = () => {
    selectedConnectionGroup.value?.classList.remove('svg-conn-selected')
    selectedConnectionGroup.value = null
    selectedConnection.value = null
  }
  const clearSubPart = () => {
    for (const el of selectedSubPartEls) el.classList.remove('svg-subpart-selected')
    selectedSubPartEls = []
    selectedSubPart.value = null
  }
  const selectConnection = (conn: DiagramConnection, el: SVGGElement) => {
    if (selectedId.value) selectedId.value = null
    clearSubPart()
    const same = selectedConnection.value?.artifact_id === conn.artifact_id
    clearConnection()
    if (!same) {
      selectedConnection.value = conn
      selectedConnectionGroup.value = el
      el.classList.add('svg-conn-selected')
    }
  }
  const selectSubPart = (subPartDetail: unknown, elements: Element[] = []) => {
    clearConnection()
    if (selectedId.value) { selectedId.value = null; entityQuery.reset() }
    clearSubPart()
    selectedSubPart.value = subPartDetail
    selectedSubPartEls = elements
    for (const el of elements) el.classList.add('svg-subpart-selected')
  }
  const selectEntity = (id: string) => {
    clearConnection()
    clearSubPart()
    if (selectedId.value === id) {
      selectedId.value = null
      entityQuery.reset()
      return
    }
    selectedId.value = id
    entityQuery.run(svc.getEntity(id))
  }

  let savingEdgeLabel = false
  const saveEdgeLabel = async () => {
    if (savingEdgeLabel) return
    const conn = selectedConnection.value
    if (!conn?.edge_key || !diagramId.value) return
    const rawLabel = edgeLabelInput.value.trim()
    const label = rawLabel.length > 0 ? rawLabel : null
    savingEdgeLabel = true
    try {
      const exit = await edgeLabelMutation.run(
        svc.setEdgeLabel({ artifact_id: diagramId.value, edge_key: conn.edge_key, label, dry_run: false }),
      )
      if (Exit.isSuccess(exit)) reload()
    } finally {
      savingEdgeLabel = false
    }
  }

  const addConnectionHitAreas = (group: SVGGElement) => {
    for (const oldHit of Array.from(group.querySelectorAll('[data-conn-hit]'))) oldHit.remove()
    const segments = Array.from(group.querySelectorAll<SVGElement>('path, line, polyline'))
    for (const segment of segments) {
      if (segment.closest('[data-entity-id]')) continue
      const tag = segment.tagName.toLowerCase()
      const hit = document.createElementNS('http://www.w3.org/2000/svg', tag)
      const skippedAttrs: readonly string[] = ['id', 'class', 'style', ...SVG_MARKER_ATTRIBUTES]
      for (const attr of Array.from(segment.attributes)) {
        if (skippedAttrs.includes(attr.name)) continue
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

  // Delegate selectable node sub-parts (e.g. datatype attribute rows) to the diagram type's
  // viewer extension, if any — keeps all type-specific knowledge out of this generic view.
  const attachNodeSubParts = (g: SVGGElement, entityId: string, signal: AbortSignal) => {
    const ext = viewerExtension.value
    const diagramTypeEntities = detail.value?.diagram_entities
    if (!ext || typeof diagramTypeEntities !== 'object' || diagramTypeEntities === null) return
    ext.attachNodeSubParts({
      entityId,
      node: g,
      diagramEntities: diagramTypeEntities as Record<string, unknown>,
      signal,
      onSelect: selectSubPart,
    })
  }

  const attachInteractivity = async () => {
    const runId = ++attachRun
    interactivityController?.abort()
    interactivityController = new AbortController()
    const { signal } = interactivityController
    svgNodeElems.value.clear()
    prevHighlighted.value = []
    await nextTick()
    await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()))
    if (runId !== attachRun || signal.aborted) return
    const svgEl = svgContainer.value?.querySelector('svg')
    if (!svgEl || !diagramEntities.value.length) return

    // Renderer-specific SVG↔artifact matching lives behind the viewer-extension contract; this
    // composable only consumes the resulting maps, never the diagram type's SVG conventions
    // directly.
    const rawDiagramEntities = detail.value?.diagram_entities
    const { nodes, edges } = resolveElementMap(detail.value?.diagram_type, svgEl, {
      entities: diagramEntities.value,
      connections: diagramConnections.value,
      diagramEntities: typeof rawDiagramEntities === 'object' && rawDiagramEntities !== null
        ? (rawDiagramEntities as Record<string, unknown>)
        : undefined,
    })

    for (const [artifactId, elems] of nodes) {
      svgNodeElems.value.set(artifactId, elems)
      for (const g of elems) {
        // Mapped representatives may be group/anchor elements OR bare shapes (an activity
        // step's rect/polygon, mapped so the whole step is clickable, not only its label).
        if (!(g instanceof SVGElement)) continue
        g.setAttribute('data-entity-id', artifactId)
        g.addEventListener('click', (ev) => { ev.stopPropagation(); ev.preventDefault(); selectEntity(artifactId) }, { signal })
        if (g instanceof SVGGElement) attachNodeSubParts(g, artifactId, signal)
        else if (g instanceof SVGAElement) neutralizeSentinelLink(g)
      }
    }

    // Inject drill-down badges for entities that scope a child C4 diagram.
    // Badges sit at the node's top-right corner inside the SVG coordinate space (first occurrence).
    const drillTargets = drilldownByEntityId.value
    for (const [artifactId, targetId] of Object.entries(drillTargets)) {
      const entityEl = svgNodeElems.value.get(artifactId)?.[0]
      if (!(entityEl instanceof SVGGraphicsElement)) continue
      try {
        const bbox = entityEl.getBBox()
        if (!bbox.width || !bbox.height) continue
        const badgeG = document.createElementNS('http://www.w3.org/2000/svg', 'g')
        badgeG.setAttribute('class', 'c4-drill-badge')
        badgeG.setAttribute('transform', `translate(${bbox.x + bbox.width - 18},${bbox.y + 2})`)
        const br = document.createElementNS('http://www.w3.org/2000/svg', 'rect')
        br.setAttribute('width', '16'); br.setAttribute('height', '14'); br.setAttribute('rx', '3')
        br.setAttribute('fill', '#1e40af'); br.setAttribute('opacity', '0.85')
        br.setAttribute('cursor', 'pointer')
        badgeG.appendChild(br)
        const bt = document.createElementNS('http://www.w3.org/2000/svg', 'text')
        bt.setAttribute('x', '8'); bt.setAttribute('y', '11')
        bt.setAttribute('text-anchor', 'middle'); bt.setAttribute('font-size', '10')
        bt.setAttribute('fill', 'white'); bt.setAttribute('pointer-events', 'none')
        bt.textContent = '⤵'
        badgeG.appendChild(bt)
        svgEl.appendChild(badgeG)
        badgeG.addEventListener('click', (ev) => {
          ev.stopPropagation()
          void router.push({ path: '/diagram', query: { id: targetId } })
        }, { signal })
      } catch { /* getBBox unavailable in non-rendered contexts */ }
    }

    for (const [connArtifactId, elems] of edges) {
      const conn = diagramConnections.value.find((c) => c.artifact_id === connArtifactId)
      if (!conn) continue
      for (const g of elems) {
        if (!(g instanceof SVGGElement) || g.hasAttribute('data-conn-id')) continue
        addConnectionHitAreas(g)
        g.setAttribute('data-conn-id', conn.artifact_id)
        g.addEventListener('click', (ev) => { ev.stopPropagation(); selectConnection(conn, g) }, { signal })
      }
    }
  }

  watch([svgHtml, diagramEntities, diagramConnections], () => { void attachInteractivity() }, { flush: 'post' })

  return {
    viewerExtension,
    svgContainer,
    selectedId,
    selectedConnection,
    selectedSubPart,
    entityQuery,
    edgeLabelInput,
    edgeLabelMutation,
    selectEntity,
    clearConnection,
    clearSubPart,
    saveEdgeLabel,
  }
}
