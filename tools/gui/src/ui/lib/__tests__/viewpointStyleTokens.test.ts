import { describe, it, expect } from 'vitest'
import { tokenColor, tokenShape, tokenIconLetter, tokenEdgeEmphasis, tokenLabel } from '../viewpointStyleTokens'

describe('viewpointStyleTokens', () => {
  it('resolves every fixed vocabulary token to a distinct color', () => {
    const tokens = ['emphasis', 'positive', 'caution', 'critical', 'neutral']
    const colors = tokens.map(tokenColor)
    expect(new Set(colors).size).toBe(tokens.length)
  })

  it('falls back to neutral for an unrecognized token', () => {
    expect(tokenColor('not-a-real-token')).toBe(tokenColor('neutral'))
    expect(tokenShape('not-a-real-token')).toBe(tokenShape('neutral'))
    expect(tokenEdgeEmphasis('not-a-real-token')).toEqual(tokenEdgeEmphasis('neutral'))
  })

  it('gives every token a non-empty icon letter and label', () => {
    for (const token of ['emphasis', 'positive', 'caution', 'critical', 'neutral']) {
      expect(tokenIconLetter(token).length).toBeGreaterThan(0)
      expect(tokenLabel(token).length).toBeGreaterThan(0)
    }
  })
})
