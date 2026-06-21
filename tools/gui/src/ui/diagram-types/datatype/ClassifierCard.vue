<script setup lang="ts">
import ActivityEntityPicker from '../activity/ActivityEntityPicker.vue'
import type { Classifier, Attribute, ClassifierKind, AttrTypeRef } from './useDatatypeModel'
import { CLASSIFIER_KINDS } from './useDatatypeModel'
import type { CatalogClassifier, TypeOptionGroup } from './ClassifierCard.helpers'
import {
  buildTypeOptions,
  optionKey,
  removeUniqueConstraint as withoutUniqueConstraint,
  replaceUniqueConstraint,
  refFromOptionKey,
} from './ClassifierCard.helpers'
import DatatypeNoteSection from './DatatypeNoteSection.vue'
import { computed } from 'vue'

const props = defineProps<{
  classifier: Classifier
  primitiveTypes: readonly string[]
  classifiers: readonly Classifier[]
  catalogClassifiers: readonly CatalogClassifier[]
  diagramId: string
  usageCount: number
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
  newClassifier: [attrIndex: number]
}>()

const onKindChange = (e: Event) => {
  const kind = (e.target as HTMLSelectElement).value as ClassifierKind
  const patch: Partial<Classifier> = { classifier_kind: kind }
  if (kind === 'enumeration') patch.attributes = undefined
  else patch.literals = undefined
  emit('update', patch)
}

const isEnum = () => props.classifier.classifier_kind === 'enumeration'

const typeOptions = computed(() => buildTypeOptions(
  props.primitiveTypes,
  props.classifiers,
  props.catalogClassifiers,
  props.diagramId,
))
const optionGroups: TypeOptionGroup[] = ['Primitives', 'This diagram', 'Engagement', 'Enterprise']
const optionsFor = (group: TypeOptionGroup) =>
  typeOptions.value.filter((option) => option.group === group)

function onTypeChange(index: number, current: AttrTypeRef | undefined, event: Event) {
  const select = event.target as HTMLSelectElement
  const key = select.value
  if (key === '__new_classifier__') {
    select.value = optionKey(current)
    emit('newClassifier', index)
    return
  }
  emit('updateAttr', index, { type: refFromOptionKey(key, typeOptions.value) })
}

function addUniqueConstraint() {
  emit('update', {
    unique_constraints: [...(props.classifier.unique_constraints ?? []), []],
  })
}

function updateUniqueConstraint(index: number, event: Event) {
  const selected = [...(event.target as HTMLSelectElement).selectedOptions]
    .map((option) => option.value)
  emit('update', {
    unique_constraints: replaceUniqueConstraint(
      props.classifier.unique_constraints ?? [],
      index,
      selected,
    ),
  })
}

function removeUniqueConstraint(index: number) {
  emit('update', {
    unique_constraints: withoutUniqueConstraint(props.classifier.unique_constraints ?? [], index),
  })
}
</script>

<template>
  <div class="cls-card">
    <section class="card-section">
      <div class="section-row">
        <span class="section-title">Identity</span>
        <span
          class="usage-count"
          :title="`${usageCount} attribute type usage${usageCount === 1 ? '' : 's'}`"
        >
          {{ usageCount }} usages
        </span>
      </div>
      <div class="cls-hdr">
        <select
          class="kind-sel"
          title="Classifier kind"
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
          placeholder="Classifier name"
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
        <span class="field-label">Data Object binding</span>
        <ActivityEntityPicker
          :entity-id="classifier.entity_id"
          :accepted-types="['data-object']"
          @pick="(id) => emit('update', { entity_id: id ?? undefined })"
        />
      </div>
    </section>

    <template v-if="!isEnum()">
      <section class="card-section attrs-section">
        <div class="section-row">
          <span class="section-title">Attributes</span>
          <button
            class="add-btn"
            type="button"
            @click="emit('addAttr')"
          >
            + Attribute
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
          <select
            class="attr-type"
            :value="optionKey(attr.type)"
            title="Attribute type"
            @change="onTypeChange(i, attr.type, $event)"
          >
            <option
              value=""
              disabled
            >
              Select type…
            </option>
            <optgroup
              v-for="group in optionGroups"
              :key="group"
              :label="group"
            >
              <option
                v-for="option in optionsFor(group)"
                :key="option.key"
                :value="option.key"
              >
                {{ option.label }}
              </option>
            </optgroup>
            <option value="__new_classifier__">
              + New classifier
            </option>
          </select>
          <label class="field-stack">
            <input
              type="text"
              class="attr-mult"
              :value="attr.multiplicity ?? ''"
              placeholder="0..1"
              title="Multiplicity (for example: 1, 0..1, 1..*, *)"
              @input="emit('updateAttr', i, { multiplicity: ($event.target as HTMLInputElement).value || undefined })"
            >
          </label>
          <label class="attr-id-chk">
            <input
              type="checkbox"
              :checked="!!attr.is_id"
              @change="emit('updateAttr', i, { is_id: ($event.target as HTMLInputElement).checked || undefined })"
            > {id}
          </label>
          <label class="attr-id-chk">
            <input
              type="checkbox"
              :checked="!!attr.is_unique"
              @change="emit('updateAttr', i, { is_unique: ($event.target as HTMLInputElement).checked || undefined })"
            > {unique}
          </label>
          <button
            class="del-btn"
            type="button"
            @click="emit('removeAttr', i)"
          >
            ×
          </button>
        </div>
      </section>
      <section class="card-section constraints-section">
        <div class="section-row">
          <span class="section-title">Constraints</span>
          <button
            class="add-btn"
            type="button"
            :disabled="!(classifier.attributes?.length)"
            @click="addUniqueConstraint"
          >
            + Constraint
          </button>
        </div>
        <div
          v-for="(constraint, i) in classifier.unique_constraints ?? []"
          :key="i"
          class="constraint-row"
        >
          <select
            multiple
            class="constraint-select"
            title="Select every attribute participating in this composite uniqueness constraint"
            @change="updateUniqueConstraint(i, $event)"
          >
            <option
              v-for="attr in classifier.attributes ?? []"
              :key="attr.name"
              :value="attr.name"
              :selected="constraint.includes(attr.name)"
            >
              {{ attr.name }}
            </option>
          </select>
          <button
            class="del-btn"
            type="button"
            title="Remove unique constraint"
            @click="removeUniqueConstraint(i)"
          >
            ×
          </button>
        </div>
      </section>
    </template>

    <template v-else>
      <section class="card-section lits-section">
        <div class="section-row">
          <span class="section-title">Literals</span>
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
      </section>
    </template>
    <section class="card-section">
      <span class="section-title">Notes</span>
      <DatatypeNoteSection
        :note="classifier.note"
        @update="emit('update', { note: $event })"
      />
    </section>
  </div>
</template>

<style scoped>
.cls-card { border: 1px solid #e2e8f0; border-radius: 6px; padding: 8px; background: #fff; display: flex; flex-direction: column; gap: 6px; }
.card-section { display: flex; flex-direction: column; gap: 5px; padding-top: 6px; border-top: 1px solid #f1f5f9; }
.card-section:first-child { padding-top: 0; border-top: 0; }
.cls-hdr { display: flex; gap: 4px; align-items: center; }
.usage-count { margin-left: auto; font-size: 10px; color: #6b7280; white-space: nowrap; }
.kind-sel { font-size: 11px; border: 1px solid #cbd5e1; border-radius: 4px; padding: 2px 4px; background: #f1f5f9; }
.label-in { flex: 1; font-size: 12px; border: 1px solid #cbd5e1; border-radius: 4px; padding: 2px 6px; }
.del-btn { border: none; background: none; cursor: pointer; color: #9ca3af; font-size: 14px; padding: 0 2px; }
.del-btn:hover { color: #ef4444; }
.dob-row { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.section-title { font-size: 11px; font-weight: 600; color: #374151; white-space: nowrap; }
.field-label { font-size: 10px; color: #6b7280; white-space: nowrap; }
.attrs-section, .lits-section, .constraints-section { display: flex; flex-direction: column; gap: 4px; }
.section-row { display: flex; align-items: center; gap: 6px; }
.add-btn { font-size: 11px; padding: 1px 6px; border: 1px solid #cbd5e1; border-radius: 4px; background: #fff; cursor: pointer; }
.add-btn:hover { background: #f1f5f9; }
.attr-row, .lit-row { display: flex; gap: 4px; align-items: center; }
.attr-name { width: 90px; font-size: 11px; border: 1px solid #e2e8f0; border-radius: 3px; padding: 1px 4px; }
.attr-type { width: 130px; font-size: 11px; border: 1px solid #e2e8f0; border-radius: 3px; padding: 1px 4px; background: #fff; }
.attr-mult { width: 55px; font-size: 11px; border: 1px solid #e2e8f0; border-radius: 3px; padding: 1px 4px; }
.field-stack { display: flex; flex-direction: column; gap: 1px; font-size: 9px; color: #6b7280; }
.attr-id-chk { font-size: 11px; color: #6b7280; display: flex; align-items: center; gap: 2px; cursor: pointer; }
.constraint-row { display: flex; align-items: center; gap: 4px; }
.constraint-select { min-width: 180px; min-height: 48px; font-size: 11px; border: 1px solid #e2e8f0; border-radius: 3px; }
.lit-in { flex: 1; font-size: 11px; border: 1px solid #e2e8f0; border-radius: 3px; padding: 1px 4px; }
</style>
