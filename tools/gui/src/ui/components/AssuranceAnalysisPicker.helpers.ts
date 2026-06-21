// Pure helpers for the assurance analysis picker — unit-testable without a DOM.

export const ANALYSIS_METHODS = ['STPA', 'CAST', 'GRC'] as const
export type AnalysisMethod = (typeof ANALYSIS_METHODS)[number]

export interface AnalysisSummary {
  analysis_id: string
  name: string
  method: string
  status?: string
  tlp?: string
  architecture_anchor_id?: string
}

export interface AnalysisOption {
  value: string
  label: string
}

/** Build `<option>` entries for the analysis dropdown (method-tagged labels). */
export function buildAnalysisOptions(analyses: AnalysisSummary[]): AnalysisOption[] {
  return analyses.map((a) => ({ value: a.analysis_id, label: `[${a.method}] ${a.name}` }))
}

export interface NewAnalysisForm {
  name: string
  method: string
  architecture_anchor_id: string
  tlp: string
}

export function emptyNewAnalysisForm(method: AnalysisMethod = 'STPA'): NewAnalysisForm {
  return { name: '', method, architecture_anchor_id: '', tlp: 'TLP:WHITE' }
}

/** Mirror the backend invariants so the form blocks before a doomed POST. */
export function validateNewAnalysis(form: NewAnalysisForm): string | null {
  if (!form.name.trim()) return 'Name is required.'
  if (!ANALYSIS_METHODS.includes(form.method as AnalysisMethod)) {
    return 'Method must be STPA, CAST, or GRC.'
  }
  return null
}

/** Build the request body, dropping the anchor when empty (it is optional). */
export function newAnalysisBody(form: NewAnalysisForm): Record<string, string> {
  const body: Record<string, string> = {
    name: form.name.trim(),
    method: form.method,
    tlp: form.tlp,
  }
  const anchor = form.architecture_anchor_id.trim()
  if (anchor) body['architecture_anchor_id'] = anchor
  return body
}

/** Node-list URL scoped to an analysis (or the unscoped list when null). */
export function nodesUrlForAnalysis(analysisId: string | null): string {
  return analysisId
    ? `/api/assurance/nodes?analysis_id=${encodeURIComponent(analysisId)}`
    : '/api/assurance/nodes'
}
