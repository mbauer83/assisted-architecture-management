<script setup lang="ts">
/**
 * PromoteView — select an entity, preview the promotion plan, prune the closure,
 * resolve conflicts, then execute.  After execution the promoted entities are
 * transparently replaced by global-entity-reference proxies in the engagement repo.
 *
 * Flow: Pick entity → Plan (shows closure + conflicts) → Review/prune → Execute
 */
import { inject, ref, computed, onMounted } from 'vue'
import { Effect } from 'effect'
import { useRoute } from 'vue-router'
import { modelServiceKey } from '../keys'
import EntitySearchInput from '../components/EntitySearchInput.vue'
import type { PromotionPlan } from '../../domain'

type ConflictStrategy = 'accept_engagement' | 'accept_enterprise' | 'merge'
type Step = 'pick' | 'plan' | 'execute' | 'done'

const svc = inject(modelServiceKey)!
const route = useRoute()

// ── State ────────────────────────────────────────────────────────────────────

const step = ref<Step>('pick')
const selectedEntityId = ref('')
const selectedEntityName = ref('')

const plan = ref<PromotionPlan | null>(null)
const planning = ref(false)
const planError = ref<string | null>(null)

// Entity exclusion: set of IDs the user unchecked from closure
const excludedEntities = ref<Set<string>>(new Set())
// Connection exclusion
const excludedConnections = ref<Set<string>>(new Set())

// Conflict resolutions: map engagement_id → strategy
const conflictStrategies = ref<Record<string, ConflictStrategy>>({})

const executing = ref(false)
const executeError = ref<string | null>(null)
const executeResult = ref<{
  copied_files: string[]
  updated_files: string[]
  verification_errors: string[]
} | null>(null)

// ── Computed ─────────────────────────────────────────────────────────────────

const effectivePlan = computed(() => {
  if (!plan.value) return null
  return {
    ...plan.value,
    entities_to_add: plan.value.entities_to_add.filter(id => !excludedEntities.value.has(id)),
    conflicts: plan.value.conflicts.filter(c => !excludedEntities.value.has(c.engagement_id)),
    connection_ids: plan.value.connection_ids.filter(id => !excludedConnections.value.has(id)),
  }
})

const totalToPromote = computed(() =>
  (effectivePlan.value?.entities_to_add.length ?? 0) +
  (effectivePlan.value?.conflicts.length ?? 0)
)

const unresolvedConflicts = computed(() =>
  (effectivePlan.value?.conflicts ?? []).filter(c => !conflictStrategies.value[c.engagement_id])
)

const canExecute = computed(() =>
  totalToPromote.value > 0 && unresolvedConflicts.value.length === 0
)

// ── Actions ──────────────────────────────────────────────────────────────────

const onEntityPicked = (id: string, name: string) => {
  selectedEntityId.value = id
  selectedEntityName.value = name
}

const loadPlan = () => {
  if (!selectedEntityId.value) return
  planning.value = true
  planError.value = null
  plan.value = null
  excludedEntities.value = new Set()
  excludedConnections.value = new Set()
  conflictStrategies.value = {}

  Effect.runPromise(
    svc.planPromotion({ entity_id: selectedEntityId.value }),
  ).then(p => {
    plan.value = p
    // Default conflict strategy: accept_enterprise (keep existing global)
    for (const c of p.conflicts) {
      conflictStrategies.value[c.engagement_id] = 'accept_enterprise'
    }
    step.value = 'plan'
  }).catch(e => {
    planError.value = String(e)
  }).finally(() => {
    planning.value = false
  })
}

const toggleEntity = (id: string) => {
  const s = new Set(excludedEntities.value)
  if (s.has(id)) s.delete(id)
  else s.add(id)
  excludedEntities.value = s
}

const toggleConnection = (id: string) => {
  const s = new Set(excludedConnections.value)
  if (s.has(id)) s.delete(id)
  else s.add(id)
  excludedConnections.value = s
}

const execute = () => {
  if (!plan.value || !canExecute.value) return
  executing.value = true
  executeError.value = null
  step.value = 'execute'

  const resolutions = Object.entries(conflictStrategies.value).map(([id, strategy]) => ({
    engagement_id: id,
    strategy,
  }))

  Effect.runPromise(
    svc.executePromotion({
      entity_id: selectedEntityId.value,
      exclude_entity_ids: [...excludedEntities.value],
      exclude_connection_ids: [...excludedConnections.value],
      conflict_resolutions: resolutions,
      dry_run: false,
    }),
  ).then(result => {
    if (result.executed) {
      executeResult.value = {
        copied_files: [...result.copied_files],
        updated_files: [...result.updated_files],
        verification_errors: [...result.verification_errors],
      }
      step.value = 'done'
    } else {
      executeError.value = [...result.verification_errors].join('\n') || 'Execution failed'
      step.value = 'plan'
    }
  }).catch(e => {
    executeError.value = String(e)
    step.value = 'plan'
  }).finally(() => {
    executing.value = false
  })
}

const restart = () => {
  step.value = 'pick'
  selectedEntityId.value = ''
  selectedEntityName.value = ''
  plan.value = null
  executeResult.value = null
  executeError.value = null
  planError.value = null
}

// Pre-populate from query param (e.g. navigated from EntityDetailView)
onMounted(() => {
  const preId = route.query.entity_id as string | undefined
  if (preId) {
    selectedEntityId.value = preId
    const parts = preId.split('.')
    selectedEntityName.value = parts.length > 2 ? parts.slice(2).join('-') : preId
    loadPlan()
  }
})

const friendlyConnId = (id: string) => {
  // "source_id conn_type → target_id" → show type + friendly names
  const arrowIdx = id.indexOf(' → ')
  if (arrowIdx === -1) return id
  const left = id.slice(0, arrowIdx)
  const target = id.slice(arrowIdx + 3)
  const parts = left.split(' ')
  const connType = parts.slice(1).join(' ')
  const srcParts = parts[0]?.split('.') ?? []
  const tgtParts = target.split('.')
  const srcName = srcParts.length > 2 ? srcParts.slice(2).join('.') : parts[0]
  const tgtName = tgtParts.length > 2 ? tgtParts.slice(2).join('.') : target
  return `${srcName} —[${connType}]→ ${tgtName}`
}
</script>

<template>
  <div class="promote-view">
    <div class="page-header">
      <h1 class="page-title">Promote to Global Repository</h1>
      <p class="page-sub">
        Selected entities are copied to the global (enterprise) repository.
        Their engagement-repo counterparts are transparently replaced by global-entity-reference proxies,
        so existing connections continue to resolve.
      </p>
    </div>

    <!-- Step indicator -->
    <div class="steps">
      <div class="step" :class="{ active: step === 'pick', done: step !== 'pick' }">1. Select entity</div>
      <div class="step-arrow">›</div>
      <div class="step" :class="{ active: step === 'plan', done: step === 'execute' || step === 'done' }">2. Review plan</div>
      <div class="step-arrow">›</div>
      <div class="step" :class="{ active: step === 'execute' || step === 'done' }">3. Execute</div>
    </div>

    <!-- ── Step 1: Pick entity ──────────────────────────────────────────────── -->
    <div v-if="step === 'pick'" class="card step-card">
      <h2 class="card-title">Select the root entity to promote</h2>
      <p class="card-hint">
        Search for the engagement entity you want to promote. The system will compute
        its transitive closure (connected entities via structural and dependency relations)
        and show a plan before any files are modified.
      </p>
      <EntitySearchInput
        placeholder="Search engagement entities…"
        @select="onEntityPicked"
      />
      <div v-if="selectedEntityId" class="selected-entity">
        <span class="sel-label">Selected:</span>
        <span class="sel-name">{{ selectedEntityName }}</span>
        <span class="sel-id mono">{{ selectedEntityId }}</span>
      </div>
      <div class="step-actions">
        <button
          class="btn btn--primary"
          :disabled="!selectedEntityId || planning"
          @click="loadPlan"
        >
          {{ planning ? 'Loading plan…' : 'Preview promotion plan →' }}
        </button>
      </div>
      <p v-if="planError" class="error-msg">{{ planError }}</p>
    </div>

    <!-- ── Step 2: Review plan ─────────────────────────────────────────────── -->
    <template v-if="step === 'plan' && plan">
      <div class="card step-card">
        <div class="plan-header">
          <h2 class="card-title">Promotion plan for <span class="mono">{{ selectedEntityName }}</span></h2>
          <button class="btn btn--ghost" @click="restart">← Start over</button>
        </div>

        <!-- Warnings -->
        <div v-if="plan.warnings.length" class="warnings-box">
          <div v-for="w in plan.warnings" :key="w" class="warn-item">⚠ {{ w }}</div>
        </div>

        <!-- Already in enterprise -->
        <div v-if="plan.already_in_enterprise.length" class="section">
          <h3 class="section-title">Already in global repository ({{ plan.already_in_enterprise.length }})</h3>
          <ul class="id-list id-list--muted">
            <li v-for="id in plan.already_in_enterprise" :key="id" class="mono">{{ id }}</li>
          </ul>
        </div>

        <!-- Fresh adds -->
        <div v-if="plan.entities_to_add.length" class="section">
          <h3 class="section-title">
            New entities to promote ({{ effectivePlan!.entities_to_add.length }} / {{ plan.entities_to_add.length }})
          </h3>
          <p class="section-hint">Uncheck to exclude from this promotion.</p>
          <ul class="checklist">
            <li v-for="id in plan.entities_to_add" :key="id" class="check-row">
              <label class="check-label">
                <input
                  type="checkbox"
                  :checked="!excludedEntities.has(id)"
                  @change="toggleEntity(id)"
                />
                <span class="mono check-id">{{ id }}</span>
              </label>
            </li>
          </ul>
        </div>

        <!-- Conflicts -->
        <div v-if="plan.conflicts.length" class="section">
          <h3 class="section-title section-title--warn">
            Conflicts ({{ effectivePlan!.conflicts.length }} active / {{ plan.conflicts.length }} total)
          </h3>
          <p class="section-hint">An entity with the same type and name already exists in the global repo. Choose how to resolve each.</p>
          <div v-for="c in plan.conflicts" :key="c.engagement_id" class="conflict-card">
            <div class="conflict-header">
              <label class="check-label">
                <input
                  type="checkbox"
                  :checked="!excludedEntities.has(c.engagement_id)"
                  @change="toggleEntity(c.engagement_id)"
                />
                <span>
                  <span class="mono">{{ c.engagement_id }}</span>
                  <span class="conflict-vs"> vs global </span>
                  <span class="mono">{{ c.enterprise_id }}</span>
                </span>
              </label>
            </div>
            <div v-if="!excludedEntities.has(c.engagement_id)" class="conflict-strategies">
              <label v-for="opt in [
                { value: 'accept_enterprise', label: 'Keep global version' },
                { value: 'accept_engagement', label: 'Replace with engagement version' },
              ]" :key="opt.value" class="strategy-opt">
                <input
                  type="radio"
                  :name="`conflict-${c.engagement_id}`"
                  :value="opt.value"
                  v-model="conflictStrategies[c.engagement_id]"
                />
                {{ opt.label }}
              </label>
            </div>
          </div>
        </div>

        <!-- Connections to promote -->
        <div v-if="plan.connection_ids.length" class="section section--collapsed">
          <h3 class="section-title">
            Connections to promote ({{ effectivePlan!.connection_ids.length }} / {{ plan.connection_ids.length }})
          </h3>
          <ul class="checklist">
            <li v-for="id in plan.connection_ids" :key="id" class="check-row">
              <label class="check-label">
                <input
                  type="checkbox"
                  :checked="!excludedConnections.has(id)"
                  @change="toggleConnection(id)"
                />
                <span class="conn-id">{{ friendlyConnId(id) }}</span>
              </label>
            </li>
          </ul>
        </div>

        <!-- Nothing to promote -->
        <div v-if="totalToPromote === 0" class="empty-plan">
          Nothing to promote — all entities in the closure are already in the global repository
          or have been excluded.
        </div>

        <!-- Unresolved conflict warning -->
        <div v-if="unresolvedConflicts.length" class="warn-banner">
          {{ unresolvedConflicts.length }} conflict{{ unresolvedConflicts.length > 1 ? 's' : '' }}
          still need{{ unresolvedConflicts.length === 1 ? 's' : '' }} a resolution strategy.
        </div>

        <div v-if="executeError" class="error-msg">{{ executeError }}</div>

        <div class="step-actions">
          <button
            class="btn btn--primary"
            :disabled="!canExecute || executing"
            @click="execute"
          >
            {{ executing ? 'Promoting…' : `Promote ${totalToPromote} ${totalToPromote === 1 ? 'entity' : 'entities'} →` }}
          </button>
        </div>
      </div>
    </template>

    <!-- ── Step 4: Done ────────────────────────────────────────────────────── -->
    <div v-if="step === 'done' && executeResult" class="card step-card step-card--success">
      <h2 class="card-title card-title--success">Promotion complete</h2>
      <p class="success-msg">
        The selected entities have been copied to the global repository and replaced
        in the engagement repo by transparent global-entity-reference proxies.
      </p>
      <div v-if="executeResult.copied_files.length" class="result-section">
        <h3 class="section-title">Files added to global repo ({{ executeResult.copied_files.length }})</h3>
        <ul class="id-list">
          <li v-for="f in executeResult.copied_files" :key="f" class="mono">{{ f }}</li>
        </ul>
      </div>
      <div v-if="executeResult.updated_files.length" class="result-section">
        <h3 class="section-title">Files updated ({{ executeResult.updated_files.length }})</h3>
        <ul class="id-list">
          <li v-for="f in executeResult.updated_files" :key="f" class="mono">{{ f }}</li>
        </ul>
      </div>
      <div class="step-actions">
        <button class="btn btn--primary" @click="restart">Promote another entity</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.promote-view { max-width: 800px; }

.page-header { margin-bottom: 24px; }
.page-title { font-size: 22px; font-weight: 600; margin-bottom: 6px; }
.page-sub { font-size: 13px; color: #6b7280; max-width: 640px; }

/* Steps */
.steps { display: flex; align-items: center; gap: 6px; margin-bottom: 24px; }
.step {
  padding: 5px 12px; border-radius: 20px; font-size: 12px; font-weight: 500;
  background: #f1f5f9; color: #64748b;
}
.step.active { background: #2563eb; color: white; }
.step.done { background: #dcfce7; color: #166534; }
.step-arrow { color: #9ca3af; font-size: 16px; }

/* Card */
.card { background: white; border-radius: 8px; border: 1px solid #e5e7eb; padding: 20px 24px; margin-bottom: 16px; }
.step-card--success { border-color: #bbf7d0; background: #f0fdf4; }
.card-title { font-size: 16px; font-weight: 600; color: #111827; margin-bottom: 10px; }
.card-title--success { color: #166534; }
.card-hint { font-size: 13px; color: #6b7280; margin-bottom: 14px; }
.plan-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px; }

/* Section */
.section { margin-top: 18px; }
.section--collapsed { margin-top: 18px; }
.section-title { font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: .05em; color: #374151; margin-bottom: 8px; }
.section-title--warn { color: #b45309; }
.section-hint { font-size: 12px; color: #6b7280; margin-bottom: 8px; }

/* Checklist */
.checklist { list-style: none; display: flex; flex-direction: column; gap: 4px; }
.check-row { display: flex; align-items: center; }
.check-label { display: flex; align-items: center; gap: 8px; cursor: pointer; font-size: 13px; }
.check-label input[type=checkbox] { width: 15px; height: 15px; accent-color: #2563eb; cursor: pointer; }

/* ID lists */
.id-list { list-style: none; display: flex; flex-direction: column; gap: 3px; }
.id-list--muted .mono { color: #9ca3af; }
.check-id { font-size: 12px; color: #374151; }
.conn-id { font-size: 12px; color: #374151; }

/* Conflicts */
.conflict-card { border: 1px solid #fde68a; border-radius: 6px; padding: 10px 14px; margin-bottom: 8px; background: #fffbeb; }
.conflict-header { margin-bottom: 8px; }
.conflict-vs { color: #9ca3af; margin: 0 6px; font-size: 12px; }
.conflict-strategies { display: flex; gap: 16px; flex-wrap: wrap; }
.strategy-opt { display: flex; align-items: center; gap: 6px; font-size: 13px; cursor: pointer; }
.strategy-opt input[type=radio] { accent-color: #2563eb; }

/* Actions */
.step-actions { margin-top: 20px; display: flex; gap: 10px; }
.selected-entity { display: flex; align-items: center; gap: 10px; margin: 12px 0; padding: 10px 14px; background: #eff6ff; border-radius: 6px; border: 1px solid #bfdbfe; }
.sel-label { font-size: 11px; font-weight: 700; text-transform: uppercase; color: #3b82f6; }
.sel-name { font-weight: 600; color: #1e40af; }
.sel-id { font-size: 11px; color: #6b7280; }

/* Buttons */
.btn { padding: 8px 18px; border-radius: 6px; font-size: 13px; font-weight: 500; cursor: pointer; border: 1px solid transparent; }
.btn--primary { background: #2563eb; color: white; }
.btn--primary:hover:not(:disabled) { background: #1d4ed8; }
.btn--primary:disabled { opacity: .5; cursor: not-allowed; }
.btn--ghost { background: transparent; color: #6b7280; border-color: #d1d5db; }
.btn--ghost:hover { background: #f9fafb; }

/* Warnings / errors */
.warnings-box { background: #fffbeb; border: 1px solid #fde68a; border-radius: 6px; padding: 10px 14px; margin-bottom: 14px; }
.warn-item { font-size: 13px; color: #92400e; }
.warn-banner { margin-top: 14px; padding: 10px 14px; background: #fef3c7; border: 1px solid #fde68a; border-radius: 6px; font-size: 13px; color: #92400e; font-weight: 500; }
.empty-plan { margin-top: 16px; font-size: 13px; color: #6b7280; font-style: italic; }
.error-msg { margin-top: 12px; color: #dc2626; font-size: 13px; }
.success-msg { font-size: 13px; color: #166534; margin-bottom: 14px; }
.result-section { margin-top: 14px; }

.mono { font-family: monospace; font-size: 12px; }
</style>
