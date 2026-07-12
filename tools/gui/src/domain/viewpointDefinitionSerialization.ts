/**
 * Top-level `ViewpointDefinitionDraft` <-> canonical wire mapping conversion — the exact
 * counterpart of `src/domain/viewpoint_serialization.py` / `viewpoint_parsing.py`
 * (structural shape only; registry-aware validation happens server-side on save).
 */

import { queryFromMapping, queryToMapping } from './viewpointCriteriaSerialization'
import { presentationFromMapping, presentationToMapping } from './viewpointPresentationSerialization'
import {
  type Content,
  type Purpose,
  type ScopeDraft,
  type ViewpointDefinitionDraft,
  mkDefinitionDraft,
} from './viewpointDefinitionDraft'

const asRecord = (raw: unknown): Record<string, unknown> => raw as Record<string, unknown>

/** `String(v)` on `unknown` trips `@typescript-eslint/no-base-to-string` — this narrows
 * first, matching how the Python parser's `str(raw.get(...) or default)` reads a mapping
 * value that is always either absent, a string, or a number in valid input. */
const stringOr = (v: unknown, fallback: string): string =>
  typeof v === 'string' || typeof v === 'number' ? String(v) : fallback

const tupleShorthand = (values: readonly string[]): string | string[] => (values.length === 1 ? values[0] : [...values])

const stringList = (raw: unknown, fallback: readonly string[]): string[] => {
  if (raw == null) return [...fallback]
  if (typeof raw === 'string') return [raw]
  if (Array.isArray(raw)) return raw.map(String)
  return [...fallback]
}

const scopeToMapping = (scope: ScopeDraft): Record<string, unknown> => {
  const result: Record<string, unknown> = {}
  if (scope.entityTypes !== null) result.entity_types = [...scope.entityTypes].sort()
  if (scope.connectionTypes !== null) result.connection_types = [...scope.connectionTypes].sort()
  return result
}

const scopeFromMapping = (raw: unknown): ScopeDraft => {
  if (raw == null || typeof raw !== 'object') return { entityTypes: null, connectionTypes: null }
  const rec = asRecord(raw)
  return {
    entityTypes: Array.isArray(rec.entity_types) ? rec.entity_types.map(String) : null,
    connectionTypes: Array.isArray(rec.connection_types) ? rec.connection_types.map(String) : null,
  }
}

export const definitionToMapping = (draft: ViewpointDefinitionDraft): Record<string, unknown> => {
  const result: Record<string, unknown> = {
    slug: draft.slug,
    version: draft.version,
    name: draft.name,
    purpose: tupleShorthand(draft.purpose),
    content: tupleShorthand(draft.content),
  }
  if (draft.description) result.description = draft.description
  if (draft.rationale) result.rationale = draft.rationale
  if (draft.stakeholders.length > 0) result.stakeholders = draft.stakeholders
  if (draft.concerns.length > 0) result.concerns = draft.concerns
  const scope = scopeToMapping(draft.scope)
  if (Object.keys(scope).length > 0) result.scope = scope
  if (draft.representationTypes.length > 0) result.representation_types = draft.representationTypes
  if (Object.keys(draft.derivationDefaults).length > 0) result.derivation_defaults = draft.derivationDefaults
  if (draft.query !== null) result.query = queryToMapping(draft.query)
  if (draft.presentation !== null) result.presentation = presentationToMapping(draft.presentation)
  return result
}

export const definitionFromMapping = (raw: Record<string, unknown>): ViewpointDefinitionDraft => {
  const draft = mkDefinitionDraft()
  draft.slug = stringOr(raw.slug, '')
  draft.version = Number(raw.version ?? 1)
  draft.name = stringOr(raw.name, draft.slug)
  draft.description = stringOr(raw.description, '')
  draft.rationale = stringOr(raw.rationale, '')
  draft.purpose = stringList(raw.purpose, ['informing']) as Purpose[]
  draft.content = stringList(raw.content, ['overview']) as Content[]
  draft.stakeholders = stringList(raw.stakeholders, [])
  draft.concerns = stringList(raw.concerns, [])
  draft.scope = scopeFromMapping(raw.scope)
  draft.representationTypes = stringList(raw.representation_types, [])
  draft.derivationDefaults = typeof raw.derivation_defaults === 'object' && raw.derivation_defaults != null
    ? asRecord(raw.derivation_defaults) : {}
  draft.query = raw.query != null ? queryFromMapping(raw.query) : null
  draft.presentation = presentationFromMapping(raw.presentation)
  return draft
}
