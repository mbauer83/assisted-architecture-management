<script setup lang="ts">
import { computed } from 'vue'
import type { EntityAttributeDescriptor } from '../../domain'

const props = defineProps<{
  modelValue: string
  descriptor: EntityAttributeDescriptor
  required?: boolean
  placeholder?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const isEnum = computed(() => Boolean(props.descriptor.enum?.length))
const isBoolean = computed(() => props.descriptor.type === 'boolean')
const isArray = computed(() => props.descriptor.type === 'array')
const isNumeric = computed(
  () => props.descriptor.type === 'integer' || props.descriptor.type === 'number',
)

const step = computed(() => {
  if (props.descriptor.type === 'integer') return 1
  if (props.descriptor.type === 'number') return 'any'
  return undefined
})

const numMin = computed(() => {
  const c = props.descriptor.constraints
  if (!c) return undefined
  return c.minimum ?? c.exclusiveMinimum
})

const numMax = computed(() => {
  const c = props.descriptor.constraints
  if (!c) return undefined
  return c.maximum ?? c.exclusiveMaximum
})

const validationError = computed((): string | null => {
  const v = props.modelValue
  if (props.required && !v.trim()) return 'Required'
  if (!v) return null
  const t = props.descriptor.type
  if (t === 'integer' && !/^-?[0-9]+$/.test(v.trim())) return 'Must be a whole number'
  if (t === 'number' && isNaN(Number(v.trim()))) return 'Must be a number'
  if (isEnum.value && !props.descriptor.enum!.includes(v)) {
    return `Must be one of: ${props.descriptor.enum!.join(', ')}`
  }
  return null
})
</script>

<template>
  <div class="typed-prop-input">
    <!-- enum → select -->
    <select
      v-if="isEnum"
      class="prop-value"
      :value="modelValue"
      @change="emit('update:modelValue', ($event.target as HTMLSelectElement).value)"
    >
      <option
        v-if="!required"
        value=""
      >
        —
      </option>
      <option
        v-for="opt in descriptor.enum"
        :key="opt"
        :value="opt"
      >
        {{ opt }}
      </option>
    </select>

    <!-- boolean → checkbox -->
    <label
      v-else-if="isBoolean"
      class="bool-label"
    >
      <input
        type="checkbox"
        :checked="modelValue === 'true'"
        @change="emit('update:modelValue', ($event.target as HTMLInputElement).checked ? 'true' : 'false')"
      >
      <span class="bool-value">{{ modelValue === 'true' ? 'true' : 'false' }}</span>
    </label>

    <!-- array → JSON textarea -->
    <textarea
      v-else-if="isArray"
      class="prop-value prop-value--array"
      rows="2"
      :value="modelValue"
      :placeholder="placeholder ?? 'JSON array'"
      @input="emit('update:modelValue', ($event.target as HTMLTextAreaElement).value)"
    />

    <!-- integer / number → number input -->
    <input
      v-else-if="isNumeric"
      class="prop-value"
      type="number"
      :step="step"
      :min="numMin"
      :max="numMax"
      :value="modelValue"
      :placeholder="placeholder ?? descriptor.type"
      @input="emit('update:modelValue', ($event.target as HTMLInputElement).value)"
    >

    <!-- string (default) → text input -->
    <input
      v-else
      class="prop-value"
      type="text"
      :value="modelValue"
      :placeholder="placeholder ?? ''"
      :pattern="descriptor.constraints?.pattern"
      @input="emit('update:modelValue', ($event.target as HTMLInputElement).value)"
    >

    <span
      v-if="validationError"
      class="prop-validation-error"
    >{{ validationError }}</span>
  </div>
</template>
