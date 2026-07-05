import { describe, it, expect } from 'vitest'
import { buildWizardDomainCards, entityTypesForDomain } from '../ModelWizardView.helpers'
import type { AuthoringGuidance } from '../../../domain'

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
})

describe('entityTypesForDomain', () => {
  const guidance: AuthoringGuidance = {
    entity_types: [
      {
        name: 'goal', prefix: 'GOL', domain: 'motivation', classes: [],
        create_when: 'a desired end state exists', never_create_when: '',
        permitted_connections: { outgoing: {}, incoming: {}, symmetric: {} },
      },
      {
        name: 'business-process', prefix: 'PRC', domain: 'business', classes: [],
        create_when: '', never_create_when: '',
        permitted_connections: { outgoing: {}, incoming: {}, symmetric: {} },
      },
    ],
  }

  it('filters entity types to the requested domain', () => {
    expect(entityTypesForDomain(guidance, 'motivation').map((e) => e.name)).toEqual(['goal'])
  })

  it('returns an empty array for a domain with no matches', () => {
    expect(entityTypesForDomain(guidance, 'technology')).toEqual([])
  })

  it('returns an empty array when guidance is null', () => {
    expect(entityTypesForDomain(null, 'motivation')).toEqual([])
  })
})
