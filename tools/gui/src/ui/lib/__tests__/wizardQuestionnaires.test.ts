import { describe, it, expect } from 'vitest'
import {
  questionnaireForDomain,
  questionForStep,
  bridgeForMode,
  SPINES,
  type WizardMode,
} from '../wizardQuestionnaires'

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

  it('every spine questionnaire step has a non-empty question in both modes', () => {
    for (const mode of ['planning', 'reverse'] as const) {
      for (const domain of SPINES[mode]) {
        const q = questionnaireForDomain(domain)
        expect(q, domain).toBeDefined()
        for (const step of q?.steps ?? []) {
          expect(questionForStep(step, mode).length, `${domain}/${step.entityType}/${mode}`)
            .toBeGreaterThan(0)
        }
      }
    }
  })

  it('returns undefined for a domain with no defined questionnaire', () => {
    expect(questionnaireForDomain('technology')).toBeUndefined()
  })
})

describe('SPINES and bridges', () => {
  it('reverse spine is the planning spine reversed', () => {
    expect([...SPINES.reverse]).toEqual([...SPINES.planning].reverse())
  })

  const chainCase = (mode: WizardMode) => {
    const spine = SPINES[mode]
    for (let i = 0; i < spine.length; i++) {
      const q = questionnaireForDomain(spine[i])
      expect(q, spine[i]).toBeDefined()
      const bridge = q ? bridgeForMode(q, mode) : undefined
      if (i < spine.length - 1) {
        expect(bridge?.nextDomain, `${spine[i]}/${mode}`).toBe(spine[i + 1])
        expect(bridge?.prompt.length).toBeGreaterThan(0)
      } else {
        expect(bridge, `${spine[i]}/${mode} should be terminal`).toBeUndefined()
      }
    }
  }

  it('planning bridges chain the spine in order; application is terminal', () => {
    chainCase('planning')
  })

  it('reverse bridges chain the reversed spine; motivation is terminal', () => {
    chainCase('reverse')
  })
})

describe('questionForStep', () => {
  it('uses the reverse variant when defined and mode is reverse', () => {
    const step = questionnaireForDomain('application')!.steps[0]
    expect(questionForStep(step, 'reverse')).toContain('existing application component')
    expect(questionForStep(step, 'planning')).not.toContain('existing application component')
  })

  it('falls back to the planning question when no reverse variant exists', () => {
    const step = questionnaireForDomain('motivation')!.steps[0]
    expect(questionForStep(step, 'reverse')).toBe(step.question)
  })
})

describe('reversePrefersFind', () => {
  it('is set on application (agent-imported entities: anchor, do not duplicate) and unset elsewhere', () => {
    expect(questionnaireForDomain('application')?.reversePrefersFind).toBe(true)
    for (const domain of ['motivation', 'business', 'common']) {
      expect(questionnaireForDomain(domain)?.reversePrefersFind, domain).toBeUndefined()
    }
  })
})
