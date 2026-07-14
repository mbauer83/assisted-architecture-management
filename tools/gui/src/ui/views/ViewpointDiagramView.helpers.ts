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

/** `graphvizMapElements` reads only `artifact_id`/`display_alias`; `display_alias` must be
 * the rendered SVG's real PlantUML alias (`execute_viewpoint_diagram`'s `entity_aliases`
 * response field — never the raw artifact id, which the ad-hoc renderer never uses as an
 * alias), or click-to-select never resolves any SVG element back to its entity. Falls back
 * to the raw id only when the map has no entry (e.g. an entity dropped from the final
 * render), matching the same stub convention `EditMatrixView.vue` uses for its picker. */
export const toEntitySummaryStub = (
  entity: EntityItemSummary,
  aliasById: ReadonlyMap<string, string> = new Map(),
): EntitySummary => ({
  artifact_id: entity.id, artifact_type: entity.type, name: entity.name,
  display_alias: aliasById.get(entity.id) ?? entity.id, version: '', status: '', domain: '', subdomain: '', path: '',
})

/** `nameById` fills in the sidebar's connection-flow display (`source_name`/`target_name`);
 * `aliasById` resolves `source_alias`/`target_alias` the same way `toEntitySummaryStub`
 * does — both fall back to the raw id when the lookup has no entry. `certainty`/`hops`/
 * `via_connection_ids` carry straight through from the execution result unchanged (`null`/
 * empty for a real, modeled connection) — the sidebar uses `certainty` to decide whether
 * to offer the witness chain. */
export const toDiagramConnectionStub = (
  connection: ConnectionItemSummary,
  nameById: ReadonlyMap<string, string> = new Map(),
  aliasById: ReadonlyMap<string, string> = new Map(),
): DiagramConnection => ({
  artifact_id: connection.id, source: connection.source, target: connection.target, conn_type: connection.type,
  source_alias: aliasById.get(connection.source) ?? connection.source,
  target_alias: aliasById.get(connection.target) ?? connection.target,
  version: '', status: '', path: '', content_text: '',
  source_name: nameById.get(connection.source) ?? connection.source,
  target_name: nameById.get(connection.target) ?? connection.target,
  certainty: connection.certainty,
  hops: connection.hops,
  via_connection_ids: connection.via_connection_ids,
})

/** Applies an override only when a value is given — NEVER clears, since `shape.style` is
 * the SAME `style="..."` attribute PlantUML already populated with the notation's native
 * stroke (e.g. every connector line's `fill="none"` relies entirely on its own native
 * stroke for visibility). `style.removeProperty` can't distinguish "an overlay I set
 * earlier" from "the renderer's own native declaration" once they share one attribute, so
 * clearing unconditionally would delete native styling wherever no overlay applies — which
 * is every unstyled connection/entity, i.e. almost always. Each execution renders a fresh
 * SVG via `v-html`, so there is never a stale prior overlay on this element to revert. */
const applyStrokeOverride = (shape: SVGElement, color: string | null, width: string | null): void => {
  if (color !== null) shape.style.setProperty('stroke', color, 'important')
  if (width !== null) shape.style.setProperty('stroke-width', width, 'important')
}

const shapeChildren = (el: Element): SVGElement[] =>
  [...el.querySelectorAll('rect, polygon, path')].filter((n): n is SVGElement => n instanceof SVGElement)

/** `node_color` highlight overlay: a colored outline on the node's shape children, fixed
 * notation (fill/shape) otherwise untouched — an overlay, not a notation change. */
export const applyNodeColorOverlay = (elems: readonly Element[], value: StyleValue | undefined): void => {
  if (value === undefined) return
  for (const el of elems) {
    for (const shape of shapeChildren(el)) applyStrokeOverride(shape, resolveStyleColor(value), '3')
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
  if (colorValue === undefined && emphasisValue === undefined) return
  const emphasis = emphasisValue !== undefined ? tokenEdgeEmphasis(styleTokenString(emphasisValue)) : null
  for (const el of elems) {
    for (const shape of shapeChildren(el)) {
      applyStrokeOverride(
        shape,
        colorValue !== undefined ? resolveStyleColor(colorValue) : null,
        emphasis ? String(emphasis.strokeWidth) : null,
      )
      if (emphasis?.dashArray !== undefined) shape.style.setProperty('stroke-dasharray', emphasis.dashArray, 'important')
    }
  }
}

export const projectionByItemId = (items: readonly ProjectedOccurrence[]): ReadonlyMap<string, ProjectedOccurrence> =>
  new Map(items.map((item) => [item.item_id, item]))

/** Tags each derived connection's matched SVG elements with `data-certainty` — nothing
 * else reads the notation differently for a derived edge (PlantUML draws every connection
 * the same way regardless of provenance), so this is purely a hook for the sidebar's own
 * click handling and for tests to target a derived edge deterministically. */
export const markDerivedConnections = (
  edges: ReadonlyMap<string, readonly Element[]>,
  connections: readonly DiagramConnection[],
): void => {
  const certaintyByConnId = new Map(connections.filter((c) => c.certainty).map((c) => [c.artifact_id, c.certainty!]))
  for (const [connId, elems] of edges) {
    const certainty = certaintyByConnId.get(connId)
    if (!certainty) continue
    for (const el of elems) el.setAttribute('data-certainty', certainty)
  }
}
