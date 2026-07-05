// Pure helpers for the guided modeling wizard's hub shell — unit-testable without a DOM.
import { DOMAIN_OPTIONS, FRAMEWORK_GROUPS, getDomainColor } from '../lib/domains'
import type { AuthoringGuidance, EntityTypeGuidance } from '../../domain'

export interface WizardDomainCard {
  readonly key: string
  readonly label: string
  readonly color: string
  readonly createdCount: number
}

const ARCHIMATE_DOMAINS: readonly string[] =
  FRAMEWORK_GROUPS.find((group) => group.key === 'archimate-next')?.domains ?? []

/** v1 scope is ArchiMate-only (WU-B2's "guided ArchiMate modeling wizard") — SysML excluded. */
export const buildWizardDomainCards = (createdCounts: Record<string, number>): WizardDomainCard[] =>
  DOMAIN_OPTIONS
    .filter((option) => ARCHIMATE_DOMAINS.includes(option.key))
    .map((option) => ({
      key: option.key,
      label: option.label,
      color: getDomainColor(option.key),
      createdCount: createdCounts[option.key] ?? 0,
    }))

export const entityTypesForDomain = (
  guidance: AuthoringGuidance | null,
  domain: string,
): EntityTypeGuidance[] =>
  (guidance?.entity_types ?? []).filter((entityType) => entityType.domain === domain)
