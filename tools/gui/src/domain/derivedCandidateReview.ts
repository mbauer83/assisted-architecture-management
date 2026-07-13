/**
 * Ephemeral, client-side-only candidate review for a layered-exploration/motivation-support
 * result: nothing here is persisted — it only tracks, for the lifetime of one rendered
 * result, which derived candidates the user has accepted or rejected, defaulting to
 * certain-accepted/potential-rejected, plus which previously-accepted candidates a Re-run
 * no longer reproduces ("stale").
 */

import type { ConnectionItemSummary } from './schemas/viewpoints'

export type CandidateDecision = 'accepted' | 'rejected'

/** A derived connection has no single persisted identity (nothing is saved) — its witness
 * chain is what makes it that specific relationship, so the chain's connection ids, in
 * order, are the review key for the lifetime of one rendered result. */
export const candidateKeyFor = (connection: Pick<ConnectionItemSummary, 'via_connection_ids'>): string =>
  connection.via_connection_ids.join(',')

export const isDerivedConnection = (connection: Pick<ConnectionItemSummary, 'certainty'>): boolean =>
  connection.certainty !== null

export interface CandidateReviewState {
  readonly decisions: ReadonlyMap<string, CandidateDecision>
}

/** Default: certain candidates start accepted, potential ones start rejected until the
 * user explicitly accepts them. */
export const initialCandidateReview = (connections: readonly ConnectionItemSummary[]): CandidateReviewState => {
  const decisions = new Map<string, CandidateDecision>()
  for (const connection of connections) {
    if (!isDerivedConnection(connection)) continue
    decisions.set(candidateKeyFor(connection), connection.certainty === 'certain' ? 'accepted' : 'rejected')
  }
  return { decisions }
}

export const withDecision = (state: CandidateReviewState, key: string, decision: CandidateDecision): CandidateReviewState => {
  const decisions = new Map(state.decisions)
  decisions.set(key, decision)
  return { decisions }
}

export const decisionFor = (state: CandidateReviewState, key: string): CandidateDecision | undefined => state.decisions.get(key)

/** Only accepted derived connections (plus every non-derived connection) render; a
 * rejected derived connection is withheld without discarding its review state. */
export const acceptedConnections = (
  state: CandidateReviewState,
  connections: readonly ConnectionItemSummary[],
): readonly ConnectionItemSummary[] =>
  connections.filter((connection) => !isDerivedConnection(connection) || decisionFor(state, candidateKeyFor(connection)) === 'accepted')

/** A candidate the user had accepted before a Re-run, whose witness chain the fresh result
 * no longer reproduces at all — the model changed under them, or the query parameters did.
 * Never silently dropped: the caller surfaces this list as an actionable finding (accept
 * the loss / re-review) rather than just shrinking the rendered graph. */
export const staleAcceptedKeys = (
  previous: CandidateReviewState,
  freshConnections: readonly ConnectionItemSummary[],
): readonly string[] => {
  const freshKeys = new Set(freshConnections.filter(isDerivedConnection).map(candidateKeyFor))
  return [...previous.decisions.entries()]
    .filter(([key, decision]) => decision === 'accepted' && !freshKeys.has(key))
    .map(([key]) => key)
}
