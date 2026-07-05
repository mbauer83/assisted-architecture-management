import type { DiagramMapContext, DiagramElementMap } from '../../lib/diagramViewerExtensions'

const _SENTINEL_STEP_TYPES = new Set(['action', 'decision', 'partition'])
const _SENTINEL_PREFIX = 'arch://'

/**
 * Maps a sentinel value (either a bound entity's own artifact id, or a diagram-local step's
 * local id — see `_step_links.py`'s `sentinel_target`) to the artifact id the frontend should
 * select. A bound sentinel already IS the target artifact id; an unbound one is looked up by
 * the diagram-local placeholder entity's `display_alias` (`extract_diagram_entities` sets it
 * to the step's own local id), scoped to step entity types to avoid an accidental collision.
 */
function buildSentinelIndex(entities: DiagramMapContext['entities']): Map<string, string> {
  const index = new Map<string, string>()
  for (const e of entities) {
    index.set(e.artifact_id, e.artifact_id)
    if (_SENTINEL_STEP_TYPES.has(e.artifact_type) && e.display_alias) {
      index.set(e.display_alias, e.artifact_id)
    }
  }
  return index
}

/**
 * Activity diagrams: PlantUML's activity syntax gives fork no label/link position at all
 * (unselectable — see `_step_links.py`), and wraps action/decision/partition links as their
 * own separate `<a>` text rather than around the shape (no `<g>` per step to attach a click
 * listener to either way). So the sentinel `<a href="arch://…">` itself is the selectable,
 * highlightable element for that step.
 */
export function activityMapElements(svgRoot: SVGSVGElement, ctx: DiagramMapContext): DiagramElementMap {
  const nodes = new Map<string, Element[]>()
  const sentinelIndex = buildSentinelIndex(ctx.entities)

  for (const a of Array.from(svgRoot.querySelectorAll<SVGAElement>('a'))) {
    const href = a.getAttribute('href') ?? ''
    if (!href.startsWith(_SENTINEL_PREFIX)) continue
    const artifactId = sentinelIndex.get(href.slice(_SENTINEL_PREFIX.length))
    if (!artifactId) continue
    const list = nodes.get(artifactId)
    if (list) list.push(a)
    else nodes.set(artifactId, [a])
  }

  return { nodes, edges: new Map() }
}
