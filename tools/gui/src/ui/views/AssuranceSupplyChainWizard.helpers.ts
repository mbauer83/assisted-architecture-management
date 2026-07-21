// Pure helpers for the supply-chain wizard — unit-testable without a DOM.

export interface SupplyStep {
  key: string
  label: string
  /** Whether this step requires an ArchiMate scope anchor to be selected first. */
  needsAnchor: boolean
}

// Supply-chain flow: Scope (ArchiMate anchor) → Import SBOM → Components →
// Vulnerabilities → AI-BOM. The AI-BOM step is store-/architecture-wide (coverage,
// candidate scan, ML-BOM export), so it does not require a per-scope anchor.
export const SUPPLY_STEPS: SupplyStep[] = [
  { key: 'scope', label: 'Scope', needsAnchor: false },
  { key: 'import', label: 'Import SBOM', needsAnchor: true },
  { key: 'components', label: 'Components', needsAnchor: true },
  { key: 'vulnerabilities', label: 'Vulnerabilities', needsAnchor: true },
  { key: 'posture', label: 'Posture & VEX', needsAnchor: true },
  { key: 'aibom', label: 'AI-BOM', needsAnchor: false },
]

/**
 * Admissible ArchiMate anchor types for an SBOM scope. Scope is expressed in
 * ArchiMate terms (never C4 container/system, which is only a view): one service
 * → application-component; a system or subset of services → application-collaboration
 * or grouping; technology → node or system-software.
 */
export const ADMISSIBLE_ANCHOR_TYPES = [
  'application-component',
  'application-collaboration',
  'grouping',
  'node',
  'system-software',
] as const

export const SEVERITY_ORDER = ['critical', 'high', 'medium', 'low', 'unknown'] as const

export interface ParseResult<T> {
  value?: T
  error?: string
}

/** Parse text as a JSON object (CycloneDX SBOM document). */
export function parseJsonObject(text: string): ParseResult<Record<string, unknown>> {
  if (!text.trim()) return { error: 'Paste a CycloneDX SBOM (JSON) first.' }
  let parsed: unknown
  try {
    parsed = JSON.parse(text)
  } catch (e) {
    return { error: `Invalid JSON: ${String(e)}` }
  }
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    return { error: 'Expected a JSON object (a CycloneDX SBOM document).' }
  }
  return { value: parsed as Record<string, unknown> }
}

/** Parse text as a JSON array (vulnerability records). */
export function parseJsonArray(text: string): ParseResult<unknown[]> {
  if (!text.trim()) return { error: 'Paste vulnerability records (a JSON array) first.' }
  let parsed: unknown
  try {
    parsed = JSON.parse(text)
  } catch (e) {
    return { error: `Invalid JSON: ${String(e)}` }
  }
  if (!Array.isArray(parsed)) {
    return { error: 'Expected a JSON array of vulnerability records.' }
  }
  return { value: parsed }
}

export interface VulnRecord {
  vuln_id?: string
  id?: string
  severity?: string
  purl?: string
  summary?: string
}

/** Count vulnerabilities by severity in canonical order (zero-count buckets dropped). */
export function summariseSeverities(vulns: VulnRecord[]): { severity: string; count: number }[] {
  const counts = new Map<string, number>()
  for (const v of vulns) {
    const sev = (v.severity ?? 'unknown').toLowerCase()
    counts.set(sev, (counts.get(sev) ?? 0) + 1)
  }
  const ordered: { severity: string; count: number }[] = []
  for (const sev of SEVERITY_ORDER) {
    const c = counts.get(sev)
    if (c) { ordered.push({ severity: sev, count: c }); counts.delete(sev) }
  }
  // Any non-canonical severities, appended as-is.
  for (const [severity, count] of counts) ordered.push({ severity, count })
  return ordered
}

export interface BomComponent {
  component_id?: string
  name?: string
  version?: string
  component_type?: string
  purl?: string
  match_type?: string
}

/** How many components resolved to an architecture anchor (per-scope binding health). */
export function componentMatchSummary(components: BomComponent[]): { matched: number; total: number } {
  const matched = components.filter((c) => c.match_type === 'anchor').length
  return { matched, total: components.length }
}
