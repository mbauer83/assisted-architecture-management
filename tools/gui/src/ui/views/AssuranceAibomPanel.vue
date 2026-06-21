<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import {
  parseRoles,
  parseCoverage,
  parseCandidates,
  selectedAiComponents,
  scoreBand,
  type CoverageReport,
  type ScanCandidate,
  type AiRole,
} from './AssuranceAibom.helpers'

const LOCKED_MSG = 'Assurance signals are not available (store locked).'

const coverage = ref<CoverageReport | null>(null)
const candidates = ref<ScanCandidate[]>([])
const selected = ref<Set<string>>(new Set())
const roles = ref<AiRole[]>([])
const defaultRole = ref<AiRole>('')
const exportJson = ref<string>('')
const error = ref<string | null>(null)
const busy = ref(false)

const selectedCount = computed(() => selected.value.size)

onMounted(loadRoles)

async function loadRoles() {
  const resp = await fetch('/api/assurance/aibom/roles')
  if (!resp.ok) return
  roles.value = parseRoles(await resp.json())
  if (!defaultRole.value && roles.value.length) defaultRole.value = roles.value[0]
}

async function loadCoverage() {
  error.value = null
  const resp = await fetch('/api/assurance/aibom/coverage')
  if (resp.status === 423) { error.value = LOCKED_MSG; return }
  if (!resp.ok) { error.value = `HTTP ${resp.status}`; return }
  coverage.value = parseCoverage(await resp.json())
}

async function runScan() {
  error.value = null
  busy.value = true
  try {
    const resp = await fetch('/api/assurance/aibom/scan')
    if (!resp.ok) { error.value = `HTTP ${resp.status}`; return }
    candidates.value = parseCandidates(await resp.json())
    selected.value = new Set()
  } catch (e) {
    error.value = String(e)
  } finally {
    busy.value = false
  }
}

function toggle(id: string) {
  const next = new Set(selected.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  selected.value = next
}

async function exportBom() {
  error.value = null
  busy.value = true
  exportJson.value = ''
  try {
    const components = selectedAiComponents(candidates.value, selected.value, {}, defaultRole.value)
    const resp = await fetch('/api/assurance/aibom/export', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ai_components: components, notes: 'Exported from the supply-chain wizard.' }),
    })
    if (!resp.ok) { error.value = `HTTP ${resp.status}`; return }
    const body = await resp.json() as { bom: unknown }
    exportJson.value = JSON.stringify(body.bom, null, 2)
  } catch (e) {
    error.value = String(e)
  } finally {
    busy.value = false
  }
}

function download() {
  const blob = new Blob([exportJson.value], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'ml-bom.cdx.json'
  a.click()
  URL.revokeObjectURL(url)
}
</script>

<template>
  <section class="aibom">
    <p class="hint-note">
      AI-BOM marks which architecture elements are AI components (models, datasets, agents,
      MCP servers, RAG pipelines). Review coverage gaps, scan the architecture for unmarked
      candidates, then export a CycloneDX 1.6 ML-BOM for the components you confirm.
    </p>

    <div
      v-if="error"
      class="wiz-error"
    >
      {{ error }}
    </div>

    <!-- Coverage -->
    <div class="block">
      <div class="row">
        <h3 class="block-title">
          Coverage
        </h3>
        <button
          class="add-btn add-btn--ghost"
          type="button"
          @click="loadCoverage"
        >
          ↺ Load coverage
        </button>
      </div>
      <div
        v-if="coverage"
        class="cov"
      >
        <div class="cov-stats">
          <span class="stat">{{ coverage.total_bom_components }} BOM components</span>
          <span class="stat stat--warn">{{ coverage.unanchored_components }} unanchored</span>
          <span class="stat">{{ coverage.anchor_mappings }} anchor mappings</span>
          <span
            v-if="coverage.withheld_components"
            class="stat"
          >{{ coverage.withheld_components }} withheld</span>
        </div>
        <p class="cov-summary">
          {{ coverage.summary }}
        </p>
        <ul
          v-if="coverage.unanchored.length"
          class="unanchored"
        >
          <li
            v-for="(c, i) in coverage.unanchored"
            :key="c.purl ?? c.name ?? i"
          >
            <span class="mono">{{ c.name }}</span>
            <span
              v-if="c.purl"
              class="mono dim"
            >{{ c.purl }}</span>
          </li>
        </ul>
        <p
          v-if="coverage.unanchored_truncated"
          class="dim"
        >
          (first 50 shown)
        </p>
      </div>
      <p
        v-else
        class="empty"
      >
        Load the coverage report to see unanchored components.
      </p>
    </div>

    <!-- Candidate scan -->
    <div class="block">
      <div class="row">
        <h3 class="block-title">
          AI-candidate scan
        </h3>
        <button
          class="add-btn"
          type="button"
          :disabled="busy"
          @click="runScan"
        >
          Scan architecture
        </button>
        <span
          v-if="candidates.length"
          class="dim"
        >{{ selectedCount }} / {{ candidates.length }} selected</span>
      </div>
      <p class="dim">
        Heuristic suggestions only — confirm each before exporting.
      </p>
      <table
        v-if="candidates.length"
        class="grid"
      >
        <thead>
          <tr>
            <th />
            <th>Name</th>
            <th>Type</th>
            <th>Score</th>
            <th>Reasons</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="c in candidates"
            :key="c.entity_id"
          >
            <td>
              <input
                type="checkbox"
                :checked="selected.has(c.entity_id)"
                :aria-label="`select ${c.name}`"
                @change="toggle(c.entity_id)"
              >
            </td>
            <td>{{ c.name }}</td>
            <td class="dim">
              {{ c.entity_type }}
            </td>
            <td>
              <span
                class="badge"
                :class="`band--${scoreBand(c.score)}`"
              >{{ c.score }}</span>
            </td>
            <td class="dim">
              {{ c.reasons.join(', ') }}
            </td>
          </tr>
        </tbody>
      </table>
      <p
        v-else
        class="empty"
      >
        Run the scan to rank architecture elements by AI-BOM relevance.
      </p>
    </div>

    <!-- Export -->
    <div class="block">
      <div class="row">
        <h3 class="block-title">
          Export ML-BOM
        </h3>
        <label class="role-label">
          default role
          <select
            v-model="defaultRole"
            class="role-select"
          >
            <option
              v-for="r in roles"
              :key="r"
              :value="r"
            >
              {{ r }}
            </option>
          </select>
        </label>
        <button
          class="add-btn"
          type="button"
          :disabled="busy || selectedCount === 0"
          @click="exportBom"
        >
          Export {{ selectedCount }} component(s)
        </button>
      </div>
      <div
        v-if="exportJson"
        class="export"
      >
        <button
          class="add-btn add-btn--ghost"
          type="button"
          @click="download"
        >
          ⭳ Download .cdx.json
        </button>
        <pre class="export-json">{{ exportJson }}</pre>
      </div>
    </div>
  </section>
</template>

<style scoped>
.aibom { display: flex; flex-direction: column; gap: 16px; }
.hint-note { font-size: 13px; color: #475569; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px 14px; margin: 0; }
.wiz-error { padding: 10px 14px; background: #fef2f2; color: #b91c1c; border-radius: 6px; font-size: 13px; }
.block { border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px 14px; display: flex; flex-direction: column; gap: 10px; }
.block-title { font-size: 14px; font-weight: 700; margin: 0; }
.row { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.cov { display: flex; flex-direction: column; gap: 8px; }
.cov-stats { display: flex; gap: 8px; flex-wrap: wrap; }
.stat { font-size: 12px; padding: 2px 10px; border-radius: 10px; background: #f1f5f9; color: #334155; font-weight: 600; }
.stat--warn { background: #fef3c7; color: #92400e; }
.cov-summary { font-size: 13px; color: #475569; margin: 0; }
.unanchored { margin: 0; padding-left: 18px; font-size: 12px; display: flex; flex-direction: column; gap: 2px; }
.unanchored li { display: flex; gap: 10px; }
.add-btn { font-size: 13px; padding: 7px 14px; border: none; border-radius: 6px; background: #2563eb; color: #fff; font-weight: 600; cursor: pointer; }
.add-btn--ghost { background: #fff; color: #2563eb; border: 1px solid #cbd5e1; }
.add-btn:disabled { opacity: 0.5; cursor: default; }
.empty { color: #94a3b8; font-size: 13px; margin: 0; }
.dim { color: #94a3b8; font-size: 12px; }
.grid { border-collapse: collapse; font-size: 12px; width: 100%; }
.grid th, .grid td { border: 1px solid #e2e8f0; padding: 6px 10px; text-align: left; }
.grid th { background: #f8fafc; font-weight: 600; }
.mono { font-family: ui-monospace, monospace; }
.badge { font-size: 11px; padding: 2px 8px; border-radius: 10px; font-weight: 600; }
.band--high { background: #dcfce7; color: #15803d; }
.band--medium { background: #fef9c3; color: #854d0e; }
.band--low { background: #f1f5f9; color: #64748b; }
.role-label { font-size: 12px; color: #475569; display: flex; align-items: center; gap: 6px; }
.role-select { font-size: 12px; padding: 5px 8px; border: 1px solid #cbd5e1; border-radius: 6px; }
.export { display: flex; flex-direction: column; gap: 8px; }
.export-json { background: #0f172a; color: #e2e8f0; font-size: 11px; padding: 10px 12px; border-radius: 6px; overflow: auto; max-height: 320px; margin: 0; }
</style>
