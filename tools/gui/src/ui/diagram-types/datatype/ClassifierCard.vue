<script setup lang="ts">
import ActivityEntityPicker from '../activity/ActivityEntityPicker.vue'
import type { Classifier, Attribute, ClassifierKind } from './useDatatypeModel'
import { CLASSIFIER_KINDS } from './useDatatypeModel'
import { buildTypeOptions } from './ClassifierCard.helpers'
import { computed } from 'vue'

const props = defineProps<{
  classifier: Classifier
  primitiveTypes: readonly string[]
  classifierLabels: readonly string[]
}>()
const emit = defineEmits<{
  update: [patch: Partial<Classifier>]
  remove: []
  addAttr: []
  removeAttr: [index: number]
  updateAttr: [index: number, patch: Partial<Attribute>]
  addLiteral: []
  removeLiteral: [index: number]
  updateLiteral: [index: number, value: string]
}>()

const onKindChange = (e: Event) => {
  const kind = (e.target as HTMLSelectElement).value as ClassifierKind
  const patch: Partial<Classifier> = { classifier_kind: kind }
  if (kind === 'enumeration') patch.attributes = undefined
  else patch.literals = undefined
  emit('update', patch)
}

const isEnum = () => props.classifier.classifier_kind === 'enumeration'

// Datalist id unique per classifier so multiple cards don't collide.
const typeListId = computed(() => `dt-type-opts-${props.classifier.id}`)

// Combined options: primitives then in-diagram classifiers (deduplicated).
const typeOptions = computed(() => buildTypeOptions(props.primitiveTypes, props.classifierLabels))
</script>

<template>
  <div class="cls-card">
    <div class="cls-hdr">
      <select
        class="kind-sel"
        :value="classifier.classifier_kind"
        @change="onKindChange"
      >
        <option
          v-for="k in CLASSIFIER_KINDS"
          :key="k"
          :value="k"
        >
          {{ k }}
        </option>
      </select>
      <input
        class="label-in"
        type="text"
        :value="classifier.label ?? ''"
        placeholder="Label"
        @input="emit('update', { label: ($event.target as HTMLInputElement).value || undefined })"
      >
      <button
        class="del-btn"
        type="button"
        title="Remove classifier"
        @click="emit('remove')"
      >
        ×
      </button>
    </div>

    <div class="dob-row">
      <span class="section-lbl">DOB binding</span>
      <ActivityEntityPicker
        :entity-id="classifier.entity_id"
        :accepted-types="['data-object']"
        @pick="(id) => emit('update', { entity_id: id ?? undefined })"
      />
    </div>

    <template v-if="!isEnum()">
      <div class="attrs-section">
        <div class="section-row">
          <span class="section-lbl">Attributes</span>
          <button
            class="add-btn"
            type="button"
            @click="emit('addAttr')"
          >
            + Attr
          </button>
        </div>
        <div
          v-for="(attr, i) in classifier.attributes ?? []"
          :key="i"
          class="attr-row"
        >
          <input
            type="text"
            class="attr-name"
            :value="attr.name"
            placeholder="name"
            @input="emit('updateAttr', i, { name: ($event.target as HTMLInputElement).value })"
          >
          <input
            :list="typeListId"
            type="text"
            class="attr-type"
            :value="attr.type ?? ''"
            placeholder="type"
            @input="emit('updateAttr', i, { type: ($event.target as HTMLInputElement).value || undefined })"
          >
          <datalist :id="typeListId">
            <option
              v-for="opt in typeOptions"
              :key="opt"
              :value="opt"
            />
          </datalist>
          <input
            type="text"
            class="attr-mult"
            :value="attr.multiplicity ?? ''"
            placeholder="mult"
            @input="emit('updateAttr', i, { multiplicity: ($event.target as HTMLInputElement).value || undefined })"
          >
          <label class="attr-id-chk">
            <input
              type="checkbox"
              :checked="!!attr.is_id"
              @change="emit('updateAttr', i, { is_id: ($event.target as HTMLInputElement).checked || undefined })"
            > {id}
          </label>
          <button
            class="del-btn"
            type="button"
            @click="emit('removeAttr', i)"
          >
            ×
          </button>
        </div>
      </div>
    </template>

    <template v-else>
      <div class="lits-section">
        <div class="section-row">
          <span class="section-lbl">Literals</span>
          <button
            class="add-btn"
            type="button"
            @click="emit('addLiteral')"
          >
            + Literal
          </button>
        </div>
        <div
          v-for="(lit, i) in classifier.literals ?? []"
          :key="i"
          class="lit-row"
        >
          <input
            type="text"
            class="lit-in"
            :value="lit"
            @input="emit('updateLiteral', i, ($event.target as HTMLInputElement).value)"
          >
          <button
            class="del-btn"
            type="button"
            @click="emit('removeLiteral', i)"
          >
            ×
          </button>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.cls-card { border: 1px solid #e2e8f0; border-radius: 6px; padding: 8px; background: #fff; display: flex; flex-direction: column; gap: 6px; }
.cls-hdr { display: flex; gap: 4px; align-items: center; }
.kind-sel { font-size: 11px; border: 1px solid #cbd5e1; border-radius: 4px; padding: 2px 4px; background: #f1f5f9; }
.label-in { flex: 1; font-size: 12px; border: 1px solid #cbd5e1; border-radius: 4px; padding: 2px 6px; }
.del-btn { border: none; background: none; cursor: pointer; color: #9ca3af; font-size: 14px; padding: 0 2px; }
.del-btn:hover { color: #ef4444; }
.dob-row { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.section-lbl { font-size: 11px; color: #6b7280; white-space: nowrap; }
.attrs-section, .lits-section { display: flex; flex-direction: column; gap: 4px; }
.section-row { display: flex; align-items: center; gap: 6px; }
.add-btn { font-size: 11px; padding: 1px 6px; border: 1px solid #cbd5e1; border-radius: 4px; background: #fff; cursor: pointer; }
.add-btn:hover { background: #f1f5f9; }
.attr-row, .lit-row { display: flex; gap: 4px; align-items: center; }
.attr-name { width: 90px; font-size: 11px; border: 1px solid #e2e8f0; border-radius: 3px; padding: 1px 4px; }
.attr-type { width: 80px; font-size: 11px; border: 1px solid #e2e8f0; border-radius: 3px; padding: 1px 4px; }
.attr-mult { width: 55px; font-size: 11px; border: 1px solid #e2e8f0; border-radius: 3px; padding: 1px 4px; }
.attr-id-chk { font-size: 11px; color: #6b7280; display: flex; align-items: center; gap: 2px; cursor: pointer; }
.lit-in { flex: 1; font-size: 11px; border: 1px solid #e2e8f0; border-radius: 3px; padding: 1px 4px; }
</style>
