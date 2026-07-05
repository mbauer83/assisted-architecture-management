import { reactive, watch } from 'vue'

export interface WizardCreatedEntity {
  readonly artifactId: string
  readonly artifactType: string
  readonly domain: string
  readonly name: string
}

export interface WizardSuggestion {
  readonly id: string
  readonly domain: string
  readonly summary: string
}

export interface WizardSessionState {
  activeDomain: string | null
  createdEntities: WizardCreatedEntity[]
  pendingSuggestions: WizardSuggestion[]
  reviewLaterQueue: WizardSuggestion[]
}

export interface WizardStorage {
  getItem(key: string): string | null
  setItem(key: string, value: string): void
  removeItem(key: string): void
}

export const WIZARD_SESSION_STORAGE_KEY = 'arch.model-wizard.session.v1'

export const initialWizardSessionState = (): WizardSessionState => ({
  activeDomain: null,
  createdEntities: [],
  pendingSuggestions: [],
  reviewLaterQueue: [],
})

export const parseWizardSessionState = (raw: string | null): WizardSessionState => {
  if (!raw) return initialWizardSessionState()
  try {
    const parsed = JSON.parse(raw) as Partial<WizardSessionState>
    return {
      activeDomain: typeof parsed.activeDomain === 'string' ? parsed.activeDomain : null,
      createdEntities: Array.isArray(parsed.createdEntities) ? parsed.createdEntities : [],
      pendingSuggestions: Array.isArray(parsed.pendingSuggestions) ? parsed.pendingSuggestions : [],
      reviewLaterQueue: Array.isArray(parsed.reviewLaterQueue) ? parsed.reviewLaterQueue : [],
    }
  } catch {
    return initialWizardSessionState()
  }
}

export const createdCountByDomain = (state: WizardSessionState): Record<string, number> => {
  const counts: Record<string, number> = {}
  for (const entity of state.createdEntities) counts[entity.domain] = (counts[entity.domain] ?? 0) + 1
  return counts
}

/**
 * Reactive wizard draft store (created ids, pending suggestions, review-later queue),
 * persisted to `storage` so a reload resumes the same in-progress session.
 */
export const useWizardSession = (storage: WizardStorage = window.sessionStorage) => {
  const state = reactive<WizardSessionState>(parseWizardSessionState(storage.getItem(WIZARD_SESSION_STORAGE_KEY)))

  watch(
    state,
    (next) => storage.setItem(WIZARD_SESSION_STORAGE_KEY, JSON.stringify(next)),
    { deep: true, flush: 'sync' },
  )

  const setActiveDomain = (domain: string | null) => { state.activeDomain = domain }

  const recordCreated = (entity: WizardCreatedEntity) => {
    if (state.createdEntities.some((e) => e.artifactId === entity.artifactId)) return
    state.createdEntities.push(entity)
  }

  const undoCreated = (artifactId: string) => {
    state.createdEntities = state.createdEntities.filter((e) => e.artifactId !== artifactId)
  }

  const queueSuggestion = (suggestion: WizardSuggestion) => {
    if (state.pendingSuggestions.some((s) => s.id === suggestion.id)) return
    state.pendingSuggestions.push(suggestion)
  }

  const dismissSuggestion = (id: string) => {
    state.pendingSuggestions = state.pendingSuggestions.filter((s) => s.id !== id)
  }

  const deferToReviewLater = (id: string) => {
    const suggestion = state.pendingSuggestions.find((s) => s.id === id)
    if (!suggestion) return
    state.pendingSuggestions = state.pendingSuggestions.filter((s) => s.id !== id)
    if (!state.reviewLaterQueue.some((s) => s.id === id)) state.reviewLaterQueue.push(suggestion)
  }

  const resolveReviewLater = (id: string) => {
    state.reviewLaterQueue = state.reviewLaterQueue.filter((s) => s.id !== id)
  }

  const reset = () => {
    Object.assign(state, initialWizardSessionState())
    storage.removeItem(WIZARD_SESSION_STORAGE_KEY)
  }

  return {
    state,
    setActiveDomain,
    recordCreated,
    undoCreated,
    queueSuggestion,
    dismissSuggestion,
    deferToReviewLater,
    resolveReviewLater,
    reset,
  }
}
