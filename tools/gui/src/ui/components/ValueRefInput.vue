<script setup lang="ts">
import { computed } from 'vue'
import type { GroupKind, ValueRef, ValueRefKind } from '../../domain/viewpointCriteria'
import { endpointValue, literalValue, selfValue } from '../../domain/viewpointCriteria'
import { valueKindOptions } from './CriteriaTreeBuilder.helpers'

const props = defineProps<{
  modelValue: ValueRef
  groupKind: GroupKind
  /** Attribute paths to offer when kind is `self`/`source`/`target` — the "reference
   * another attribute" cases; same option list a condition's own attribute picker uses. */
  attributePaths: readonly string[]
  /** Fixed choices for a literal value (e.g. known entity/connection types), or null for
   * a free-text literal input. */
  literalChoices: readonly string[] | null
}>()
const emit = defineEmits<{ 'update:modelValue': [value: ValueRef] }>()

const kindOptions = computed(() => valueKindOptions(props.groupKind))

const onKindChange = (event: Event) => {
  const kind = (event.target as HTMLSelectElement).value as ValueRefKind
  if (kind === 'literal') emit('update:modelValue', literalValue(''))
  else if (kind === 'self') emit('update:modelValue', selfValue(props.attributePaths[0] ?? ''))
  else emit('update:modelValue', endpointValue(kind, props.attributePaths[0] ?? ''))
}

const onReferenceAttributeChange = (event: Event) => {
  const attribute = (event.target as HTMLSelectElement).value
  if (props.modelValue.kind === 'literal') return
  emit('update:modelValue', props.modelValue.kind === 'self' ? selfValue(attribute) : endpointValue(props.modelValue.kind, attribute))
}

const onLiteralChange = (raw: string) => emit('update:modelValue', literalValue(raw))
</script>

<template>
  <span class="value-ref">
    <select
      class="inp val-kind"
      :value="modelValue.kind"
      @change="onKindChange"
    >
      <option
        v-for="option in kindOptions"
        :key="option.kind"
        :value="option.kind"
      >
        {{ option.label }}
      </option>
    </select>

    <select
      v-if="modelValue.kind !== 'literal'"
      class="inp val"
      :value="modelValue.attribute"
      @change="onReferenceAttributeChange"
    >
      <option
        v-for="path in attributePaths"
        :key="path"
        :value="path"
      >
        {{ path }}
      </option>
    </select>

    <select
      v-else-if="literalChoices"
      class="inp val"
      :value="String(modelValue.literal ?? '')"
      @change="onLiteralChange(($event.target as HTMLSelectElement).value)"
    >
      <option
        v-for="choice in literalChoices"
        :key="choice"
        :value="choice"
      >
        {{ choice }}
      </option>
    </select>

    <input
      v-else
      class="inp val"
      type="text"
      :value="String(modelValue.literal ?? '')"
      @input="onLiteralChange(($event.target as HTMLInputElement).value)"
    >
  </span>
</template>

<style scoped>
.value-ref { display: inline-flex; gap: 6px; align-items: center; flex-wrap: wrap; }
.val-kind { max-width: 220px; color: #6b7280; }
.val { min-width: 90px; }
.inp { padding: 4px 6px; border-radius: 5px; border: 1px solid #d1d5db; font-size: 12.5px; font-family: inherit; }
</style>
