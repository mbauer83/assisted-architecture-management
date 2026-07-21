import { describe, it, expect } from 'vitest'
import {
  SUPPLY_STEPS,
  ADMISSIBLE_ANCHOR_TYPES,
  summariseSeverities,
} from '../AssuranceSupplyChainWizard.helpers'

describe('SUPPLY_STEPS', () => {
  it('runs Scope → Components → Vulnerabilities → Posture & VEX → AI-BOM', () => {
    expect(SUPPLY_STEPS.map((s) => s.key)).toEqual([
      'scope', 'components', 'vulnerabilities', 'posture', 'aibom',
    ])
  })

  it('has no import step — ingest is not a browser action', () => {
    /* Ingest is serialised, audited and idempotent, owned by the
       IngestSecuritySignals command and reached via CLI/MCP/REST. A paste-JSON box
       could carry neither a request id nor generator provenance, so the wizard
       VIEWS the active snapshot instead of appearing to produce one. */
    expect(SUPPLY_STEPS.map((s) => s.key)).not.toContain('import')
  })

  it('gates the SBOM steps on an anchor; scope and aibom are anchor-free', () => {
    expect(SUPPLY_STEPS.find((s) => s.key === 'scope')?.needsAnchor).toBe(false)
    // AI-BOM is store-/architecture-wide (scan, export), so not anchor-gated.
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

