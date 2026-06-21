import { describe, expect, it } from 'vitest'
import {
  assuranceNodeAlias,
  buildAssuranceAliasMap,
  buildUcaMatrixRows,
} from '../AssuranceDiagramPanel.helpers'

describe('assurance diagram selection data', () => {
  it('maps PlantUML aliases back to assurance node ids', () => {
    const nodeId = 'CSN@1234.ab-cd'
    expect(assuranceNodeAlias(nodeId)).toBe('N_CSN_1234_ab_cd')
    expect(buildAssuranceAliasMap([
      { node_id: nodeId, node_type: 'control-structure-node', name: 'Controller' },
    ]).get('N_CSN_1234_ab_cd')).toBe(nodeId)
  })

  it('builds the UCA grid from real concern edges', () => {
    const rows = buildUcaMatrixRows([
      { node_id: 'CA1', node_type: 'control-action', name: 'Brake' },
      {
        node_id: 'U1',
        node_type: 'unsafe-control-action',
        name: 'Brake omitted',
        uca_type: 'not-provided',
      },
    ], [
      { edge_id: 'E1', source_id: 'U1', target_id: 'CA1', conn_type: 'concerns' },
    ])

    expect(rows).toHaveLength(1)
    expect(rows[0]?.controlAction.name).toBe('Brake')
    expect(rows[0]?.cells['not-provided']?.[0]?.node_id).toBe('U1')
  })

  it('does not place a UCA without a concern edge into the wrong row', () => {
    const rows = buildUcaMatrixRows([
      { node_id: 'CA1', node_type: 'control-action', name: 'Brake' },
      { node_id: 'U1', node_type: 'unsafe-control-action', name: 'Orphan' },
    ], [])

    expect(rows[0]?.cells).toEqual({})
  })
})
