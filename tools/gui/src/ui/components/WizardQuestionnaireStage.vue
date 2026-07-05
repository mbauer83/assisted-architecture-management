<script setup lang="ts">
import { ref, computed } from 'vue'
import type { useWizardSession } from '../composables/useWizardSession'
import type { AuthoringGuidance } from '../../domain'
import type { DomainQuestionnaire } from '../lib/wizardQuestionnaires'
import WizardEntityStage from './WizardEntityStage.vue'

const props = defineProps<{
  questionnaire: DomainQuestionnaire
  guidance: AuthoringGuidance | null
  session: ReturnType<typeof useWizardSession>
}>()
const emit = defineEmits<{ exit: [] }>()

const stepIndex = ref(0)

const currentStep = computed(() => props.questionnaire.steps[stepIndex.value])
const isLastStep = computed(() => stepIndex.value === props.questionnaire.steps.length - 1)
const complete = computed(() => stepIndex.value >= props.questionnaire.steps.length)

// Anchors live in the session, not locally: a bridge to the next domain's questionnaire keeps
// the whole cross-domain spine (motivation chain → business actors → …) as ranking context.
const spineAnchors = computed(() => [...props.session.state.spineAnchorIds])

const onStepDone = (entity: { id: string; name: string } | null) => {
  if (!entity) { emit('exit'); return }
  props.session.recordSpineAnchor(entity.id)
  stepIndex.value += 1
}

const restart = () => {
  stepIndex.value = 0
}

const openNextDomain = () => {
  if (!props.questionnaire.bridge) return
  props.session.setActiveDomain(props.questionnaire.bridge.nextDomain)
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

    <template v-if="!complete">
      <p class="progress">
        Question {{ stepIndex + 1 }} of {{ questionnaire.steps.length }}
      </p>
      <h3 class="question">
        {{ currentStep.question }}
      </h3>
      <WizardEntityStage
        :key="currentStep.entityType"
        :entity-type="currentStep.entityType"
        :domain="questionnaire.domain"
        :guidance="guidance"
        :session="session"
        :proximity-anchors="spineAnchors"
        :done-label="isLastStep ? 'Finish questionnaire' : 'Next question →'"
        @done="onStepDone"
      />
    </template>

    <template v-else>
      <h3 class="question">
        Questionnaire complete
      </h3>
      <p class="bridge-prompt">
        {{ questionnaire.bridge?.prompt
          ?? 'The cross-domain spine is complete — motivation through application. Review any '
            + 'deferred connection suggestions below, or pick another domain to go deeper.' }}
      </p>
      <div class="bridge-actions">
        <button
          v-if="questionnaire.bridge"
          type="button"
          class="btn-primary"
          @click="openNextDomain"
        >
          Open {{ questionnaire.bridge.nextDomain }}
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
