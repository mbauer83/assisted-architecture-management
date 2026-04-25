<script setup lang="ts">
import type { PromotionPlan } from '../../domain'
import type { ConflictStrategy } from '../composables/promotionShared'

const props = defineProps<{
  loading: boolean
  errorMessage: string
  plan: PromotionPlan | null
  strategies: Record<string, ConflictStrategy>
  unresolvedCount: number
}>()

const emit = defineEmits<{
  setStrategy: [artifactId: string, strategy: ConflictStrategy]
}>()

const strategyOptions = [
  { value: 'accept_enterprise', label: 'Keep global version' },
  { value: 'accept_engagement', label: 'Replace with selected version' },
] as const

const updateStrategy = (artifactId: string, event: Event) => {
  emit('setStrategy', artifactId, (event.target as HTMLInputElement).value as ConflictStrategy)
}
</script>

<template>
  <div class="card step-card">
    <h2 class="card-title">
      Plan Summary
    </h2>

    <div
      v-if="loading"
      class="state-msg"
    >
      Refreshing plan…
    </div>
    <p
      v-if="errorMessage"
      class="error-msg"
    >
      {{ errorMessage }}
    </p>

    <template v-if="props.plan">
      <div
        v-if="props.plan.warnings.length"
        class="warnings-box"
      >
        <div
          v-for="warning in props.plan.warnings"
          :key="warning"
          class="warn-item"
        >
          {{ warning }}
        </div>
      </div>

      <div
        v-if="props.plan.schema_errors.length"
        class="errors-box"
      >
        <div
          v-for="error in props.plan.schema_errors"
          :key="error"
          class="error-item"
        >
          {{ error }}
        </div>
      </div>

      <section
        v-if="props.plan.already_in_enterprise.length"
        class="section"
      >
        <h3 class="section-title">
          Already in global repository
        </h3>
        <ul class="id-list id-list--muted">
          <li
            v-for="artifactId in props.plan.already_in_enterprise"
            :key="artifactId"
            class="mono"
          >
            {{ artifactId }}
          </li>
        </ul>
      </section>

      <section
        v-for="entry in [
          { title: 'New entities to promote', items: props.plan.entities_to_add },
          { title: 'New documents to promote', items: props.plan.documents_to_add },
          { title: 'New diagrams to promote', items: props.plan.diagrams_to_add },
          { title: 'Selected connections', items: props.plan.connection_ids },
        ]"
        v-show="entry.items.length"
        :key="entry.title"
        class="section"
      >
        <h3 class="section-title">
          {{ entry.title }}
        </h3>
        <ul class="id-list">
          <li
            v-for="artifactId in entry.items"
            :key="artifactId"
            class="mono"
          >
            {{ artifactId }}
          </li>
        </ul>
      </section>

      <section
        v-for="group in [
          {
            title: 'Entity conflicts',
            conflicts: props.plan.conflicts.map((conflict) => ({
              id: conflict.engagement_id,
              heading: `${conflict.engagement_id} vs global ${conflict.enterprise_id}`,
              meta: '',
            })),
          },
          {
            title: 'Document conflicts',
            conflicts: props.plan.doc_conflicts.map((conflict) => ({
              id: conflict.engagement_id,
              heading: `${conflict.engagement_title} vs global ${conflict.enterprise_title}`,
              meta: `${conflict.engagement_id} → ${conflict.enterprise_id}`,
            })),
          },
          {
            title: 'Diagram conflicts',
            conflicts: props.plan.diagram_conflicts.map((conflict) => ({
              id: conflict.engagement_id,
              heading: `${conflict.engagement_name} vs global ${conflict.enterprise_name}`,
              meta: `${conflict.engagement_id} → ${conflict.enterprise_id}`,
            })),
          },
        ]"
        v-show="group.conflicts.length"
        :key="group.title"
        class="section"
      >
        <h3 class="section-title section-title--warn">
          {{ group.title }}
        </h3>
        <div
          v-for="conflict in group.conflicts"
          :key="conflict.id"
          class="conflict-card"
        >
          <div class="conflict-header">
            {{ conflict.heading }}
          </div>
          <div
            v-if="conflict.meta"
            class="conflict-meta mono"
          >
            {{ conflict.meta }}
          </div>
          <div class="conflict-strategies">
            <label
              v-for="option in strategyOptions"
              :key="option.value"
              class="strategy-opt"
            >
              <input
                :checked="props.strategies[conflict.id] === option.value"
                type="radio"
                :name="`conflict-${conflict.id}`"
                :value="option.value"
                @change="updateStrategy(conflict.id, $event)"
              >
              {{ option.label }}
            </label>
          </div>
        </div>
      </section>

      <div
        v-if="props.unresolvedCount"
        class="warn-banner"
      >
        {{ props.unresolvedCount }} conflict{{ props.unresolvedCount > 1 ? 's' : '' }}
        still need{{ props.unresolvedCount === 1 ? 's' : '' }} a resolution strategy.
      </div>
    </template>
  </div>
</template>

<style scoped>
.card { background: white; border-radius: 8px; border: 1px solid #e5e7eb; padding: 20px 24px; margin-bottom: 16px; }
.card-title { font-size: 16px; font-weight: 600; color: #111827; margin-bottom: 10px; }
.section { margin-top: 18px; }
.section-title { font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: .05em; color: #374151; margin-bottom: 8px; }
.section-title--warn { color: #b45309; }
.warnings-box { background: #fffbeb; border: 1px solid #fde68a; border-radius: 6px; padding: 10px 14px; margin-bottom: 14px; }
.errors-box { background: #fff7f7; border: 1px solid #fecaca; border-radius: 6px; padding: 10px 14px; margin-bottom: 14px; }
.warn-item { font-size: 13px; color: #92400e; }
.error-item { font-size: 13px; color: #b91c1c; }
.id-list { list-style: none; display: flex; flex-direction: column; gap: 3px; }
.id-list--muted .mono { color: #9ca3af; }
.conflict-card { border: 1px solid #fde68a; border-radius: 6px; padding: 10px 14px; margin-bottom: 8px; background: #fffbeb; }
.conflict-header { margin-bottom: 6px; color: #111827; }
.conflict-meta { font-size: 11px; color: #6b7280; margin-bottom: 8px; }
.conflict-strategies { display: flex; gap: 16px; flex-wrap: wrap; }
.strategy-opt { display: flex; align-items: center; gap: 6px; font-size: 13px; cursor: pointer; }
.strategy-opt input[type=radio] { accent-color: #2563eb; }
.warn-banner {
  margin-top: 14px; padding: 10px 14px; background: #fef3c7; border: 1px solid #fde68a;
  border-radius: 6px; font-size: 13px; color: #92400e; font-weight: 500;
}
.state-msg { font-size: 13px; color: #6b7280; }
.error-msg { margin-top: 12px; color: #dc2626; font-size: 13px; white-space: pre-wrap; }
.mono { font-family: monospace; font-size: 12px; }
</style>
