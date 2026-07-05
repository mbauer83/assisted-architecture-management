<script setup lang="ts">
import { inject, onMounted, computed } from 'vue'
import { modelServiceKey } from '../keys'
import { useQuery } from '../composables/useQuery'
import { useWizardSession, createdCountByDomain } from '../composables/useWizardSession'
import { buildWizardDomainCards, entityTypesForDomain } from './ModelWizardView.helpers'
import type { AuthoringGuidance } from '../../domain'
import type { RepoError } from '../../ports/ModelRepository'

const svc = inject(modelServiceKey)!
const session = useWizardSession()
const guidanceQuery = useQuery<AuthoringGuidance, RepoError>()

const domainCards = computed(() => buildWizardDomainCards(createdCountByDomain(session.state)))
const activeDomain = computed(() => session.state.activeDomain)
const activeEntityTypes = computed(() => entityTypesForDomain(guidanceQuery.data.value, activeDomain.value ?? ''))
const hasProgress = computed(() =>
  session.state.createdEntities.length > 0 || session.state.reviewLaterQueue.length > 0)

const openDomain = (domain: string) => {
  session.setActiveDomain(domain)
  guidanceQuery.run(svc.getAuthoringGuidance({ domains: [domain] }))
}

const startOver = () => {
  session.reset()
  guidanceQuery.reset()
}

onMounted(() => {
  if (session.state.activeDomain) openDomain(session.state.activeDomain)
})
</script>

<template>
  <div class="wizard-view">
    <div class="wizard-header">
      <h1 class="page-title">
        Guided Modeling Wizard
      </h1>
      <p class="wizard-subtitle">
        Pick a domain to see what belongs there and why. Skip freely between domains — nothing
        here is gated.
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
      <ul
        v-else
        class="entity-type-list"
      >
        <li
          v-for="entityType in activeEntityTypes"
          :key="entityType.name"
          class="entity-type-item"
        >
          <span class="entity-type-name">{{ entityType.name }}</span>
          <p
            v-if="entityType.create_when"
            class="entity-type-hint"
          >
            Create when: {{ entityType.create_when }}
          </p>
          <p
            v-if="entityType.never_create_when"
            class="entity-type-hint entity-type-hint--never"
          >
            Never create when: {{ entityType.never_create_when }}
          </p>
        </li>
      </ul>
    </div>

    <div
      v-if="session.state.reviewLaterQueue.length"
      class="review-later"
    >
      <h2 class="domain-panel__title">
        Review later
      </h2>
      <ul class="entity-type-list">
        <li
          v-for="suggestion in session.state.reviewLaterQueue"
          :key="suggestion.id"
          class="entity-type-item"
        >
          <span>{{ suggestion.summary }}</span>
          <button
            type="button"
            class="btn-link"
            @click="session.resolveReviewLater(suggestion.id)"
          >
            Resolved
          </button>
        </li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
.page-title { font-size: 22px; font-weight: 600; margin-bottom: 4px; }
.wizard-header { margin-bottom: 20px; }
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
.domain-card__count { font-size: 12px; color: #6b7280; }

.domain-panel, .review-later {
  border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px 20px; margin-bottom: 20px;
}
.domain-panel__title { font-size: 16px; font-weight: 600; margin: 0 0 12px; }
.entity-type-list { list-style: none; margin: 0; padding: 0; }
.entity-type-item { padding: 8px 0; border-top: 1px solid #f3f4f6; }
.entity-type-item:first-child { border-top: none; }
.entity-type-name { font-weight: 600; }
.entity-type-hint { margin: 2px 0 0; color: #4b5563; font-size: 13px; }
.entity-type-hint--never { color: #b45309; }
</style>
