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

/** Coerce an unknown to a string, but only for primitives (objects → ''). */
function asStr(v: unknown): string {
  return typeof v === 'string' || typeof v === 'number' || typeof v === 'boolean' ? String(v) : ''
}

function asNum(v: unknown): number {
  return typeof v === 'number' ? v : 0
}

export interface ScanCandidate {
  entity_id: string
  name: string
  entity_type: string
  score: number
  reasons: string[]
}

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
