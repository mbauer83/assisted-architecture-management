<script setup lang="ts">
import { ref, inject } from 'vue'
import { Effect } from 'effect'
import { modelServiceKey } from '../keys'
import type { EntityList } from '../../domain'

const props = defineProps<{ placeholder?: string; typePrefix?: string; artifactType?: string }>()
const emit = defineEmits<{ select: [id: string, name: string] }>()

const svc = inject(modelServiceKey)!
const query = ref('')
const results = ref<EntityList['items']>([])
const showDropdown = ref(false)
const loading = ref(false)

let debounceTimer: ReturnType<typeof setTimeout> | null = null

const doSearch = () => {
  const q = query.value.trim()
  if (q.length < 2) { results.value = []; return }
  loading.value = true
  // Use artifactType prop (preferred) or fall back to legacy typePrefix for backward compat
  const filterType = props.artifactType ?? undefined
  Effect.runPromise(svc.listEntities({ limit: 200, artifactType: filterType })).then((list) => {
    const lc = q.toLowerCase()
    results.value = list.items.filter((e) => {
      const friendly = e.name.toLowerCase()
      const randomPart = e.artifact_id.split('.')[1]?.toLowerCase() ?? ''
      return friendly.includes(lc) || randomPart.includes(lc) || e.artifact_id.toLowerCase().includes(lc)
    }).slice(0, 10)
    loading.value = false
    showDropdown.value = true
  }).catch(() => { loading.value = false })
}

const onInput = () => {
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(doSearch, 200)
}

const selectEntity = (e: EntityList['items'][number]) => {
  emit('select', e.artifact_id, e.name)
  query.value = ''
  results.value = []
  showDropdown.value = false
}

const friendlyName = (id: string) => {
  const parts = id.split('.')
  return parts.length > 2 ? parts.slice(2).join(' ').replace(/-/g, ' ') : id
}

const onBlur = () => {
  // Delay to allow click on dropdown item
  setTimeout(() => { showDropdown.value = false }, 200)
}
</script>

<template>
  <div class="search-wrapper">
    <input
      v-model="query"
      class="search-input"
      type="text"
      :placeholder="placeholder ?? 'Search entities by name or ID...'"
      @input="onInput"
      @focus="showDropdown = results.length > 0"
      @blur="onBlur"
    />
    <div v-if="showDropdown && results.length" class="dropdown">
      <button
        v-for="e in results" :key="e.artifact_id"
        class="dropdown-item"
        @mousedown.prevent="selectEntity(e)"
      >
        <span class="item-name">{{ e.name || friendlyName(e.artifact_id) }}</span>
        <span v-if="e.is_global" class="item-global">global</span>
        <span class="item-type">{{ e.artifact_type }}</span>
        <span class="item-id">{{ e.artifact_id.split('.')[1] }}</span>
      </button>
    </div>
    <div v-else-if="showDropdown && query.length >= 2 && !loading" class="dropdown">
      <div class="dropdown-empty">No matches</div>
    </div>
  </div>
</template>

<style scoped>
.search-wrapper { position: relative; flex: 1; }
.search-input {
  width: 100%; padding: 7px 12px; border-radius: 6px; border: 1px solid #d1d5db;
  font-size: 13px; outline: none;
}
.search-input:focus { border-color: #2563eb; box-shadow: 0 0 0 3px rgba(37,99,235,.15); }

.dropdown {
  position: absolute; top: 100%; left: 0; right: 0; z-index: 50;
  background: white; border: 1px solid #e5e7eb; border-radius: 6px;
  box-shadow: 0 4px 12px rgba(0,0,0,.12); max-height: 240px; overflow-y: auto; margin-top: 2px;
}
.dropdown-item {
  display: flex; gap: 8px; align-items: baseline; width: 100%; padding: 8px 12px;
  border: none; background: none; cursor: pointer; text-align: left; font-size: 13px;
}
.dropdown-item:hover { background: #f3f4f6; }
.item-name { font-weight: 500; flex: 1; }
.item-global {
  font-size: 10px; font-weight: 600; padding: 0 5px;
  background: #fef3c7; color: #92400e; border: 1px solid #fde68a; border-radius: 3px;
  flex-shrink: 0;
}
.item-type { font-size: 11px; color: #6b7280; }
.item-id { font-size: 11px; color: #9ca3af; font-family: monospace; }
.dropdown-empty { padding: 12px; color: #6b7280; font-size: 13px; text-align: center; }
</style>
