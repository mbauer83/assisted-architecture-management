<script setup lang="ts">
/**
 * "Scope" tab of the viewpoint definition editor: the entity/connection-type allow-list
 * (`unrestricted` when null). Standard modelValue/update:modelValue two-way binding, same
 * convention as CriteriaTreeBuilder — the parent v-models this onto its own `draft.scope`.
 */
import type { CriteriaCatalog } from '../../domain'
import type { ScopeDraft } from '../../domain/viewpointDefinitionDraft'

const props = defineProps<{
  modelValue: ScopeDraft
  catalog: CriteriaCatalog
}>()
const emit = defineEmits<{ 'update:modelValue': [value: ScopeDraft] }>()

const toggleScopeType = (axis: 'entityTypes' | 'connectionTypes', value: string) => {
  const current = props.modelValue[axis] ?? []
  emit('update:modelValue', {
    ...props.modelValue,
    [axis]: current.includes(value) ? current.filter((v) => v !== value) : [...current, value],
  })
}
</script>

<template>
  <div>
    <fieldset>
      <legend>
        entity_types
        <label><input
          type="checkbox"
          :checked="modelValue.entityTypes === null"
          @change="emit('update:modelValue', { ...modelValue, entityTypes: modelValue.entityTypes === null ? [] : null })"
        > unrestricted</label>
      </legend>
      <label
        v-for="t in catalog.entity_types"
        v-show="modelValue.entityTypes !== null"
        :key="t"
      >
        <input
          type="checkbox"
          :checked="modelValue.entityTypes?.includes(t)"
          @change="toggleScopeType('entityTypes', t)"
        > {{ t }}
      </label>
    </fieldset>
    <fieldset>
      <legend>
        connection_types
        <label><input
          type="checkbox"
          :checked="modelValue.connectionTypes === null"
          @change="emit('update:modelValue', { ...modelValue, connectionTypes: modelValue.connectionTypes === null ? [] : null })"
        > unrestricted</label>
      </legend>
      <label
        v-for="t in catalog.connection_types"
        v-show="modelValue.connectionTypes !== null"
        :key="t"
      >
        <input
          type="checkbox"
          :checked="modelValue.connectionTypes?.includes(t)"
          @change="toggleScopeType('connectionTypes', t)"
        > {{ t }}
      </label>
    </fieldset>
  </div>
</template>

<style scoped>
fieldset { border: 1px solid #d1d5db; border-radius: 8px; margin: 10px 0; padding: 8px 12px; }
</style>
