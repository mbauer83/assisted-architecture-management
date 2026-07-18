import { describe, expect, it } from 'vitest'
import {
  collapsedScopeSummary, definitionNeedsInput, filterAndSortDefinitions, representationOf,
} from '../ViewpointDefinitionsList.helpers'
import type { ViewpointDefinitionEnvelope } from '../../../domain'

const envelope = (overrides: Partial<ViewpointDefinitionEnvelope> = {}): ViewpointDefinitionEnvelope => ({
  slug: 'sample', version: 1, name: 'Sample', tier: 'module',
  scope_summary: { unrestricted: true }, query_summary: null, fork_status: null,
  ...overrides,
})

describe('representationOf', () => {
  it('reads the presentation representation, defaulting to exploration', () => {
    expect(representationOf(envelope())).toBe('exploration')
    expect(representationOf(envelope({ presentation: { representation: 'table' } }))).toBe('table')
  })
})

describe('definitionNeedsInput', () => {
  it('is true only for a required, undefaulted parameter', () => {
    expect(definitionNeedsInput(envelope())).toBe(false)
    const parameterised = envelope({
      query: { query_schema: 1, parameters: [{ name: 'anchor', value_type: 'entity-id', required: true }] },
    })
    expect(definitionNeedsInput(parameterised)).toBe(true)
    const defaulted = envelope({
      query: { query_schema: 1, parameters: [{ name: 'anchor', value_type: 'string', required: true, default: 'x' }] },
    })
    expect(definitionNeedsInput(defaulted)).toBe(false)
  })
})

describe('collapsedScopeSummary', () => {
  it('collapses type dumps to counts', () => {
    expect(collapsedScopeSummary({ unrestricted: true })).toBe('unrestricted')
    expect(collapsedScopeSummary({
      unrestricted: false,
      entity_types: ['goal', 'requirement', 'capability'],
      excluded_domains: ['implementation'],
    })).toBe('3 entity types, 1 excluded domain')
  })
})

describe('filterAndSortDefinitions', () => {
  const definitions = [
    envelope({ slug: 'b-view', name: 'Beta', version: 3, tier: 'module', description: 'shows existing links' }),
    envelope({ slug: 'a-view', name: 'Alpha', version: 1, tier: 'engagement' }),
    envelope({ slug: 'c-view', name: 'Gamma', version: 2, tier: 'enterprise' }),
  ]

  it('searches name, slug, and description case-insensitively', () => {
    expect(filterAndSortDefinitions(definitions, 'alpha', '', null, 'asc').map((d) => d.slug)).toEqual(['a-view'])
    expect(filterAndSortDefinitions(definitions, 'existing LINKS', '', null, 'asc').map((d) => d.slug)).toEqual(['b-view'])
  })

  it('filters by tier and preserves served order when unsorted', () => {
    expect(filterAndSortDefinitions(definitions, '', 'module', null, 'asc').map((d) => d.slug)).toEqual(['b-view'])
    expect(filterAndSortDefinitions(definitions, '', '', null, 'asc').map((d) => d.slug)).toEqual(['b-view', 'a-view', 'c-view'])
  })

  it('sorts by name, version, and tier (engagement first), honoring direction', () => {
    expect(filterAndSortDefinitions(definitions, '', '', 'name', 'asc').map((d) => d.name)).toEqual(['Alpha', 'Beta', 'Gamma'])
    expect(filterAndSortDefinitions(definitions, '', '', 'version', 'desc').map((d) => d.version)).toEqual([3, 2, 1])
    expect(filterAndSortDefinitions(definitions, '', '', 'tier', 'asc').map((d) => d.tier)).toEqual(['engagement', 'enterprise', 'module'])
  })
})
