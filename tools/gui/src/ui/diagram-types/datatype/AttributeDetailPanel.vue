<script setup lang="ts">
import type { AttributeDetail } from './attributeSelection'

defineProps<{ detail: AttributeDetail }>()
defineEmits<{ close: [] }>()
</script>

<template>
  <div class="ent-det">
    <div class="det-hdr">
      <span class="det-name">{{ detail.name }}</span>
      <button
        class="det-close"
        @click="$emit('close')"
      >
        ×
      </button>
    </div>
    <div class="det-chips">
      <span class="chip chip-type">attribute</span>
      <span
        v-for="badge in detail.badges"
        :key="badge"
        class="chip chip-key"
      >{{ badge }}</span>
    </div>
    <dl class="attr-fields">
      <template v-if="detail.typeLabel">
        <dt>Type</dt><dd>{{ detail.typeLabel }}</dd>
      </template>
      <template v-if="detail.multiplicity">
        <dt>Multiplicity</dt><dd>{{ detail.multiplicity }}</dd>
      </template>
      <template v-if="detail.optional">
        <dt>Optional</dt><dd>yes</dd>
      </template>
      <template v-if="detail.default">
        <dt>Default</dt><dd>{{ detail.default }}</dd>
      </template>
      <template v-if="detail.role">
        <dt>Role</dt><dd>{{ detail.role }}</dd>
      </template>
      <template v-if="detail.provenance">
        <dt>Provenance</dt><dd>{{ detail.provenance }}</dd>
      </template>
    </dl>
    <div class="attr-owner">
      on {{ detail.ownerLabel }}
    </div>
  </div>
</template>

<style scoped>
.ent-det { border-top: 1px solid #e5e7eb; padding: 12px; }
.det-hdr { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.det-name { font-weight: 600; font-size: 14px; color: #111827; }
.det-close { border: none; background: none; font-size: 18px; line-height: 1; cursor: pointer; color: #9ca3af; }
.det-close:hover { color: #374151; }
.det-chips { display: flex; flex-wrap: wrap; gap: 6px; margin: 8px 0; }
.chip { font-size: 11px; padding: 2px 8px; border-radius: 999px; background: #f3f4f6; color: #374151; }
.chip-type { background: #e0e7ff; color: #3730a3; }
.chip-key { background: #fef3c7; color: #92400e; }
.attr-fields { display: grid; grid-template-columns: auto 1fr; gap: 4px 10px; margin: 0; font-size: 12px; }
.attr-fields dt { color: #6b7280; font-weight: 500; }
.attr-fields dd { margin: 0; color: #111827; word-break: break-word; }
.attr-owner { margin-top: 10px; font-size: 11px; color: #9ca3af; }
</style>
