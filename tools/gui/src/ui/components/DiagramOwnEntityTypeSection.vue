<script setup lang="ts">
import { computed } from 'vue'
import type { DiagramOwnEntityTypeUiConfig, EntityDisplayInfo } from '../../domain'
import EntityPickerInput from './EntityPickerInput.vue'

type DiagramOnlyEntity = {
  id: string
  label: string
  entity_id?: string
}

const props = defineProps<{
  config: DiagramOwnEntityTypeUiConfig
  diagramEntities: Record<string, unknown>
}>()
const emit = defineEmits<{ diagramEntitiesChange: [patch: Record<string, unknown>] }>()

const collectionKey = computed(() => props.config.entity_type)
const items = computed<DiagramOnlyEntity[]>(() => {
  const raw = props.diagramEntities[collectionKey.value]
  return Array.isArray(raw) ? raw.filter((item): item is DiagramOnlyEntity => Boolean(item && typeof item === 'object')) : []
})
const canAdd = computed(() => props.config.max === null || items.value.length < props.config.max)
const canRemove = computed(() => items.value.length > props.config.min)
const permittedTypes = computed(() => props.config.permitted_mappings.entity_types)

const updateItems = (next: DiagramOnlyEntity[]) => emit('diagramEntitiesChange', { [collectionKey.value]: next })
const addItem = () => {
  if (!canAdd.value) return
  const id = `${props.config.entity_type}-${Date.now().toString(36)}`
  updateItems([...items.value, { id, label: props.config.label }])
}
const removeItem = (id: string) => {
  if (!canRemove.value) return
  updateItems(items.value.filter((item) => item.id !== id))
}
const patchItem = (id: string, patch: Partial<DiagramOnlyEntity>) =>
  updateItems(items.value.map((item) => item.id === id ? { ...item, ...patch } : item))
const setMapping = (id: string, entity: EntityDisplayInfo) =>
  patchItem(id, { entity_id: entity.artifact_id, label: entity.name })
</script>

<template>
  <section class="kind-section">
    <div class="kind-section__header">
      <span>{{ config.plural }}</span>
      <button
        class="mini-btn"
        :disabled="!canAdd"
        type="button"
        @click="addItem"
      >
        +
      </button>
    </div>
    <div
      v-for="item in items"
      :key="item.id"
      class="kind-row"
    >
      <input
        class="inp"
        :value="item.label"
        :placeholder="config.label"
        @input="patchItem(item.id, { label: ($event.target as HTMLInputElement).value })"
      >
      <EntityPickerInput
        v-if="permittedTypes.length"
        class="mapping-picker"
        :fixed-entity-types="[...permittedTypes]"
        :placeholder="item.entity_id ? 'Change mapping…' : 'Map to model entity…'"
        @select="setMapping(item.id, $event)"
      />
      <button
        class="mini-btn"
        :disabled="!canRemove"
        type="button"
        @click="removeItem(item.id)"
      >
        ×
      </button>
    </div>
  </section>
</template>

<style scoped>
.kind-section { display: grid; gap: 8px; }
.kind-section__header { display: flex; align-items: center; justify-content: space-between; font-weight: 650; }
.kind-row { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.2fr) auto; gap: 6px; align-items: start; }
.mini-btn { min-width: 28px; height: 28px; border: 1px solid #cbd5e1; background: #fff; border-radius: 6px; cursor: pointer; }
.mini-btn:disabled { opacity: .45; cursor: not-allowed; }
.mapping-picker { min-width: 0; }
</style>
