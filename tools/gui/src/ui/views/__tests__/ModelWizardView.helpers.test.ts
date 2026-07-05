import { describe, it, expect } from 'vitest'
import { buildWizardDomainCards, recommendedNextDomain } from '../ModelWizardView.helpers'

describe('buildWizardDomainCards', () => {
  it('scopes to ArchiMate domains only (excludes sysml)', () => {
    const cards = buildWizardDomainCards({})
    const keys = cards.map((c) => c.key)
    expect(keys).toEqual(['motivation', 'strategy', 'common', 'business', 'application', 'technology', 'implementation'])
    expect(keys).not.toContain('sysml')
  })

  it('carries the created count for a domain with progress', () => {
    const cards = buildWizardDomainCards({ motivation: 3 })
    expect(cards.find((c) => c.key === 'motivation')?.createdCount).toBe(3)
  })

  it('defaults an unmentioned domain to zero', () => {
    const cards = buildWizardDomainCards({ motivation: 3 })
    expect(cards.find((c) => c.key === 'business')?.createdCount).toBe(0)
  })

  it('every card has a non-empty label and color', () => {
    for (const card of buildWizardDomainCards({})) {
      expect(card.label.length).toBeGreaterThan(0)
      expect(card.color.length).toBeGreaterThan(0)
    }
  })

  it('recommends motivation on a fresh session', () => {
    const cards = buildWizardDomainCards({})
    expect(cards.filter((c) => c.recommended).map((c) => c.key)).toEqual(['motivation'])
  })

  it('recommends the first untouched spine domain once earlier ones have content', () => {
    expect(recommendedNextDomain({ motivation: 2 })).toBe('business')
    expect(recommendedNextDomain({ motivation: 2, business: 1 })).toBe('common')
    expect(recommendedNextDomain({ motivation: 2, business: 1, common: 3 })).toBe('application')
  })

  it('recommends nothing once every spine domain has content', () => {
    const counts = { motivation: 1, business: 1, common: 1, application: 1 }
    expect(recommendedNextDomain(counts)).toBeNull()
    expect(buildWizardDomainCards(counts).some((c) => c.recommended)).toBe(false)
  })

  it('spine recommendation ignores off-spine progress (technology does not satisfy it)', () => {
    expect(recommendedNextDomain({ technology: 5 })).toBe('motivation')
  })
})
