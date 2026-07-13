/**
 * Pure helpers for the ad-hoc `diagram` execution representation: synthesizes the minimal
 * `EntitySummary`/`DiagramConnection` shapes the generic graphviz/PlantUML element mapper
 * (`graphvizElementMapping.ts`) needs to resolve SVG elements back to artifact ids, plus
 * the `node_color`/`edge_color`/`edge_emphasis` highlight-overlay application — the same
 * client-side technique a real diagram's ghost/hide overlay uses, never baked into the
 * rendered PUML.
 */

import type { ConnectionItemSummary, DiagramConnection, EntityItemSummary, EntitySummary, ProjectedOccurrence } from '../../domain'
import type { StyleValue } from '../../domain/schemas/viewpoints'
import { resolveStyleColor, styleTokenString, tokenEdgeEmphasis } from '../lib/viewpointStyleTokens'

/** `graphvizMapElements` reads only `artifact_id`/`display_alias`; the ArchiMate renderer's
 * convention is alias === artifact_id (see `_ConfiguredArchimateDiagramType`'s write
 * guidance), so the stub only needs those two fields populated meaningfully — the rest are
 * placeholders never read by the mapper, following the same stub convention
 * `EditMatrixView.vue` already uses for its entity picker. */
export const toEntitySummaryStub = (entity: EntityItemSummary): EntitySummary => ({
  artifact_id: entity.id, artifact_type: entity.type, name: entity.name,
  display_alias: entity.id, version: '', status: '', domain: '', subdomain: '', path: '',
})

export const toDiagramConnectionStub = (connection: ConnectionItemSummary): DiagramConnection => ({
  artifact_id: connection.id, source: connection.source, target: connection.target, conn_type: connection.type,
  source_alias: connection.source, target_alias: connection.target,
  version: '', status: '', path: '', content_text: '', source_name: '', target_name: '',
})

const setOrClearStroke = (shape: SVGElement, color: string | null, width: string | null): void => {
  if (color !== null) shape.style.setProperty('stroke', color, 'important')
  else shape.style.removeProperty('stroke')
  if (width !== null) shape.style.setProperty('stroke-width', width, 'important')
  else shape.style.removeProperty('stroke-width')
}

const shapeChildren = (el: Element): SVGElement[] =>
  [...el.querySelectorAll('rect, polygon, path')].filter((n): n is SVGElement => n instanceof SVGElement)

/** `node_color` highlight overlay: a colored outline on the node's shape children, fixed
 * notation (fill/shape) otherwise untouched — an overlay, not a notation change. */
export const applyNodeColorOverlay = (elems: readonly Element[], value: StyleValue | undefined): void => {
  for (const el of elems) {
    for (const shape of shapeChildren(el)) setOrClearStroke(shape, value !== undefined ? resolveStyleColor(value) : null, value !== undefined ? '3' : null)
  }
}

/** `edge_color`/`edge_emphasis` highlight overlay, mirroring the exploration surface's
 * `edgeVisualFor` mapping (`GraphExploreView.helpers.ts`) but applied to real SVG path
 * elements instead of the custom force-graph renderer. */
export const applyEdgeHighlightOverlay = (
  elems: readonly Element[],
  colorValue: StyleValue | undefined,
  emphasisValue: StyleValue | undefined,
): void => {
  const emphasis = emphasisValue !== undefined ? tokenEdgeEmphasis(styleTokenString(emphasisValue)) : null
  for (const el of elems) {
    for (const shape of shapeChildren(el)) {
      setOrClearStroke(shape, colorValue !== undefined ? resolveStyleColor(colorValue) : null, emphasis ? String(emphasis.strokeWidth) : null)
      if (emphasis?.dashArray !== undefined) shape.style.setProperty('stroke-dasharray', emphasis.dashArray, 'important')
      else shape.style.removeProperty('stroke-dasharray')
    }
  }
}

export const projectionByItemId = (items: readonly ProjectedOccurrence[]): ReadonlyMap<string, ProjectedOccurrence> =>
  new Map(items.map((item) => [item.item_id, item]))
