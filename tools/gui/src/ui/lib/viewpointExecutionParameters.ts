/**
 * Pure helpers driving the execution-time parameter prompt: deriving a definition's
 * declared parameter signature from its stored envelope, deciding whether a prompt is
 * needed before the first execution, and coercing typed string inputs to the wire values
 * `POST /api/viewpoints/execute` expects.
 */

import { parameterFromMapping } from '../../domain/viewpointBindingsSerialization'
import type { ParameterValueType, QueryParameterNode } from '../../domain/viewpointBindings'
import type { ViewpointDefinitionEnvelope } from '../../domain'

const asRecord = (raw: unknown): Record<string, unknown> => raw as Record<string, unknown>

/** A definition's declared parameters, parsed from its stored `query.parameters` — empty
 * for a scope-only or unparameterized definition. */
export const parameterSignatureOf = (envelope: ViewpointDefinitionEnvelope | undefined): readonly QueryParameterNode[] => {
  const query = envelope?.query
  if (query == null || typeof query !== 'object') return []
  const parameters = asRecord(query).parameters
  return Array.isArray(parameters) ? parameters.map(parameterFromMapping) : []
}

/** A prompt is needed exactly when at least one required parameter has no default —
 * an all-optional or all-defaulted signature executes immediately, same as today. */
export const needsParameterPrompt = (signature: readonly QueryParameterNode[]): boolean =>
  signature.some((p) => p.required && p.default === '')

/** Typed string-input drafts, one per declared parameter, seeded from each parameter's
 * own default (or empty) — the prompt dialog's own local form state shape. */
export const initialParameterDraft = (signature: readonly QueryParameterNode[]): Record<string, string> =>
  Object.fromEntries(signature.map((p) => [p.name, p.default]))

/** A required parameter still missing a value in the current draft — drives the submit
 * button's disabled state and which fields to flag. */
export const missingRequiredParameters = (
  signature: readonly QueryParameterNode[],
  draft: Readonly<Record<string, string>>,
): readonly QueryParameterNode[] => signature.filter((p) => p.required && !(draft[p.name] ?? '').trim())

/** Coerces one typed string draft value to the wire shape `execute`'s `parameters` body
 * expects — `entity-id`/`string`/`slug` pass through as strings (an artifact id is a
 * string), `integer`/`number` parse numerically, `boolean` from a checkbox's own
 * true/false string, `date` stays an ISO date string (the wire format already used
 * elsewhere in this codebase). Non-numeric numeric input yields `null` (caller's own
 * required-field check already prevents submitting an empty one; a malformed one is
 * caught by save-mode... execution-mode validation server-side, never silently coerced
 * to 0). */
export const coerceParameterValue = (valueType: ParameterValueType, raw: string): unknown => {
  if (valueType === 'boolean') return raw === 'true'
  if (valueType === 'integer') {
    const parsed = Number.parseInt(raw, 10)
    return Number.isNaN(parsed) ? null : parsed
  }
  if (valueType === 'number') {
    const parsed = Number.parseFloat(raw)
    return Number.isNaN(parsed) ? null : parsed
  }
  return raw
}

/** The full wire-shaped `parameters` body from a draft — omits a parameter entirely when
 * its draft value is blank (an unsupplied optional parameter, not an explicit empty
 * string), matching the backend's "missing" vs. "supplied-empty" distinction. */
export const parametersToWireValues = (
  signature: readonly QueryParameterNode[],
  draft: Readonly<Record<string, string>>,
): Record<string, unknown> => {
  const result: Record<string, unknown> = {}
  for (const parameter of signature) {
    const raw = draft[parameter.name] ?? ''
    if (raw.trim() === '') continue
    result[parameter.name] = coerceParameterValue(parameter.valueType, raw)
  }
  return result
}
