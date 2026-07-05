<script setup lang="ts">
import { ref, computed } from 'vue'
import type { useWizardSession } from '../composables/useWizardSession'
import type { AuthoringGuidance } from '../../domain'
import { questionForStep, bridgeForMode, type DomainQuestionnaire } from '../lib/wizardQuestionnaires'
import WizardEntityStage from './WizardEntityStage.vue'

/**
 * A questionnaire is a menu of prompts, not a rail: every question is skippable and the step
 * chips jump anywhere, so "a requirement without a stakeholder" or "a process without a role"
 * are one click away. Only answered steps feed the spine's proximity anchors.
 */
const props = defineProps<{
  questionnaire: DomainQuestionnaire
  guidance: AuthoringGuidance | null
  session: ReturnType<typeof useWizardSession>
}>()
const emit = defineEmits<{ exit: [] }>()

const stepIndex = ref(0)
const answered = ref<Set<number>>(new Set())

const mode = computed(() => props.session.state.mode)
const currentStep = computed(() => props.questionnaire.steps[stepIndex.value])
const currentQuestion = computed(() =>
  currentStep.value ? questionForStep(currentStep.value, mode.value) : '')
const isLastStep = computed(() => stepIndex.value === props.questionnaire.steps.length - 1)
const complete = computed(() => stepIndex.value >= props.questionnaire.steps.length)
const bridge = computed(() => bridgeForMode(props.questionnaire, mode.value))
const preferFind = computed(() =>
  mode.value === 'reverse' && props.questionnaire.reversePrefersFind === true)

// Anchors live in the session, not locally: a bridge to the next domain's questionnaire keeps
// the whole cross-domain spine (motivation chain → business actors → …) as ranking context.
const spineAnchors = computed(() => [...props.session.state.spineAnchorIds])

const onStepDone = (entity: { id: string; name: string } | null) => {
  if (!entity) { emit('exit'); return }
  props.session.recordSpineAnchor(entity.id)
  answered.value.add(stepIndex.value)
  stepIndex.value += 1
}

const skipStep = () => { stepIndex.value += 1 }
const jumpTo = (index: number) => { stepIndex.value = index }

const restart = () => {
  stepIndex.value = 0
  answered.value = new Set()
}

const openNextDomain = () => {
  if (!bridge.value) return
  props.session.setActiveDomain(bridge.value.nextDomain)
  emit('exit')
}
</script>

<template>
  <div class="questionnaire">
    <button
      type="button"
      class="btn-link"
      @click="emit('exit')"
    >
      ← Exit questionnaire
    </button>

    <div class="step-chips">
      <button
        v-for="(step, index) in questionnaire.steps"
        :key="step.entityType"
        type="button"
        class="step-chip"
        :class="{
          'step-chip--active': index === stepIndex,
          'step-chip--answered': answered.has(index),
        }"
        @click="jumpTo(index)"
      >
        {{ answered.has(index) ? '✓' : index + 1 }} {{ step.entityType }}
      </button>
    </div>

    <template v-if="!complete">
      <p class="progress">
        Question {{ stepIndex + 1 }} of {{ questionnaire.steps.length }} — answer any, in any order
      </p>
      <h3 class="question">
        {{ currentQuestion }}
      </h3>
      <button
        type="button"
        class="btn-link"
        @click="skipStep"
      >
        Skip — I don't need a {{ currentStep.entityType }} here →
      </button>
      <WizardEntityStage
        :key="currentStep.entityType"
        :entity-type="currentStep.entityType"
        :domain="questionnaire.domain"
        :guidance="guidance"
        :session="session"
        :proximity-anchors="spineAnchors"
        :prefer-find="preferFind"
        :done-label="isLastStep ? 'Finish questionnaire' : 'Next question →'"
        @done="onStepDone"
      />
    </template>

    <template v-else>
      <h3 class="question">
        Questionnaire complete
      </h3>
      <p class="bridge-prompt">
        {{ bridge?.prompt
          ?? 'The cross-domain spine is complete. Review any deferred connection suggestions '
            + 'below, or pick another domain to go deeper.' }}
      </p>
      <div class="bridge-actions">
        <button
          v-if="bridge"
          type="button"
          class="btn-primary"
          @click="openNextDomain"
        >
          Open {{ bridge.nextDomain }}
        </button>
        <button
          type="button"
          class="btn-link"
          @click="restart"
        >
          Start over
        </button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.questionnaire { display: flex; flex-direction: column; gap: 12px; }
.step-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.step-chip {
  padding: 3px 10px; border-radius: 12px; border: 1px solid #d1d5db; background: #fff;
  font-size: 12px; color: #4b5563; cursor: pointer;
}
.step-chip--active { border-color: #2563eb; color: #1d4ed8; background: #eff6ff; font-weight: 600; }
.step-chip--answered { border-color: #86efac; background: #f0fdf4; color: #15803d; }
.progress { font-size: 12px; color: #6b7280; margin: 0; text-transform: uppercase; letter-spacing: .04em; }
.question { font-size: 16px; font-weight: 600; margin: 0; color: #1f2937; }
.bridge-prompt { font-size: 13px; color: #374151; line-height: 1.5; }
.bridge-actions { display: flex; align-items: center; gap: 12px; }
.btn-primary {
  padding: 7px 16px; border-radius: 6px; border: none; background: #2563eb; color: #fff;
  font-size: 13px; font-weight: 600; cursor: pointer;
}
.btn-link { align-self: flex-start; background: none; border: none; color: #2563eb; cursor: pointer; padding: 0; font-size: 12px; text-decoration: underline; }
</style>
