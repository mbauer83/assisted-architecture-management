<script setup lang="ts">
import type { DiagramTypeUiConfig, EntityDisplayInfo } from '../../../domain'
import ClassifierCard from './ClassifierCard.vue'
import RelationList from './RelationList.vue'
import { useDatatypeModel } from './useDatatypeModel'
import type { Attribute, Classifier, DtConn } from './useDatatypeModel'
import { computed } from 'vue'

const props = defineProps<{
  uiConfig: DiagramTypeUiConfig
  diagramEntities: Record<string, unknown>
  entities: EntityDisplayInfo[]
}>()
const emit = defineEmits<{
  diagramEntitiesChange: [patch: Record<string, unknown>]
}>()

const {
  classifiers, connections,
  addClassifier, removeClassifier, updateClassifier,
  addAttribute, removeAttribute, updateAttribute,
  addLiteral, removeLiteral, updateLiteral,
  addConnection, removeConnection, updateConnection,
} = useDatatypeModel(
  () => props.diagramEntities,
  (patch) => emit('diagramEntitiesChange', patch),
)

const primitiveTypes = computed(() => props.uiConfig.primitive_types ?? [])
const classifierLabels = computed(() =>
  classifiers.value.map((c) => c.label ?? c.id).filter(Boolean)
)
</script>

<template>
  <div class="dte">
    <section class="dte-section">
      <div class="dte-hdr">
        <span class="dte-title">Classifiers</span>
        <button
          class="dte-add-btn"
          type="button"
          @click="addClassifier()"
        >
          + Classifier
        </button>
      </div>
      <div
        v-if="!classifiers.length"
        class="dte-empty"
      >
        Add classifiers to build the diagram.
      </div>
      <ClassifierCard
        v-for="cls in classifiers"
        :key="cls.id"
        :classifier="cls"
        :primitive-types="primitiveTypes"
        :classifier-labels="classifierLabels"
        @update="(patch: Partial<Classifier>) => updateClassifier(cls.id, patch)"
        @remove="removeClassifier(cls.id)"
        @add-attr="addAttribute(cls.id)"
        @remove-attr="(i: number) => removeAttribute(cls.id, i)"
        @update-attr="(i: number, patch: Partial<Attribute>) => updateAttribute(cls.id, i, patch)"
        @add-literal="addLiteral(cls.id)"
        @remove-literal="(i: number) => removeLiteral(cls.id, i)"
        @update-literal="(i: number, val: string) => updateLiteral(cls.id, i, val)"
      />
    </section>

    <section class="dte-section">
      <RelationList
        :classifiers="classifiers"
        :connections="connections"
        @add-conn="(src: string, tgt: string) => addConnection(src, tgt)"
        @remove-conn="(id: string) => removeConnection(id)"
        @update-conn="(id: string, patch: Partial<DtConn>) => updateConnection(id, patch)"
      />
    </section>
  </div>
</template>

<style scoped>
.dte { display: flex; flex-direction: column; gap: 12px; }
.dte-section { display: flex; flex-direction: column; gap: 6px; padding: 10px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; }
.dte-hdr { display: flex; align-items: center; justify-content: space-between; }
.dte-title { font-size: 12px; font-weight: 700; color: #374151; text-transform: uppercase; letter-spacing: .04em; }
.dte-add-btn { font-size: 11px; padding: 2px 8px; border: 1px solid #cbd5e1; border-radius: 4px; background: #fff; cursor: pointer; }
.dte-add-btn:hover { background: #f1f5f9; }
.dte-empty { font-size: 11px; color: #9ca3af; }
</style>
