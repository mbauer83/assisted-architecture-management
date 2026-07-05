import { describe, it, expect } from 'vitest'
import { questionnaireForDomain, QUESTIONNAIRE_SPINE } from '../wizardQuestionnaires'

describe('questionnaireForDomain', () => {
  it('returns the motivation questionnaire with its full stakeholder-to-requirement sequence', () => {
    const q = questionnaireForDomain('motivation')
    expect(q).toBeDefined()
    expect(q?.steps.map((s) => s.entityType)).toEqual([
      'stakeholder', 'driver', 'assessment', 'goal', 'outcome', 'requirement',
    ])
  })

  it('covers the business who/what pair', () => {
    expect(questionnaireForDomain('business')?.steps.map((s) => s.entityType))
      .toEqual(['business-actor', 'business-object'])
  })

  it('covers the common behavioural core (role, process, service)', () => {
    expect(questionnaireForDomain('common')?.steps.map((s) => s.entityType))
      .toEqual(['role', 'process', 'service'])
  })

  it('covers the application support pair', () => {
    expect(questionnaireForDomain('application')?.steps.map((s) => s.entityType))
      .toEqual(['application-component', 'data-object'])
  })

  it('every spine questionnaire step has a non-empty question', () => {
    for (const domain of QUESTIONNAIRE_SPINE) {
      const q = questionnaireForDomain(domain)
      expect(q, domain).toBeDefined()
      for (const step of q?.steps ?? []) expect(step.question.length).toBeGreaterThan(0)
    }
  })

  it('bridges chain the spine in order, and only the terminal domain has no bridge', () => {
    for (let i = 0; i < QUESTIONNAIRE_SPINE.length; i++) {
      const q = questionnaireForDomain(QUESTIONNAIRE_SPINE[i])
      if (i < QUESTIONNAIRE_SPINE.length - 1) {
        expect(q?.bridge?.nextDomain, QUESTIONNAIRE_SPINE[i]).toBe(QUESTIONNAIRE_SPINE[i + 1])
        expect(q?.bridge?.prompt.length).toBeGreaterThan(0)
      } else {
        expect(q?.bridge, QUESTIONNAIRE_SPINE[i]).toBeUndefined()
      }
    }
  })

  it('returns undefined for a domain with no defined questionnaire', () => {
    expect(questionnaireForDomain('technology')).toBeUndefined()
  })
})
