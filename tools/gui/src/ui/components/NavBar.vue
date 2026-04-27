<script setup lang="ts">
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { computed, inject, ref } from 'vue'
import { Effect } from 'effect'
import { modelServiceKey } from '../keys'
import ArchimateTypeGlyph from './ArchimateTypeGlyph.vue'
import type { EnterpriseSyncStatus, SearchHit } from '../../domain'
import { readErrorMessage } from '../lib/errors'

type SaveMode = 'engagement-save' | 'enterprise-save' | 'enterprise-submit' | 'enterprise-withdraw'

defineProps<{
  adminMode: boolean
  readOnly: boolean
  engDirty: boolean
  entStatus: EnterpriseSyncStatus | null
}>()

const emit = defineEmits<{ openSaveDialog: [mode: SaveMode] }>()

const svc = inject(modelServiceKey)!
const route = useRoute()
const router = useRouter()

const browseTo = computed(() => {
  const q: Record<string, string> = {}
  const { domain, view, type } = route.query
  if (domain) q.domain = domain as string
  if (view) q.view = view as string
  if (type) q.type = type as string
  return Object.keys(q).length ? { path: '/entities', query: q } : '/entities'
})

const searchQuery = ref('')
type SearchDropdownHit = SearchHit | {
  record_type: 'entity'
  artifact_id: string
  name: string
  artifact_type: string
}

const searchHits = ref<SearchDropdownHit[]>([])
const showDropdown = ref(false)
let debounceTimer: ReturnType<typeof setTimeout> | null = null

const onSearchInput = () => {
  const q = searchQuery.value.trim()
  if (debounceTimer) clearTimeout(debounceTimer)
  if (q.length < 2) { searchHits.value = []; showDropdown.value = false; return }
  debounceTimer = setTimeout(() => {
    void Effect.runPromise(svc.search(q, 20))
      .then((result) => {
        const raw = result.hits
        const seen = new Set<string>()
        const resolved: SearchDropdownHit[] = []
        for (const hit of raw) {
          if (hit.record_type === 'connection') {
            for (const id of [hit.source, hit.target].filter((value): value is string => Boolean(value))) {
              if (!seen.has(id)) {
                seen.add(id)
                resolved.push({ record_type: 'entity', artifact_id: id, name: id, artifact_type: 'generic' })
              }
            }
          } else if (!seen.has(hit.artifact_id)) {
            seen.add(hit.artifact_id)
            resolved.push(hit)
          }
        }
        const entityNames = new Map(resolved.map((hit) => [hit.artifact_id, hit.name]))
        searchHits.value = resolved.slice(0, 12).map((hit) => ({
          ...hit,
          name: entityNames.get(hit.artifact_id) ?? hit.artifact_id,
        }))
        showDropdown.value = searchHits.value.length > 0
      })
      .catch((error: unknown) => {
        console.error('Search failed', readErrorMessage(error))
        searchHits.value = []
        showDropdown.value = false
      })
  }, 280)
}

const selectHit = (hit: SearchDropdownHit) => {
  showDropdown.value = false; searchQuery.value = ''; searchHits.value = []
  if (hit.record_type === 'diagram') void router.push({ path: '/diagram', query: { id: hit.artifact_id } })
  else void router.push({ path: '/entity', query: { id: hit.artifact_id } })
}
const submitSearch = () => {
  const q = searchQuery.value.trim()
  if (!q) return
  showDropdown.value = false
  void router.push({ path: '/search', query: { q } })
  searchQuery.value = ''; searchHits.value = []
}
const onSearchBlur = () => { setTimeout(() => { showDropdown.value = false }, 180) }
const onSearchFocus = () => { if (searchHits.value.length > 0) showDropdown.value = true }
const hitGlyphType = (hit: SearchDropdownHit) =>
  (hit.record_type === 'diagram' || hit.record_type === 'connection') ? 'generic' : hit.artifact_type
const hitTypeLabel = (hit: SearchDropdownHit) => (hit.artifact_type || hit.record_type || '').replace(/^archimate[-_]/i, '')
</script>

<template>
  <header class="nav">
    <RouterLink
      class="nav__brand"
      to="/"
    >
      Architecture Repository
    </RouterLink>
    <div class="nav__sections">
      <div class="nav__section">
        <span class="nav__section-label">Engagement</span>
        <nav
          class="nav__links"
          aria-label="Engagement"
        >
          <button
            v-if="!readOnly"
            class="nav__save-btn"
            :class="{ 'nav__save-btn--clean': !engDirty }"
            :disabled="!engDirty"
            @click="emit('openSaveDialog', 'engagement-save')"
          >
            ● Save
          </button>
          <RouterLink :to="browseTo">
            Browse
          </RouterLink>
          <RouterLink to="/documents">
            Documents
          </RouterLink>
          <RouterLink to="/diagrams">
            Diagrams
          </RouterLink>
          <RouterLink
            to="/promote"
            class="nav__promote"
          >
            ↑ Promote
          </RouterLink>
        </nav>
      </div>
      <div
        class="nav__divider"
        aria-hidden="true"
      />
      <div class="nav__section">
        <span class="nav__section-label nav__section-label--global">Global</span>
        <nav
          class="nav__links"
          aria-label="Global"
        >
          <template v-if="entStatus && adminMode">
            <button
              v-if="entStatus.has_uncommitted_changes"
              class="nav__save-btn nav__save-btn--global"
              @click="emit('openSaveDialog', 'enterprise-save')"
            >
              ● Save
            </button>
            <button
              v-if="entStatus.status === 'accumulating'"
              class="nav__action-btn"
              @click="emit('openSaveDialog', 'enterprise-submit')"
            >
              Submit
            </button>
            <button
              v-if="entStatus.status === 'pending'"
              class="nav__action-btn nav__action-btn--warn"
              @click="emit('openSaveDialog', 'enterprise-withdraw')"
            >
              Discard
            </button>
            <span
              v-if="entStatus.status !== 'synced'"
              class="nav__ent-status"
              :class="`nav__ent-status--${entStatus.status}`"
            >{{ entStatus.label }}</span>
          </template>
          <RouterLink to="/global/entities">
            Browse
          </RouterLink>
          <RouterLink to="/global/diagrams">
            Diagrams
          </RouterLink>
        </nav>
      </div>
    </div>
    <form
      class="nav__search"
      @submit.prevent="submitSearch"
    >
      <input
        v-model="searchQuery"
        class="nav__search-input"
        type="search"
        placeholder="Search…"
        aria-label="Search"
        autocomplete="off"
        @input="onSearchInput"
        @focus="onSearchFocus"
        @blur="onSearchBlur"
      >
      <div
        v-if="showDropdown"
        class="nav__search-dropdown"
      >
        <button
          v-for="hit in searchHits"
          :key="hit.artifact_id"
          class="nav__search-item"
          @mousedown.prevent="selectHit(hit)"
        >
          <ArchimateTypeGlyph
            :type="hitGlyphType(hit)"
            :size="14"
            class="nav__search-item-glyph"
          />
          <span class="nav__search-item-name">{{ hit.name || hit.artifact_id }}</span>
          <span class="nav__search-item-type">{{ hitTypeLabel(hit) }}</span>
        </button>
      </div>
    </form>
  </header>
</template>

<style scoped>
.nav { display: flex; align-items: center; gap: 20px; padding: 0 24px; height: 48px; background: #1e293b; color: #f8fafc; position: sticky; top: 0; z-index: 10; }
.nav__brand { font-weight: 600; font-size: 15px; color: #f8fafc; white-space: nowrap; flex-shrink: 0; }
.nav__brand:hover { text-decoration: none; color: #93c5fd; }
.nav__sections { display: flex; align-items: center; gap: 0; flex: 1; }
.nav__section { display: flex; align-items: center; gap: 8px; }
.nav__section-label { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: .07em; color: #64748b; white-space: nowrap; padding: 0 4px; }
.nav__section-label--global { color: #f59e0b; }
.nav__divider { width: 1px; height: 20px; background: #334155; margin: 0 12px; }
.nav__links { display: flex; gap: 4px; }
.nav__links a { color: #b0bec5; font-size: 13px; padding: 4px 8px; border-radius: 4px; }
.nav__links a.router-link-active { color: #f8fafc; font-weight: 500; background: #2d3f55; }
.nav__links a:hover { color: #f1f5f9; text-decoration: none; background: #263347; }
.nav__promote { color: #fbbf24 !important; }
.nav__promote:hover { color: #f59e0b !important; }
.nav__save-btn { background: #166534; color: #bbf7d0; border: none; border-radius: 4px; font-size: 12px; font-weight: 600; padding: 3px 9px; cursor: pointer; white-space: nowrap; }
.nav__save-btn:hover:not(:disabled) { background: #15803d; }
.nav__save-btn:disabled { cursor: not-allowed; }
.nav__save-btn--clean { background: #1e3a2a; color: #4b7a5c; opacity: 0.6; }
.nav__save-btn--global { background: #78350f; color: #fde68a; }
.nav__save-btn--global:hover:not(:disabled) { background: #92400e; }
.nav__action-btn { background: transparent; color: #93c5fd; border: 1px solid #475569; border-radius: 4px; font-size: 12px; padding: 3px 9px; cursor: pointer; white-space: nowrap; }
.nav__action-btn:hover { background: #263347; }
.nav__action-btn--warn { color: #fca5a5; border-color: #7f1d1d; }
.nav__action-btn--warn:hover { background: #450a0a; }
.nav__ent-status { font-size: 11px; padding: 2px 7px; border-radius: 10px; font-weight: 600; }
.nav__ent-status--accumulating { background: #1e3a5f; color: #93c5fd; }
.nav__ent-status--pending { background: #3b0764; color: #d8b4fe; }
.nav__search { margin-left: auto; display: flex; align-items: center; flex-shrink: 0; position: relative; }
.nav__search-input { width: clamp(140px, 18vw, 260px); padding: 5px 10px; border-radius: 5px; border: 1px solid #334155; background: #0f172a; color: #f1f5f9; font-size: 13px; outline: none; transition: width .2s, border-color .15s; }
.nav__search-input::placeholder { color: #64748b; }
.nav__search-input:focus { width: clamp(180px, 22vw, 340px); border-color: #475569; background: #1e293b; }
.nav__search-input::-webkit-search-cancel-button { display: none; }
.nav__search-dropdown { position: absolute; top: calc(100% + 4px); right: 0; width: 100%; min-width: 0; background: #fff; border: 1px solid #e2e8f0; border-radius: 6px; box-shadow: 0 8px 24px rgba(0,0,0,.18); max-height: 320px; overflow-y: auto; z-index: 100; }
.nav__search-item { display: flex; align-items: flex-start; gap: 7px; width: 100%; padding: 8px 12px; border: none; background: none; cursor: pointer; text-align: left; font-size: 13px; color: #1a1a1a; }
.nav__search-item:hover { background: #f1f5f9; }
.nav__search-item-glyph { flex-shrink: 0; color: #6b7280; margin-top: 1px; }
.nav__search-item-name { flex: 1; font-weight: 500; }
.nav__search-item-type { font-size: 11px; color: #64748b; white-space: nowrap; flex-shrink: 0; }
</style>
