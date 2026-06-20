<script setup lang="ts">
import { ref, inject, watch, computed, onUnmounted } from 'vue'
import { Effect, Exit } from 'effect'
import { modelServiceKey } from '../keys'
import { useEntityFilters } from '../composables/useEntityFilters'
import type { EntityDisplayInfo, ReferenceSearchHit } from '../../domain'
import ArchimateTypeGlyph from './ArchimateTypeGlyph.vue'
import { toGlyphKey } from '../lib/glyphKey'
import {
  calcHasStageUI,
  calcCanGoBack,
  calcCanGoForward,
} from './EntityPickerInput.helpers'
import type { WidenableTo } from './EntityPickerInput.helpers'

type Stage = 'scope' | 'entity-type'

const props = defineProps<{
  excludedIds?: Set<string>
  placeholder?: string
  fixedDomains?: string[]
  fixedEntityTypes?: string[]
  widenableTo?: WidenableTo
  acceptedTypes?: Set<string>
  diagramType?: string
}>()
const emit = defineEmits<{ select: [entity: EntityDisplayInfo] }>()

const svc = inject(modelServiceKey)!
const { selectedDomains, selectedEntityTypes, domainOptions, availableEntityTypes, impliedDomains, toggle } =
  useEntityFilters({ fixedEntityTypes: props.fixedEntityTypes })

const query = ref('')
const results = ref<ReferenceSearchHit[]>([])
const open = ref(false)
const busy = ref(false)
const activeResultIdx = ref(-1)
const inputRef = ref<HTMLInputElement | null>(null)
const wrapRef = ref<HTMLElement | null>(null)
const chipRowRef = ref<HTMLElement | null>(null)
const navRef = ref<HTMLElement | null>(null)
let timer: ReturnType<typeof setTimeout> | null = null

// ── Dropdown positioning (fixed to viewport so it never extends page height) ──

const dropStyle = ref<Record<string, string>>({})

const computeDropPos = () => {
  const rect = inputRef.value?.getBoundingClientRect()
  if (!rect) return
  const minW = Math.max(280, rect.width)
  const left = Math.min(rect.left, window.innerWidth - minW - 12)
  dropStyle.value = {
    top: `${rect.bottom + 3}px`,
    left: `${Math.max(0, left)}px`,
    minWidth: `${minW}px`,
    maxHeight: `${Math.max(120, window.innerHeight - rect.bottom - 12)}px`,
  }
}

watch(open, (isOpen) => {
  if (isOpen) {
    computeDropPos()
    window.addEventListener('scroll', computeDropPos, true)
    window.addEventListener('resize', computeDropPos)
  } else {
    window.removeEventListener('scroll', computeDropPos, true)
    window.removeEventListener('resize', computeDropPos)
  }
})

onUnmounted(() => {
  window.removeEventListener('scroll', computeDropPos, true)
  window.removeEventListener('resize', computeDropPos)
})

// ── Stage ──────────────────────────────────────────────────────────────────────

const initialStage = computed<Stage>(() => props.fixedDomains?.length ? 'entity-type' : 'scope')
const currentStage = ref<Stage>(initialStage.value)

const hasStageUI = computed(() =>
  calcHasStageUI(props.fixedDomains, props.fixedEntityTypes, props.widenableTo),
)
const stageTitle = computed(() =>
  currentStage.value === 'scope' ? '1. Filter Domains' : '2. Filter Entity Types',
)
const canGoBack = computed(() =>
  calcCanGoBack(currentStage.value, props.fixedDomains, props.widenableTo),
)
const canGoForward = computed(() =>
  calcCanGoForward(currentStage.value, props.fixedEntityTypes, props.widenableTo),
)

const effectiveDomains = computed(() => [
  ...(props.fixedDomains ?? []),
  ...selectedDomains.value,
  ...impliedDomains.value,
])
const effectiveEntityTypes = computed(() => [...(props.fixedEntityTypes ?? []), ...selectedEntityTypes.value])

const summaryParts = computed(() => {
  const parts: string[] = []
  if (effectiveDomains.value.length) parts.push(`Domains: ${effectiveDomains.value.join(', ')}`)
  if (effectiveEntityTypes.value.length) parts.push(`Types: ${effectiveEntityTypes.value.join(', ')}`)
  return parts
})

// ── Search ─────────────────────────────────────────────────────────────────────

const doSearch = async () => {
  busy.value = true
  if (props.diagramType) {
    const exit = await Effect.runPromiseExit(svc.searchEntityDisplay(query.value.trim() || '', 30, props.diagramType))
    busy.value = false
    if (Exit.isSuccess(exit)) {
      const hits: ReferenceSearchHit[] = exit.value.map((entity) => ({
        artifact_id: entity.artifact_id,
        record_type: 'entity',
        name: entity.name,
        status: entity.status,
        path: '',
        artifact_type: entity.artifact_type,
        domain: entity.domain,
      }))
      results.value = hits.filter(r =>
        !props.excludedIds?.has(r.artifact_id)
        && (!props.acceptedTypes || props.acceptedTypes.has(String(r.artifact_type))),
      )
      activeResultIdx.value = -1
    }
    return
  }

  const exit = await Effect.runPromiseExit(
    svc.searchReferenceArtifacts({
      q: query.value.trim() || undefined,
      kind: 'entity',
      domains: effectiveDomains.value.length ? effectiveDomains.value : undefined,
      entity_types: effectiveEntityTypes.value.length ? effectiveEntityTypes.value : undefined,
      limit: 30,
    }),
  )
  busy.value = false
  if (Exit.isSuccess(exit)) {
    results.value = exit.value.hits.filter(r =>
      !props.excludedIds?.has(r.artifact_id)
      && (!props.acceptedTypes || props.acceptedTypes.has(String(r.artifact_type))),
    )
    activeResultIdx.value = -1
  }
}

const scheduleSearch = () => {
  if (timer) clearTimeout(timer)
  timer = setTimeout(() => void doSearch(), 200)
}

const openDropdown = () => {
  currentStage.value = initialStage.value
  open.value = true
  void doSearch()
}

const onInput = () => { open.value = true; scheduleSearch() }

const pick = async (hit: ReferenceSearchHit) => {
  const exit = await Effect.runPromiseExit(svc.getEntityDisplayItem(hit.artifact_id))
  if (!Exit.isSuccess(exit)) return
  // Focus before emit: prevents the focused li from being the element removed
  // from DOM (which would shift focus to <body> and reset window scroll).
  inputRef.value?.focus({ preventScroll: true })
  activeResultIdx.value = -1
  emit('select', exit.value)
  // excludedIds watcher removes the picked item reactively — no full re-fetch
  // needed, which avoids flickering from replacing the entire results array.
}

const toggleDomain = (d: string) => {
  if (props.fixedDomains?.includes(d)) return
  selectedDomains.value = toggle(selectedDomains.value, d)
  selectedEntityTypes.value = selectedEntityTypes.value.filter(t => availableEntityTypes.value.includes(t))
  scheduleSearch()
}

const toggleEntityType = (t: string) => {
  if (props.fixedEntityTypes?.includes(t)) return
  selectedEntityTypes.value = toggle(selectedEntityTypes.value, t)
  scheduleSearch()
}

const goBack = () => { currentStage.value = 'scope'; selectedEntityTypes.value = [] }
const goForward = () => { currentStage.value = 'entity-type' }

// ── Keyboard helpers ───────────────────────────────────────────────────────────

const chipEls = () => [...(chipRowRef.value?.querySelectorAll<HTMLElement>('.chip') ?? [])]
const resultEls = () => [...(wrapRef.value?.querySelectorAll<HTMLElement>('[data-result]') ?? [])]
const navEl = () => navRef.value?.querySelector<HTMLElement>('button') ?? null

const focusResult = (idx: number) => { activeResultIdx.value = idx; resultEls()[idx]?.focus() }
const focusAfterNav = () => { const c = chipEls(); if (c.length) c[0].focus(); else focusResult(0) }
const focusBeforeChips = () => { const n = navEl(); if (n) n.focus(); else inputRef.value?.focus() }

const onInputKeydown = (e: KeyboardEvent) => {
  if (!open.value) { if (e.key === 'ArrowDown' || e.key === 'Enter') openDropdown(); return }
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    const n = navEl()
    if (n) n.focus(); else focusAfterNav()
  } else if (e.key === 'Escape') { open.value = false; activeResultIdx.value = -1 }
}

const onNavKeydown = (e: KeyboardEvent) => {
  if (e.key === 'ArrowDown') { e.preventDefault(); focusAfterNav() }
  else if (e.key === 'ArrowUp') { e.preventDefault(); inputRef.value?.focus() }
  else if (e.key === 'Escape') { open.value = false; inputRef.value?.focus() }
}

const onChipKeydown = (e: KeyboardEvent, i: number) => {
  const chips = chipEls()
  if (e.key === 'ArrowDown') { e.preventDefault(); focusResult(0) }
  else if (e.key === 'ArrowUp') { e.preventDefault(); focusBeforeChips() }
  else if (e.key === 'ArrowRight') { e.preventDefault(); chips[i + 1]?.focus() }
  else if (e.key === 'ArrowLeft') { e.preventDefault(); chips[i - 1]?.focus() }
  else if (e.key === 'Escape') { open.value = false; inputRef.value?.focus() }
}

const onResultKeydown = (e: KeyboardEvent, hit: ReferenceSearchHit, i: number) => {
  if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); void pick(hit) }
  else if (e.key === 'ArrowDown') { e.preventDefault(); focusResult(Math.min(i + 1, results.value.length - 1)) }
  else if (e.key === 'ArrowUp') {
    e.preventDefault()
    if (i > 0) { focusResult(i - 1) } else {
      const chips = chipEls()
      if (chips.length) chips[0].focus(); else { const n = navEl(); if (n) n.focus(); else inputRef.value?.focus() }
    }
  } else if (e.key === 'Escape') { open.value = false; inputRef.value?.focus() }
}

const onFocusOut = (e: FocusEvent) => {
  if (!wrapRef.value?.contains(e.relatedTarget as Node))
    setTimeout(() => { open.value = false }, 100)
}

watch(() => props.excludedIds, () => {
  results.value = results.value.filter(r => !props.excludedIds?.has(r.artifact_id))
})
watch([selectedDomains, selectedEntityTypes], scheduleSearch)
</script>

<template>
  <div
    ref="wrapRef"
    class="ep"
    @focusout="onFocusOut"
  >
    <input
      ref="inputRef"
      v-model="query"
      class="ep-inp"
      type="search"
      autocomplete="off"
      :placeholder="placeholder ?? 'Search entities…'"
      @input="onInput"
      @focus="openDropdown"
      @keydown="onInputKeydown"
    >

    <div
      v-if="open"
      class="ep-drop"
      :style="dropStyle"
      @mousedown.prevent
    >
      <!-- Fixed domain display — strategy A: compact chip (1 value), disabled row (N values) -->
      <div
        v-if="fixedDomains?.length"
        class="ep-fixed-row"
      >
        <span class="ep-fixed-label">{{ fixedDomains.length === 1 ? 'Domain' : 'Domains' }}</span>
        <template v-if="fixedDomains.length === 1">
          <span
            class="ep-fixed-chip"
            title="Domain filter is pinned"
          >{{ fixedDomains[0] }}</span>
          <span
            class="ep-fixed-lock"
            aria-label="locked"
          >🔒</span>
        </template>
        <template v-else>
          <div class="ep-fixed-set">
            <span
              v-for="d in fixedDomains"
              :key="d"
              class="ep-fixed-chip"
            >{{ d }}</span>
          </div>
          <span
            class="ep-fixed-lock"
            aria-label="locked"
          >🔒</span>
        </template>
      </div>

      <!-- Fixed entity type display — strategy A: compact chip (1 value), disabled row (N values) -->
      <div
        v-if="fixedEntityTypes?.length"
        class="ep-fixed-row ep-fixed-row--types"
      >
        <span class="ep-fixed-label">{{ fixedEntityTypes.length === 1 ? 'Type' : 'Types' }}</span>
        <template v-if="fixedEntityTypes.length === 1">
          <span
            class="ep-fixed-chip ep-fixed-chip--type"
            title="Entity type filter is pinned"
          >{{ fixedEntityTypes[0] }}</span>
          <span
            class="ep-fixed-lock"
            aria-label="locked"
          >🔒</span>
        </template>
        <template v-else>
          <div class="ep-fixed-set">
            <span
              v-for="t in fixedEntityTypes"
              :key="t"
              class="ep-fixed-chip ep-fixed-chip--type"
            >{{ t }}</span>
          </div>
          <span
            class="ep-fixed-lock"
            aria-label="locked"
          >🔒</span>
        </template>
      </div>

      <!-- Interactive filter stage (hidden when widenableTo=none or all levels are fixed) -->
      <div
        v-if="hasStageUI"
        class="ep-stage"
      >
        <div class="ep-stage-hdr">
          <span class="ep-stage-title">{{ stageTitle }}</span>
          <div
            ref="navRef"
            class="ep-nav"
          >
            <button
              v-if="canGoBack"
              class="nav-btn"
              type="button"
              @click="goBack"
              @keydown="onNavKeydown"
            >
              ← Back
            </button>
            <button
              v-if="canGoForward"
              class="nav-btn nav-btn--fwd"
              type="button"
              @click="goForward"
              @keydown="onNavKeydown"
            >
              Entity Types →
            </button>
          </div>
        </div>

        <div
          ref="chipRowRef"
          class="ep-chips"
        >
          <template v-if="currentStage === 'scope'">
            <button
              v-for="(d, i) in domainOptions"
              :key="d.key"
              class="chip"
              :class="{
                'chip--on': effectiveDomains.includes(d.key),
                'chip--fixed': fixedDomains?.includes(d.key),
                'chip--implied': impliedDomains.includes(d.key) && !selectedDomains.includes(d.key) && !fixedDomains?.includes(d.key),
              }"
              type="button"
              :title="impliedDomains.includes(d.key) && !selectedDomains.includes(d.key) ? 'Derived from selected entity type' : undefined"
              @click="toggleDomain(d.key)"
              @keydown="(e) => onChipKeydown(e, i)"
            >
              {{ d.label }}
            </button>
          </template>
          <template v-else>
            <button
              v-for="(t, i) in availableEntityTypes"
              :key="t"
              class="chip chip--sm"
              :class="{ 'chip--on': effectiveEntityTypes.includes(t), 'chip--fixed': fixedEntityTypes?.includes(t) }"
              type="button"
              @click="toggleEntityType(t)"
              @keydown="(e) => onChipKeydown(e, i)"
            >
              {{ t }}
            </button>
          </template>
        </div>

        <div
          v-if="summaryParts.length"
          class="ep-summary"
        >
          {{ summaryParts.join(' · ') }}
        </div>
      </div>

      <!-- Results -->
      <div
        v-if="busy"
        class="ep-state"
      >
        Searching…
      </div>
      <ul
        v-else-if="results.length"
        class="ep-results"
        role="listbox"
      >
        <li
          v-for="(r, i) in results"
          :key="r.artifact_id"
          data-result
          role="option"
          class="ep-result"
          :class="{ 'ep-result--hi': i === activeResultIdx }"
          tabindex="0"
          @mousedown.prevent="void pick(r)"
          @keydown="onResultKeydown($event, r, i)"
          @focus="activeResultIdx = i"
        >
          <span
            v-if="r.artifact_type"
            class="ep-glyph"
          >
            <ArchimateTypeGlyph
              :type="toGlyphKey(r.artifact_type)"
              :size="14"
            />
          </span>
          <span class="ep-name">{{ r.name }}</span>
          <span class="ep-meta">{{ r.artifact_type ?? r.record_type }} · {{ r.domain }}</span>
        </li>
      </ul>
      <div
        v-else
        class="ep-state"
      >
        {{ query.trim() ? 'No matches.' : 'Type to search or apply filters.' }}
      </div>
    </div>
  </div>
</template>

<style scoped>
.ep { position: relative; }
.ep-inp { width: 100%; padding: 7px 10px; border-radius: 6px; border: 1px solid #d1d5db; font-size: 13px; outline: none; box-sizing: border-box; }
.ep-inp:focus { border-color: #2563eb; box-shadow: 0 0 0 2px #bfdbfe; }

.ep-drop {
  position: fixed; z-index: 1000;
  background: white; border: 1px solid #d1d5db; border-radius: 8px;
  box-shadow: 0 6px 20px rgba(0,0,0,.13); overflow-y: auto;
}

/* Fixed-level read-only sections (strategy A: compact chip for single, row for set) */
.ep-fixed-row { display: flex; align-items: center; gap: 6px; padding: 6px 10px; background: #f0f9ff; border-bottom: 1px solid #bae6fd; font-size: 12px; flex-wrap: wrap; }
.ep-fixed-row--types { background: #f5f3ff; border-bottom-color: #c4b5fd; }
.ep-fixed-label { font-size: 10px; font-weight: 700; color: #0369a1; flex-shrink: 0; text-transform: uppercase; letter-spacing: .05em; }
.ep-fixed-row--types .ep-fixed-label { color: #6d28d9; }
.ep-fixed-chip { background: #e0f2fe; border: 1px solid #7dd3fc; color: #0369a1; border-radius: 999px; padding: 2px 9px; font-size: 11px; cursor: default; }
.ep-fixed-chip--type { background: #ede9fe; border-color: #a78bfa; color: #6d28d9; }
.ep-fixed-set { display: flex; flex-wrap: wrap; gap: 4px; }
.ep-fixed-lock { color: #94a3b8; font-size: 10px; }

.ep-stage { padding: 10px 10px 6px; border-bottom: 1px solid #f3f4f6; background: #f8fafc; }
.ep-stage-hdr { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.ep-stage-title { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: .06em; color: #475569; }
.ep-nav { display: flex; gap: 6px; }
.nav-btn { border: 1px solid #cbd5e1; background: white; color: #334155; border-radius: 6px; padding: 4px 9px; font-size: 11px; font-weight: 600; cursor: pointer; }
.nav-btn:hover { background: #f8fafc; }
.nav-btn--fwd { background: #dbeafe; border-color: #bfdbfe; color: #1d4ed8; }
.nav-btn--fwd:hover { background: #bfdbfe; }

.ep-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.chip { border: 1px solid #cbd5e1; background: white; border-radius: 999px; padding: 5px 11px; font-size: 12px; color: #334155; cursor: pointer; outline: none; }
.chip:hover:not(.chip--fixed), .chip:focus:not(.chip--fixed) { border-color: #2563eb; color: #1d4ed8; }
.chip--sm { font-size: 11px; padding: 4px 9px; }
.chip--on { background: #0f172a; border-color: #0f172a; color: white; }
.chip--fixed { opacity: .6; cursor: default; }
.chip--implied { border-style: dashed; border-color: #6366f1; color: #4338ca; background: #eef2ff; }

.ep-summary { margin-top: 7px; font-size: 11px; color: #64748b; }

.ep-results { margin: 0; padding: 4px 0; list-style: none; }
.ep-result { display: flex; align-items: center; gap: 8px; padding: 7px 10px; cursor: pointer; outline: none; }
.ep-result:hover, .ep-result:focus, .ep-result--hi { background: #eff6ff; }
.ep-glyph { flex-shrink: 0; color: #4b5563; display: flex; align-items: center; }
.ep-name { flex: 1; font-weight: 500; font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ep-meta { font-size: 11px; color: #9ca3af; white-space: nowrap; }
.ep-state { font-size: 12px; color: #9ca3af; padding: 10px 12px; }
</style>
