import { describe, it, expect } from 'vitest'
import {
  computeExecutionDiagnostics,
  computeUnsupportedCapabilities,
  deriveLegend,
  deriveScaleGradients,
} from '../ViewpointExecutionDiagnostics.helpers'
import { mkPresentation, mkStyleRule } from '../../../domain/viewpointPresentation'
import { mkGroup } from '../../../domain/viewpointCriteria'
import type { ViewpointExecutionResult } from '../../../domain'

const baseResult: ViewpointExecutionResult = {
  slug: 'test-vp', version: 1, query_schema: 1, repo_scope: 'both', executed_at: '2026-07-11T00:00:00Z',
  index_generation: null, entity_ids: [], connection_ids: [], entities: [], connections: [],
  total_entity_count: 0, returned_entity_count: 0, total_connection_count: 0, returned_connection_count: 0,
  truncated: false, entity_limit: 500, matrix_axes: null, warnings: [], duration_ms: 1, query_summary: 'test',
  anchor_ids: [],
}

describe('computeExecutionDiagnostics', () => {
  it('reports the explained empty state when nothing matches', () => {
    const diagnostics = computeExecutionDiagnostics(baseResult, null, 'exploration')
    expect(diagnostics.isEmpty).toBe(true)
    expect(diagnostics.emptyReason).toMatch(/no entities/i)
    expect(diagnostics.truncated).toBe(false)
  })

  it('reports truncation with the applied limit', () => {
    const result: ViewpointExecutionResult = {
      ...baseResult, total_entity_count: 10, returned_entity_count: 5, entity_limit: 5, truncated: true,
    }
    const diagnostics = computeExecutionDiagnostics(result, null, 'exploration')
    expect(diagnostics.isEmpty).toBe(false)
    expect(diagnostics.truncated).toBe(true)
    expect(diagnostics.truncationMessage).toContain('5 of 10')
  })

  it('passes through result warnings (schema/capability drift, stale pin)', () => {
    const result: ViewpointExecutionResult = { ...baseResult, warnings: ['schema drift on attribute x'] }
    const diagnostics = computeExecutionDiagnostics(result, null, 'exploration')
    expect(diagnostics.warnings).toEqual(['schema drift on attribute x'])
  })

  it('reports every-match-truncated when total > 0 but nothing is returned', () => {
    const result: ViewpointExecutionResult = { ...baseResult, total_entity_count: 3, entity_limit: 0 }
    const diagnostics = computeExecutionDiagnostics(result, null, 'exploration')
    expect(diagnostics.isEmpty).toBe(false)
    expect(diagnostics.emptyReason).toMatch(/truncated/i)
  })
})

describe('computeUnsupportedCapabilities', () => {
  it('is empty when there is no presentation', () => {
    expect(computeUnsupportedCapabilities(null, 'table')).toEqual([])
  })

  it('flags an exploration-only capability rendered in table view', () => {
    const presentation = mkPresentation('exploration')
    const rule = mkStyleRule('exploration')
    rule.capability = 'cluster_grouping'
    presentation.stylingRules = [rule]
    expect(computeUnsupportedCapabilities(presentation, 'table')).toEqual(['cluster_grouping'])
  })

  it('does not flag a capability the representation supports', () => {
    const presentation = mkPresentation('exploration')
    const rule = mkStyleRule('exploration')
    rule.capability = 'node_color'
    presentation.stylingRules = [rule]
    expect(computeUnsupportedCapabilities(presentation, 'exploration')).toEqual([])
  })

  it('flags an unsupported default_style capability', () => {
    const presentation = mkPresentation('table')
    presentation.defaultStyle = { node_color: 'neutral' }
    expect(computeUnsupportedCapabilities(presentation, 'table')).toEqual(['node_color'])
  })

  it('flags a table-only capability (row grouping) rendered in matrix view', () => {
    const presentation = mkPresentation('table')
    const rule = mkStyleRule('table')
    rule.capability = 'badges'
    presentation.stylingRules = [rule]
    expect(computeUnsupportedCapabilities(presentation, 'matrix')).toEqual(['badges'])
  })

  it('flags a matrix-only capability (cell_emphasis) rendered in diagram view', () => {
    const presentation = mkPresentation('matrix')
    const rule = mkStyleRule('matrix')
    rule.capability = 'cell_emphasis'
    presentation.stylingRules = [rule]
    expect(computeUnsupportedCapabilities(presentation, 'diagram')).toEqual(['cell_emphasis'])
  })

  it('does not flag node_color/edge_color/edge_emphasis rendered in diagram view — they are supported there', () => {
    const presentation = mkPresentation('diagram')
    presentation.defaultStyle = { node_color: 'positive', edge_color: 'critical', edge_emphasis: 'caution' }
    expect(computeUnsupportedCapabilities(presentation, 'diagram')).toEqual([])
  })
})

describe('deriveLegend', () => {
  it('is empty when there is no presentation', () => {
    expect(deriveLegend(null)).toEqual([])
  })

  it('derives a match-mode entry from a styling rule', () => {
    const presentation = mkPresentation('exploration')
    const rule = mkStyleRule('exploration')
    rule.capability = 'node_color'
    rule.value = 'positive'
    rule.appliesTo = ['application-component']
    rule.matchCriteria = mkGroup('entity')
    presentation.stylingRules = [rule]
    expect(deriveLegend(presentation)).toEqual([
      { capability: 'node_color', token: 'positive', label: 'application-component' },
    ])
  })

  it('derives one entry per range band', () => {
    const presentation = mkPresentation('exploration')
    const rule = mkStyleRule('exploration')
    rule.capability = 'node_color'
    rule.mode = 'range'
    rule.rangeAttribute = 'risk_score'
    rule.rangeBands = [
      { id: 'b1', minimum: null, maximum: 5, value: 'positive' },
      { id: 'b2', minimum: 5, maximum: null, value: 'critical' },
    ]
    presentation.stylingRules = [rule]
    expect(deriveLegend(presentation)).toEqual([
      { capability: 'node_color', token: 'positive', label: 'risk_score in [-∞, 5)' },
      { capability: 'node_color', token: 'critical', label: 'risk_score in [5, ∞)' },
    ])
  })

  it('derives an entry from default_style', () => {
    const presentation = mkPresentation('exploration')
    presentation.defaultStyle = { node_color: 'neutral' }
    expect(deriveLegend(presentation)).toEqual([{ capability: 'node_color', token: 'neutral', label: 'default' }])
  })
})

describe('deriveScaleGradients', () => {
  it('is empty when there is no presentation', () => {
    expect(deriveScaleGradients(null)).toEqual([])
  })

  it('ignores match- and range-mode rules', () => {
    const presentation = mkPresentation('exploration')
    const matchRule = mkStyleRule('exploration')
    const rangeRule = mkStyleRule('exploration')
    rangeRule.mode = 'range'
    rangeRule.rangeBands = [{ id: 'b1', minimum: 0, maximum: 5, value: 'positive' }]
    presentation.stylingRules = [matchRule, rangeRule]
    expect(deriveScaleGradients(presentation)).toEqual([])
  })

  it('ignores a scale rule with no scale_tokens (unauthored)', () => {
    const presentation = mkPresentation('exploration')
    const rule = mkStyleRule('exploration')
    rule.mode = 'scale'
    presentation.stylingRules = [rule]
    expect(deriveScaleGradients(presentation)).toEqual([])
  })

  it('builds a gradient between the two declared scale_tokens, labelled with data-driven (null) bounds as unbounded', () => {
    const presentation = mkPresentation('exploration')
    const rule = mkStyleRule('exploration')
    rule.capability = 'node_color'
    rule.mode = 'scale'
    rule.scaleAttribute = 'derived.impact-distance'
    rule.scaleTokens = ['heat-near', 'heat-far']
    presentation.stylingRules = [rule]
    const gradients = deriveScaleGradients(presentation)
    expect(gradients).toEqual([{
      capability: 'node_color',
      gradientCss: 'linear-gradient(to right, #0891b2, #dc2626)',
      minLabel: '−∞',
      maxLabel: '∞',
    }])
  })

  it('labels finite scale_min/scale_max bounds with their numeric value', () => {
    const presentation = mkPresentation('exploration')
    const rule = mkStyleRule('exploration')
    rule.mode = 'scale'
    rule.scaleMin = 1
    rule.scaleMax = 4
    rule.scaleTokens = ['heat-near', 'heat-far']
    presentation.stylingRules = [rule]
    const gradients = deriveScaleGradients(presentation)
    expect(gradients[0].minLabel).toBe('1')
    expect(gradients[0].maxLabel).toBe('4')
  })
})
