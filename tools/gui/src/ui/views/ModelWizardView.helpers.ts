// Pure helpers for the guided modeling wizard's hub shell — unit-testable without a DOM.
import { DOMAIN_OPTIONS, FRAMEWORK_GROUPS, getDomainColor } from '../lib/domains'
import { SPINES, type WizardMode } from '../lib/wizardQuestionnaires'

export interface WizardDomainCard {
  readonly key: string
  readonly label: string
  readonly color: string
  readonly createdCount: number
  /** True on the one card the spine recommends working on next ("Start here" / "Next"). */
  readonly recommended: boolean
}

const ARCHIMATE_DOMAINS: readonly string[] =
  FRAMEWORK_GROUPS.find((group) => group.key === 'archimate-next')?.domains ?? []

/**
 * First spine domain (in the mode's order) the session hasn't touched yet — the "model this
 * next" recommendation. Untouched = nothing created there this session; once the whole spine
 * has content, no card is recommended (the user has outgrown the guided order).
 */
export const recommendedNextDomain = (
  createdCounts: Record<string, number>,
  mode: WizardMode = 'planning',
): string | null =>
  SPINES[mode].find((domain) => (createdCounts[domain] ?? 0) === 0) ?? null

/** v1 scope is ArchiMate-only (WU-B2's "guided ArchiMate modeling wizard") — SysML excluded. */
export const buildWizardDomainCards = (
  createdCounts: Record<string, number>,
  mode: WizardMode = 'planning',
): WizardDomainCard[] => {
  const recommended = recommendedNextDomain(createdCounts, mode)
  return DOMAIN_OPTIONS
    .filter((option) => ARCHIMATE_DOMAINS.includes(option.key))
    .map((option) => ({
      key: option.key,
      label: option.label,
      color: getDomainColor(option.key),
      createdCount: createdCounts[option.key] ?? 0,
      recommended: option.key === recommended,
    }))
}
