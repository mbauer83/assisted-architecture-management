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
import { archimateGlyphMarkup } from '../lib/glyphKey'
import type { EdgeVisual, NodeVisual } from '../components/GraphCanvas.helpers'
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

/** `node_color`/`node_shape`/`node_icon` resolved from the projection's per-entity style
 * map, falling back to the existing domain-color convention when the viewpoint carries
 * no styling for a given capability. `node_color` alone can be a scale-mode
 * `{position, tokens}` value (interpolated); shape/icon always read a discrete token. */
export const nodeVisualFor = (
  style: Readonly<Record<string, StyleValue>> | undefined,
  fallbackColor: string,
  artifactType?: string,
): NodeVisual => ({
  color: style?.node_color !== undefined ? resolveStyleColor(style.node_color) : fallbackColor,
  shape: style?.node_shape !== undefined ? tokenShape(styleTokenString(style.node_shape)) : 'circle',
  iconLetter: style?.node_icon !== undefined ? tokenIconLetter(styleTokenString(style.node_icon)) : null,
  glyph: archimateGlyphMarkup(artifactType),
})

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
