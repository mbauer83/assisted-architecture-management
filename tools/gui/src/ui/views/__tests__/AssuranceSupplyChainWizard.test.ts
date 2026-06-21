import { describe, it, expect } from 'vitest'
import {
  SUPPLY_STEPS,
  ADMISSIBLE_ANCHOR_TYPES,
  parseJsonObject,
  parseJsonArray,
  summariseSeverities,
  componentMatchSummary,
} from '../AssuranceSupplyChainWizard.helpers'

describe('SUPPLY_STEPS', () => {
  it('runs Scope → Import SBOM → Components → Vulnerabilities → AI-BOM', () => {
    expect(SUPPLY_STEPS.map((s) => s.key)).toEqual([
      'scope', 'import', 'components', 'vulnerabilities', 'aibom',
    ])
  })

  it('gates the SBOM steps on an anchor; scope and aibom are anchor-free', () => {
    expect(SUPPLY_STEPS.find((s) => s.key === 'scope')?.needsAnchor).toBe(false)
    // AI-BOM is store-/architecture-wide (coverage, scan, export), so not anchor-gated.
    expect(SUPPLY_STEPS.find((s) => s.key === 'aibom')?.needsAnchor).toBe(false)
    const anchorGated = SUPPLY_STEPS.filter((s) => s.key !== 'scope' && s.key !== 'aibom')
    expect(anchorGated.every((s) => s.needsAnchor)).toBe(true)
  })

  it('admits ArchiMate scope types (never C4 container/system)', () => {
    expect([...ADMISSIBLE_ANCHOR_TYPES]).toEqual([
      'application-component', 'application-collaboration', 'grouping', 'node', 'system-software',
    ])
  })
})

describe('parseJsonObject', () => {
  it('accepts a JSON object', () => {
    expect(parseJsonObject('{"bomFormat":"CycloneDX"}').value).toEqual({ bomFormat: 'CycloneDX' })
  })

  it('rejects empty, malformed, and non-object JSON', () => {
    expect(parseJsonObject('   ').error).toMatch(/Paste a CycloneDX/)
    expect(parseJsonObject('{').error).toMatch(/Invalid JSON/)
    expect(parseJsonObject('[1,2]').error).toMatch(/Expected a JSON object/)
  })
})

describe('parseJsonArray', () => {
  it('accepts a JSON array', () => {
    expect(parseJsonArray('[{"id":"CVE-1"}]').value).toEqual([{ id: 'CVE-1' }])
  })

  it('rejects empty, malformed, and non-array JSON', () => {
    expect(parseJsonArray('').error).toMatch(/Paste vulnerability/)
    expect(parseJsonArray('nope').error).toMatch(/Invalid JSON/)
    expect(parseJsonArray('{"a":1}').error).toMatch(/Expected a JSON array/)
  })
})

describe('summariseSeverities', () => {
  it('counts by severity in canonical order, dropping empty buckets', () => {
    const out = summariseSeverities([
      { severity: 'HIGH' }, { severity: 'high' }, { severity: 'critical' }, {},
    ])
    expect(out).toEqual([
      { severity: 'critical', count: 1 },
      { severity: 'high', count: 2 },
      { severity: 'unknown', count: 1 },
    ])
  })

  it('appends non-canonical severities after the canonical ones', () => {
    const out = summariseSeverities([{ severity: 'low' }, { severity: 'moderate' }])
    expect(out).toEqual([
      { severity: 'low', count: 1 },
      { severity: 'moderate', count: 1 },
    ])
  })
})

describe('componentMatchSummary', () => {
  it('counts anchor-matched components', () => {
    expect(componentMatchSummary([
      { match_type: 'anchor' }, { match_type: 'none' }, { match_type: 'anchor' },
    ])).toEqual({ matched: 2, total: 3 })
  })
})
