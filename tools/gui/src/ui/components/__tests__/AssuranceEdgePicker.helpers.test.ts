/**
 * Ontology-driven edge picker logic: legal-set filtering per concrete pair
 * (both directions), the empty-legal-set message, and direction-honoring
 * submission payloads. The catalog fixture mirrors the served
 * /api/assurance/edge-catalog shape.
 */
import { describe, it, expect } from 'vitest'
import {
  edgeSubmission, emptyLegalSetMessage, legalTypesForPair, legalTypesForSelection,
  type EdgeCatalog,
} from '../AssuranceEdgePicker.helpers'

const catalog: EdgeCatalog = {
  edge_types: [
    { name: 'leads-to', label: 'leads to' },
    { name: 'explains', label: 'explains' },
    { name: 'derives', label: 'derives' },
  ],
  permitted: [
    { source_type: 'hazard', target_type: 'loss', connection_types: ['leads-to'] },
    { source_type: 'unsafe-control-action', target_type: 'hazard', connection_types: ['leads-to'] },
    { source_type: 'loss-scenario', target_type: 'hazard', connection_types: ['explains'] },
    { source_type: 'hazard', target_type: 'assurance-constraint', connection_types: ['derives'] },
  ],
  reference_types: [{ name: 'binds-to', description: 'evidence binding' }],
}

describe('legalTypesForPair', () => {
  it('returns exactly the catalog row for the pair', () => {
    expect(legalTypesForPair(catalog, 'hazard', 'loss')).toEqual(['leads-to'])
  })

  it('is direction-sensitive: the reversed pair has no row', () => {
    expect(legalTypesForPair(catalog, 'loss', 'hazard')).toEqual([])
  })

  it('never offers reference types as edge types', () => {
    for (const row of catalog.permitted) {
      expect(row.connection_types).not.toContain('binds-to')
    }
  })
})

describe('legalTypesForSelection', () => {
  it('outgoing reads (panel → other)', () => {
    expect(legalTypesForSelection(catalog, 'outgoing', 'hazard', 'loss')).toEqual(['leads-to'])
  })

  it('incoming reads (other → panel)', () => {
    expect(legalTypesForSelection(catalog, 'incoming', 'hazard', 'loss-scenario')).toEqual(['explains'])
    expect(legalTypesForSelection(catalog, 'incoming', 'hazard', 'unsafe-control-action')).toEqual(['leads-to'])
  })

  it('a pair with zero legal types yields the empty set', () => {
    expect(legalTypesForSelection(catalog, 'outgoing', 'loss', 'hazard')).toEqual([])
  })
})

describe('emptyLegalSetMessage', () => {
  it('names the pair in reading order for the chosen direction', () => {
    expect(emptyLegalSetMessage('outgoing', 'loss', 'hazard'))
      .toContain('from loss to hazard')
    expect(emptyLegalSetMessage('incoming', 'loss', 'hazard'))
      .toContain('from hazard to loss')
  })
})

describe('edgeSubmission', () => {
  it('outgoing: panel node is the source', () => {
    expect(edgeSubmission('outgoing', 'HAZ@1', 'LSS@1', 'leads-to'))
      .toEqual({ source_id: 'HAZ@1', target_id: 'LSS@1', conn_type: 'leads-to' })
  })

  it('incoming: panel node is the target', () => {
    expect(edgeSubmission('incoming', 'HAZ@1', 'UCA@1', 'leads-to'))
      .toEqual({ source_id: 'UCA@1', target_id: 'HAZ@1', conn_type: 'leads-to' })
  })
})
