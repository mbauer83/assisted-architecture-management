<script setup lang="ts">
import { RouterLink, RouterView, useRouter } from 'vue-router'
import { inject, provide, ref, onMounted, onUnmounted, computed } from 'vue'
import { Effect } from 'effect'
import { modelServiceKey } from './keys'
import ArchimateTypeGlyph from './components/ArchimateTypeGlyph.vue'
import ToastStack from './components/ToastStack.vue'

const svc = inject(modelServiceKey)!
const router = useRouter()
const adminMode = ref(false)
const readOnly = ref(false)
const writeBlocked = ref(false)

const toasts = ref<Array<{id: number, message: string, type: 'info'|'warn'|'error'}>>([])
let toastCounter = 0

const addToast = (message: string, type: 'info'|'warn'|'error' = 'info', durationMs = 4000) => {
  const id = ++toastCounter
  toasts.value.push({ id, message, type })
  setTimeout(() => { toasts.value = toasts.value.filter(t => t.id !== id) }, durationMs)
}

const anyWriteBlocked = computed(() => readOnly.value || writeBlocked.value)

let eventSource: EventSource | null = null

onMounted(() => {
  Effect.runPromise(svc.getServerInfo())
    .then((info: any) => {
      adminMode.value = Boolean(info?.admin_mode)
      readOnly.value = Boolean(info?.read_only)
    })
    .catch(() => {})

  // Subscribe to SSE events
  try {
    eventSource = new EventSource('/api/events')

    eventSource.addEventListener('write_block_changed', (e) => {
      const data = JSON.parse(e.data)
      writeBlocked.value = data.blocked
      addToast(
        data.blocked ? 'Sync in progress — writes paused' : 'Sync complete — writes resumed',
        data.blocked ? 'warn' : 'info'
      )
    })

    eventSource.addEventListener('git_sync_started', () => {
      addToast('Pulling updates…', 'info')
    })

    eventSource.addEventListener('git_sync_completed', (e) => {
      const data = JSON.parse(e.data)
      addToast(`Pulled ${data.commits_pulled} commit(s)`, 'info')
    })

    eventSource.addEventListener('git_sync_failed', (e) => {
      const data = JSON.parse(e.data)
      addToast(
        `Sync failed: ${data.error}. Writes resume in ${data.auto_unblock_in_seconds}s`,
        'error',
        7000
      )
    })
  } catch (err) {
    console.error('Failed to connect to event stream:', err)
  }

  provide('writeBlocked', anyWriteBlocked)
})

onUnmounted(() => {
  if (eventSource) {
    eventSource.close()
  }
})

const searchQuery = ref('')
const searchHits = ref<any[]>([])
const showDropdown = ref(false)
let debounceTimer: ReturnType<typeof setTimeout> | null = null

const onSearchInput = () => {
  const q = searchQuery.value.trim()
  if (debounceTimer) clearTimeout(debounceTimer)
  if (q.length < 2) { searchHits.value = []; showDropdown.value = false; return }
  debounceTimer = setTimeout(() => {
    Effect.runPromise(svc.search(q, 20))
      .then((result: any) => {
        const raw: any[] = result.hits ?? []
        const seen = new Set<string>()
        const resolved: any[] = []
        for (const hit of raw) {
          if (hit.record_type === 'connection') {
            for (const id of [hit.source, hit.target].filter(Boolean)) {
              if (!seen.has(id)) { seen.add(id); resolved.push({ _resolvedFrom: hit.artifact_id, _resolvedId: id, record_type: 'entity-ref', artifact_id: id, name: id, artifact_type: 'generic' }) }
            }
          } else if (!seen.has(hit.artifact_id)) {
            seen.add(hit.artifact_id); resolved.push(hit)
          }
        }
        // Back-fill names for entity-refs that already appear as proper entity hits
        const entityNames = new Map(resolved.filter(h => h.record_type !== 'entity-ref').map(h => [h.artifact_id, h.name]))
        searchHits.value = resolved.slice(0, 12).map(h => h.record_type === 'entity-ref' ? { ...h, name: entityNames.get(h.artifact_id) || h.artifact_id, record_type: 'entity' } : h)
        showDropdown.value = searchHits.value.length > 0
      })
      .catch(() => { searchHits.value = []; showDropdown.value = false })
  }, 280)
}

const selectHit = (hit: any) => {
  showDropdown.value = false
  searchQuery.value = ''
  searchHits.value = []
  if (hit.record_type === 'diagram') {
    router.push({ path: '/diagram', query: { id: hit.artifact_id } })
  } else {
    router.push({ path: '/entity', query: { id: hit.artifact_id } })
  }
}

const submitSearch = () => {
  const q = searchQuery.value.trim()
  if (!q) return
  showDropdown.value = false
  router.push({ path: '/search', query: { q } })
  searchQuery.value = ''
  searchHits.value = []
}

const onSearchBlur = () => {
  setTimeout(() => { showDropdown.value = false }, 180)
}
const onSearchFocus = () => {
  if (searchHits.value.length > 0) showDropdown.value = true
}

const hitGlyphType = (hit: any): string => {
  if (hit.record_type === 'diagram') return 'generic'
  if (hit.record_type === 'connection') return 'generic'
  return hit.artifact_type ?? 'generic'
}

const hitTypeLabel = (hit: any): string => {
  const raw: string = hit.artifact_type || hit.record_type || ''
  return raw.replace(/^archimate[-_]/i, '')
}
</script>

<template>
  <header class="nav">
    <RouterLink class="nav__brand" to="/">Architecture Repository</RouterLink>

    <div class="nav__sections">
      <!-- Engagement section -->
      <div class="nav__section">
        <span class="nav__section-label">Engagement</span>
        <nav class="nav__links" aria-label="Engagement">
          <RouterLink to="/entities">Browse</RouterLink>
          <RouterLink to="/documents">Documents</RouterLink>
          <RouterLink to="/diagrams">Diagrams</RouterLink>
          <RouterLink to="/promote" class="nav__promote">↑ Promote</RouterLink>
        </nav>
      </div>

      <div class="nav__divider" aria-hidden="true"></div>

      <!-- Global (enterprise) section -->
      <div class="nav__section">
        <span class="nav__section-label nav__section-label--global">Global</span>
        <nav class="nav__links" aria-label="Global">
          <RouterLink to="/global/entities">Browse</RouterLink>
          <RouterLink to="/global/diagrams">Diagrams</RouterLink>
        </nav>
      </div>
    </div>

    <!-- Persistent search bar with live dropdown -->
    <form class="nav__search" @submit.prevent="submitSearch">
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
      />
      <div v-if="showDropdown" class="nav__search-dropdown">
        <button
          v-for="hit in searchHits"
          :key="hit.artifact_id"
          class="nav__search-item"
          @mousedown.prevent="selectHit(hit)"
        >
          <ArchimateTypeGlyph :type="hitGlyphType(hit)" :size="14" class="nav__search-item-glyph" />
          <span class="nav__search-item-name">{{ hit.name || hit.artifact_id }}</span>
          <span class="nav__search-item-type">{{ hitTypeLabel(hit) }}</span>
        </button>
      </div>
    </form>
  </header>

  <!-- Admin mode banner — visible in all views when --admin-mode is active -->
  <output v-if="adminMode" class="admin-banner">
    <strong>Admin mode</strong> — writes to both repositories are permitted.
    Remember to <code>git commit</code> in the enterprise repository before
    ending this session or restarting in normal mode.
  </output>

  <!-- Read-only mode banner — visible when --read-only is active -->
  <output v-if="readOnly" class="readonly-banner">
    <strong>Read-only mode</strong> — write operations are disabled.
  </output>

  <main class="main">
    <RouterView />
  </main>

  <ToastStack :toasts="toasts" />
</template>

<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: system-ui, -apple-system, sans-serif;
  font-size: 14px;
  line-height: 1.5;
  color: #1a1a1a;
  background: #f5f5f5;
}

a { color: #2563eb; text-decoration: none; }
a:hover { text-decoration: underline; }

pre, code {
  font-family: 'Cascadia Code', 'Fira Code', monospace;
  font-size: 13px;
}
</style>

<style scoped>
.nav {
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 0 24px;
  height: 48px;
  background: #1e293b;
  color: #f8fafc;
  position: sticky;
  top: 0;
  z-index: 10;
}

.nav__brand {
  font-weight: 600;
  font-size: 15px;
  color: #f8fafc;
  white-space: nowrap;
  flex-shrink: 0;
}
.nav__brand:hover { text-decoration: none; color: #93c5fd; }

.nav__sections {
  display: flex;
  align-items: center;
  gap: 0;
  flex: 1;
}

.nav__section {
  display: flex;
  align-items: center;
  gap: 8px;
}

.nav__section-label {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .07em;
  color: #64748b;
  white-space: nowrap;
  padding: 0 4px;
}

.nav__section-label--global {
  color: #f59e0b;
}

.nav__divider {
  width: 1px;
  height: 20px;
  background: #334155;
  margin: 0 12px;
}

.nav__links {
  display: flex;
  gap: 4px;
}

.nav__links a {
  color: #b0bec5;
  font-size: 13px;
  padding: 4px 8px;
  border-radius: 4px;
}
.nav__links a.router-link-active {
  color: #f8fafc;
  font-weight: 500;
  background: #2d3f55;
}
.nav__links a:hover { color: #f1f5f9; text-decoration: none; background: #263347; }
.nav__promote { color: #fbbf24 !important; }
.nav__promote:hover { color: #f59e0b !important; }

.nav__search { margin-left: auto; display: flex; align-items: center; flex-shrink: 0; position: relative; }
.nav__search-input {
  width: clamp(140px, 18vw, 260px);
  padding: 5px 10px;
  border-radius: 5px;
  border: 1px solid #334155;
  background: #0f172a;
  color: #f1f5f9;
  font-size: 13px;
  outline: none;
  transition: width .2s, border-color .15s;
}
.nav__search-input::placeholder { color: #64748b; }
.nav__search-input:focus {
  width: clamp(180px, 22vw, 340px);
  border-color: #475569;
  background: #1e293b;
}
.nav__search-input::-webkit-search-cancel-button { display: none; }

.nav__search-dropdown {
  position: absolute;
  top: calc(100% + 4px);
  right: 0;
  width: 100%;
  min-width: 0;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  box-shadow: 0 8px 24px rgba(0,0,0,.18);
  max-height: 320px;
  overflow-y: auto;
  z-index: 100;
}
.nav__search-item-glyph { flex-shrink: 0; color: #6b7280; margin-top: 1px; }

.nav__search-item {
  display: flex;
  align-items: flex-start;
  gap: 7px;
  width: 100%;
  padding: 8px 12px;
  border: none;
  background: none;
  cursor: pointer;
  text-align: left;
  font-size: 13px;
  color: #1a1a1a;
}
.nav__search-item:hover { background: #f1f5f9; }
.nav__search-item-name { flex: 1; font-weight: 500; }
.nav__search-item-type { font-size: 11px; color: #64748b; white-space: nowrap; flex-shrink: 0; }

.admin-banner {
  background: #7c2d12;
  color: #fed7aa;
  padding: 7px 24px;
  font-size: 13px;
  line-height: 1.5;
  border-bottom: 2px solid #ea580c;
}
.admin-banner strong { color: #fb923c; font-weight: 700; }
.admin-banner code {
  background: rgba(0,0,0,.25);
  border-radius: 3px;
  padding: 1px 5px;
  font-family: monospace;
  font-size: 12px;
  color: #fed7aa;
}

.readonly-banner {
  background: #1e3a5f;
  color: #bfdbfe;
  padding: 7px 24px;
  font-size: 13px;
  line-height: 1.5;
  border-bottom: 2px solid #3b82f6;
}
.readonly-banner strong { color: #93c5fd; font-weight: 700; }

.main {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;
}
</style>
