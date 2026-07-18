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

/** Execution connection summaries joined onto rendered edges by the same
 * source/target/connType key `buildConnectionStyleIndex` uses — this is how a selected
 * edge finds its provenance (certainty, hops, ordered witness steps). */
export const buildConnectionSummaryIndex = (
  connections: readonly ConnectionItemSummary[],
): ReadonlyMap<string, ConnectionItemSummary> => {
  const index = new Map<string, ConnectionItemSummary>()
  for (const connection of connections) {
    index.set(edgeStyleKey(connection.source, connection.target, connection.type), connection)
  }
  return index
}

/** Human-readable name derived from an artifact id's slug part — used where the real
 * display name is not in the result (e.g. witness-chain intermediates). */
export const friendlyEntityName = (id: string): string => {
  const parts = id.split('.')
  return parts.length > 2 ? parts.slice(2).join(' ').replace(/-/g, ' ') : id
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

/** Anchor-relative modeled distances as the execution reported them
 * (`anchor_modeled_distance`: 0 = anchor, 1 = direct modeled edge, N = minimum derived
 * witness-chain length). Entities the server left unranked are absent from the map —
 * "no distance" is its own visual category, never rendered as 0 or 1. */
export const anchorDistancesFromResult = (
  entities: readonly { id: string; anchor_modeled_distance?: number | null }[],
): Map<string, number> => {
  const distances = new Map<string, number>()
  for (const entity of entities) {
    if (entity.anchor_modeled_distance != null) distances.set(entity.id, entity.anchor_modeled_distance)
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

/** One legend chip per OBSERVED nonzero modeled distance (the real ring set — e.g.
 * 1/2/4 when those are the witness-chain lengths present), colored exactly as
 * `distanceColor` colors the nodes. Distance 0 is the anchor itself, which the legend
 * already names with its dedicated Anchor chip. */
export const distanceLegend = (depths: readonly number[]): readonly DistanceLegendEntry[] => {
  const observed = [...new Set(depths.filter((depth) => depth > 0))].sort((a, b) => a - b)
  const maxDepth = observed.length > 0 ? observed[observed.length - 1] : 0
  return observed.map((depth) => ({
    label: depth === 1 ? '1 hop' : `${depth} hops`,
    color: distanceColor(depth, maxDepth),
  }))
}

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

/** Provenance dash patterns: derived edges are visually distinct from modeled ones by
 * construction, and certain vs potential derivations differ in dash density. The edge
 * legend labels exactly these patterns. */
export const DERIVED_EDGE_DASH: Readonly<Record<'certain' | 'potential', string>> = {
  certain: '7 4',
  potential: '2 4',
}

/** `edge_color`/`edge_emphasis` resolved from the projection's per-connection style map;
 * `null` fields mean "no viewpoint style — render the default edge". A derived
 * connection with no authored emphasis falls back to its provenance dash so modeled and
 * derived edges never look identical. */
export const edgeVisualFor = (
  style: Readonly<Record<string, StyleValue>> | undefined,
  certainty: 'certain' | 'potential' | null = null,
): EdgeVisual => {
  const emphasis = style?.edge_emphasis !== undefined ? tokenEdgeEmphasis(styleTokenString(style.edge_emphasis)) : null
  return {
    stroke: style?.edge_color !== undefined ? resolveStyleColor(style.edge_color) : null,
    strokeWidth: emphasis?.strokeWidth ?? null,
    dashArray: emphasis?.dashArray ?? (certainty !== null ? DERIVED_EDGE_DASH[certainty] : undefined),
  }
}

/** Static UI option tables for the exploration surface. */
export const EXPLORATION_LAYOUT_OPTIONS: { value: ExplorationLayoutOverride; label: string }[] = [
  { value: 'auto', label: 'Auto' }, { value: 'clusters', label: 'Clusters' },
  { value: 'radial', label: 'Radial' }, { value: 'force', label: 'Force' },
]

export const SPACING_PRESETS = [
  { label: 'Compact', repulsion: 1500, idealDist: 150 },
  { label: 'Normal', repulsion: 3000, idealDist: 250 },
  { label: 'Spacious', repulsion: 6000, idealDist: 400 },
  { label: 'Very spacious', repulsion: 12000, idealDist: 600 },
]

export const DOMAIN_COLORS: Record<string, string> = {
  motivation: '#d8c1e4', strategy: '#efbd5d', business: '#f4de7f',
  common: '#e8e5d3', application: '#b6d7e1', technology: '#c3e1b4',
}

export interface ViewBoxRect { x: number; y: number; w: number; h: number }

/** ViewBox that fits every node with padding, aspect-corrected to the container — the
 * one-click answer to results rendered off-viewport. Falls back to the container rect
 * when there is nothing to fit. */
export const fitViewBox = (
  nodes: readonly { x: number; y: number }[],
  containerWidth: number,
  containerHeight: number,
  padding = 80,
): ViewBoxRect => {
  if (nodes.length === 0 || containerWidth <= 0 || containerHeight <= 0) {
    return { x: 0, y: 0, w: Math.max(containerWidth, 1), h: Math.max(containerHeight, 1) }
  }
  const xs = nodes.map((n) => n.x)
  const ys = nodes.map((n) => n.y)
  const minX = Math.min(...xs) - padding
  const maxX = Math.max(...xs) + padding
  const minY = Math.min(...ys) - padding
  const maxY = Math.max(...ys) + padding
  const width = maxX - minX
  const height = maxY - minY
  const containerRatio = containerWidth / containerHeight
  const contentRatio = width / height
  if (contentRatio > containerRatio) {
    const correctedHeight = width / containerRatio
    return { x: minX, y: minY - (correctedHeight - height) / 2, w: width, h: correctedHeight }
  }
  const correctedWidth = height * containerRatio
  return { x: minX - (correctedWidth - width) / 2, y: minY, w: correctedWidth, h: height }
}

/** Word-aware label wrapping for SVG tspans: up to `maxLines` lines of `maxChars`,
 * with an ellipsis when content remains — mid-word truncation was producing misreadings
 * that reached real review artifacts. The full name always travels in the node tooltip. */
export const wrapLabel = (label: string, maxChars = 14, maxLines = 2): string[] => {
  const words = label.split(/\s+/).filter((word) => word.length > 0)
  const wrapped: string[] = []
  let current = ''
  for (const word of words) {
    const candidate = current === '' ? word : `${current} ${word}`
    if (candidate.length <= maxChars) {
      current = candidate
      continue
    }
    if (current !== '') wrapped.push(current)
    current = word
  }
  if (current !== '') wrapped.push(current)
  const lines = wrapped.slice(0, maxLines).map(
    (line) => (line.length > maxChars ? `${line.slice(0, maxChars - 1)}…` : line),
  )
  if (wrapped.length > maxLines && !lines[maxLines - 1].endsWith('…')) {
    const last = lines[maxLines - 1]
    lines[maxLines - 1] = last.length >= maxChars ? `${last.slice(0, maxChars - 1)}…` : `${last}…`
  }
  return lines.length > 0 ? lines : ['']
}

interface PositionedNode {
  readonly id: string
  readonly x: number
  readonly y: number
}

/** SVG path for an edge: orthogonal elbows in cluster layout, a straight segment
 * otherwise. Empty string when either endpoint is missing from the node set. */
export const edgePathFor = (
  nodes: readonly PositionedNode[],
  edge: { readonly source: string; readonly target: string },
  clusterLayout: boolean,
): string => {
  const src = nodes.find((n) => n.id === edge.source)
  const tgt = nodes.find((n) => n.id === edge.target)
  if (!src || !tgt) return ''
  if (clusterLayout) {
    const midY = (src.y + tgt.y) / 2
    return `M ${src.x} ${src.y} V ${midY} H ${tgt.x} V ${tgt.y}`
  }
  return `M ${src.x} ${src.y} L ${tgt.x} ${tgt.y}`
}

/** SVG coords for a multiplicity label at `frac` (0=source, 1=target) along an edge,
 * offset 8px perpendicular-ish above the line for legibility. */
export const edgeCardPosFor = (
  nodes: readonly PositionedNode[],
  edge: { readonly source: string; readonly target: string },
  frac: number,
): { x: number; y: number } => {
  const src = nodes.find((n) => n.id === edge.source)
  const tgt = nodes.find((n) => n.id === edge.target)
  if (!src || !tgt) return { x: 0, y: 0 }
  const dx = tgt.x - src.x
  const dy = tgt.y - src.y
  const len = Math.max(Math.sqrt(dx * dx + dy * dy), 1)
  return {
    x: src.x + dx * frac - (dy / len) * 8,
    y: src.y + dy * frac + (dx / len) * 8,
  }
}
