<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AssuranceAnalysisPicker from '../components/AssuranceAnalysisPicker.vue'
import {
  GRC_STEPS,
  TREATMENT_OPTIONS,
  RISK_LEVELS,
  ACCOUNTABLE_REF_TYPE,
  ANTI_SUBORDINATION_NOTE,
  parseAttributes,
  riskTreatment,
  riskScore,
  summariseGrcComplete,
  grcStepBadges,
  gapNodeIds,
  unlinkedSources,
  linkedSourceIds,
  type AssuranceNode,
  type AssuranceEdge,
  type GrcStep,
  type GrcCompleteResponse,
} from './AssuranceGrcWizard.helpers'

const route = useRoute()
const router = useRouter()

const analysisId = ref<string | null>(
  typeof route.query['analysis_id'] === 'string' ? route.query['analysis_id'] : null,
)
const stepKey = ref<string>('risks')
const currentStep = computed<GrcStep>(
  () => GRC_STEPS.find((s) => s.key === stepKey.value) ?? GRC_STEPS[0],
)

const nodes = ref<AssuranceNode[]>([])
const edges = ref<AssuranceEdge[]>([])
const guidance = ref<{ what?: string; why?: string; how?: string }>({})
const completeness = ref<GrcCompleteResponse | null>(null)
const error = ref<string | null>(null)
const busy = ref(false)

// Per-step add form
const newRisk = ref({ name: '', likelihood: 'medium', impact: 'medium' })
const newControl = ref('')
const newObligation = ref({ name: '', scheme: '', code: '' })
const ownerInput = ref<Record<string, string>>({})

const risks = computed(() => nodes.value.filter((n) => n.node_type === 'risk'))
const controls = computed(() => nodes.value.filter((n) => n.node_type === 'assurance-constraint'))
const obligations = computed(() => nodes.value.filter((n) => n.node_type === 'obligation'))
const contentSteps = computed(() => grcStepBadges(nodes.value))

const treatmentGapIds = computed(() => gapNodeIds(completeness.value, 'risk_has_treatment'))
const ownerGapIds = computed(() => gapNodeIds(completeness.value, 'risk_has_owner'))
const completenessSummary = computed(() =>
  completeness.value ? summariseGrcComplete(completeness.value) : null,
)

function hasOwner(risk: AssuranceNode): boolean {
  return !ownerGapIds.value.has(risk.node_id)
}

async function loadNodes() {
  if (!analysisId.value) { nodes.value = []; edges.value = []; return }
  const aid = encodeURIComponent(analysisId.value)
  const [nResp, eResp] = await Promise.all([
    fetch(`/api/assurance/nodes?analysis_id=${aid}`),
    fetch('/api/assurance/edges'),
  ])
  if (nResp.status === 423) { error.value = 'The assurance store is locked.'; return }
  const nBody = await nResp.json() as { nodes: AssuranceNode[] }
  nodes.value = nBody.nodes
  const ids = new Set(nodes.value.map((n) => n.node_id))
  const eBody = await eResp.json() as { edges: AssuranceEdge[] }
  edges.value = eBody.edges.filter((e) => ids.has(e.source_id) && ids.has(e.target_id))
}

async function loadGuidance() {
  guidance.value = {}
  if (!currentStep.value.guidanceTopic) return
  const resp = await fetch(`/api/assurance/guidance?topic=${currentStep.value.guidanceTopic}`)
  if (resp.ok) guidance.value = await resp.json() as { what?: string; why?: string; how?: string }
}

async function loadCompleteness() {
  if (!analysisId.value) return
  const resp = await fetch(`/api/assurance/grc-complete?analysis_id=${encodeURIComponent(analysisId.value)}`)
  if (resp.ok) completeness.value = await resp.json() as GrcCompleteResponse
}

async function createNode(
  nodeType: string,
  name: string,
  attributes: Record<string, string> = {},
): Promise<string | null> {
  if (!name.trim() || !analysisId.value) return null
  busy.value = true
  error.value = null
  try {
    const resp = await fetch('/api/assurance/nodes', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        node_type: nodeType, name: name.trim(), analysis_id: analysisId.value, attributes,
      }),
    })
    const body = await resp.json().catch(() => ({})) as Record<string, unknown>
    if (!resp.ok || typeof body['node_id'] !== 'string') {
      error.value = typeof body['error'] === 'string' ? body['error'] : `HTTP ${resp.status}`
      return null
    }
    return body['node_id']
  } catch (e) {
    error.value = String(e)
    return null
  } finally {
    busy.value = false
  }
}

async function createEdge(source: string, target: string, connType: string) {
  await fetch('/api/assurance/edges', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ source_id: source, target_id: target, conn_type: connType }),
  })
}

// Assurance edits replace attributes wholesale, so merge before PATCH.
async function patchAttributes(risk: AssuranceNode, changes: Record<string, string>) {
  busy.value = true
  try {
    await fetch(`/api/assurance/nodes/${encodeURIComponent(risk.node_id)}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ attributes: { ...parseAttributes(risk), ...changes } }),
    })
    await loadNodes()
    await loadCompleteness()
  } finally {
    busy.value = false
  }
}

async function addRisk() {
  const id = await createNode('risk', newRisk.value.name, {
    likelihood: newRisk.value.likelihood, impact: newRisk.value.impact,
  })
  if (id) { newRisk.value = { name: '', likelihood: 'medium', impact: 'medium' }; await loadNodes() }
}

async function addControl() {
  const id = await createNode('assurance-constraint', newControl.value)
  if (id) { newControl.value = ''; await loadNodes() }
}

async function addObligation() {
  const attrs: Record<string, string> = {}
  if (newObligation.value.scheme.trim()) attrs['scheme'] = newObligation.value.scheme.trim()
  if (newObligation.value.code.trim()) attrs['code'] = newObligation.value.code.trim()
  const id = await createNode('obligation', newObligation.value.name, attrs)
  if (id) { newObligation.value = { name: '', scheme: '', code: '' }; await loadNodes() }
}

function setTreatment(risk: AssuranceNode, treatment: string) {
  if (treatment) void patchAttributes(risk, { treatment })
}

async function assignOwner(risk: AssuranceNode) {
  const archId = (ownerInput.value[risk.node_id] ?? '').trim()
  if (!archId) return
  busy.value = true
  error.value = null
  try {
    const resp = await fetch('/api/assurance/arch-refs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        assurance_node_id: risk.node_id, arch_artifact_id: archId, ref_type: ACCOUNTABLE_REF_TYPE,
      }),
    })
    if (!resp.ok) {
      const body = await resp.json().catch(() => ({})) as Record<string, unknown>
      error.value = typeof body['error'] === 'string' ? body['error'] : `HTTP ${resp.status}`
      return
    }
    ownerInput.value[risk.node_id] = ''
    await loadCompleteness()
  } finally {
    busy.value = false
  }
}

async function linkSource(sourceId: string, targetId: string, connType: string) {
  busy.value = true
  try {
    await createEdge(sourceId, targetId, connType)
    await loadNodes()
  } finally {
    busy.value = false
  }
}

function treatedByRisks(control: AssuranceNode): AssuranceNode[] {
  const linked = linkedSourceIds(edges.value, control.node_id, 'treated-by')
  return risks.value.filter((r) => linked.has(r.node_id))
}

function compliantControls(obligation: AssuranceNode): AssuranceNode[] {
  const linked = linkedSourceIds(edges.value, obligation.node_id, 'complies-with')
  return controls.value.filter((c) => linked.has(c.node_id))
}

const unlinkedRisksFor = (control: AssuranceNode) =>
  unlinkedSources(risks.value, edges.value, control.node_id, 'treated-by')
const unlinkedControlsFor = (obligation: AssuranceNode) =>
  unlinkedSources(controls.value, edges.value, obligation.node_id, 'complies-with')

async function sealBaseline() {
  busy.value = true
  try {
    await fetch('/api/assurance/baselines/seal', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ notes: `GRC analysis ${analysisId.value}`, analysis_id: analysisId.value }),
    })
    await loadCompleteness()
  } finally {
    busy.value = false
  }
}

function goToStep(key: string) {
  stepKey.value = key
}

watch(analysisId, (val) => {
  void router.replace({ path: '/assurance/grc', query: val ? { analysis_id: val } : {} })
  void loadNodes()
  void loadCompleteness()
})
watch(stepKey, () => {
  void loadGuidance()
  if (stepKey.value === 'treatment' || stepKey.value === 'coverage') void loadCompleteness()
})

onMounted(() => {
  void loadNodes()
  void loadGuidance()
  void loadCompleteness()
})
</script>

<template>
  <div class="wiz">
    <div class="wiz-header">
      <h1 class="wiz-title">
        GRC wizard
      </h1>
      <AssuranceAnalysisPicker
        v-model="analysisId"
        default-method="GRC"
      />
    </div>

    <div
      v-if="error"
      class="wiz-error"
    >
      {{ error }}
    </div>

    <p
      v-if="!analysisId"
      class="wiz-hint"
    >
      Select or create a GRC analysis above to begin. Every risk, control and
      obligation you author belongs to that analysis.
    </p>

    <template v-else>
      <!-- Stepper -->
      <nav class="stepper">
        <button
          v-for="(s, i) in GRC_STEPS"
          :key="s.key"
          class="step-tab"
          :class="{ 'step-tab--active': s.key === stepKey, 'step-tab--done': contentSteps.has(s.key) }"
          type="button"
          @click="goToStep(s.key)"
        >
          <span class="step-num">{{ i + 1 }}</span>
          {{ s.label }}
        </button>
      </nav>

      <!-- Guidance -->
      <div
        v-if="guidance.what"
        class="guidance"
      >
        <p class="guidance-what">
          {{ guidance.what }}
        </p>
        <p
          v-if="guidance.why"
          class="guidance-why"
        >
          {{ guidance.why }}
        </p>
        <p
          v-if="guidance.how"
          class="guidance-how"
        >
          {{ guidance.how }}
        </p>
      </div>

      <!-- Risks -->
      <section
        v-if="currentStep.key === 'risks'"
        class="step-body"
      >
        <div class="add-row">
          <input
            v-model="newRisk.name"
            class="add-input"
            placeholder="New risk (e.g. 'Unauthorised data exposure')"
            @keyup.enter="addRisk"
          >
          <select
            v-model="newRisk.likelihood"
            class="lvl-select"
            aria-label="Likelihood"
          >
            <option
              v-for="lvl in RISK_LEVELS"
              :key="lvl"
              :value="lvl"
            >
              L: {{ lvl }}
            </option>
          </select>
          <select
            v-model="newRisk.impact"
            class="lvl-select"
            aria-label="Impact"
          >
            <option
              v-for="lvl in RISK_LEVELS"
              :key="lvl"
              :value="lvl"
            >
              I: {{ lvl }}
            </option>
          </select>
          <button
            class="add-btn"
            type="button"
            :disabled="busy"
            @click="addRisk"
          >
            + Add
          </button>
        </div>
        <p
          v-if="risks.length === 0"
          class="empty"
        >
          No risks yet. A risk evaluates a hazard or loss-scenario (likelihood × impact).
        </p>
        <ul
          v-else
          class="node-list"
        >
          <li
            v-for="risk in risks"
            :key="risk.node_id"
            class="node-row"
          >
            <span class="node-name">{{ risk.name }}</span>
            <span
              v-if="riskScore(risk)"
              class="score"
            >{{ riskScore(risk) }}</span>
          </li>
        </ul>
      </section>

      <!-- Treatment -->
      <section
        v-else-if="currentStep.key === 'treatment'"
        class="step-body"
      >
        <p
          v-if="risks.length === 0"
          class="empty"
        >
          Add risks first, then set each one's treatment and accountable owner here.
        </p>
        <ul
          v-else
          class="node-list"
        >
          <li
            v-for="risk in risks"
            :key="risk.node_id"
            class="treat-row"
          >
            <div class="treat-head">
              <span class="node-name">{{ risk.name }}</span>
              <span
                v-if="treatmentGapIds.has(risk.node_id)"
                class="badge badge--gap"
              >no treatment</span>
            </div>
            <div class="treat-controls">
              <label class="treat-label">Treatment
                <select
                  class="lvl-select"
                  :value="riskTreatment(risk)"
                  :disabled="busy"
                  @change="setTreatment(risk, ($event.target as HTMLSelectElement).value)"
                >
                  <option value="">
                    choose…
                  </option>
                  <option
                    v-for="t in TREATMENT_OPTIONS"
                    :key="t"
                    :value="t"
                  >
                    {{ t }}
                  </option>
                </select>
              </label>
              <span
                v-if="hasOwner(risk)"
                class="badge badge--ok"
              >owner ✓</span>
              <span
                v-else
                class="owner-assign"
              >
                <input
                  v-model="ownerInput[risk.node_id]"
                  class="owner-input"
                  placeholder="Accountable arch role id"
                  aria-label="Accountable architecture role id"
                  @keyup.enter="assignOwner(risk)"
                >
                <button
                  class="add-btn add-btn--sm"
                  type="button"
                  :disabled="busy"
                  @click="assignOwner(risk)"
                >
                  Assign owner
                </button>
              </span>
            </div>
          </li>
        </ul>
        <p class="hint-note">
          Accountability points to an architecture role (assurance → architecture, one-way).
          Enter the architecture entity id of the accountable owner.
        </p>
      </section>

      <!-- Controls -->
      <section
        v-else-if="currentStep.key === 'controls'"
        class="step-body"
      >
        <div class="add-row">
          <input
            v-model="newControl"
            class="add-input"
            placeholder="New control / assurance constraint"
            @keyup.enter="addControl"
          >
          <button
            class="add-btn"
            type="button"
            :disabled="busy"
            @click="addControl"
          >
            + Add
          </button>
        </div>
        <p
          v-if="controls.length === 0"
          class="empty"
        >
          No controls yet. A control is the assurance constraint that treats a risk.
        </p>
        <ul
          v-else
          class="node-list"
        >
          <li
            v-for="control in controls"
            :key="control.node_id"
            class="link-row"
          >
            <span class="node-name">{{ control.name }}</span>
            <span class="link-chips">
              <span
                v-for="r in treatedByRisks(control)"
                :key="r.node_id"
                class="chip"
              >treats: {{ r.name }}</span>
            </span>
            <select
              v-if="unlinkedRisksFor(control).length"
              class="relation-select"
              :disabled="busy"
              @change="linkSource(($event.target as HTMLSelectElement).value, control.node_id, 'treated-by')"
            >
              <option value="">
                treated-by risk…
              </option>
              <option
                v-for="r in unlinkedRisksFor(control)"
                :key="r.node_id"
                :value="r.node_id"
              >
                {{ r.name }}
              </option>
            </select>
          </li>
        </ul>
      </section>

      <!-- Obligations -->
      <section
        v-else-if="currentStep.key === 'obligations'"
        class="step-body"
      >
        <div class="add-row">
          <input
            v-model="newObligation.name"
            class="add-input"
            placeholder="New obligation (e.g. 'ISO 27001 A.8.1')"
            @keyup.enter="addObligation"
          >
          <input
            v-model="newObligation.scheme"
            class="cite-input"
            placeholder="scheme"
            aria-label="Citation scheme"
          >
          <input
            v-model="newObligation.code"
            class="cite-input"
            placeholder="code"
            aria-label="Citation code"
          >
          <button
            class="add-btn"
            type="button"
            :disabled="busy"
            @click="addObligation"
          >
            + Add
          </button>
        </div>
        <p
          v-if="obligations.length === 0"
          class="empty"
        >
          No obligations yet. An obligation is a compliance instance (clause X of standard Y).
        </p>
        <ul
          v-else
          class="node-list"
        >
          <li
            v-for="obligation in obligations"
            :key="obligation.node_id"
            class="link-row"
          >
            <span class="node-name">{{ obligation.name }}</span>
            <span class="link-chips">
              <span
                v-for="c in compliantControls(obligation)"
                :key="c.node_id"
                class="chip"
              >complies: {{ c.name }}</span>
            </span>
            <select
              v-if="unlinkedControlsFor(obligation).length"
              class="relation-select"
              :disabled="busy"
              @change="linkSource(($event.target as HTMLSelectElement).value, obligation.node_id, 'complies-with')"
            >
              <option value="">
                complies-with control…
              </option>
              <option
                v-for="c in unlinkedControlsFor(obligation)"
                :key="c.node_id"
                :value="c.node_id"
              >
                {{ c.name }}
              </option>
            </select>
          </li>
        </ul>
      </section>

      <!-- Coverage -->
      <section
        v-else
        class="step-body"
      >
        <p class="safeguard">
          {{ ANTI_SUBORDINATION_NOTE }}
        </p>
        <button
          class="add-btn"
          type="button"
          :disabled="busy"
          @click="loadCompleteness"
        >
          ↺ Re-check coverage
        </button>
        <div
          v-if="completenessSummary"
          class="review"
        >
          <p
            class="review-status"
            :class="completenessSummary.passed ? 'review-status--ok' : 'review-status--gap'"
          >
            {{ completenessSummary.passed ? 'All GRC coverage checks passed.' : 'Coverage gaps remain:' }}
          </p>
          <ul
            v-if="!completenessSummary.passed"
            class="gap-list"
          >
            <li
              v-for="f in completenessSummary.failed"
              :key="f.key"
            >
              {{ f.key }} — {{ f.gapCount }} gap{{ f.gapCount === 1 ? '' : 's' }}
            </li>
          </ul>
          <button
            class="seal-btn"
            type="button"
            :disabled="busy || !completenessSummary.passed"
            @click="sealBaseline"
          >
            Seal baseline
          </button>
          <p
            v-if="!completenessSummary.passed"
            class="seal-note"
          >
            Resolve the gaps above (set treatments and owners, link controls to obligations)
            before sealing.
          </p>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.wiz { padding: 20px 24px; max-width: 900px; }
.wiz-header { display: flex; flex-direction: column; gap: 12px; margin-bottom: 16px; }
.wiz-title { font-size: 20px; font-weight: 700; margin: 0; }
.wiz-error { padding: 10px 14px; background: #fef2f2; color: #b91c1c; border-radius: 6px; margin-bottom: 12px; font-size: 13px; }
.wiz-hint { color: #64748b; font-size: 14px; }
.stepper { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 16px; border-bottom: 1px solid #e2e8f0; padding-bottom: 8px; }
.step-tab {
  display: flex; align-items: center; gap: 6px;
  padding: 6px 12px; border: 1px solid #e2e8f0; border-radius: 6px;
  background: #fff; color: #475569; font-size: 13px; cursor: pointer;
}
.step-tab--active { background: #2563eb; color: #fff; border-color: #2563eb; }
.step-tab--done:not(.step-tab--active) { border-color: #86efac; }
.step-num {
  display: inline-flex; align-items: center; justify-content: center;
  width: 18px; height: 18px; border-radius: 50%; background: #e2e8f0; color: #475569; font-size: 11px;
}
.step-tab--active .step-num { background: rgba(255,255,255,0.3); color: #fff; }
.guidance { background: #f0f9ff; border: 1px solid #bae6fd; border-radius: 8px; padding: 12px 16px; margin-bottom: 16px; }
.guidance-what { font-size: 14px; font-weight: 600; color: #075985; margin: 0 0 4px; }
.guidance-why { font-size: 13px; color: #0c4a6e; margin: 0 0 4px; }
.guidance-how { font-size: 12px; color: #0369a1; margin: 0; }
.step-body { display: flex; flex-direction: column; gap: 12px; }
.add-row { display: flex; gap: 8px; flex-wrap: wrap; }
.add-input { flex: 1; min-width: 200px; font-size: 13px; padding: 7px 10px; border: 1px solid #cbd5e1; border-radius: 6px; }
.cite-input { width: 90px; font-size: 13px; padding: 7px 10px; border: 1px solid #cbd5e1; border-radius: 6px; }
.lvl-select { font-size: 13px; padding: 6px 8px; border: 1px solid #cbd5e1; border-radius: 6px; }
.add-btn {
  font-size: 13px; padding: 7px 14px; border: none; border-radius: 6px;
  background: #2563eb; color: #fff; font-weight: 600; cursor: pointer;
}
.add-btn--sm { padding: 5px 10px; font-size: 12px; }
.add-btn:disabled { opacity: 0.5; cursor: default; }
.empty { color: #94a3b8; font-size: 13px; }
.node-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.node-row { display: flex; align-items: center; gap: 10px; padding: 8px 12px; border: 1px solid #e2e8f0; border-radius: 6px; }
.node-name { font-size: 13px; font-weight: 500; }
.score { font-size: 12px; color: #b45309; background: #fffbeb; padding: 2px 8px; border-radius: 10px; }
.treat-row { display: flex; flex-direction: column; gap: 8px; padding: 10px 12px; border: 1px solid #e2e8f0; border-radius: 6px; }
.treat-head { display: flex; align-items: center; gap: 10px; }
.treat-controls { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.treat-label { font-size: 12px; color: #475569; display: flex; align-items: center; gap: 6px; }
.badge { font-size: 11px; padding: 2px 8px; border-radius: 10px; font-weight: 600; }
.badge--gap { background: #fef3c7; color: #b45309; }
.badge--ok { background: #dcfce7; color: #15803d; }
.owner-assign { display: flex; gap: 6px; align-items: center; }
.owner-input { font-size: 12px; padding: 5px 8px; border: 1px solid #cbd5e1; border-radius: 5px; min-width: 180px; }
.hint-note { font-size: 12px; color: #64748b; margin: 0; }
.link-row { display: flex; align-items: center; gap: 10px; padding: 8px 12px; border: 1px solid #e2e8f0; border-radius: 6px; flex-wrap: wrap; }
.link-chips { display: flex; gap: 6px; flex-wrap: wrap; flex: 1; }
.chip { font-size: 11px; background: #eef2ff; color: #3730a3; padding: 2px 8px; border-radius: 10px; }
.relation-select { font-size: 12px; padding: 4px 8px; border: 1px solid #cbd5e1; border-radius: 5px; }
.safeguard { font-size: 13px; color: #7c2d12; background: #fff7ed; border: 1px solid #fed7aa; border-radius: 8px; padding: 10px 14px; margin: 0; }
.review { display: flex; flex-direction: column; gap: 10px; margin-top: 4px; }
.review-status { font-size: 14px; font-weight: 600; margin: 0; }
.review-status--ok { color: #15803d; }
.review-status--gap { color: #b45309; }
.gap-list { margin: 0; padding-left: 20px; font-size: 13px; color: #475569; }
.seal-btn {
  align-self: flex-start; font-size: 13px; padding: 8px 18px; border: none; border-radius: 6px;
  background: #15803d; color: #fff; font-weight: 600; cursor: pointer;
}
.seal-btn:disabled { opacity: 0.5; cursor: default; }
.seal-note { font-size: 12px; color: #94a3b8; margin: 0; }
</style>
