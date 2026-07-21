// Pure helpers for the supply-chain wizard — unit-testable without a DOM.

export interface SupplyStep {
  key: string
  label: string
  /** Whether this step requires an ArchiMate scope anchor to be selected first. */
  needsAnchor: boolean
}

// Supply-chain flow: Scope (ArchiMate anchor) → Components → Vulnerabilities →
// Posture & VEX → AI-BOM. The AI-BOM step is store-/architecture-wide (candidate
// scan, ML-BOM export), so it does not require a per-scope anchor.
//
// There is deliberately NO import step. Ingest is a serialised, audited, idempotent
// act owned by the IngestSecuritySignals command, reached through the CLI, MCP, or
// the REST ingest endpoint. A paste-JSON box could not carry a request id or
// generator provenance, so this wizard VIEWS the active snapshot rather than
// pretending to produce one.
export const SUPPLY_STEPS: SupplyStep[] = [
  { key: 'scope', label: 'Scope', needsAnchor: false },
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

/** A component row of the active signal snapshot. */
export interface BomComponent {
  component_id?: string
  name?: string
  version?: string
  component_type?: string
  purl?: string
  directness?: string
}
