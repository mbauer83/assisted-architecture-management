import { describe, it, expect } from 'vitest'
import {
  STPA_STEPS,
  STPA_GUIDEWORDS,
  ucaName,
  buildGuidewordGrid,
  summariseStpaComplete,
  stepsWithContent,
  unboundControlNodes,
  type AssuranceNode,
} from '../AssuranceStpaWizard.helpers'

describe('STPA_STEPS', () => {
  it('runs Losses → Hazards → Control Structure → UCAs → Constraints → Review', () => {
    expect(STPA_STEPS.map((s) => s.key)).toEqual([
      'losses', 'hazards', 'control-structure', 'ucas', 'constraints', 'review',
    ])
  })

  it('declares the leads-to relation on hazards', () => {
    const hazards = STPA_STEPS.find((s) => s.key === 'hazards')
    expect(hazards?.relation).toEqual({ connType: 'leads-to', targetType: 'loss', targetLabel: 'loss' })
  })
})

describe('ucaName', () => {
  it('combines control action and guideword', () => {
    expect(ucaName('Apply brakes', 'not-provided')).toBe('Apply brakes — not-provided')
  })
})

describe('buildGuidewordGrid', () => {
  const actions: AssuranceNode[] = [{ node_id: 'CAC@1', node_type: 'control-action', name: 'Brake' }]
  const ucas: AssuranceNode[] = [
    { node_id: 'UCA@1', node_type: 'unsafe-control-action', name: 'x', uca_type: 'not-provided' },
  ]
  const edges = [{ source_id: 'UCA@1', target_id: 'CAC@1', conn_type: 'concerns' }]

  it('produces a row per control action and a cell per guideword', () => {
    const grid = buildGuidewordGrid(actions, ucas, edges)
    expect(grid).toHaveLength(1)
    expect(grid[0].cells.map((c) => c.guideword)).toEqual([...STPA_GUIDEWORDS])
  })

  it('marks the matching cell as existing', () => {
    const grid = buildGuidewordGrid(actions, ucas, edges)
    const notProvided = grid[0].cells.find((c) => c.guideword === 'not-provided')
    expect(notProvided?.existing?.node_id).toBe('UCA@1')
    const provided = grid[0].cells.find((c) => c.guideword === 'provided')
    expect(provided?.existing).toBeNull()
  })

  it('ignores non-concerns edges', () => {
    const grid = buildGuidewordGrid(actions, ucas, [
      { source_id: 'UCA@1', target_id: 'CAC@1', conn_type: 'violates' },
    ])
    expect(grid[0].cells.every((c) => c.existing === null)).toBe(true)
  })
})

describe('summariseStpaComplete', () => {
  it('extracts failed checks with gap counts', () => {
    const summary = summariseStpaComplete({
      passed: false,
      checks: {
        hazard_leads_to_loss: { passed: true, gap_count: 0 },
        uca_concerns_control_action: { passed: false, gap_count: 2 },
      },
    })
    expect(summary.passed).toBe(false)
    expect(summary.failed).toEqual([{ key: 'uca_concerns_control_action', gapCount: 2 }])
  })
})

describe('stepsWithContent', () => {
  it('flags steps whose node type is present', () => {
    const keys = stepsWithContent([
      { node_id: 'L@1', node_type: 'loss', name: 'L' },
      { node_id: 'H@1', node_type: 'hazard', name: 'H' },
    ])
    expect(keys.has('losses')).toBe(true)
    expect(keys.has('hazards')).toBe(true)
    expect(keys.has('ucas')).toBe(false)
  })
})

describe('unboundControlNodes', () => {
  it('returns only unbound-pending control-structure nodes', () => {
    const result = unboundControlNodes([
      { node_id: 'CSN@1', node_type: 'control-structure-node', name: 'A', binding_status: 'unbound-pending' },
      { node_id: 'CSN@2', node_type: 'control-structure-node', name: 'B', binding_status: 'bound' },
      { node_id: 'L@1', node_type: 'loss', name: 'L' },
    ])
    expect(result.map((n) => n.node_id)).toEqual(['CSN@1'])
  })
})
