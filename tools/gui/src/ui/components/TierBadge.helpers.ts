import type { Tier } from '../lib/tierUrlState'

/** User-facing tier copy: always "Enterprise", never "Global". The third tier keeps
 * its technical name pending an owner decision on its display label. */
export const TIER_LABELS: Record<Tier, string> = {
  engagement: 'Engagement',
  enterprise: 'Enterprise',
  module: 'module',
}

/** The one accessibility label every tier badge carries. */
export const tierBadgeAriaLabel = (tier: Tier): string => `Repository tier: ${TIER_LABELS[tier]}`

/** Row badges derive their tier from the list contract's required `is_global` flag. */
export const tierFromIsGlobal = (isGlobal: boolean): Tier => (isGlobal ? 'enterprise' : 'engagement')
