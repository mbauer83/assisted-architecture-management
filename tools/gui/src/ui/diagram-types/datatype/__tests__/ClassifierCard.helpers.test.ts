import { describe, expect, it } from 'vitest'
import {
  buildTypeOptions,
  optionKey,
  removeUniqueConstraint,
  replaceUniqueConstraint,
  refFromOptionKey,
} from '../ClassifierCard.helpers'

const local = [
  { id: 'CLF@1.local.order', classifier_kind: 'class' as const, label: 'Order' },
]
const catalog = [
  {
    type_id: 'CLF@1.eng.customer',
    label: 'Customer',
    scope: 'engagement',
    host_diagram_id: 'DT-2',
  },
  {
    type_id: 'CLF@1.ent.money',
    label: 'Money',
    scope: 'enterprise',
    host_diagram_id: 'DT-3',
  },
]

describe('buildTypeOptions', () => {
  it('builds closed tagged-reference options in display groups', () => {
    const options = buildTypeOptions(['String'], local, catalog, 'DT-1')
    expect(options.map((option) => [option.group, option.label])).toEqual([
      ['Primitives', 'String'],
      ['This diagram', 'Order'],
      ['Engagement', 'Customer'],
      ['Enterprise', 'Money'],
    ])
  })

  it('deduplicates a local classifier already returned by discovery', () => {
    const options = buildTypeOptions(['String'], local, [
      ...catalog,
      {
        type_id: local[0].id,
        label: 'Order',
        scope: 'engagement',
        host_diagram_id: 'DT-1',
      },
    ], 'DT-1')
    expect(options.filter((option) => option.key === `classifier:${local[0].id}`)).toHaveLength(1)
  })

  it('keeps a classifier that shadows a primitive as a distinct choice', () => {
    const options = buildTypeOptions(['String'], [{
      id: 'CLF@1.local.string',
      classifier_kind: 'primitive',
      label: 'String',
    }], [], 'DT-1')
    expect(options.map((option) => option.key)).toEqual([
      'primitive:String',
      'classifier:CLF@1.local.string',
    ])
  })

  it('round-trips only known option keys', () => {
    const options = buildTypeOptions(['String'], local, [], 'DT-1')
    const classifierRef = { kind: 'classifier' as const, id: local[0].id }
    expect(refFromOptionKey(optionKey(classifierRef), options)).toEqual(classifierRef)
    expect(refFromOptionKey('free text', options)).toBeUndefined()
  })
})

describe('unique constraint editing', () => {
  it('replaces one composite constraint without mutating the others', () => {
    expect(replaceUniqueConstraint([['tenant'], ['email']], 0, ['tenant', 'number'])).toEqual([
      ['tenant', 'number'],
      ['email'],
    ])
  })

  it('removes the final constraint as an absent optional field', () => {
    expect(removeUniqueConstraint([['email']], 0)).toBeUndefined()
  })
})
