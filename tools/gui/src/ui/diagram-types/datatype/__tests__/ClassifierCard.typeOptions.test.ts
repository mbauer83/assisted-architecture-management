/**
 * Tests for WU-F1: attribute type combobox option building.
 *
 * Covers: primitive types, in-diagram classifiers, deduplication, free-entry preserved.
 */
import { describe, it, expect } from 'vitest'
import { buildTypeOptions } from '../ClassifierCard.helpers'

describe('buildTypeOptions', () => {
  it('returns primitives when no classifiers', () => {
    const prims = ['String', 'Integer', 'Boolean']
    expect(buildTypeOptions(prims, [])).toEqual(['String', 'Integer', 'Boolean'])
  })

  it('returns classifiers when no primitives', () => {
    expect(buildTypeOptions([], ['Order', 'Customer'])).toEqual(['Order', 'Customer'])
  })

  it('puts primitives before classifiers', () => {
    const opts = buildTypeOptions(['String'], ['MyClass'])
    expect(opts.indexOf('String')).toBeLessThan(opts.indexOf('MyClass'))
  })

  it('deduplicates when a classifier name matches a primitive', () => {
    const opts = buildTypeOptions(['String', 'Integer'], ['String', 'Order'])
    expect(opts.filter((o) => o === 'String').length).toBe(1)
    expect(opts).toEqual(['String', 'Integer', 'Order'])
  })

  it('deduplicates duplicate classifier labels', () => {
    const opts = buildTypeOptions([], ['Foo', 'Foo', 'Bar'])
    expect(opts).toEqual(['Foo', 'Bar'])
  })

  it('returns empty array when both inputs are empty', () => {
    expect(buildTypeOptions([], [])).toEqual([])
  })

  it('includes all seven standard scalar primitives in the expected order', () => {
    const scalars = ['String', 'Integer', 'Number', 'Boolean', 'Date', 'DateTime', 'UUID']
    const opts = buildTypeOptions(scalars, [])
    expect(opts).toEqual(scalars)
  })
})
