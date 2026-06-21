import { describe, it, expect } from 'vitest'
import {
  parseRoles,
  parseCoverage,
  parseCandidates,
  selectedAiComponents,
  scoreBand,
} from '../AssuranceAibom.helpers'

describe('parseRoles', () => {
  it('decodes the roles array from the backend', () => {
    expect(parseRoles({ roles: ['machine-learning-model', 'dataset'] })).toEqual([
      'machine-learning-model',
      'dataset',
    ])
  })

  it('returns empty on a malformed body', () => {
    expect(parseRoles(null)).toEqual([])
    expect(parseRoles({})).toEqual([])
    expect(parseRoles({ roles: 'nope' })).toEqual([])
  })
})

describe('parseCoverage', () => {
  it('decodes a full coverage report', () => {
    const report = parseCoverage({
      total_bom_components: 3,
      unanchored_components: 1,
      anchor_mappings: 2,
      unanchored_truncated: false,
      unanchored: [{ name: 'orphan' }],
      anchored_entity_ids: ['APP@1'],
      withheld_components: 0,
      summary: 'ok',
    })
    expect(report.total_bom_components).toBe(3)
    expect(report.unanchored_components).toBe(1)
    expect(report.unanchored[0].name).toBe('orphan')
    expect(report.anchored_entity_ids).toEqual(['APP@1'])
  })

  it('falls back to a stable empty shape on garbage', () => {
    const report = parseCoverage('not-an-object')
    expect(report.total_bom_components).toBe(0)
    expect(report.unanchored).toEqual([])
    expect(report.anchored_entity_ids).toEqual([])
  })
})

describe('parseCandidates', () => {
  it('decodes candidates and coerces fields', () => {
    const out = parseCandidates({
      candidates: [
        { entity_id: 'APP@1', name: 'Claude', entity_type: 'application-component', score: 55, reasons: ['LLM name pattern'] },
        { entity_id: 'APP@2', name: 'X', entity_type: 't', score: 'bad', reasons: 'bad' },
      ],
    })
    expect(out).toHaveLength(2)
    expect(out[0].score).toBe(55)
    expect(out[1].score).toBe(0)
    expect(out[1].reasons).toEqual([])
  })

  it('returns empty when candidates is absent or malformed', () => {
    expect(parseCandidates({})).toEqual([])
    expect(parseCandidates({ candidates: 'nope' })).toEqual([])
    expect(parseCandidates(null)).toEqual([])
  })
})

describe('selectedAiComponents', () => {
  const candidates = [
    { entity_id: 'APP@1', name: 'Claude', entity_type: 'application-component', score: 55, reasons: [] },
    { entity_id: 'APP@2', name: 'Vectors', entity_type: 'data-object', score: 25, reasons: [] },
    { entity_id: 'APP@3', name: 'Ledger', entity_type: 'application-component', score: 10, reasons: [] },
  ]

  it('maps only selected candidates with their resolved role', () => {
    const out = selectedAiComponents(
      candidates,
      new Set(['APP@1', 'APP@2']),
      { 'APP@2': 'vector-store' },
      'machine-learning-model',
    )
    expect(out).toEqual([
      { name: 'Claude', arch_entity_id: 'APP@1', ai_role: 'machine-learning-model' },
      { name: 'Vectors', arch_entity_id: 'APP@2', ai_role: 'vector-store' },
    ])
  })

  it('returns empty when nothing is selected', () => {
    expect(selectedAiComponents(candidates, new Set(), {}, 'tool')).toEqual([])
  })
})

describe('scoreBand', () => {
  it('bands scores into high/medium/low', () => {
    expect(scoreBand(70)).toBe('high')
    expect(scoreBand(50)).toBe('high')
    expect(scoreBand(35)).toBe('medium')
    expect(scoreBand(30)).toBe('medium')
    expect(scoreBand(10)).toBe('low')
  })
})
