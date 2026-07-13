import { computed, onUnmounted, ref, type Ref } from 'vue'

/**
 * Drag-to-resize for a two-column layout's right-hand sidebar, clamped to
 * [260px, min(520px, 45% of the grid width)]. `gridRef` is the grid container the width
 * percentage is measured against.
 */
export function useSidebarResize(gridRef: Ref<HTMLElement | null>) {
  const sidebarWidth = ref(320)
  const gridStyle = computed(() => ({ '--sidebar-width': `${sidebarWidth.value}px` }))

  const clampSidebarWidth = (nextWidth: number): number => {
    const gridWidth = gridRef.value?.getBoundingClientRect().width ?? window.innerWidth
    const minWidth = 260
    const maxWidth = Math.min(520, Math.max(minWidth, Math.floor(gridWidth * 0.45)))
    return Math.min(maxWidth, Math.max(minWidth, nextWidth))
  }

  let resizing = false

  const onResizeMove = (e: MouseEvent) => {
    if (!resizing || !gridRef.value) return
    const rect = gridRef.value.getBoundingClientRect()
    sidebarWidth.value = clampSidebarWidth(rect.right - e.clientX)
  }

  const stopResize = () => {
    resizing = false
    document.body.classList.remove('diagram-split-resizing')
    window.removeEventListener('mousemove', onResizeMove)
    window.removeEventListener('mouseup', stopResize)
  }

  const startResize = (e: MouseEvent) => {
    if (!gridRef.value) return
    const rect = gridRef.value.getBoundingClientRect()
    if (rect.width < 900) return
    e.preventDefault()
    resizing = true
    document.body.classList.add('diagram-split-resizing')
    window.addEventListener('mousemove', onResizeMove)
    window.addEventListener('mouseup', stopResize)
  }

  onUnmounted(stopResize)

  return { gridStyle, startResize }
}
