<script setup lang="ts">
/**
 * "Presentation" tab of the viewpoint definition editor: representation choice, table
 * columns, matrix axes, exploration/diagram grouping, and style rules. Standard
 * modelValue/update:modelValue two-way binding, same convention MatrixAxesEditor and
 * StyleRuleEditor already use for this exact node — the parent v-models this onto its own
 * `draft.presentation`.
 */
import type { CriteriaCatalog } from '../../domain'
import { GROUP_BY_DIMENSIONS, mkColumn, mkPresentation } from '../../domain/viewpointPresentation'
import type { ColumnSpecNode, PresentationNode, Representation } from '../../domain/viewpointPresentation'
import StyleRuleEditor from './StyleRuleEditor.vue'
import MatrixAxesEditor from './MatrixAxesEditor.vue'

const props = defineProps<{
  modelValue: PresentationNode | null
  catalog: CriteriaCatalog
}>()
const emit = defineEmits<{ 'update:modelValue': [value: PresentationNode | null] }>()

const REPRESENTATIONS: Representation[] = ['exploration', 'table', 'matrix', 'diagram']

const emitUpdate = (patch: Partial<PresentationNode>) => {
  if (!props.modelValue) return
  emit('update:modelValue', { ...props.modelValue, ...patch })
}

const addPresentation = (representation: Representation) => emit('update:modelValue', mkPresentation(representation))
const removePresentation = () => emit('update:modelValue', null)
const changeRepresentation = (representation: Representation) => emit('update:modelValue', mkPresentation(representation))
const addColumn = () => emitUpdate({ columns: [...(props.modelValue?.columns ?? []), mkColumn()] })
const removeColumn = (index: number) => {
  if (!props.modelValue?.columns) return
  emitUpdate({ columns: props.modelValue.columns.filter((_, i) => i !== index) })
}
const updateColumn = (index: number, column: ColumnSpecNode) => {
  if (!props.modelValue?.columns) return
  const columns = [...props.modelValue.columns]
  columns[index] = column
  emitUpdate({ columns })
}
</script>

<template>
  <div>
    <div v-if="modelValue === null">
      <p>No presentation — this definition is query-only (execution result has no fixed display).</p>
      <select @change="addPresentation(($event.target as HTMLSelectElement).value as Representation)">
        <option value="" />
        <option
          v-for="r in REPRESENTATIONS"
          :key="r"
          :value="r"
        >
          {{ r }}
        </option>
      </select>
    </div>
    <div v-else>
      <label class="field">
        representation
        <select
          :value="modelValue.representation"
          @change="changeRepresentation(($event.target as HTMLSelectElement).value as Representation)"
        >
          <option
            v-for="r in REPRESENTATIONS"
            :key="r"
            :value="r"
          >
            {{ r }}
          </option>
        </select>
      </label>
      <button
        type="button"
        @click="removePresentation"
      >
        Remove presentation
      </button>

      <div v-if="modelValue.representation === 'table'">
        <h3>Columns</h3>
        <div
          v-for="(column, index) in modelValue.columns ?? []"
          :key="column.id"
          class="column-row"
        >
          <input
            :value="column.label"
            placeholder="label"
            @input="updateColumn(index, { ...column, label: ($event.target as HTMLInputElement).value })"
          >
          <input
            :value="column.source"
            placeholder="source (attribute path)"
            @input="updateColumn(index, { ...column, source: ($event.target as HTMLInputElement).value })"
          >
          <button
            type="button"
            @click="removeColumn(index)"
          >
            ✕
          </button>
        </div>
        <button
          type="button"
          class="add-btn"
          @click="addColumn"
        >
          + Add column
        </button>
      </div>

      <div v-if="modelValue.representation === 'matrix'">
        <MatrixAxesEditor
          :model-value="modelValue"
          :catalog="catalog"
          @update:model-value="emit('update:modelValue', $event)"
        />
      </div>

      <div v-if="modelValue.representation === 'exploration' || modelValue.representation === 'diagram'">
        <label class="field">
          group_by
          <select
            :value="modelValue.groupBy ?? ''"
            @change="emitUpdate({ groupBy: ($event.target as HTMLSelectElement).value || null })"
          >
            <option value="" />
            <option
              v-for="d in [...GROUP_BY_DIMENSIONS, ...Object.keys(catalog.entity_attribute_types)]"
              :key="d"
              :value="d"
            >
              {{ d }}
            </option>
          </select>
        </label>
      </div>

      <h3>Style rules</h3>
      <StyleRuleEditor
        :model-value="modelValue"
        :catalog="catalog"
        @update:model-value="emit('update:modelValue', $event)"
      />
    </div>
  </div>
</template>

<style scoped>
.field { display: block; margin: 8px 0; font-size: 12.5px; font-weight: 600; color: #6b7280; }
.column-row { display: flex; gap: 6px; margin: 4px 0; }
.add-btn { appearance: none; border: 1px dashed #d1d5db; background: #fff; color: #6b7280; border-radius: 7px; padding: 5px 10px; font-size: 12px; font-weight: 600; cursor: pointer; margin-top: 8px; }
</style>
