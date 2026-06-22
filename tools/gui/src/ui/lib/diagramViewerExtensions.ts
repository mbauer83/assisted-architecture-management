import type { Component } from 'vue'

/**
 * Viewer-side diagram-type extension registry.
 *
 * Mirrors `diagramAuthoringExtensions` but for the read-only diagram viewer: a diagram type
 * may contribute selectable *sub-parts* of an entity node (e.g. a classifier's attribute rows)
 * plus a sidebar panel that renders the selected sub-part's detail. This keeps all diagram-type
 * knowledge inside `ui/diagram-types/<type>/`; the generic viewer only knows "a type may make
 * node sub-parts selectable and supply a detail component", never what a classifier or an
 * attribute is.
 */
export interface ViewerSubPartContext {
  /** Resolved entity id of the node (its `data-entity-id`). */
  entityId: string
  /** The SVG `<g>` element for this entity. */
  node: SVGGElement
  /** Raw `diagram-entities` frontmatter — shape is owned by the diagram type. */
  diagramEntities: Record<string, unknown>
  /** Aborted when interactivity is re-attached; use to scope event listeners. */
  signal: AbortSignal
  /**
   * Select a sub-part. `detail` is opaque to the viewer and handed to `detailComponent` as
   * `detail`. `elements` are the SVG nodes that make up the sub-part (e.g. an attribute row's
   * glyph and label); the viewer toggles a generic selected-highlight class on them.
   */
  onSelect: (detail: unknown, elements?: Element[]) => void
}

export interface DiagramViewerExtension {
  /** Attach click handlers to selectable sub-parts within an entity node. */
  attachNodeSubParts: (ctx: ViewerSubPartContext) => void
  /** Sidebar component for a selected sub-part. Receives `detail` (the `onSelect` payload); emits `close`. */
  detailComponent: Component
}

const registry = new Map<string, DiagramViewerExtension>()

export const registerViewerExtension = (diagramType: string, ext: DiagramViewerExtension): void => {
  registry.set(diagramType, ext)
}

export const lookupViewerExtension = (
  diagramType: string | null | undefined,
): DiagramViewerExtension | undefined => (diagramType ? registry.get(diagramType) : undefined)
