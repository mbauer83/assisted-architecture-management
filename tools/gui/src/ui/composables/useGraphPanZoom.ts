import { computed, ref, type Ref } from 'vue'
import type { GraphNode } from './useForceGraph'
import { fitViewBox, type ViewBoxRect } from '../components/GraphCanvas.helpers'

/**
 * SVG pan/zoom/drag interaction for the graph explorer: wheel zoom around the cursor,
 * background panning, node dragging (pins the node while held), plus the explicit
 * zoom-in/out and fit-to-view controls — one place for all viewBox mutations.
 */
export function useGraphPanZoom(
  svgRef: Ref<SVGSVGElement | null>,
  svgWidth: Ref<number>,
  svgHeight: Ref<number>,
  nodes: Ref<GraphNode[]>,
  onDragTick: () => void,
) {
  const viewBox = ref<ViewBoxRect>({ x: 0, y: 0, w: 800, h: 600 })
  const isPanning = ref(false)
  const panStart = ref({ x: 0, y: 0 })
  const dragging = ref<GraphNode | null>(null)
  const dragOffset = ref({ x: 0, y: 0 })

  const toSvgCoords = (clientX: number, clientY: number) => {
    const svg = svgRef.value
    if (!svg) return { x: clientX, y: clientY }
    const pt = svg.createSVGPoint()
    pt.x = clientX
    pt.y = clientY
    const ctm = svg.getScreenCTM()?.inverse()
    if (!ctm) return { x: clientX, y: clientY }
    const svgPt = pt.matrixTransform(ctm)
    return { x: svgPt.x, y: svgPt.y }
  }

  const onNodeMouseDown = (e: MouseEvent, n: GraphNode) => {
    e.preventDefault()
    e.stopPropagation()
    dragging.value = n
    n.pinned = true
    const svgPt = toSvgCoords(e.clientX, e.clientY)
    dragOffset.value = { x: n.x - svgPt.x, y: n.y - svgPt.y }
  }

  const onSvgMouseMove = (e: MouseEvent) => {
    if (dragging.value) {
      const svgPt = toSvgCoords(e.clientX, e.clientY)
      dragging.value.x = svgPt.x + dragOffset.value.x
      dragging.value.y = svgPt.y + dragOffset.value.y
      onDragTick()
      return
    }
    if (isPanning.value) {
      const dx = (e.clientX - panStart.value.x) * (viewBox.value.w / svgWidth.value)
      const dy = (e.clientY - panStart.value.y) * (viewBox.value.h / svgHeight.value)
      viewBox.value.x -= dx
      viewBox.value.y -= dy
      panStart.value = { x: e.clientX, y: e.clientY }
    }
  }

  const onSvgMouseUp = () => {
    if (dragging.value) {
      dragging.value.pinned = false
      dragging.value = null
      onDragTick()
    }
    isPanning.value = false
  }

  const onSvgMouseDown = (e: MouseEvent) => {
    isPanning.value = true
    panStart.value = { x: e.clientX, y: e.clientY }
  }

  const onWheel = (e: WheelEvent) => {
    e.preventDefault()
    const factor = e.deltaY > 0 ? 1.1 : 0.9
    const svgPt = toSvgCoords(e.clientX, e.clientY)
    const box = viewBox.value
    box.x = svgPt.x - (svgPt.x - box.x) * factor
    box.y = svgPt.y - (svgPt.y - box.y) * factor
    box.w *= factor
    box.h *= factor
  }

  const zoomBy = (factor: number) => {
    const box = viewBox.value
    const cx = box.x + box.w / 2
    const cy = box.y + box.h / 2
    box.w *= factor
    box.h *= factor
    box.x = cx - box.w / 2
    box.y = cy - box.h / 2
  }

  const fitToView = () => {
    viewBox.value = fitViewBox(nodes.value, svgWidth.value, svgHeight.value)
  }

  const vb = computed(() => `${viewBox.value.x} ${viewBox.value.y} ${viewBox.value.w} ${viewBox.value.h}`)

  return {
    viewBox, vb, dragging,
    onNodeMouseDown, onSvgMouseDown, onSvgMouseMove, onSvgMouseUp, onWheel,
    zoomBy, fitToView,
  }
}
