// Pure helpers for the AI-BOM panel — unit-testable without a DOM.

/**
 * An AI-BOM role for an exported ML-BOM component (CycloneDX 1.6 ML-BOM / ASBOM).
 * The vocabulary is owned by the backend (GET /api/assurance/aibom/roles) and
 * fetched at runtime — never redeclared here — so the two cannot drift.
 */
export type AiRole = string

/** Decode the roles endpoint response into the role vocabulary. */
export function parseRoles(body: unknown): AiRole[] {
  if (!body || typeof body !== 'object') return []
  const raw = (body as Record<string, unknown>)['roles']
  return Array.isArray(raw) ? raw.map(String) : []
}

export interface CoverageReport {
  total_bom_components: number
  unanchored_components: number
  anchor_mappings: number
  unanchored_truncated: boolean
  unanchored: { name?: string; purl?: string; arch_entity_id?: string }[]
  anchored_entity_ids: string[]
  withheld_components?: number
  summary: string
}

const EMPTY_COVERAGE: CoverageReport = {
  total_bom_components: 0,
  unanchored_components: 0,
  anchor_mappings: 0,
  unanchored_truncated: false,
  unanchored: [],
  anchored_entity_ids: [],
  summary: '',
}

/** Coerce an unknown to a string, but only for primitives (objects → ''). */
function asStr(v: unknown): string {
  return typeof v === 'string' || typeof v === 'number' || typeof v === 'boolean' ? String(v) : ''
}

function asNum(v: unknown): number {
  return typeof v === 'number' ? v : 0
}

/** Decode the coverage endpoint response defensively into a stable shape. */
export function parseCoverage(body: unknown): CoverageReport {
  if (!body || typeof body !== 'object') return EMPTY_COVERAGE
  const b = body as Record<string, unknown>
  const unanchored = Array.isArray(b['unanchored'])
    ? (b['unanchored'].filter((c): c is Record<string, unknown> => !!c && typeof c === 'object')
        .map((c) => ({ name: asStr(c['name']), purl: asStr(c['purl']), arch_entity_id: asStr(c['arch_entity_id']) })))
    : []
  const anchoredIds = Array.isArray(b['anchored_entity_ids'])
    ? b['anchored_entity_ids'].map(asStr).filter((s) => s !== '')
    : []
  return {
    total_bom_components: asNum(b['total_bom_components']),
    unanchored_components: asNum(b['unanchored_components']),
    anchor_mappings: asNum(b['anchor_mappings']),
    unanchored_truncated: b['unanchored_truncated'] === true,
    unanchored,
    anchored_entity_ids: anchoredIds,
    withheld_components: asNum(b['withheld_components']),
    summary: asStr(b['summary']),
  }
}

export interface ScanCandidate {
  entity_id: string
  name: string
  entity_type: string
  score: number
  reasons: string[]
}

/** Decode the scan endpoint response into a list of candidates. */
export function parseCandidates(body: unknown): ScanCandidate[] {
  if (!body || typeof body !== 'object') return []
  const raw = (body as Record<string, unknown>)['candidates']
  if (!Array.isArray(raw)) return []
  return raw
    .filter((c): c is Record<string, unknown> => !!c && typeof c === 'object')
    .map((c) => ({
      entity_id: asStr(c['entity_id']),
      name: asStr(c['name']),
      entity_type: asStr(c['entity_type']),
      score: asNum(c['score']),
      reasons: Array.isArray(c['reasons']) ? c['reasons'].map(asStr).filter((s) => s !== '') : [],
    }))
}

export interface AiComponent {
  name: string
  arch_entity_id: string
  ai_role: AiRole
}

/**
 * Build the export payload from confirmed scan candidates. A candidate is
 * included when its entity_id is in `selectedIds`; its role comes from `roleById`
 * (falling back to `defaultRole`).
 */
export function selectedAiComponents(
  candidates: ScanCandidate[],
  selectedIds: ReadonlySet<string>,
  roleById: Readonly<Record<string, AiRole>>,
  defaultRole: AiRole,
): AiComponent[] {
  return candidates
    .filter((c) => selectedIds.has(c.entity_id))
    .map((c) => ({
      name: c.name,
      arch_entity_id: c.entity_id,
      ai_role: roleById[c.entity_id] ?? defaultRole,
    }))
}

/** Confidence band for a candidate score (drives the badge colour). */
export function scoreBand(score: number): 'high' | 'medium' | 'low' {
  return score >= 50 ? 'high' : score >= 30 ? 'medium' : 'low'
}
