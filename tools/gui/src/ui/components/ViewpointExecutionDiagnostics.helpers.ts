/**
 * Pure diagnostics/legend logic for the viewpoint-execution diagnostics panel — shared by
 * every execution representation (exploration, table, matrix, diagram) so "empty",
 * "truncated", and "unsupported capability" states, and the derived legend, are computed
 * identically everywhere.
 */

import { REPRESENTATION_CAPABILITIES, type PresentationNode, type Representation } from '../../domain/viewpointPresentation'
import type { ViewpointExecutionResult } from '../../domain'
import { tokenColor } from '../lib/viewpointStyleTokens'

export interface ExecutionDiagnostics {
  readonly isEmpty: boolean
  readonly emptyReason: string | null
  readonly truncated: boolean
  readonly truncationMessage: string | null
  readonly totalEntityCount: number
  readonly returnedEntityCount: number
  readonly totalConnectionCount: number
  readonly returnedConnectionCount: number
  readonly unsupportedCapabilities: readonly string[]
  readonly warnings: readonly string[]
}

const usedCapabilities = (presentation: PresentationNode | null): string[] => {
  if (!presentation) return []
  const fromRules = presentation.stylingRules.map((rule) => rule.capability)
  const fromDefaults = Object.keys(presentation.defaultStyle)
  return [...new Set([...fromRules, ...fromDefaults])]
}

/** Capabilities the definition uses but the *current* representation surface can't
 * render (e.g. an exploration-authored rule viewed as `table`) — surfaced as a warning,
 * never silently dropped. */
export const computeUnsupportedCapabilities = (
  presentation: PresentationNode | null,
  representation: Representation,
): readonly string[] => {
  const supported = new Set(REPRESENTATION_CAPABILITIES[representation])
  return usedCapabilities(presentation).filter((capability) => !supported.has(capability))
}

export const computeExecutionDiagnostics = (
  result: ViewpointExecutionResult | null,
  presentation: PresentationNode | null,
  representation: Representation,
): ExecutionDiagnostics => {
  const totalEntityCount = result?.total_entity_count ?? 0
  const returnedEntityCount = result?.returned_entity_count ?? 0
  const totalConnectionCount = result?.total_connection_count ?? 0
  const returnedConnectionCount = result?.returned_connection_count ?? 0
  const isEmpty = totalEntityCount === 0
  const emptyReason = isEmpty
    ? "No entities in the current model match this viewpoint's criteria."
    : returnedEntityCount === 0
      ? 'Every matching entity was truncated by the current limit.'
      : null
  const truncated = result?.truncated ?? false
  const truncationMessage = truncated
    ? `Showing ${returnedEntityCount} of ${totalEntityCount} entities (limit ${result?.entity_limit ?? 0}); ` +
      'expanded context members are dropped before primary matches.'
    : null
  return {
    isEmpty,
    emptyReason,
    truncated,
    truncationMessage,
    totalEntityCount,
    returnedEntityCount,
    totalConnectionCount,
    returnedConnectionCount,
    unsupportedCapabilities: computeUnsupportedCapabilities(presentation, representation),
    warnings: result?.warnings ?? [],
  }
}

export interface LegendEntry {
  readonly capability: string
  readonly token: string
  readonly label: string
}

/** Every surface renders its legend mechanically from `styling_rules` + `range_bands` +
 * `default_style` — nothing to author separately. `scale` mode has no discrete bands to
 * enumerate here; its own continuous spectrum is rendered by `deriveScaleGradients`
 * instead, never as fabricated per-band entries. */
export const deriveLegend = (presentation: PresentationNode | null): readonly LegendEntry[] => {
  if (!presentation) return []
  const entries: LegendEntry[] = []
  for (const rule of presentation.stylingRules) {
    if (rule.mode === 'match') {
      if (rule.value !== null) {
        entries.push({
          capability: rule.capability,
          token: rule.value,
          label: rule.appliesTo.length > 0 ? rule.appliesTo.join(', ') : 'matching criteria',
        })
      }
    } else if (rule.mode === 'range') {
      for (const band of rule.rangeBands) {
        const lo = band.minimum ?? '-∞'
        const hi = band.maximum ?? '∞'
        entries.push({
          capability: rule.capability,
          token: band.value,
          label: `${rule.rangeAttribute ?? '?'} in [${lo}, ${hi})`,
        })
      }
    }
  }
  for (const [capability, token] of Object.entries(presentation.defaultStyle)) {
    entries.push({ capability, token, label: 'default' })
  }
  return entries
}

export interface ScaleGradientLegend {
  readonly capability: string
  readonly gradientCss: string
  readonly minLabel: string
  readonly maxLabel: string
}

/** A `mode: "scale"` rule declares a continuous spectrum (`scale_min`..`scale_max`
 * interpolating between its two `scale_tokens` endpoints) rather than discrete bands —
 * this renders that spectrum as a single gradient bar labelled with its two endpoints.
 * `null` bounds are data-driven (computed server-side per execution, not known here), so
 * they render as unbounded (±∞) rather than a guessed number. */
export const deriveScaleGradients = (presentation: PresentationNode | null): readonly ScaleGradientLegend[] => {
  if (!presentation) return []
  const gradients: ScaleGradientLegend[] = []
  for (const rule of presentation.stylingRules) {
    if (rule.mode !== 'scale' || rule.scaleTokens === null) continue
    gradients.push({
      capability: rule.capability,
      gradientCss: `linear-gradient(to right, ${tokenColor(rule.scaleTokens[0])}, ${tokenColor(rule.scaleTokens[1])})`,
      minLabel: rule.scaleMin !== null ? String(rule.scaleMin) : '−∞',
      maxLabel: rule.scaleMax !== null ? String(rule.scaleMax) : '∞',
    })
  }
  return gradients
}
