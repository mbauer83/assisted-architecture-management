<script setup lang="ts">
import { computed, inject, ref } from 'vue'
import type { CriteriaCatalog } from '../../domain'
import type { Comparator, ConditionNode, GroupKind, ValueRef } from '../../domain/viewpointCriteria'
import { literalValue } from '../../domain/viewpointCriteria'
import { HIGHLIGHTED_NODE_ID_KEY, attributeOptions, comparatorsFor, enumChoicesFor } from './CriteriaTreeBuilder.helpers'
import ValueRefInput from './ValueRefInput.vue'

const props = defineProps<{
  modelValue: ConditionNode
  groupKind: GroupKind
  catalog: CriteriaCatalog
}>()
const emit = defineEmits<{ 'update:modelValue': [value: ConditionNode]; remove: [] }>()

const highlightedNodeId = inject(HIGHLIGHTED_NODE_ID_KEY, ref(null))

const attributes = computed(() => attributeOptions(props.groupKind, props.catalog))
const attributePaths = computed(() => attributes.value.map((a) => a.path))
const currentAttribute = computed(
  () => attributes.value.find((a) => a.path === props.modelValue.attribute) ?? attributes.value[0],
)
const comparatorChoices = computed(() => comparatorsFor(currentAttribute.value))
const literalChoices = computed(() => enumChoicesFor(props.modelValue.attribute, props.groupKind, props.catalog))
const valueTakesNoInput = computed(() => props.modelValue.comparator === 'exists' || props.modelValue.comparator === 'absent')
const valueTakesList = computed(() => props.modelValue.comparator === 'in')
const listValueText = computed(() => {
  const value = props.modelValue.value
  return value.kind === 'literal' && Array.isArray(value.literal) ? value.literal.join(', ') : ''
})

const update = (patch: Partial<ConditionNode>) => emit('update:modelValue', { ...props.modelValue, ...patch })

const onAttributeChange = (event: Event) => {
  const attribute = (event.target as HTMLSelectElement).value
  const nextComparators = comparatorsFor(attributes.value.find((a) => a.path === attribute) ?? attributes.value[0])
  const comparator = nextComparators.includes(props.modelValue.comparator) ? props.modelValue.comparator : nextComparators[0]
  update({ attribute, comparator, value: literalValue('') })
}

const onComparatorChange = (event: Event) => {
  const comparator = (event.target as HTMLSelectElement).value as Comparator
  update({ comparator, value: comparator === 'in' ? literalValue([]) : literalValue('') })
}

const onValueChange = (value: ValueRef) => update({ value })
const onListValueChange = (raw: string) =>
  update({ value: literalValue(raw.split(',').map((v) => v.trim()).filter((v) => v.length > 0)) })
</script>

<template>
  <div
    class="row"
    :class="{ highlighted: highlightedNodeId === modelValue.id }"
  >
    <select
      class="inp attr"
      :value="modelValue.attribute"
      @change="onAttributeChange"
    >
      <option
        v-for="attribute in attributes"
        :key="attribute.path"
        :value="attribute.path"
      >
        {{ attribute.path }}
      </option>
    </select>

    <select
      class="inp cmp"
      :value="modelValue.comparator"
      @change="onComparatorChange"
    >
      <option
        v-for="comparator in comparatorChoices"
        :key="comparator"
        :value="comparator"
      >
        {{ comparator }}
      </option>
    </select>

    <input
      v-if="valueTakesList"
      class="inp val"
      type="text"
      placeholder="comma-separated values"
      :value="listValueText"
      @input="onListValueChange(($event.target as HTMLInputElement).value)"
    >
    <ValueRefInput
      v-else-if="!valueTakesNoInput"
      :model-value="modelValue.value"
      :group-kind="groupKind"
      :attribute-paths="attributePaths"
      :literal-choices="literalChoices"
      @update:model-value="onValueChange"
    />

    <button
      type="button"
      class="not-toggle"
      :class="{ on: modelValue.negate }"
      title="negate this condition"
      @click="update({ negate: !modelValue.negate })"
    >
      NOT
    </button>
    <button
      type="button"
      class="icon-btn"
      title="remove condition"
      @click="emit('remove')"
    >
      ✕
    </button>
  </div>
</template>

<style scoped>
.row {
  display: flex; gap: 6px; align-items: center; background: #fff; border: 1px solid #d1d5db;
  border-radius: 7px; padding: 6px 8px; margin: 5px 0; flex-wrap: wrap;
}
.row.highlighted { outline: 2px solid #dc2626; outline-offset: 2px; }
.inp { padding: 4px 6px; border-radius: 5px; border: 1px solid #d1d5db; font-size: 12.5px; font-family: inherit; }
.attr { min-width: 118px; }
.cmp { min-width: 80px; }
.val { min-width: 90px; flex: 1; }
.not-toggle {
  appearance: none; border: 1px solid #d1d5db; border-radius: 99px; background: #fff;
  color: #9ca3af; font-size: 10.5px; font-weight: 700; padding: 3px 9px; cursor: pointer;
}
.not-toggle.on { background: #fee2e2; color: #991b1b; border-color: transparent; }
.icon-btn {
  appearance: none; border: none; background: none; color: #9ca3af; cursor: pointer;
  font-size: 15px; line-height: 1; padding: 2px 5px; border-radius: 5px;
}
.icon-btn:hover { background: #fee2e2; color: #991b1b; }
</style>
