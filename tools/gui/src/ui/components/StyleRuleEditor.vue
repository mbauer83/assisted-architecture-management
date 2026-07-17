<script setup lang="ts">
/**
 * Ordered style-rule list (first-match-wins per capability), the default-style fallback
 * map, and the read-only derived legend. `mode="match"` reuses the criteria-tree builder
 * unmodified; `mode="range"` is a numeric attribute plus ordered half-open bands;
 * `mode="scale"` is a numeric/derived attribute, optional bounds, and a two-endpoint
 * gradient. Every style value is picked visually (semantic token, named endpoint, or an
 * explicit hex color) — never typed as free text.
 */
import { computed } from 'vue'
import type { CriteriaCatalog } from '../../domain'
import type { GroupNode } from '../../domain/viewpointCriteria'
import { isEdgeCapability, mkRangeBand, mkStyleRule, withStyleMode } from '../../domain/viewpointPresentation'
import type { PresentationNode, RangeBandNode, StyleMode, StyleRuleNode } from '../../domain/viewpointPresentation'
import { tokenColor } from '../lib/viewpointStyleTokens'
import { capabilitiesFor, derivedLegend, numericAttributeOptions } from './StyleRuleEditor.helpers'
import CriteriaTreeBuilder from './CriteriaTreeBuilder.vue'
import StyleRuleScaleFields from './StyleRuleScaleFields.vue'
import StyleValuePicker from './StyleValuePicker.vue'

const props = defineProps<{
  modelValue: PresentationNode
  catalog: CriteriaCatalog
}>()
const emit = defineEmits<{ 'update:modelValue': [value: PresentationNode] }>()

const STYLE_MODES: readonly StyleMode[] = ['match', 'range', 'scale']

const capabilities = computed(() => capabilitiesFor(props.modelValue.representation))
const numericAttributes = computed(() => numericAttributeOptions(props.catalog))
const legend = computed(() => derivedLegend(props.modelValue))

const emitUpdate = (patch: Partial<PresentationNode>) => emit('update:modelValue', { ...props.modelValue, ...patch })

const updateRule = (index: number, rule: StyleRuleNode) => {
  const stylingRules = [...props.modelValue.stylingRules]
  stylingRules[index] = rule
  emitUpdate({ stylingRules })
}
const removeRule = (index: number) => emitUpdate({ stylingRules: props.modelValue.stylingRules.filter((_, i) => i !== index) })
const moveRule = (index: number, delta: number) => {
  const stylingRules = [...props.modelValue.stylingRules]
  const target = index + delta
  if (target < 0 || target >= stylingRules.length) return
  ;[stylingRules[index], stylingRules[target]] = [stylingRules[target], stylingRules[index]]
  emitUpdate({ stylingRules })
}
const addRule = () => emitUpdate({ stylingRules: [...props.modelValue.stylingRules, mkStyleRule(props.modelValue.representation)] })

const onCapabilityChange = (index: number, capability: string) => {
  const rule = props.modelValue.stylingRules[index]
  updateRule(index, { ...rule, capability })
}
const onModeChange = (index: number, mode: StyleMode) =>
  updateRule(index, withStyleMode(props.modelValue.stylingRules[index], mode))
const onMatchCriteriaChange = (index: number, group: GroupNode) => {
  const rule = props.modelValue.stylingRules[index]
  updateRule(index, { ...rule, matchCriteria: group })
}

const addBand = (index: number) => {
  const rule = props.modelValue.stylingRules[index]
  updateRule(index, { ...rule, rangeBands: [...rule.rangeBands, mkRangeBand()] })
}
const removeBand = (index: number, bandIndex: number) => {
  const rule = props.modelValue.stylingRules[index]
  updateRule(index, { ...rule, rangeBands: rule.rangeBands.filter((_, i) => i !== bandIndex) })
}
const updateBand = (index: number, bandIndex: number, band: RangeBandNode) => {
  const rule = props.modelValue.stylingRules[index]
  const rangeBands = [...rule.rangeBands]
  rangeBands[bandIndex] = band
  updateRule(index, { ...rule, rangeBands })
}

const onDefaultStyleChange = (capability: string, token: string) => {
  const defaultStyle = { ...props.modelValue.defaultStyle }
  if (token === '') delete defaultStyle[capability]
  else defaultStyle[capability] = token
  emitUpdate({ defaultStyle })
}
</script>

<template>
  <div class="style-rule-editor">
    <div class="rule-list">
      <div
        v-for="(rule, index) in modelValue.stylingRules"
        :key="rule.id"
        class="rule-card"
      >
        <div class="rule-top">
          <span class="rule-order">#{{ index + 1 }}</span>
          <select
            class="inp"
            :value="rule.capability"
            @change="onCapabilityChange(index, ($event.target as HTMLSelectElement).value)"
          >
            <option
              v-for="capability in capabilities"
              :key="capability"
              :value="capability"
            >
              {{ capability }}
            </option>
          </select>
          <div class="mode-toggle">
            <button
              v-for="mode in STYLE_MODES"
              :key="mode"
              type="button"
              :class="{ sel: rule.mode === mode }"
              @click="onModeChange(index, mode)"
            >
              {{ mode }}
            </button>
          </div>
          <button
            type="button"
            class="icon-btn move-btn"
            @click="moveRule(index, -1)"
          >
            ↑
          </button>
          <button
            type="button"
            class="icon-btn move-btn"
            @click="moveRule(index, 1)"
          >
            ↓
          </button>
          <button
            type="button"
            class="icon-btn"
            @click="removeRule(index)"
          >
            ✕
          </button>
        </div>

        <template v-if="rule.mode === 'match'">
          <CriteriaTreeBuilder
            v-if="rule.matchCriteria"
            :model-value="rule.matchCriteria"
            :group-kind="isEdgeCapability(rule.capability) ? 'connection' : 'entity'"
            :catalog="catalog"
            is-root
            @update:model-value="onMatchCriteriaChange(index, $event)"
          />
          <label class="value-line">
            value:
            <StyleValuePicker
              :model-value="rule.value"
              @update:model-value="updateRule(index, { ...rule, value: $event || null })"
            />
          </label>
        </template>

        <template v-else-if="rule.mode === 'range'">
          <label class="value-line">
            range_attribute:
            <select
              class="inp"
              :value="rule.rangeAttribute ?? ''"
              @change="updateRule(index, { ...rule, rangeAttribute: ($event.target as HTMLSelectElement).value || null })"
            >
              <option value="" />
              <option
                v-for="attr in numericAttributes"
                :key="attr"
                :value="attr"
              >
                {{ attr }}
              </option>
            </select>
          </label>
          <div
            v-for="(band, bandIndex) in rule.rangeBands"
            :key="band.id"
            class="band-row"
          >
            <input
              class="inp band-input"
              type="number"
              placeholder="-inf"
              :value="band.minimum ?? ''"
              @input="updateBand(index, bandIndex, { ...band, minimum: ($event.target as HTMLInputElement).value === '' ? null : Number(($event.target as HTMLInputElement).value) })"
            >
            <span>to</span>
            <input
              class="inp band-input"
              type="number"
              placeholder="+inf"
              :value="band.maximum ?? ''"
              @input="updateBand(index, bandIndex, { ...band, maximum: ($event.target as HTMLInputElement).value === '' ? null : Number(($event.target as HTMLInputElement).value) })"
            >
            <StyleValuePicker
              :model-value="band.value"
              @update:model-value="updateBand(index, bandIndex, { ...band, value: $event })"
            />
            <button
              type="button"
              class="icon-btn"
              @click="removeBand(index, bandIndex)"
            >
              ✕
            </button>
          </div>
          <button
            type="button"
            class="add-btn"
            @click="addBand(index)"
          >
            + Add band
          </button>
        </template>

        <StyleRuleScaleFields
          v-else
          :model-value="rule"
          :numeric-attributes="numericAttributes"
          @update:model-value="updateRule(index, $event)"
        />
      </div>
    </div>
    <div class="add-row">
      <button
        type="button"
        class="add-btn"
        @click="addRule"
      >
        + Add style rule
      </button>
    </div>

    <div class="card">
      <b>Default style (fallback when no rule matches)</b>
      <div
        v-for="capability in capabilities"
        :key="capability"
        class="default-row"
      >
        <span>{{ capability }}</span>
        <StyleValuePicker
          :model-value="modelValue.defaultStyle[capability] ?? null"
          allow-scale-endpoints
          clearable
          @update:model-value="onDefaultStyleChange(capability, $event)"
        />
      </div>
    </div>

    <div class="card">
      <div class="legend-header">
        <b>Legend</b>
        <span class="pill">derived — not authored</span>
      </div>
      <p
        v-if="legend.length === 0"
        class="placeholder"
      >
        No style tokens in use yet.
      </p>
      <div
        v-else
        class="legend"
      >
        <span
          v-for="entry in legend"
          :key="entry.token"
          class="legend-item"
        >
          <span
            class="swatch"
            :style="{ background: tokenColor(entry.token) }"
          />
          {{ entry.token }} ({{ entry.usageCount }})
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.rule-list { display: flex; flex-direction: column; gap: 8px; }
.rule-card { border: 1px solid #d1d5db; border-radius: 8px; padding: 10px; background: #fff; margin: 6px 0; }
.rule-top { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 8px; }
.rule-order { font-family: monospace; font-size: 11px; color: #9ca3af; background: #f3f4f6; border-radius: 5px; padding: 2px 6px; }
.mode-toggle { display: inline-flex; border: 1px solid #d1d5db; border-radius: 99px; overflow: hidden; }
.mode-toggle button { appearance: none; border: none; background: #fff; color: #6b7280; font-size: 11px; font-weight: 700; padding: 3px 10px; cursor: pointer; }
.mode-toggle button.sel { background: #6366f1; color: #fff; }
.value-line { display: flex; align-items: center; gap: 6px; font-size: 12.5px; color: #6b7280; margin-top: 8px; }
.band-row { display: flex; gap: 6px; align-items: center; margin: 4px 0; }
.band-input { width: 72px; }
.inp { padding: 4px 6px; border-radius: 5px; border: 1px solid #d1d5db; font-size: 12.5px; font-family: inherit; }
.icon-btn { appearance: none; border: none; background: none; color: #9ca3af; cursor: pointer; font-size: 15px; line-height: 1; padding: 2px 5px; border-radius: 5px; }
.icon-btn:hover { background: #fee2e2; color: #991b1b; }
.move-btn { color: #6b7280; font-size: 13px; }
.move-btn:hover { background: #eef2ff; color: #4338ca; }
.add-row { margin-top: 8px; }
.add-btn { appearance: none; border: 1px dashed #d1d5db; background: #fff; color: #6b7280; border-radius: 7px; padding: 5px 10px; font-size: 12px; font-weight: 600; cursor: pointer; }
.add-btn:hover { border-color: #6366f1; color: #4338ca; }
.card { border: 1px solid #d1d5db; border-radius: 10px; padding: 12px; margin-top: 12px; }
.default-row {
  display: grid; grid-template-columns: 140px auto; align-items: center;
  column-gap: 16px; margin: 6px 0; font-size: 12.5px;
}
.default-row > span:first-child { color: #374151; }
.legend-header { display: flex; align-items: center; justify-content: space-between; }
.pill { font-size: 11px; font-weight: 600; color: #6b7280; background: #f3f4f6; border-radius: 99px; padding: 2px 8px; }
.legend { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 8px; }
.legend-item { display: flex; align-items: center; gap: 6px; font-size: 12px; color: #6b7280; }
.swatch { width: 12px; height: 12px; border-radius: 3px; display: inline-block; border: 1px solid rgba(0,0,0,.15); }
.placeholder { font-size: 12.5px; color: #6b7280; margin: 4px 0; }
</style>
