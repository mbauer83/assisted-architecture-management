import { describe, it, expect } from 'vitest'
import { TIER_LABELS, tierBadgeAriaLabel, tierFromIsGlobal } from '../TierBadge.helpers'

describe('TIER_LABELS', () => {
  it('renders Enterprise, never Global', () => {
    expect(TIER_LABELS.enterprise).toBe('Enterprise')
    expect(Object.values(TIER_LABELS).join(' ')).not.toMatch(/global/i)
  })
})

describe('tierBadgeAriaLabel', () => {
  it('is the one semantic accessibility label per tier', () => {
    expect(tierBadgeAriaLabel('enterprise')).toBe('Repository tier: Enterprise')
    expect(tierBadgeAriaLabel('engagement')).toBe('Repository tier: Engagement')
  })
})

describe('tierFromIsGlobal', () => {
  it('maps the required list-contract flag to a tier', () => {
    expect(tierFromIsGlobal(true)).toBe('enterprise')
    expect(tierFromIsGlobal(false)).toBe('engagement')
  })
})
