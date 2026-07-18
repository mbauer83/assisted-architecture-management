import { describe, expect, it } from 'vitest'
import { sortEntityRows } from '../EntitiesView.helpers'
import type { EntitySummary } from '../../../domain'

const row = (overrides: Partial<EntitySummary>): EntitySummary => ({
  artifact_id: 'REQ@1.a.a',
  artifact_type: 'requirement',
  name: 'A',
  version: '0.1.0',
  status: 'draft',
  domain: 'motivation',
  subdomain: 'requirement',
  path: '/x.md',
  is_global: false,
  ...overrides,
})

describe('sortEntityRows', () => {
  const items = [
    row({ artifact_id: 'a', artifact_type: 'goal', conn_in: 3, conn_sym: 0, conn_out: 1 }),
    row({ artifact_id: 'b', artifact_type: 'driver', conn_in: 1, conn_sym: 2, conn_out: 5 }),
  ]

  it('null key preserves server order in a fresh copy', () => {
    const sorted = sortEntityRows(items, null, 1)
    expect(sorted.map((r) => r.artifact_id)).toEqual(['a', 'b'])
    expect(sorted).not.toBe(items)
  })

  it('sorts by type and by connection columns in both directions', () => {
    expect(sortEntityRows(items, 'type', 1).map((r) => r.artifact_id)).toEqual(['b', 'a'])
    expect(sortEntityRows(items, 'in', -1).map((r) => r.artifact_id)).toEqual(['a', 'b'])
    expect(sortEntityRows(items, 'total', 1).map((r) => r.artifact_id)).toEqual(['a', 'b'])
  })
})
