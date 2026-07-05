import type { EntityDisplayInfo } from '../../domain'
import type { WizardSuggestion } from '../composables/useWizardSession'

export type ConnectionDirection = 'outgoing' | 'incoming' | 'symmetric'

export interface LegalConnectionPair {
  readonly direction: ConnectionDirection
  readonly connectionType: string
  readonly targetType: string
}

/**
 * Structural shape shared by `OntologyClassification` and `EntityTypeGuidance.permitted_connections`
 * — per `_classify_connections` (`type_guidance.py`), each record is keyed by **target type**,
 * with the value array holding every legal **connection type** to/from that target (never the
 * other way around).
 */
export interface PermittedConnectionsByPeer {
  readonly outgoing: Record<string, readonly string[]>
  readonly incoming: Record<string, readonly string[]>
  readonly symmetric: Record<string, readonly string[]>
}

/**
 * Every (direction, connectionType, targetType) triple the ontology permits from a source type,
 * flattened out of a `{outgoing, incoming, symmetric}` peer-connection record — the shape shared
 * by `getOntologyClassification` and `getAuthoringGuidance`'s per-entity-type
 * `permitted_connections` (the wizard reuses whichever guidance it already has loaded, no extra
 * round trip). This is the "metamodel validity" ranking signal — a pair search that isn't in this
 * list is never a candidate at all, regardless of name similarity.
 */
export function legalConnectionPairs(classification: PermittedConnectionsByPeer): LegalConnectionPair[] {
  const pairs: LegalConnectionPair[] = []
  const directions: [ConnectionDirection, Record<string, readonly string[]>][] = [
    ['outgoing', classification.outgoing],
    ['incoming', classification.incoming],
    ['symmetric', classification.symmetric],
  ]
  for (const [direction, byTargetType] of directions) {
    for (const [targetType, connectionTypes] of Object.entries(byTargetType)) {
      for (const connectionType of connectionTypes) pairs.push({ direction, connectionType, targetType })
    }
  }
  return pairs
}

/** Lowercased word set, ignoring punctuation and words of length < 3 (drops noise like "a"/"to"). */
function wordSet(text: string): Set<string> {
  return new Set(
    text.toLowerCase().replace(/[^a-z0-9\s]/g, ' ').split(/\s+/).filter((w) => w.length >= 3),
  )
}

/** Jaccard similarity of the two names' word sets — the "name/text similarity" ranking signal. */
export function nameSimilarity(a: string, b: string): number {
  const wa = wordSet(a)
  const wb = wordSet(b)
  if (wa.size === 0 || wb.size === 0) return 0
  let intersection = 0
  for (const w of wa) if (wb.has(w)) intersection += 1
  const union = wa.size + wb.size - intersection
  return union === 0 ? 0 : intersection / union
}

/**
 * A small nudge added on top of name similarity for a candidate that's a graph neighbor of the
 * entities built up so far in this session (`discoverDiagramEntities`-style hop suggestions) —
 * the plan's stated ranking order is metamodel validity (structural — only legal pairs are ever
 * considered at all) *then* name/text similarity *then* graph proximity, so this is a tiebreaker
 * on top of `nameSimilarity`, never a signal that overrides it outright.
 */
const PROXIMITY_BONUS = 0.15

function candidateScore(sourceName: string, candidate: EntityDisplayInfo, proximityBoost: ReadonlySet<string>): number {
  return nameSimilarity(sourceName, candidate.name) + (proximityBoost.has(candidate.artifact_id) ? PROXIMITY_BONUS : 0)
}

const phraseVerb = (connectionType: string): string => connectionType.replace(/[-_]/g, ' ')

export function phraseSuggestion(sourceName: string, connectionType: string, targetName: string): string {
  return `${sourceName} probably ${phraseVerb(connectionType)} ${targetName}`
}

export interface WizardSuggestionSource {
  readonly id: string
  readonly name: string
  readonly domain: string
}

export interface ChainAnchor {
  readonly id: string
  readonly name: string
  readonly type: string
}

const suggestionFor = (
  source: WizardSuggestionSource,
  pair: LegalConnectionPair,
  peerId: string,
  peerName: string,
): WizardSuggestion => {
  const [sourceId, sourceName, targetId, targetName] = pair.direction === 'incoming'
    ? [peerId, peerName, source.id, source.name]
    : [source.id, source.name, peerId, peerName]
  return {
    id: `${sourceId}:${pair.connectionType}:${targetId}`,
    domain: source.domain,
    summary: phraseSuggestion(sourceName, pair.connectionType, targetName),
    sourceId,
    sourceName,
    connectionType: pair.connectionType,
    targetId,
    targetName,
  }
}

/**
 * Deterministic chain-first suggestions (WU-B4.2): connect the new entity to the session's own
 * spine anchors — the entities the user just built. These outrank every similarity-scored
 * candidate because "link the driver to the stakeholder you created a minute ago" is the
 * wizard's single most likely next action, and similarity ranking cannot be trusted to surface
 * it (a fresh chain has no graph neighborhood yet, and the candidate search cap can drop
 * just-created entities entirely). One suggestion per anchor — the first legal pair wins —
 * most recent anchors first, capped.
 */
export function buildChainSuggestions(
  source: WizardSuggestionSource,
  legalPairs: readonly LegalConnectionPair[],
  anchors: readonly ChainAnchor[],
  cap: number,
): WizardSuggestion[] {
  const suggestions: WizardSuggestion[] = []
  for (const anchor of [...anchors].reverse()) {
    if (anchor.id === source.id) continue
    const pair = legalPairs.find((p) => p.targetType === anchor.type)
    if (!pair) continue
    suggestions.push(suggestionFor(source, pair, anchor.id, anchor.name))
    if (suggestions.length >= cap) break
  }
  return suggestions
}

/**
 * Builds ranked, commit-ready suggestions for `source`: for each legal (direction, connType,
 * targetType) triple, take the best-scoring candidate from `candidatesByTargetType` (name
 * similarity, nudged by `proximityBoost`), phrase it, and cap the combined list to `cap` — the
 * wizard's "max 3-5 ranked suggestions" rule. `incoming` pairs flip the endpoints so
 * `sourceId`/`targetId` are always the real connection direction (candidate → source), not "the
 * entity the wizard happened to start from". `proximityBoost` is optional — omit it for a plain
 * metamodel-validity-then-name-similarity ranking.
 */
export function buildWizardSuggestions(
  source: WizardSuggestionSource,
  legalPairs: readonly LegalConnectionPair[],
  candidatesByTargetType: ReadonlyMap<string, readonly EntityDisplayInfo[]>,
  cap: number,
  proximityBoost: ReadonlySet<string> = new Set(),
): WizardSuggestion[] {
  const scored: { score: number; suggestion: WizardSuggestion }[] = []
  for (const pair of legalPairs) {
    const candidates = candidatesByTargetType.get(pair.targetType)
    if (!candidates || candidates.length === 0) continue
    const best = [...candidates].sort(
      (a, b) => candidateScore(source.name, b, proximityBoost) - candidateScore(source.name, a, proximityBoost),
    )[0]
    if (!best) continue
    scored.push({
      score: candidateScore(source.name, best, proximityBoost),
      suggestion: suggestionFor(source, pair, best.artifact_id, best.name),
    })
  }
  return scored
    .sort((a, b) => b.score - a.score)
    .slice(0, cap)
    .map((s) => s.suggestion)
}
