import { describe, it, expect } from 'vitest'
import {
  buildAnalysisOptions,
  emptyNewAnalysisForm,
  newAnalysisBody,
  validateNewAnalysis,
  nodesUrlForAnalysis,
  ANALYSIS_METHODS,
  type AnalysisSummary,
} from '../AssuranceAnalysisPicker.helpers'

const sample: AnalysisSummary[] = [
  { analysis_id: 'STPA@1', name: 'Brakes', method: 'STPA' },
  { analysis_id: 'GRC@2', name: 'Q3 Controls', method: 'GRC' },
]

describe('buildAnalysisOptions', () => {
  it('tags labels with the method', () => {
    expect(buildAnalysisOptions(sample)).toEqual([
      { value: 'STPA@1', label: '[STPA] Brakes' },
      { value: 'GRC@2', label: '[GRC] Q3 Controls' },
    ])
  })

  it('handles an empty list', () => {
    expect(buildAnalysisOptions([])).toEqual([])
  })
})

describe('validateNewAnalysis', () => {
  it('accepts a valid form', () => {
    expect(validateNewAnalysis({ ...emptyNewAnalysisForm(), name: 'X' })).toBeNull()
  })

  it('rejects an empty name', () => {
    expect(validateNewAnalysis({ ...emptyNewAnalysisForm(), name: '  ' }))
      .toBe('Name is required.')
  })

  it('rejects an unknown method', () => {
    expect(validateNewAnalysis({ ...emptyNewAnalysisForm(), name: 'X', method: 'HAZOP' }))
      .toBe('Method must be STPA, CAST, or GRC.')
  })

  it('accepts every supported method', () => {
    for (const m of ANALYSIS_METHODS) {
      expect(validateNewAnalysis({ ...emptyNewAnalysisForm(), name: 'X', method: m })).toBeNull()
    }
  })
})

describe('newAnalysisBody', () => {
  it('trims fields and includes a non-empty anchor', () => {
    const body = newAnalysisBody({
      name: '  Brakes ', method: 'STPA',
      architecture_anchor_id: ' APP@1 ', tlp: 'TLP:AMBER',
    })
    expect(body).toEqual({
      name: 'Brakes', method: 'STPA', tlp: 'TLP:AMBER', architecture_anchor_id: 'APP@1',
    })
  })

  it('omits the anchor when empty (it is optional)', () => {
    const body = newAnalysisBody({
      name: 'Q3', method: 'GRC', architecture_anchor_id: '   ', tlp: 'TLP:WHITE',
    })
    expect(body).toEqual({ name: 'Q3', method: 'GRC', tlp: 'TLP:WHITE' })
    expect('architecture_anchor_id' in body).toBe(false)
  })
})

describe('emptyNewAnalysisForm', () => {
  it('defaults the method to STPA', () => {
    expect(emptyNewAnalysisForm().method).toBe('STPA')
  })

  it('honours an explicit default method', () => {
    expect(emptyNewAnalysisForm('GRC').method).toBe('GRC')
  })
})

describe('nodesUrlForAnalysis', () => {
  it('returns the unscoped url for null', () => {
    expect(nodesUrlForAnalysis(null)).toBe('/api/assurance/nodes')
  })

  it('encodes the analysis id', () => {
    expect(nodesUrlForAnalysis('STPA@1.a/b'))
      .toBe('/api/assurance/nodes?analysis_id=STPA%401.a%2Fb')
  })
})
