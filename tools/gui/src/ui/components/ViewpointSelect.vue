<script setup lang="ts">
import { watch } from 'vue'
import type { ViewpointSummary } from '../../domain'
import { viewpointOptionLabel, findViewpointBySlug } from './ViewpointSelect.helpers'

const props = defineProps<{
  modelValue: string | null
  viewpoints: readonly ViewpointSummary[]
}>()
const emit = defineEmits<{
  'update:modelValue': [slug: string | null]
  select: [viewpoint: ViewpointSummary | null]
}>()

const onChange = (event: Event) => {
  const raw = (event.target as HTMLSelectElement).value
  const slug = raw === '' ? null : raw
  emit('update:modelValue', slug)
  emit('select', findViewpointBySlug(props.viewpoints, slug))
}

// Re-emit `select` if the catalog loads after modelValue was already set (e.g. pre-filled
// from an existing diagram's applied viewpoint before the guidance fetch resolves).
watch(() => props.viewpoints, (viewpoints) => {
  if (props.modelValue !== null) emit('select', findViewpointBySlug(viewpoints, props.modelValue))
})
</script>

<template>
  <select
    class="inp"
    :value="modelValue ?? ''"
    @change="onChange"
  >
    <option value="">
      None (unrestricted)
    </option>
    <option
      v-for="viewpoint in viewpoints"
      :key="viewpoint.slug"
      :value="viewpoint.slug"
    >
      {{ viewpointOptionLabel(viewpoint) }}
    </option>
  </select>
</template>
