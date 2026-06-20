/**
 * Pure helpers for ClassifierCard attribute-type combobox option building.
 */

/**
 * Build the ordered, deduplicated list of type options for the attribute type combobox.
 * Primitives appear first, then in-diagram classifier labels.
 */
export function buildTypeOptions(primitiveTypes: readonly string[], classifierLabels: readonly string[]): string[] {
  const seen = new Set<string>()
  const opts: string[] = []
  for (const t of [...primitiveTypes, ...classifierLabels]) {
    if (!seen.has(t)) { seen.add(t); opts.push(t) }
  }
  return opts
}
