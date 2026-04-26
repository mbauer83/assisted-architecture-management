/** Converts a camelCase ArchiMate type name to the kebab-case key used by ArchimateTypeGlyph. */
export const toGlyphKey = (t: string): string =>
  t.replace(/[A-Z]/g, (c, i) => (i > 0 ? '-' : '') + c.toLowerCase())
