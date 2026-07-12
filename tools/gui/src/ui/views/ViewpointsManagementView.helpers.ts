/**
 * Pure helpers for `ViewpointsManagementView.vue`: the semantic-edit-vs-descriptive-edit
 * diff that drives the version-bump hint (mirrors `_semantic_snapshot`/`_validate_lifecycle`
 * in `src/domain/viewpoint_validation.py` — scope/query/presentation/representation_types
 * are the semantic fields; everything else is descriptive), and small text-field helpers.
 */

import { definitionToMapping } from '../../domain/viewpointDefinitionSerialization'
import type { ViewpointDefinitionDraft } from '../../domain/viewpointDefinitionDraft'
import { resolveIssuePathNodeId } from '../../domain/viewpointIssuePath'
import type { ScopeSummary, ViewpointExecutionResult, ViewpointValidationIssue } from '../../domain'

const SEMANTIC_KEYS = ['scope', 'query', 'presentation', 'representation_types'] as const

/** True when any semantic field differs from `original` — a real editor never diffs by
 * field name directly since `definitionToMapping` is the one place both this and the
 * server agree on what "the same value" means (default-omission, sort order, ...). */
export const isSemanticEdit = (current: ViewpointDefinitionDraft, original: ViewpointDefinitionDraft): boolean => {
  const currentMapping = definitionToMapping(current)
  const originalMapping = definitionToMapping(original)
  return SEMANTIC_KEYS.some((key) => JSON.stringify(currentMapping[key]) !== JSON.stringify(originalMapping[key]))
}

export const csvToList = (text: string): string[] => text.split(',').map((v) => v.trim()).filter((v) => v.length > 0)
export const listToCsv = (list: readonly string[]): string => list.join(', ')

export const formatScopeSummary = (summary: ScopeSummary): string => {
  if (summary.unrestricted) return 'unrestricted'
  const parts: string[] = []
  if (summary.entity_types) parts.push(`entities: ${summary.entity_types.join(', ')}`)
  if (summary.connection_types) parts.push(`connections: ${summary.connection_types.join(', ')}`)
  return parts.join('; ') || 'unrestricted'
}

// ── WU-E5c: live preview + test-run before save ──────────────────────────────

/** Debounced live-preview counts (§7.1's total counts only — a `limit: 0` execution never
 * fetches entity/connection records, so it stays cheap enough to run on every settled
 * keystroke while building criteria). */
export const formatPreviewCounts = (
  result: Pick<ViewpointExecutionResult, 'total_entity_count' | 'total_connection_count'> | null,
): string => {
  if (!result) return ''
  const { total_entity_count: entities, total_connection_count: connections } = result
  return `${entities} entit${entities === 1 ? 'y' : 'ies'} / ${connections} connection${connections === 1 ? '' : 's'}`
}

/** The builder-node id to highlight for a full test-run's save-mode validation issues —
 * same convention `save()`'s real persist-error path already uses, so a definition that
 * fails validation points at the same offending node whether caught by a test-run or by an
 * actual save attempt. */
export const firstErrorNodeId = (
  issues: readonly ViewpointValidationIssue[],
  draft: ViewpointDefinitionDraft,
): string | null => {
  const firstError = issues.find((issue) => issue.severity === 'error')
  return firstError ? resolveIssuePathNodeId(firstError.path, draft) : null
}
