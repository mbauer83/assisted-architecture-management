/**
 * Content-driven questionnaire/spine step definitions (WU-B2c). Wording lives here, not in a
 * component template, so it iterates without code churn — the GQM/KAOS-style goal-elicitation
 * sequence the plan calls for: stakeholder → driver → assessment → goal → outcome → requirement,
 * one question per step, each answer becoming an entity the wizard's existing create/find/
 * suggest machinery (`WizardEntityStage.vue`) handles exactly as it would in free-choice mode.
 *
 * Every question is optional — the questionnaire is a menu of prompts, not a rail: users skip
 * questions or jump between them freely (a requirement without a stakeholder, a process without
 * a role, are all legitimate lightweight models).
 *
 * Two modes serve the two personas: **planning** walks the spine top-down (motivation →
 * business → common → application, "start from why"), **reverse** architecture walks it
 * bottom-up (application → common → business → motivation, "start from what exists"). The same
 * per-domain step content serves both; a step carries a `reverseQuestion` variant only where the
 * planning phrasing would be jarring when documenting an existing system, and each domain
 * carries one bridge per mode. Question wording is grounded in each type's `create_when`
 * guidance (`/api/authoring-guidance`); the behavioural core (role/process/service) lives in the
 * **common** domain in this ontology, not business.
 */
export type WizardMode = 'planning' | 'reverse'

export interface QuestionnaireStep {
  readonly entityType: string
  readonly question: string
  /** Reverse-architecture phrasing; omitted when `question` reads naturally in both modes. */
  readonly reverseQuestion?: string
}

export interface QuestionnaireBridge {
  readonly prompt: string
  readonly nextDomain: string
}

export interface DomainQuestionnaire {
  readonly domain: string
  readonly steps: readonly QuestionnaireStep[]
  /** One hand-off per mode; a mode with no entry makes this domain the spine's terminal. */
  readonly bridges: Partial<Record<WizardMode, QuestionnaireBridge>>
  /** In reverse mode, steps default to "find existing" instead of "create new" — set where the
   * entities usually already exist in the model (e.g. application components imported by the
   * MCP reverse-architecture agent) and the GUI user's job is to anchor on them, not duplicate
   * them. */
  readonly reversePrefersFind?: boolean
}

/** Recommended modeling order per mode — drives the hub's "start here / next" hint. */
export const SPINES: Record<WizardMode, readonly string[]> = {
  planning: ['motivation', 'business', 'common', 'application'],
  reverse: ['application', 'common', 'business', 'motivation'],
}

const QUESTIONNAIRES: readonly DomainQuestionnaire[] = [
  {
    domain: 'motivation',
    steps: [
      { entityType: 'stakeholder', question: 'Who cares about this, and why?' },
      {
        entityType: 'driver',
        question: 'What internal or external force is pushing for change?',
        reverseQuestion: 'What force or need led to this system existing?',
      },
      { entityType: 'assessment', question: 'What specific problem or condition does that force create?' },
      { entityType: 'goal', question: 'What desired state of affairs would resolve it?' },
      { entityType: 'outcome', question: 'How will you know the goal was actually achieved?' },
      {
        entityType: 'requirement',
        question: 'What specific, testable need must be met to get there?',
        reverseQuestion: 'What specific, testable need does the system meet?',
      },
    ],
    bridges: {
      planning: {
        prompt: 'You have a motivation chain from stakeholder to requirement. Now bridge it to '
          + 'impact: who in the business is affected, and what do they work with?',
        nextDomain: 'business',
      },
      // Terminal in reverse mode — the why is captured last.
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
    bridges: {
      planning: {
        prompt: 'You know who is involved and what they handle. Now model how the work actually '
          + 'gets done: the roles, processes, and services live in the common domain.',
        nextDomain: 'common',
      },
      reverse: {
        prompt: 'You know who is involved. Finally, capture why the system exists — drivers, '
          + 'goals, and the requirements it fulfils — so future changes can trace intent.',
        nextDomain: 'motivation',
      },
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
    bridges: {
      planning: {
        prompt: 'The behaviour is modeled. Which applications support or automate it, and what '
          + 'data do they manage?',
        nextDomain: 'application',
      },
      reverse: {
        prompt: 'The behaviour is mapped. Now, who is involved: which organizational entities '
          + 'perform or consume it, and what business things do they handle?',
        nextDomain: 'business',
      },
    },
  },
  {
    domain: 'application',
    steps: [
      {
        entityType: 'application-component',
        question: 'What deployable unit of software supports or automates the process?',
        reverseQuestion: 'Which existing application component (often imported by the '
          + 'reverse-architecture tooling) are you documenting?',
      },
      {
        entityType: 'data-object',
        question: 'What type of data does that application manage or exchange?',
        reverseQuestion: 'What type of data does it manage as its source of truth?',
      },
    ],
    bridges: {
      // Terminal in planning mode.
      reverse: {
        prompt: 'You have anchored on what exists. Now model the behaviour it supports — the '
          + 'services it offers, the processes behind them, and the roles involved — which the '
          + 'tooling cannot infer from code alone.',
        nextDomain: 'common',
      },
    },
    reversePrefersFind: true,
  },
]

export const questionnaireForDomain = (domain: string): DomainQuestionnaire | undefined =>
  QUESTIONNAIRES.find((q) => q.domain === domain)

export const questionForStep = (step: QuestionnaireStep, mode: WizardMode): string =>
  (mode === 'reverse' && step.reverseQuestion) ? step.reverseQuestion : step.question

export const bridgeForMode = (
  questionnaire: DomainQuestionnaire,
  mode: WizardMode,
): QuestionnaireBridge | undefined => questionnaire.bridges[mode]
