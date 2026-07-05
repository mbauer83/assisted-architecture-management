import { describe, it, expect } from 'vitest'
import { ALLOWED_URI_REGEXP } from '../svgSanitize'

describe('ALLOWED_URI_REGEXP', () => {
  it('allows the arch: sentinel scheme', () => {
    expect(ALLOWED_URI_REGEXP.test('arch://a1')).toBe(true)
  })

  it('still allows the schemes DOMPurify permits by default', () => {
    expect(ALLOWED_URI_REGEXP.test('https://example.com')).toBe(true)
    expect(ALLOWED_URI_REGEXP.test('mailto:a@b.com')).toBe(true)
  })

  it('still blocks unlisted schemes', () => {
    expect(ALLOWED_URI_REGEXP.test('javascript:alert(1)')).toBe(false)
    expect(ALLOWED_URI_REGEXP.test('data:text/html,<script>')).toBe(false)
  })
})
