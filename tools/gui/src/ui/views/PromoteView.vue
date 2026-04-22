<script setup lang="ts">
import { inject, ref, computed, onMounted, onUnmounted } from 'vue'
import { Effect } from 'effect'
import { useRoute } from 'vue-router'
import { modelServiceKey } from '../keys'
import EntitySearchInput from '../components/EntitySearchInput.vue'
import ArchimateTypeGlyph from '../components/ArchimateTypeGlyph.vue'
import EntitySelectionList from '../components/EntitySelectionList.vue'
import type { PromotionPlan, EntityDisplayInfo, EntityContextConnection } from '../../domain'

type ConflictStrategy = 'accept_engagement' | 'accept_enterprise' | 'merge'
type Step = 'pick' | 'review' | 'execute' | 'done'

const svc = inject(modelServiceKey)!
const route = useRoute()
const toGlyphKey = (t: string) => t.replace(/[A-Z]/g, (c, i) => (i > 0 ? '-' : '') + c.toLowerCase())

const step = ref<Step>('pick')
const selectedEntityId = ref('')
const selectedEntityName = ref('')

const includedEntities = ref<EntityDisplayInfo[]>([])
const newInclusionIds = ref<Set<string>>(new Set())
const allModelConns = ref<Map<string, EntityContextConnection>>(new Map())
const includedConnIds = ref<Set<string>>(new Set())
const expandedConnectionEntityIds = ref<Set<string>>(new Set())
const expandedRelatedEntityIds = ref<Set<string>>(new Set())
const includedEntityIds = computed(() => new Set(includedEntities.value.map((e) => e.artifact_id)))

const searchQuery = ref('')
const searchResults = ref<EntityDisplayInfo[]>([])
const showDropdown = ref(false)
let searchTimer: ReturnType<typeof setTimeout> | null = null

const plan = ref<PromotionPlan | null>(null)
const planning = ref(false)
const planError = ref<string | null>(null)
const conflictStrategies = ref<Record<string, ConflictStrategy>>({})

const executing = ref(false)
const executeError = ref<string | null>(null)
const executeResult = ref<{
  copied_files: string[]
  updated_files: string[]
  verification_errors: string[]
} | null>(null)

const selectionRows = computed(() =>
  includedEntities.value.map((entity) => ({
    entity,
    newInclusion: newInclusionIds.value.has(entity.artifact_id),
    badgeText: newInclusionIds.value.has(entity.artifact_id) ? 'new' : undefined,
    actionKind: 'remove' as const,
    actionTitle: 'Remove entity from promotion set',
  })),
)

const relatedEntitiesById = computed<Record<string, EntityDisplayInfo[]>>(() => {
  const related: Record<string, EntityDisplayInfo[]> = {}
  const seenByEntity = new Map<string, Set<string>>()
  for (const entity of includedEntities.value) related[entity.artifact_id] = []
  for (const conn of allModelConns.value.values()) {
    const endpoints: Array<[string, string]> = [
      [conn.source, conn.target],
      [conn.target, conn.source],
    ]
    for (const [ownerId, otherId] of endpoints) {
      if (!includedEntityIds.value.has(ownerId) || includedEntityIds.value.has(otherId)) continue
      const seen = seenByEntity.get(ownerId) ?? new Set<string>()
      if (seen.has(otherId)) continue
      seen.add(otherId)
      seenByEntity.set(ownerId, seen)
      const name = ownerId === conn.source ? (conn.target_name ?? otherId) : (conn.source_name ?? otherId)
      const artifactType = ownerId === conn.source ? conn.target_artifact_type : conn.source_artifact_type
      const domain = ownerId === conn.source ? conn.target_domain : conn.source_domain
      const scope = ownerId === conn.source ? conn.target_scope : conn.source_scope
      related[ownerId].push({
        artifact_id: otherId,
        name,
        artifact_type: artifactType,
        domain,
        subdomain: '',
        status: scope,
        display_alias: '',
        element_type: artifactType,
        element_label: name,
      })
    }
  }
  for (const entityId of Object.keys(related)) related[entityId].sort((a, b) => a.name.localeCompare(b.name))
  return related
})

const unresolvedConflicts = computed(() =>
  (plan.value?.conflicts ?? []).filter(c => !conflictStrategies.value[c.engagement_id])
)
const totalToPromote = computed(() =>
  (plan.value?.entities_to_add.length ?? 0) + (plan.value?.conflicts.length ?? 0)
)
const canExecute = computed(() =>
  includedEntities.value.length > 0 && unresolvedConflicts.value.length === 0
)

const refreshDiscovery = async () => {
  const discovery = await Effect.runPromise(
    svc.discoverDiagramEntities({
      includedEntityIds: includedEntities.value.map((e) => e.artifact_id),
      query: searchQuery.value.trim() || undefined,
      maxHops: 1,
      limit: 20,
    }),
  ).catch(() => null)
  if (!discovery) return
  allModelConns.value = new Map(discovery.candidate_connections.map((conn) => [conn.artifact_id, conn]))
  searchResults.value = discovery.search_results.filter((item) => !includedEntityIds.value.has(item.artifact_id))
  showDropdown.value = Boolean(searchQuery.value.trim() && searchResults.value.length)
}

const refreshPlan = async () => {
  if (!includedEntities.value.length) {
    plan.value = null
    conflictStrategies.value = {}
    return
  }
  planning.value = true
  planError.value = null
  const nextPlan = await Effect.runPromise(
    svc.planPromotion({
      entity_id: selectedEntityId.value || includedEntities.value[0]?.artifact_id,
      entity_ids: includedEntities.value.map((e) => e.artifact_id),
      connection_ids: [...includedConnIds.value],
    }),
  ).catch((e) => {
    planError.value = String(e)
    return null
  })
  planning.value = false
  if (!nextPlan) return
  plan.value = nextPlan
  const nextStrategies: Record<string, ConflictStrategy> = {}
  for (const conflict of nextPlan.conflicts) {
    nextStrategies[conflict.engagement_id] = conflictStrategies.value[conflict.engagement_id] ?? 'accept_enterprise'
  }
  conflictStrategies.value = nextStrategies
}

const onSearchInput = () => {
  if (searchTimer) clearTimeout(searchTimer)
  const q = searchQuery.value.trim()
  if (!q) {
    searchResults.value = []
    showDropdown.value = false
    void refreshDiscovery()
    return
  }
  searchTimer = setTimeout(() => {
    void refreshDiscovery()
  }, 280)
}

const closeDropdown = () => { setTimeout(() => { showDropdown.value = false }, 150) }

const addEntity = async (entity: EntityDisplayInfo) => {
  if (includedEntityIds.value.has(entity.artifact_id)) return
  includedEntities.value.push(entity)
  newInclusionIds.value = new Set(newInclusionIds.value).add(entity.artifact_id)
  showDropdown.value = false
  searchQuery.value = ''
  await refreshDiscovery()
  const nextConnIds = new Set(includedConnIds.value)
  for (const conn of allModelConns.value.values()) {
    const otherId = conn.source === entity.artifact_id ? conn.target : conn.source
    if ((conn.source === entity.artifact_id || conn.target === entity.artifact_id) && includedEntityIds.value.has(otherId)) {
      nextConnIds.add(conn.artifact_id)
    }
  }
  includedConnIds.value = nextConnIds
  await refreshPlan()
}

const removeEntity = async (artifactId: string) => {
  includedEntities.value = includedEntities.value.filter((e) => e.artifact_id !== artifactId)
  const nextNewIds = new Set(newInclusionIds.value)
  nextNewIds.delete(artifactId)
  newInclusionIds.value = nextNewIds
  const nextConnPanel = new Set(expandedConnectionEntityIds.value)
  nextConnPanel.delete(artifactId)
  expandedConnectionEntityIds.value = nextConnPanel
  const nextRelatedPanel = new Set(expandedRelatedEntityIds.value)
  nextRelatedPanel.delete(artifactId)
  expandedRelatedEntityIds.value = nextRelatedPanel
  const nextConnIds = new Set(includedConnIds.value)
  for (const id of [...nextConnIds]) {
    const conn = allModelConns.value.get(id)
    if (conn && (conn.source === artifactId || conn.target === artifactId)) nextConnIds.delete(id)
  }
  includedConnIds.value = nextConnIds
  await refreshDiscovery()
  await refreshPlan()
}

const toggleConnections = (entityId: string) => {
  const next = new Set(expandedConnectionEntityIds.value)
  if (next.has(entityId)) next.delete(entityId)
  else next.add(entityId)
  expandedConnectionEntityIds.value = next
}

const toggleRelated = (entityId: string) => {
  const next = new Set(expandedRelatedEntityIds.value)
  if (next.has(entityId)) next.delete(entityId)
  else next.add(entityId)
  expandedRelatedEntityIds.value = next
}

const toggleConnection = async (id: string) => {
  const next = new Set(includedConnIds.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  includedConnIds.value = next
  await refreshPlan()
}

const loadSelectedEntity = async (id: string, fallbackName: string) => {
  const entity = await Effect.runPromise(svc.getEntity(id)).catch(() => null)
  if (!entity) return null
  selectedEntityId.value = id
  selectedEntityName.value = entity.name || fallbackName
  return {
    artifact_id: entity.artifact_id,
    name: entity.name,
    artifact_type: entity.artifact_type,
    domain: entity.domain,
    subdomain: entity.subdomain,
    status: entity.status,
    display_alias: '',
    element_type: entity.artifact_type,
    element_label: entity.name,
  } as EntityDisplayInfo
}

const startPromotion = async () => {
  if (!selectedEntityId.value) return
  const rootEntity = await loadSelectedEntity(selectedEntityId.value, selectedEntityName.value)
  if (!rootEntity) {
    planError.value = 'Could not load selected entity'
    return
  }
  includedEntities.value = [rootEntity]
  newInclusionIds.value = new Set()
  includedConnIds.value = new Set()
  expandedConnectionEntityIds.value = new Set()
  expandedRelatedEntityIds.value = new Set()
  executeError.value = null
  await refreshDiscovery()
  await refreshPlan()
  step.value = 'review'
}

const onEntityPicked = (id: string, name: string) => {
  selectedEntityId.value = id
  selectedEntityName.value = name
}

const execute = () => {
  if (!canExecute.value) return
  executing.value = true
  executeError.value = null
  step.value = 'execute'
  const resolutions = Object.entries(conflictStrategies.value).map(([id, strategy]) => ({
    engagement_id: id,
    strategy,
  }))
  Effect.runPromise(
    svc.executePromotion({
      entity_id: selectedEntityId.value || includedEntities.value[0]?.artifact_id,
      entity_ids: includedEntities.value.map((e) => e.artifact_id),
      connection_ids: [...includedConnIds.value],
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
      step.value = 'review'
    }
  }).catch(e => {
    executeError.value = String(e)
    step.value = 'review'
  }).finally(() => {
    executing.value = false
  })
}

const restart = () => {
  step.value = 'pick'
  selectedEntityId.value = ''
  selectedEntityName.value = ''
  includedEntities.value = []
  newInclusionIds.value = new Set()
  allModelConns.value = new Map()
  includedConnIds.value = new Set()
  expandedConnectionEntityIds.value = new Set()
  expandedRelatedEntityIds.value = new Set()
  plan.value = null
  planError.value = null
  executeResult.value = null
  executeError.value = null
  conflictStrategies.value = {}
}

onMounted(() => {
  const preId = route.query.entity_id as string | undefined
  if (preId) {
    selectedEntityId.value = preId
    const parts = preId.split('.')
    selectedEntityName.value = parts.length > 2 ? parts.slice(2).join('-') : preId
    void startPromotion()
  }
})

onUnmounted(() => {
  if (searchTimer) clearTimeout(searchTimer)
})
</script>

<template>
  <div class="promote-view">
    <div class="page-header">
      <h1 class="page-title">Promote to Global Repository</h1>
      <p class="page-sub">
        Build an explicit promotion set of entities and connections, review any conflicts, then execute.
      </p>
    </div>

    <div class="steps">
      <div class="step" :class="{ active: step === 'pick', done: step !== 'pick' }">1. Select root</div>
      <div class="step-arrow">›</div>
      <div class="step" :class="{ active: step === 'review', done: step === 'execute' || step === 'done' }">2. Curate set</div>
      <div class="step-arrow">›</div>
      <div class="step" :class="{ active: step === 'execute' || step === 'done' }">3. Execute</div>
    </div>

    <div v-if="step === 'pick'" class="card step-card">
      <h2 class="card-title">Select the first entity to promote</h2>
      <p class="card-hint">
        Promotion now uses only the entities and connections you explicitly include.
      </p>
      <EntitySearchInput placeholder="Search engagement entities…" @select="onEntityPicked" />
      <div v-if="selectedEntityId" class="selected-entity">
        <span class="sel-label">Selected:</span>
        <span class="sel-name">{{ selectedEntityName }}</span>
        <span class="sel-id mono">{{ selectedEntityId }}</span>
      </div>
      <div class="step-actions">
        <button class="btn btn--primary" :disabled="!selectedEntityId" @click="startPromotion">
          Build promotion set →
        </button>
      </div>
      <p v-if="planError" class="error-msg">{{ planError }}</p>
    </div>

    <template v-if="step === 'review'">
      <div class="review-grid">
        <div class="card step-card">
          <div class="plan-header">
            <h2 class="card-title">Promotion set for <span class="mono">{{ selectedEntityName }}</span></h2>
            <button class="btn btn--ghost" @click="restart">← Start over</button>
          </div>

          <div class="form-row">
            <label class="section-title">Add Entities</label>
            <div class="search-wrap">
              <input
                v-model="searchQuery"
                class="inp"
                placeholder="Search by name, type, domain…"
                @input="onSearchInput"
                @blur="closeDropdown"
                @focus="() => { if (searchResults.length) showDropdown = true }"
              />
              <div v-if="showDropdown" class="dropdown">
                <button
                  v-for="r in searchResults"
                  :key="r.artifact_id"
                  class="dd-item"
                  @mousedown.prevent="addEntity(r)"
                >
                  <span class="dd-glyph" :title="r.element_type || r.artifact_type"><ArchimateTypeGlyph :type="toGlyphKey(r.element_type || r.artifact_type)" :size="16" /></span>
                  <span class="dd-name">{{ r.name }}</span>
                  <span class="dd-domain">{{ r.domain }}</span>
                </button>
              </div>
            </div>
          </div>

          <div v-if="includedEntities.length" class="form-row">
            <label class="section-title">Included Entities ({{ includedEntities.length }})</label>
            <EntitySelectionList
              :rows="selectionRows"
              :candidate-connections="[...allModelConns.values()]"
              :included-entity-ids="[...includedEntityIds]"
              :included-connection-ids="[...includedConnIds]"
              :related-entities-by-id="relatedEntitiesById"
              :expanded-connection-entity-ids="[...expandedConnectionEntityIds]"
              :expanded-related-entity-ids="[...expandedRelatedEntityIds]"
              @toggle-connections="toggleConnections"
              @toggle-related="toggleRelated"
              @toggle-connection="toggleConnection"
              @add-related-entity="addEntity"
              @entity-action="removeEntity"
            />
          </div>

          <div v-if="executeError" class="error-msg">{{ executeError }}</div>

          <div class="step-actions">
            <button class="btn btn--primary" :disabled="!canExecute || executing || planning" @click="execute">
              {{ executing ? 'Promoting…' : `Promote ${totalToPromote} ${totalToPromote === 1 ? 'entity' : 'entities'} →` }}
            </button>
          </div>
        </div>

        <div class="card step-card">
          <h2 class="card-title">Plan Summary</h2>
          <div v-if="planning" class="state-msg">Refreshing plan…</div>
          <p v-if="planError" class="error-msg">{{ planError }}</p>
          <template v-if="plan">
            <div v-if="plan.warnings.length" class="warnings-box">
              <div v-for="w in plan.warnings" :key="w" class="warn-item">{{ w }}</div>
            </div>

            <div v-if="plan.already_in_enterprise.length" class="section">
              <h3 class="section-title">Already in global repository</h3>
              <ul class="id-list id-list--muted">
                <li v-for="id in plan.already_in_enterprise" :key="id" class="mono">{{ id }}</li>
              </ul>
            </div>

            <div v-if="plan.entities_to_add.length" class="section">
              <h3 class="section-title">New entities to promote</h3>
              <ul class="id-list">
                <li v-for="id in plan.entities_to_add" :key="id" class="mono">{{ id }}</li>
              </ul>
            </div>

            <div v-if="plan.conflicts.length" class="section">
              <h3 class="section-title section-title--warn">Conflicts</h3>
              <div v-for="c in plan.conflicts" :key="c.engagement_id" class="conflict-card">
                <div class="conflict-header">
                  <span class="mono">{{ c.engagement_id }}</span>
                  <span class="conflict-vs"> vs global </span>
                  <span class="mono">{{ c.enterprise_id }}</span>
                </div>
                <div class="conflict-strategies">
                  <label v-for="opt in [
                    { value: 'accept_enterprise', label: 'Keep global version' },
                    { value: 'accept_engagement', label: 'Replace with selected version' },
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

            <div v-if="plan.connection_ids.length" class="section">
              <h3 class="section-title">Selected connections</h3>
              <ul class="id-list">
                <li v-for="id in plan.connection_ids" :key="id" class="mono">{{ id }}</li>
              </ul>
            </div>

            <div v-if="unresolvedConflicts.length" class="warn-banner">
              {{ unresolvedConflicts.length }} conflict{{ unresolvedConflicts.length > 1 ? 's' : '' }}
              still need{{ unresolvedConflicts.length === 1 ? 's' : '' }} a resolution strategy.
            </div>
          </template>
        </div>
      </div>
    </template>

    <div v-if="step === 'done' && executeResult" class="card step-card step-card--success">
      <h2 class="card-title card-title--success">Promotion complete</h2>
      <div v-if="executeResult.copied_files.length" class="result-section">
        <h3 class="section-title">Files added to global repo</h3>
        <ul class="id-list">
          <li v-for="f in executeResult.copied_files" :key="f" class="mono">{{ f }}</li>
        </ul>
      </div>
      <div v-if="executeResult.updated_files.length" class="result-section">
        <h3 class="section-title">Files updated</h3>
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
.promote-view { max-width: 1280px; }
.page-header { margin-bottom: 24px; }
.page-title { font-size: 22px; font-weight: 600; margin-bottom: 6px; }
.page-sub { font-size: 13px; color: #6b7280; max-width: 720px; }
.steps { display: flex; align-items: center; gap: 6px; margin-bottom: 24px; }
.step { padding: 5px 12px; border-radius: 20px; font-size: 12px; font-weight: 500; background: #f1f5f9; color: #64748b; }
.step.active { background: #2563eb; color: white; }
.step.done { background: #dcfce7; color: #166534; }
.step-arrow { color: #9ca3af; font-size: 16px; }
.review-grid { display: grid; grid-template-columns: minmax(0, 1.3fr) minmax(320px, .8fr); gap: 16px; align-items: start; }
@media (max-width: 980px) { .review-grid { grid-template-columns: 1fr; } }
.card { background: white; border-radius: 8px; border: 1px solid #e5e7eb; padding: 20px 24px; margin-bottom: 16px; }
.step-card--success { border-color: #bbf7d0; background: #f0fdf4; }
.card-title { font-size: 16px; font-weight: 600; color: #111827; margin-bottom: 10px; }
.card-title--success { color: #166534; }
.card-hint { font-size: 13px; color: #6b7280; margin-bottom: 14px; }
.plan-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; margin-bottom: 10px; }
.form-row { margin-bottom: 16px; }
.section { margin-top: 18px; }
.section-title { font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: .05em; color: #374151; margin-bottom: 8px; }
.section-title--warn { color: #b45309; }
.search-wrap { position: relative; }
.inp { width: 100%; padding: 7px 10px; border-radius: 6px; border: 1px solid #d1d5db; font-size: 13px; outline: none; box-sizing: border-box; background: white; }
.inp:focus { border-color: #2563eb; }
.dropdown { position: absolute; top: calc(100% + 3px); left: 0; right: 0; background: white; border: 1px solid #d1d5db; border-radius: 6px; box-shadow: 0 4px 12px rgba(0,0,0,.1); z-index: 100; max-height: 260px; overflow-y: auto; }
.dd-item { display: flex; align-items: center; gap: 6px; width: 100%; text-align: left; padding: 8px 10px; background: none; border: none; border-bottom: 1px solid #f3f4f6; cursor: pointer; font-size: 13px; }
.dd-item:last-child { border-bottom: none; }
.dd-item:hover { background: #f0f7ff; }
.dd-glyph { display: flex; align-items: center; flex-shrink: 0; color: #4b5563; }
.dd-name { font-weight: 500; flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dd-domain { font-size: 11px; color: #9ca3af; white-space: nowrap; }
.id-list { list-style: none; display: flex; flex-direction: column; gap: 3px; }
.id-list--muted .mono { color: #9ca3af; }
.conflict-card { border: 1px solid #fde68a; border-radius: 6px; padding: 10px 14px; margin-bottom: 8px; background: #fffbeb; }
.conflict-header { margin-bottom: 8px; }
.conflict-vs { color: #9ca3af; margin: 0 6px; font-size: 12px; }
.conflict-strategies { display: flex; gap: 16px; flex-wrap: wrap; }
.strategy-opt { display: flex; align-items: center; gap: 6px; font-size: 13px; cursor: pointer; }
.strategy-opt input[type=radio] { accent-color: #2563eb; }
.warnings-box { background: #fffbeb; border: 1px solid #fde68a; border-radius: 6px; padding: 10px 14px; margin-bottom: 14px; }
.warn-item { font-size: 13px; color: #92400e; }
.warn-banner { margin-top: 14px; padding: 10px 14px; background: #fef3c7; border: 1px solid #fde68a; border-radius: 6px; font-size: 13px; color: #92400e; font-weight: 500; }
.step-actions { margin-top: 20px; display: flex; gap: 10px; }
.selected-entity { display: flex; align-items: center; gap: 10px; margin: 12px 0; padding: 10px 14px; background: #eff6ff; border-radius: 6px; border: 1px solid #bfdbfe; }
.sel-label { font-size: 11px; font-weight: 700; text-transform: uppercase; color: #3b82f6; }
.sel-name { font-weight: 600; color: #1e40af; }
.sel-id { font-size: 11px; color: #6b7280; }
.btn { padding: 8px 18px; border-radius: 6px; font-size: 13px; font-weight: 500; cursor: pointer; border: 1px solid transparent; }
.btn--primary { background: #2563eb; color: white; }
.btn--primary:hover:not(:disabled) { background: #1d4ed8; }
.btn--primary:disabled { opacity: .5; cursor: not-allowed; }
.btn--ghost { background: transparent; color: #6b7280; border-color: #d1d5db; }
.btn--ghost:hover { background: #f9fafb; }
.state-msg { font-size: 13px; color: #6b7280; }
.error-msg { margin-top: 12px; color: #dc2626; font-size: 13px; }
.result-section { margin-top: 14px; }
.mono { font-family: monospace; font-size: 12px; }
</style>
