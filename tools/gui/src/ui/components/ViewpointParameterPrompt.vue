<script setup lang="ts">
/**
 * Parameter-prompt dialog: shown before the first execution of a definition that
 * declares at least one required parameter with no default. Typed inputs per declared
 * `value_type` — no free-text escape hatch for anything but `string`/`slug`; `entity-id`
 * reuses the existing entity picker rather than a raw id text field.
 */
import { ref, watch } from 'vue'
import type { QueryParameterNode } from '../../domain/viewpointBindings'
import type { EntityDisplayInfo } from '../../domain'
import { initialParameterDraft, missingRequiredParameters } from '../lib/viewpointExecutionParameters'
import EntityPickerInput from './EntityPickerInput.vue'

const props = defineProps<{ parameters: readonly QueryParameterNode[] }>()
const emit = defineEmits<{ submit: [draft: Record<string, string>]; cancel: [] }>()

const draft = ref<Record<string, string>>(initialParameterDraft(props.parameters))
watch(() => props.parameters, (parameters) => { draft.value = initialParameterDraft(parameters) })

const setValue = (name: string, value: string) => { draft.value = { ...draft.value, [name]: value } }
const missing = () => missingRequiredParameters(props.parameters, draft.value)
const onSubmit = () => { if (missing().length === 0) emit('submit', draft.value) }
</script>

<template>
  <div class="prompt-backdrop">
    <div
      class="prompt-panel"
      role="dialog"
      aria-label="Viewpoint parameters"
    >
      <h2>This viewpoint takes parameters</h2>
      <div
        v-for="parameter in parameters"
        :key="parameter.name"
        class="param-field"
      >
        <label :for="`vp-param-${parameter.name}`">
          {{ parameter.name }}<span v-if="parameter.required"> (required)</span>
        </label>
        <p
          v-if="parameter.description"
          class="param-desc"
        >
          {{ parameter.description }}
        </p>

        <EntityPickerInput
          v-if="parameter.valueType === 'entity-id'"
          :placeholder="`select an entity for ${parameter.name}`"
          @select="(entity: EntityDisplayInfo) => setValue(parameter.name, entity.artifact_id)"
        />
        <input
          v-else-if="parameter.valueType === 'boolean'"
          :id="`vp-param-${parameter.name}`"
          type="checkbox"
          :checked="draft[parameter.name] === 'true'"
          @change="setValue(parameter.name, ($event.target as HTMLInputElement).checked ? 'true' : 'false')"
        >
        <input
          v-else-if="parameter.valueType === 'date'"
          :id="`vp-param-${parameter.name}`"
          type="date"
          :value="draft[parameter.name]"
          @input="setValue(parameter.name, ($event.target as HTMLInputElement).value)"
        >
        <input
          v-else-if="parameter.valueType === 'integer' || parameter.valueType === 'number'"
          :id="`vp-param-${parameter.name}`"
          type="number"
          :step="parameter.valueType === 'integer' ? '1' : 'any'"
          :value="draft[parameter.name]"
          @input="setValue(parameter.name, ($event.target as HTMLInputElement).value)"
        >
        <input
          v-else
          :id="`vp-param-${parameter.name}`"
          type="text"
          :value="draft[parameter.name]"
          @input="setValue(parameter.name, ($event.target as HTMLInputElement).value)"
        >
        <span
          v-if="parameter.valueType === 'entity-id' && draft[parameter.name]"
          class="selected-hint"
        >selected: {{ draft[parameter.name] }}</span>
      </div>

      <p
        v-if="missing().length > 0"
        class="missing-hint"
      >
        Still needed: {{ missing().map((p) => p.name).join(', ') }}.
      </p>

      <div class="prompt-actions">
        <button
          type="button"
          @click="emit('cancel')"
        >
          Cancel
        </button>
        <button
          type="button"
          class="primary-btn"
          :disabled="missing().length > 0"
          @click="onSubmit"
        >
          Run
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.prompt-backdrop { position: fixed; inset: 0; background: rgba(17, 24, 39, .4); display: flex; align-items: center; justify-content: center; z-index: 50; }
.prompt-panel { background: #fff; border-radius: 10px; padding: 20px 24px; min-width: 340px; max-width: 480px; box-shadow: 0 10px 30px rgba(0,0,0,.2); }
.prompt-panel h2 { font-size: 15px; margin: 0 0 12px; }
.param-field { margin: 10px 0; display: flex; flex-direction: column; gap: 4px; }
.param-field label { font-size: 12.5px; font-weight: 600; color: #374151; }
.param-desc { font-size: 11.5px; color: #6b7280; margin: 0; }
.param-field input { padding: 6px 8px; border-radius: 6px; border: 1px solid #d1d5db; font-size: 13px; font-family: inherit; }
.selected-hint { font-size: 11.5px; color: #4338ca; }
.missing-hint { font-size: 12px; color: #92400e; background: #fef3c7; padding: 6px 10px; border-radius: 6px; }
.prompt-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 14px; }
.prompt-actions button { padding: 6px 14px; border-radius: 7px; border: 1px solid #d1d5db; background: #fff; font-size: 13px; cursor: pointer; }
.primary-btn { background: #6366f1; color: #fff; border: none; font-weight: 600; }
.primary-btn:disabled { opacity: .5; cursor: not-allowed; }
</style>
