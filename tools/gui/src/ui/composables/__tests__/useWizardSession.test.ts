/**
 * Tests for useWizardSession: reactive draft store (created ids, pending suggestions,
 * review-later queue) persisted to an injected storage, so a fresh call with the same
 * storage resumes the prior session.
 *
 * Runs without Vue component mounting (no DOM) — the composable itself has no
 * `inject()` dependency, only Vue's reactivity system, so it is exercised directly.
 */
import { describe, it, expect } from 'vitest'
import {
  useWizardSession,
  initialWizardSessionState,
  parseWizardSessionState,
  createdCountByDomain,
  WIZARD_SESSION_STORAGE_KEY,
  type WizardStorage,
} from '../useWizardSession'

const fakeStorage = (): WizardStorage => {
  const map = new Map<string, string>()
  return {
    getItem: (key) => map.get(key) ?? null,
    setItem: (key, value) => { map.set(key, value) },
    removeItem: (key) => { map.delete(key) },
  }
}

describe('parseWizardSessionState', () => {
  it('returns the initial state for null input', () => {
    expect(parseWizardSessionState(null)).toEqual(initialWizardSessionState())
  })

  it('returns the initial state for malformed JSON', () => {
    expect(parseWizardSessionState('{not json')).toEqual(initialWizardSessionState())
  })

  it('falls back to empty arrays for a partial/corrupt shape', () => {
    const result = parseWizardSessionState(JSON.stringify({ activeDomain: 'motivation' }))
    expect(result).toEqual({
      activeDomain: 'motivation',
      createdEntities: [],
      pendingSuggestions: [],
      reviewLaterQueue: [],
    })
  })
})

describe('createdCountByDomain', () => {
  it('counts created entities per domain', () => {
    const state = {
      ...initialWizardSessionState(),
      createdEntities: [
        { artifactId: 'a', artifactType: 'goal', domain: 'motivation', name: 'A' },
        { artifactId: 'b', artifactType: 'requirement', domain: 'motivation', name: 'B' },
        { artifactId: 'c', artifactType: 'business-process', domain: 'business', name: 'C' },
      ],
    }
    expect(createdCountByDomain(state)).toEqual({ motivation: 2, business: 1 })
  })
})

describe('useWizardSession', () => {
  it('starts from the initial state when storage is empty', () => {
    const session = useWizardSession(fakeStorage())
    expect(session.state).toEqual(initialWizardSessionState())
  })

  it('resumes a prior session from storage', () => {
    const storage = fakeStorage()
    storage.setItem(WIZARD_SESSION_STORAGE_KEY, JSON.stringify({
      activeDomain: 'business',
      createdEntities: [{ artifactId: 'x', artifactType: 'goal', domain: 'motivation', name: 'X' }],
      pendingSuggestions: [],
      reviewLaterQueue: [],
    }))
    const session = useWizardSession(storage)
    expect(session.state.activeDomain).toBe('business')
    expect(session.state.createdEntities).toHaveLength(1)
  })

  it('persists activeDomain changes to storage', () => {
    const storage = fakeStorage()
    const session = useWizardSession(storage)
    session.setActiveDomain('application')
    const persisted = parseWizardSessionState(storage.getItem(WIZARD_SESSION_STORAGE_KEY))
    expect(persisted.activeDomain).toBe('application')
  })

  it('recordCreated adds an entity once and ignores duplicates', () => {
    const session = useWizardSession(fakeStorage())
    const entity = { artifactId: 'GOL@1.a.x', artifactType: 'goal', domain: 'motivation', name: 'X' }
    session.recordCreated(entity)
    session.recordCreated(entity)
    expect(session.state.createdEntities).toHaveLength(1)
  })

  it('undoCreated removes a previously recorded entity', () => {
    const session = useWizardSession(fakeStorage())
    session.recordCreated({ artifactId: 'a', artifactType: 'goal', domain: 'motivation', name: 'A' })
    session.undoCreated('a')
    expect(session.state.createdEntities).toHaveLength(0)
  })

  it('queueSuggestion, deferToReviewLater, and resolveReviewLater move a suggestion through its lifecycle', () => {
    const session = useWizardSession(fakeStorage())
    const suggestion = { id: 's1', domain: 'motivation', summary: 'X probably serves Y' }
    session.queueSuggestion(suggestion)
    expect(session.state.pendingSuggestions).toHaveLength(1)

    session.deferToReviewLater('s1')
    expect(session.state.pendingSuggestions).toHaveLength(0)
    expect(session.state.reviewLaterQueue).toHaveLength(1)

    session.resolveReviewLater('s1')
    expect(session.state.reviewLaterQueue).toHaveLength(0)
  })

  it('dismissSuggestion drops a pending suggestion without queuing it for review', () => {
    const session = useWizardSession(fakeStorage())
    session.queueSuggestion({ id: 's1', domain: 'motivation', summary: 'X probably serves Y' })
    session.dismissSuggestion('s1')
    expect(session.state.pendingSuggestions).toHaveLength(0)
    expect(session.state.reviewLaterQueue).toHaveLength(0)
  })

  it('reset clears in-memory state and storage', () => {
    const storage = fakeStorage()
    const session = useWizardSession(storage)
    session.recordCreated({ artifactId: 'a', artifactType: 'goal', domain: 'motivation', name: 'A' })
    session.setActiveDomain('motivation')

    session.reset()

    expect(session.state).toEqual(initialWizardSessionState())
    expect(storage.getItem(WIZARD_SESSION_STORAGE_KEY)).toBeNull()
  })
})
