/**
 * Pure helpers for the viewpoint-driven exploration mode: `group_by` -> cluster key
 * resolution, style-token -> node/edge visual mapping layered on top of
 * `viewpointStyleTokens.ts`'s fixed vocabulary, and anchored-execution derivations
 * (hop distances, layout choice, distance coloring).
 */

import type {
  ConnectionItemSummary, EntityItemSummary, ProjectedOccurrence, ViewpointDefinitionEnvelope, ViewpointProjection,
} from '../../domain'
import type { StyleValue } from '../../domain/schemas/viewpoints'
import { resolveStyleColor, styleTokenString, tokenShape, tokenIconLetter, tokenEdgeEmphasis } from '../lib/viewpointStyleTokens'
import { presentationFromMapping } from '../../domain/viewpointPresentationSerialization'
import { executionRouteFor } from './ViewpointsManagementView.helpers'

/** The in-page viewpoint selector executes exploration-representation definitions
 * in place; anything else (table/matrix/diagram) must redirect to its own dedicated
 * surface instead of being force-rendered as a graph, which is how it declared its
 * intended presentation. `null` means "stay here and execute as exploration". */
export const explorationRedirectFor = (
  envelope: ViewpointDefinitionEnvelope | undefined,
): { path: string; query: { viewpoint: string } } | null => {
  if (!envelope) return null
  const representation = presentationFromMapping(envelope.presentation)?.representation ?? 'exploration'
  return representation === 'exploration' ? null : executionRouteFor(envelope)
}

/** Same shape as `EditDiagramView.helpers.ts`'s function of the same name — kept as a
 * small local duplicate rather than a cross-view import so this view's helper module has
 * no dependency on another view's already-shipped module. */
export const projectionByItemId = (projection: ViewpointProjection | null): ReadonlyMap<string, ProjectedOccurrence> =>
  new Map((projection?.items ?? []).map((item) => [item.item_id, item]))

/** `GraphEdge` (a rendered force-graph edge) is keyed by source/target/connType, not the
 * underlying connection's artifact id — this derives the matching key so a connection's
 * style (looked up by id via `projectionByItemId`) can be joined back onto it. */
export const edgeStyleKey = (source: string, target: string, connType: string): string => `${source}|${target}|${connType}`

export const buildConnectionStyleIndex = (
  connections: readonly ConnectionItemSummary[],
  projection: ViewpointProjection | null,
): ReadonlyMap<string, Readonly<Record<string, StyleValue>>> => {
  const byId = projectionByItemId(projection)
  const index = new Map<string, Readonly<Record<string, StyleValue>>>()
  for (const connection of connections) {
    const item = byId.get(connection.id)
    if (item) index.set(edgeStyleKey(connection.source, connection.target, connection.type), item.style)
  }
  return index
}

/** `group_by` resolves against the fixed entity summary — the three well-known
 * non-attribute dimensions are always resolvable; an arbitrary profile-attribute path is
 * not (the summary carries no properties map), so it falls back to grouping by type
 * rather than silently mis-grouping. */
export const groupKeyFor = (entity: Pick<EntityItemSummary, 'type' | 'group' | 'specialization_slugs'>, groupBy: string | null): string => {
  if (groupBy === 'group') return entity.group
  if (groupBy === 'specialization') return entity.specialization_slugs[0] ?? '(none)'
  return entity.type
}

export interface NodeVisual {
  readonly color: string
  readonly shape: 'circle' | 'diamond' | 'triangle' | 'square'
  readonly iconLetter: string | null
}

/** `node_color`/`node_shape`/`node_icon` resolved from the projection's per-entity style
 * map, falling back to the existing domain-color convention when the viewpoint carries
 * no styling for a given capability. `node_color` alone can be a scale-mode
 * `{position, tokens}` value (interpolated); shape/icon always read a discrete token. */
export const nodeVisualFor = (style: Readonly<Record<string, StyleValue>> | undefined, fallbackColor: string): NodeVisual => ({
  color: style?.node_color !== undefined ? resolveStyleColor(style.node_color) : fallbackColor,
  shape: style?.node_shape !== undefined ? tokenShape(styleTokenString(style.node_shape)) : 'circle',
  iconLetter: style?.node_icon !== undefined ? tokenIconLetter(styleTokenString(style.node_icon)) : null,
})

const SHAPE_SIDES: Record<NodeVisual['shape'], number> = { circle: 24, diamond: 4, square: 4, triangle: 3 }
const SHAPE_ROTATION: Record<NodeVisual['shape'], number> = { circle: 0, diamond: 0, square: Math.PI / 4, triangle: -Math.PI / 2 }

/** Renders every `node_shape` as a regular polygon (a 24-gon reads as a circle) so the
 * fixed-notation exploration surface can show real shape variety with one SVG element
 * type — no per-shape template branching. */
export const nodeShapePoints = (shape: NodeVisual['shape'], radius: number): string => {
  const sides = SHAPE_SIDES[shape]
  const rotation = SHAPE_ROTATION[shape]
  const points: string[] = []
  for (let i = 0; i < sides; i++) {
    const angle = rotation + (i / sides) * Math.PI * 2
    points.push(`${(Math.cos(angle) * radius).toFixed(2)},${(Math.sin(angle) * radius).toFixed(2)}`)
  }
  return points.join(' ')
}

/** Multi-source BFS over the undirected edge set: hop distance from the nearest anchor
 * for every reachable node. Unreachable nodes (and anchors absent from `nodeIds`) are
 * simply absent from the map — callers treat "no distance" as its own visual category. */
export const hopDistances = (
  anchorIds: readonly string[],
  edges: readonly { source: string; target: string }[],
  nodeIds: readonly string[],
): Map<string, number> => {
  const nodeSet = new Set(nodeIds)
  const adjacency = new Map<string, string[]>()
  for (const edge of edges) {
    if (!nodeSet.has(edge.source) || !nodeSet.has(edge.target)) continue
    if (!adjacency.has(edge.source)) adjacency.set(edge.source, [])
    if (!adjacency.has(edge.target)) adjacency.set(edge.target, [])
    adjacency.get(edge.source)!.push(edge.target)
    adjacency.get(edge.target)!.push(edge.source)
  }
  const distances = new Map<string, number>()
  const queue: string[] = []
  for (const anchorId of anchorIds) {
    if (nodeSet.has(anchorId) && !distances.has(anchorId)) {
      distances.set(anchorId, 0)
      queue.push(anchorId)
    }
  }
  for (let head = 0; head < queue.length; head++) {
    const current = queue[head]
    const depth = distances.get(current)!
    for (const neighbor of adjacency.get(current) ?? []) {
      if (!distances.has(neighbor)) {
        distances.set(neighbor, depth + 1)
        queue.push(neighbor)
      }
    }
  }
  return distances
}

export type ExplorationLayoutChoice = 'clusters' | 'radial' | 'force'
export type ExplorationLayoutOverride = ExplorationLayoutChoice | 'auto'

const EXPLORATION_LAYOUT_VALUES: readonly ExplorationLayoutChoice[] = ['clusters', 'radial', 'force']

/** Which layout the exploration surface should apply for the current execution: an
 * explicit in-session user override always wins; otherwise the definition's validated
 * `display_options.layout` (an unknown/absent value is ignored, not an error); otherwise
 * an anchored execution defaults to the anchor-centric radial layout and an unanchored
 * one to the `group_by` cluster packing. */
export const effectiveExplorationLayout = (
  override: ExplorationLayoutOverride,
  displayOptionLayout: unknown,
  anchored: boolean,
): ExplorationLayoutChoice => {
  if (override !== 'auto') return override
  const declared = EXPLORATION_LAYOUT_VALUES.find((value) => value === displayOptionLayout)
  if (declared) return declared
  return anchored ? 'radial' : 'clusters'
}

/** Hop-distance fill for nodes the projection leaves uncolored: the same
 * `heat-near`→`heat-far` spectrum scale-mode style rules use, so distance reads
 * consistently across surfaces. Depth 0 (the anchor itself) is the near endpoint. */
export const distanceColor = (depth: number, maxDepth: number): string =>
  resolveStyleColor({ position: maxDepth > 0 ? depth / maxDepth : 0, tokens: ['heat-near', 'heat-far'] })

export interface DistanceLegendEntry {
  readonly label: string
  readonly color: string
}

/** One legend chip per hop count, colored exactly as `distanceColor` colors the nodes. */
export const distanceLegend = (maxDepth: number): readonly DistanceLegendEntry[] =>
  maxDepth < 0
    ? []
    : Array.from({ length: maxDepth + 1 }, (_, depth) => ({
        label: depth === 1 ? '1 hop' : `${depth} hops`,
        color: distanceColor(depth, maxDepth),
      }))

/** Legible text color for glyphs drawn on top of a node fill: dark ink on light fills,
 * white on dark fills, decided by perceived (YIQ) brightness. Non-hex input (never
 * produced by the fill pipeline) defaults to dark ink. */
export const contrastTextColor = (fillColor: string): string => {
  const match = /^#([0-9a-f]{6})$/i.exec(fillColor)
  if (!match) return '#252327'
  const [r, g, b] = [0, 2, 4].map((offset) => parseInt(match[1].slice(offset, offset + 2), 16))
  const brightness = (r * 299 + g * 587 + b * 114) / 1000
  return brightness >= 145 ? '#252327' : '#ffffff'
}

export interface EdgeVisual {
  readonly stroke: string | null
  readonly strokeWidth: number | null
  readonly dashArray: string | undefined
}

/** `edge_color`/`edge_emphasis` resolved from the projection's per-connection style map;
 * `null` fields mean "no viewpoint style — render the default edge". */
export const edgeVisualFor = (style: Readonly<Record<string, StyleValue>> | undefined): EdgeVisual => {
  const emphasis = style?.edge_emphasis !== undefined ? tokenEdgeEmphasis(styleTokenString(style.edge_emphasis)) : null
  return {
    stroke: style?.edge_color !== undefined ? resolveStyleColor(style.edge_color) : null,
    strokeWidth: emphasis?.strokeWidth ?? null,
    dashArray: emphasis?.dashArray,
  }
}
