/**
 * Content-driven questionnaire/spine step definitions (WU-B2c). Wording lives here, not in a
 * component template, so it iterates without code churn — the GQM/KAOS-style goal-elicitation
 * sequence the plan calls for: stakeholder → driver → assessment → goal → outcome → requirement,
 * one question per step, each answer becoming an entity the wizard's existing create/find/
 * suggest machinery (`WizardEntityStage.vue`) handles exactly as it would in free-choice mode.
 *
 * The questionnaires chain into a cross-domain spine (motivation → business → common →
 * application): each bridge hands off to the next domain's questionnaire, and every completed
 * step's entity becomes a session-wide proximity anchor so later domains' connection suggestions
 * rank near the chain built so far. Question wording is grounded in each type's `create_when`
 * guidance (`/api/authoring-guidance`); the behavioural core (role/process/service) lives in the
 * **common** domain in this ontology, not business.
 */
export interface QuestionnaireStep {
  readonly entityType: string
  readonly question: string
}

export interface DomainQuestionnaire {
  readonly domain: string
  readonly steps: readonly QuestionnaireStep[]
  /** Shown after the last step — the "impact mapping" bridge to the next domain in the spine.
   * Absent on the spine's terminal questionnaire. */
  readonly bridge?: {
    readonly prompt: string
    readonly nextDomain: string
  }
}

/** Recommended lightweight modeling order — drives the hub's "start here / next" hint. */
export const QUESTIONNAIRE_SPINE: readonly string[] =
  ['motivation', 'business', 'common', 'application']

const QUESTIONNAIRES: readonly DomainQuestionnaire[] = [
  {
    domain: 'motivation',
    steps: [
      { entityType: 'stakeholder', question: 'Who cares about this, and why?' },
      { entityType: 'driver', question: 'What internal or external force is pushing for change?' },
      { entityType: 'assessment', question: 'What specific problem or condition does that force create?' },
      { entityType: 'goal', question: 'What desired state of affairs would resolve it?' },
      { entityType: 'outcome', question: 'How will you know the goal was actually achieved?' },
      { entityType: 'requirement', question: 'What specific, testable need must be met to get there?' },
    ],
    bridge: {
      prompt: 'You have a motivation chain from stakeholder to requirement. Now bridge it to '
        + 'impact: who in the business is affected, and what do they work with?',
      nextDomain: 'business',
    },
  },
  {
    domain: 'business',
    steps: [
      {
        entityType: 'business-actor',
        question: 'Which organizational entity — department, team, or external organization — '
          + 'does or is affected by this work?',
      },
      {
        entityType: 'business-object',
        question: 'What tangible or intangible business thing does that work use or produce?',
      },
    ],
    bridge: {
      prompt: 'You know who is involved and what they handle. Now model how the work actually '
        + 'gets done: the roles, processes, and services live in the common domain.',
      nextDomain: 'common',
    },
  },
  {
    domain: 'common',
    steps: [
      {
        entityType: 'role',
        question: 'What responsibility or capability — independent of who currently holds it — '
          + 'performs this work?',
      },
      {
        entityType: 'process',
        question: 'What ordered sequence of activities achieves the result?',
      },
      {
        entityType: 'service',
        question: 'What explicit, well-defined behavior does that work offer to its environment?',
      },
    ],
    bridge: {
      prompt: 'The behaviour is modeled. Which applications support or automate it, and what '
        + 'data do they manage?',
      nextDomain: 'application',
    },
  },
  {
    domain: 'application',
    steps: [
      {
        entityType: 'application-component',
        question: 'What deployable unit of software supports or automates the process?',
      },
      {
        entityType: 'data-object',
        question: 'What type of data does that application manage or exchange?',
      },
    ],
    // Terminal spine domain — completion UI offers review-later cleanup instead of a bridge.
  },
]

export const questionnaireForDomain = (domain: string): DomainQuestionnaire | undefined =>
  QUESTIONNAIRES.find((q) => q.domain === domain)
