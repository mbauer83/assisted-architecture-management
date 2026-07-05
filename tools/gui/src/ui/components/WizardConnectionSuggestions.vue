<script setup lang="ts">
import type { WizardSuggestion } from '../composables/useWizardSession'

defineProps<{ suggestions: WizardSuggestion[]; busy?: boolean; hideLater?: boolean }>()
const emit = defineEmits<{
  accept: [suggestion: WizardSuggestion]
  dismiss: [id: string]
  later: [id: string]
}>()
</script>

<template>
  <ul
    v-if="suggestions.length"
    class="suggestion-list"
  >
    <li
      v-for="s in suggestions"
      :key="s.id"
      class="suggestion-row"
    >
      <span class="suggestion-summary">{{ s.summary }}</span>
      <span class="suggestion-actions">
        <button
          type="button"
          class="btn-accept"
          :disabled="busy"
          @click="emit('accept', s)"
        >
          Accept
        </button>
        <button
          v-if="!hideLater"
          type="button"
          class="btn-later"
          :disabled="busy"
          @click="emit('later', s.id)"
        >
          Later
        </button>
        <button
          type="button"
          class="btn-dismiss"
          :disabled="busy"
          @click="emit('dismiss', s.id)"
        >
          Dismiss
        </button>
      </span>
    </li>
  </ul>
  <p
    v-else
    class="suggestion-empty"
  >
    No connection suggestions yet.
  </p>
</template>

<style scoped>
.suggestion-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.suggestion-row {
  display: flex; align-items: center; justify-content: space-between; gap: 12px;
  padding: 8px 12px; border: 1px solid #e5e7eb; border-radius: 6px; background: #fafafa;
}
.suggestion-summary { font-size: 13px; color: #374151; }
.suggestion-actions { display: flex; gap: 6px; flex-shrink: 0; }
.suggestion-actions button {
  font-size: 12px; padding: 4px 10px; border-radius: 5px; cursor: pointer; border: 1px solid transparent;
}
.suggestion-actions button:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-accept { background: #16a34a; color: white; }
.btn-later { background: white; border-color: #d1d5db; color: #4b5563; }
.btn-dismiss { background: white; border-color: #fecaca; color: #dc2626; }
.suggestion-empty { color: #9ca3af; font-size: 13px; }
</style>
