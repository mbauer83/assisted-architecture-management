<script setup lang="ts">
import { inject, watch, computed } from 'vue'
import { modelServiceKey } from '../keys'
import { useQuery } from '../composables/useQuery'
import { useWizardSession, createdCountByDomain } from '../composables/useWizardSession'
import { useSuggestionCommit } from '../composables/useSuggestionCommit'
import { buildWizardDomainCards } from './ModelWizardView.helpers'
import WizardDomainStage from '../components/WizardDomainStage.vue'
import WizardConnectionSuggestions from '../components/WizardConnectionSuggestions.vue'
import { SPINES, type WizardMode } from '../lib/wizardQuestionnaires'
import { getDomainLabel } from '../lib/domains'
import type { AuthoringGuidance } from '../../domain'
import type { RepoError } from '../../ports/ModelRepository'

const svc = inject(modelServiceKey)!
const session = useWizardSession()
const guidanceQuery = useQuery<AuthoringGuidance, RepoError>()
const reviewLaterCommit = useSuggestionCommit(session)

const mode = computed(() => session.state.mode)
const setMode = (m: WizardMode) => session.setMode(m)
const spineLabel = computed(() => SPINES[mode.value].map(getDomainLabel).join(' → '))

const domainCards = computed(() =>
  buildWizardDomainCards(createdCountByDomain(session.state), mode.value))
const activeDomain = computed(() => session.state.activeDomain)
const hasProgress = computed(() =>
  session.state.createdEntities.length > 0 || session.state.reviewLaterQueue.length > 0)

const openDomain = (domain: string) => session.setActiveDomain(domain)

const startOver = () => {
  session.reset()
  guidanceQuery.reset()
}

const acceptReviewLater = (suggestion: (typeof session.state.reviewLaterQueue)[number]) =>
  reviewLaterCommit.accept(suggestion, (id) => session.resolveReviewLater(id))
const dismissReviewLater = (id: string) => session.resolveReviewLater(id)

// Any activeDomain change — a direct click, resuming a session on mount, or a questionnaire's
// bridge step switching domains — refetches guidance for it. Single source of truth instead of
// duplicating the fetch at every call site that can change the active domain.
watch(activeDomain, (domain) => {
  if (domain) guidanceQuery.run(svc.getAuthoringGuidance({ domains: [domain] }))
}, { immediate: true })
</script>

<template>
  <div class="wizard-view">
    <div class="wizard-header">
      <h1 class="page-title">
        Guided Modeling Wizard
      </h1>
      <div
        class="mode-toggle"
        role="group"
        aria-label="Wizard mode"
      >
        <button
          type="button"
          class="mode-btn"
          :class="{ 'mode-btn--active': mode === 'planning' }"
          @click="setMode('planning')"
        >
          Planning — start from why
        </button>
        <button
          type="button"
          class="mode-btn"
          :class="{ 'mode-btn--active': mode === 'reverse' }"
          @click="setMode('reverse')"
        >
          Reverse architecture — start from what exists
        </button>
      </div>
      <p class="wizard-subtitle">
        Pick a domain to see what belongs there and why. For a lightweight end-to-end model,
        follow the guided spine: {{ spineLabel }}. Skip freely between domains and questions —
        nothing here is gated.
      </p>
      <button
        v-if="hasProgress"
        type="button"
        class="btn-link"
        @click="startOver"
      >
        Start over
      </button>
    </div>

    <div class="domain-hub">
      <button
        v-for="card in domainCards"
        :key="card.key"
        type="button"
        class="domain-card"
        :class="{ 'domain-card--active': card.key === activeDomain }"
        :style="{ borderLeftColor: card.color }"
        @click="openDomain(card.key)"
      >
        <span class="domain-card__label">{{ card.label }}</span>
        <span
          v-if="card.recommended"
          class="domain-card__badge"
        >{{ hasProgress ? 'Next' : 'Start here' }}</span>
        <span
          v-if="card.createdCount > 0"
          class="domain-card__count"
        >{{ card.createdCount }} created</span>
      </button>
    </div>

    <div
      v-if="activeDomain"
      class="domain-panel"
    >
      <h2 class="domain-panel__title">
        {{ domainCards.find(c => c.key === activeDomain)?.label }}
      </h2>

      <div
        v-if="guidanceQuery.loading.value"
        class="state-msg"
      >
        Loading guidance…
      </div>
      <div
        v-else-if="guidanceQuery.errorMessage.value"
        class="state-msg state-msg--error"
      >
        {{ guidanceQuery.errorMessage.value }}
      </div>
      <WizardDomainStage
        v-else
        :key="activeDomain"
        :domain="activeDomain"
        :guidance="guidanceQuery.data.value"
        :session="session"
      />
    </div>

    <div
      v-if="session.state.reviewLaterQueue.length"
      class="review-later"
    >
      <h2 class="domain-panel__title">
        Review later
      </h2>
      <div
        v-if="reviewLaterCommit.error.value"
        class="state-msg state-msg--error"
      >
        {{ reviewLaterCommit.error.value }}
      </div>
      <WizardConnectionSuggestions
        :suggestions="session.state.reviewLaterQueue"
        :busy="reviewLaterCommit.busy.value"
        hide-later
        @accept="acceptReviewLater"
        @dismiss="dismissReviewLater"
      />
    </div>
  </div>
</template>

<style scoped>
.page-title { font-size: 22px; font-weight: 600; margin-bottom: 4px; }
.wizard-header { margin-bottom: 20px; }
.mode-toggle { display: flex; gap: 8px; margin: 6px 0 10px; }
.mode-btn {
  padding: 6px 14px; border-radius: 6px; border: 1px solid #d1d5db; background: #fff;
  font-size: 13px; cursor: pointer; color: #374151;
}
.mode-btn--active { background: #2563eb; color: #fff; border-color: #2563eb; }
.wizard-subtitle { color: #6b7280; margin: 0 0 8px; }
.btn-link {
  background: none; border: none; color: #2563eb; cursor: pointer; padding: 0;
  font-size: 13px; text-decoration: underline;
}
.state-msg { color: #6b7280; padding: 8px 0; }
.state-msg--error { color: #dc2626; }

.domain-hub {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 12px;
  margin-bottom: 24px;
}
.domain-card {
  display: flex; flex-direction: column; gap: 4px;
  padding: 14px 16px; border: 1px solid #e5e7eb; border-left: 4px solid transparent;
  border-radius: 8px; background: #fff; cursor: pointer; text-align: left;
}
.domain-card:hover { box-shadow: 0 2px 8px rgba(0, 0, 0, .08); }
.domain-card--active { outline: 2px solid #2563eb; outline-offset: -1px; }
.domain-card__label { font-weight: 600; }
.domain-card__badge {
  align-self: flex-start; font-size: 11px; font-weight: 600; color: #1d4ed8;
  background: #dbeafe; border-radius: 10px; padding: 1px 8px;
}
.domain-card__count { font-size: 12px; color: #6b7280; }

.domain-panel, .review-later {
  border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px 20px; margin-bottom: 20px;
}
.domain-panel__title { font-size: 16px; font-weight: 600; margin: 0 0 12px; }
</style>
