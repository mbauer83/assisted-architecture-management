<script setup lang="ts">
// Explains *why* some assurance content is hidden: it is classified above the
// store's TLP ceiling. This is feature-correctness (confidentiality), not an error —
// the message names the ceiling and reassures rather than alarms.
import { computed, onMounted, ref } from 'vue'

withDefaults(defineProps<{ kind?: string }>(), { kind: 'items' })

const ceiling = ref('')
const ceilingLabel = computed(() => (ceiling.value ? ` (${ceiling.value})` : ''))

onMounted(async () => {
  try {
    const resp = await fetch('/api/assurance/status')
    if (resp.ok) {
      const body = await resp.json() as { max_classification?: unknown }
      if (typeof body.max_classification === 'string') ceiling.value = body.max_classification
    }
  } catch {
    /* ceiling label is best-effort; the explanation stands without it */
  }
})
</script>

<template>
  <p class="withheld-notice">
    <span
      class="withheld-icon"
      aria-hidden="true"
    >🔒</span>
    Some {{ kind }} are hidden because they are classified above your current access
    ceiling{{ ceilingLabel }}. This is the confidentiality policy working as intended.
    To view higher-classification content, raise the assurance store's
    <code>max_classification</code> setting.
  </p>
</template>

<style scoped>
.withheld-notice {
  display: flex;
  align-items: baseline;
  gap: 6px;
  font-size: 12px;
  color: #92400e;
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-radius: 6px;
  padding: 8px 10px;
  margin: 8px 0 0;
}
.withheld-icon { flex-shrink: 0; }
.withheld-notice code {
  font-size: 11px;
  background: #fef3c7;
  padding: 1px 4px;
  border-radius: 3px;
}
</style>
