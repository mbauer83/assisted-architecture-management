<script setup lang="ts">
/**
 * Viewpoint definitions management view: list the effective merged catalog (engagement
 * definitions editable, enterprise/module read-only), and create/edit through the
 * criteria-tree builder — one save path (`persist_edit`-mode validation) shared with the
 * MCP authoring tool. No raw-YAML editing surface anywhere.
 */
import { computed, inject, onMounted, provide, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Effect } from 'effect'
import { modelServiceKey } from '../keys'
import { useWriteBlock } from '../composables/useWriteBlock'
import { readErrorMessage } from '../lib/errors'
import type {
  CriteriaCatalog, ViewpointDefinitionEnvelope, ViewpointExecutionResult, ViewpointPersistResult,
  ViewpointReferencer, ViewpointValidationIssue,
} from '../../domain'
import { VALID_CONTENTS, VALID_PURPOSES, mkDefinitionDraft } from '../../domain/viewpointDefinitionDraft'
import type { ViewpointDefinitionDraft } from '../../domain/viewpointDefinitionDraft'
import { definitionFromMapping, definitionToMapping } from '../../domain/viewpointDefinitionSerialization'
import { presentationFromMapping } from '../../domain/viewpointPresentationSerialization'
import { groupFromMapping, queryToMapping } from '../../domain/viewpointCriteriaSerialization'
import { mkNeighborInclusion } from '../../domain/viewpointCriteria'
import type { NeighborInclusionNode } from '../../domain/viewpointCriteria'
import { GROUP_BY_DIMENSIONS, mkColumn, mkPresentation } from '../../domain/viewpointPresentation'
import type { ColumnSpecNode, Representation } from '../../domain/viewpointPresentation'
import { resolveIssuePathNodeId } from '../../domain/viewpointIssuePath'
import { HIGHLIGHTED_NODE_ID_KEY } from '../components/CriteriaTreeBuilder.helpers'
import { createDebouncer } from '../lib/debounce'
import {
  csvToList, firstErrorNodeId, formatPreviewCounts, formatScopeSummary, isSemanticEdit, listToCsv,
} from './ViewpointsManagementView.helpers'
import CriteriaTreeBuilder from '../components/CriteriaTreeBuilder.vue'
import OptionalCriteriaSlot from '../components/OptionalCriteriaSlot.vue'
import StyleRuleEditor from '../components/StyleRuleEditor.vue'
import MatrixAxesEditor from '../components/MatrixAxesEditor.vue'

const svc = inject(modelServiceKey)!
const writeBlocked = useWriteBlock()
const route = useRoute()
const router = useRouter()

const highlightedNodeId = ref<string | null>(null)
provide(HIGHLIGHTED_NODE_ID_KEY, highlightedNodeId)

const mode = ref<'list' | 'edit'>('list')
const definitions = ref<readonly ViewpointDefinitionEnvelope[]>([])
const catalog = ref<CriteriaCatalog | null>(null)
const loadError = ref<string | null>(null)

const draft = ref<ViewpointDefinitionDraft | null>(null)
const originalDraft = ref<ViewpointDefinitionDraft | null>(null)
const isCreating = ref(false)
const activeTab = ref<'general' | 'scope' | 'query' | 'presentation'>('general')
const issues = ref<readonly ViewpointValidationIssue[]>([])
const referencers = ref<readonly ViewpointReferencer[]>([])
const saving = ref(false)
const summary = ref('')

// ── WU-E5c: live preview + test-run before save ────────────────────────────
// Two distinct results, kept in separate refs so the debounced tight-limit preview never
// masquerades as a completed test-run (a `limit: 0` preview always shows 0 returned).
const previewResult = ref<ViewpointExecutionResult | null>(null)
const testRunResult = ref<ViewpointExecutionResult | null>(null)
const testRunning = ref(false)
const testRunError = ref<string | null>(null)

const REPRESENTATIONS: Representation[] = ['exploration', 'table', 'matrix', 'diagram']

const loadDefinitions = () =>
  Effect.runPromise(svc.listViewpointDefinitions()).then((list) => { definitions.value = list })
const loadCatalog = () =>
  Effect.runPromise(svc.getCriteriaCatalog()).then((c) => { catalog.value = c })

onMounted(() => {
  Promise.all([loadDefinitions(), loadCatalog()]).catch((reason: unknown) => { loadError.value = readErrorMessage(reason) })
  const seed = route.query.seedEntityCriteria
  if (typeof seed === 'string') {
    startCreate()
    try {
      draft.value!.query!.entityCriteria = groupFromMapping(JSON.parse(seed) as Record<string, unknown>, 'entity')
    } catch {
      // Malformed/stale seed param — ignore and leave the fresh, empty criteria in place.
    }
    void router.replace({ path: '/viewpoints', query: {} })
  }
})

const startCreate = () => {
  draft.value = mkDefinitionDraft()
  originalDraft.value = null
  isCreating.value = true
  issues.value = []
  referencers.value = []
  activeTab.value = 'general'
  mode.value = 'edit'
  previewResult.value = null
  testRunResult.value = null
  testRunError.value = null
}

const startEdit = (envelope: ViewpointDefinitionEnvelope) => {
  draft.value = definitionFromMapping(envelope)
  originalDraft.value = definitionFromMapping(envelope)
  isCreating.value = false
  issues.value = []
  activeTab.value = 'general'
  mode.value = 'edit'
  previewResult.value = null
  testRunResult.value = null
  testRunError.value = null
  void Effect.runPromise(svc.getViewpointReferencers(envelope.slug)).then((r) => { referencers.value = r })
}

/** Execute action (WU-E8 exploration; WU-E9 table/matrix/diagram): route to the
 * representation-appropriate execution surface, pre-loaded with this viewpoint's
 * repository-context population — no separate anchor entity required. */
const EXECUTION_ROUTE_BY_REPRESENTATION: Record<Representation, string> = {
  exploration: '/graph', table: '/entities', matrix: '/viewpoints/matrix', diagram: '/viewpoints/diagram',
}

const executeViewpoint = (envelope: ViewpointDefinitionEnvelope) => {
  const representation = presentationFromMapping(envelope.presentation)?.representation ?? 'exploration'
  void router.push({ path: EXECUTION_ROUTE_BY_REPRESENTATION[representation], query: { viewpoint: envelope.slug } })
}

const backToList = () => {
  mode.value = 'list'
  draft.value = null
  originalDraft.value = null
  void loadDefinitions()
}

const isSemantic = computed(() => draft.value && originalDraft.value && isSemanticEdit(draft.value, originalDraft.value))
const versionBumped = computed(() => draft.value && originalDraft.value && draft.value.version > originalDraft.value.version)
const showVersionBumpHint = computed(() => !isCreating.value && isSemantic.value && !versionBumped.value)

let summaryTimer: ReturnType<typeof setTimeout> | undefined
watch(() => draft.value?.query, (query) => {
  if (summaryTimer) clearTimeout(summaryTimer)
  if (!query) { summary.value = ''; return }
  summaryTimer = setTimeout(() => {
    Effect.runPromise(svc.summarizeViewpointQuery(queryToMapping(query))).then((s) => { summary.value = s }).catch(() => {})
  }, 250)
}, { deep: true, immediate: true })

/** Debounced live-preview counts (WU-E5c, companion plan §7.1): a `limit: 0` execution of
 * the draft's ad-hoc query — cheap enough (no entity/connection records fetched) to run on
 * every settled keystroke while building criteria. */
const debouncePreview = createDebouncer(400)
watch(() => draft.value?.query, (query) => {
  if (!query) { previewResult.value = null; return }
  debouncePreview(() => {
    Effect.runPromise(svc.executeViewpoint({ query: queryToMapping(query), limit: 0 }))
      .then((result) => { previewResult.value = result })
      .catch(() => { previewResult.value = null })
  })
}, { deep: true, immediate: true })

/** Full test-run (WU-E5c): the real §7.1 counts + warnings the query would return today
 * (default limit — the actual execution bound, not the tight preview limit), plus a
 * `dry_run` save-mode validation pass so a definition that would fail to persist is
 * caught, and highlighted at its offending node, before the user attempts to save. */
const testRun = async () => {
  if (!draft.value) return
  testRunning.value = true
  testRunError.value = null
  testRunResult.value = null
  try {
    if (draft.value.query) {
      testRunResult.value = await Effect.runPromise(svc.executeViewpoint({ query: queryToMapping(draft.value.query) }))
    }
    const body = { definition: definitionToMapping(draft.value), dry_run: true }
    const call = isCreating.value ? svc.createViewpointDefinition(body) : svc.editViewpointDefinition(body)
    const result = await Effect.runPromise(call)
    issues.value = result.issues
    highlightedNodeId.value = firstErrorNodeId(result.issues, draft.value)
  } catch (reason) {
    testRunError.value = readErrorMessage(reason)
  } finally {
    testRunning.value = false
  }
}

const save = () => {
  if (!draft.value) return
  saving.value = true
  const body = { definition: definitionToMapping(draft.value), dry_run: false }
  const call = isCreating.value ? svc.createViewpointDefinition(body) : svc.editViewpointDefinition(body)
  Effect.runPromise(call).then((result: ViewpointPersistResult) => {
    saving.value = false
    if (result.ok) { backToList(); return }
    issues.value = result.issues
    referencers.value = result.referencers.length > 0 ? result.referencers : referencers.value
    highlightedNodeId.value = draft.value ? firstErrorNodeId(result.issues, draft.value) : null
  }).catch((reason: unknown) => {
    saving.value = false
    loadError.value = readErrorMessage(reason)
  })
}

const focusIssue = (issue: ViewpointValidationIssue) => {
  if (!draft.value) return
  highlightedNodeId.value = resolveIssuePathNodeId(issue.path, draft.value)
}

const deleteDefinition = (envelope: ViewpointDefinitionEnvelope) => {
  if (!window.confirm(`Delete viewpoint '${envelope.slug}'?`)) return
  Effect.runPromise(svc.deleteViewpointDefinition({ slug: envelope.slug, dry_run: false })).then((result) => {
    if (result.ok) { void loadDefinitions(); return }
    loadError.value = result.issues[0]?.message ?? 'Delete failed'
  }).catch((reason: unknown) => { loadError.value = readErrorMessage(reason) })
}

// ── General tab ────────────────────────────────────────────────────────────
const togglePurpose = (value: (typeof VALID_PURPOSES)[number]) => {
  if (!draft.value) return
  draft.value.purpose = draft.value.purpose.includes(value)
    ? draft.value.purpose.filter((v) => v !== value)
    : [...draft.value.purpose, value]
}
const toggleContent = (value: (typeof VALID_CONTENTS)[number]) => {
  if (!draft.value) return
  draft.value.content = draft.value.content.includes(value)
    ? draft.value.content.filter((v) => v !== value)
    : [...draft.value.content, value]
}

// ── Scope tab ──────────────────────────────────────────────────────────────
const toggleScopeType = (axis: 'entityTypes' | 'connectionTypes', value: string) => {
  if (!draft.value) return
  const current = draft.value.scope[axis] ?? []
  draft.value.scope = {
    ...draft.value.scope,
    [axis]: current.includes(value) ? current.filter((v) => v !== value) : [...current, value],
  }
}

// ── Query tab ──────────────────────────────────────────────────────────────
const addInclusion = () => {
  if (!draft.value?.query) return
  draft.value.query.includeConnected.push(mkNeighborInclusion())
}
const removeInclusion = (index: number) => {
  if (!draft.value?.query) return
  draft.value.query.includeConnected.splice(index, 1)
}
const updateInclusion = (index: number, patch: Partial<NeighborInclusionNode>) => {
  if (!draft.value?.query) return
  draft.value.query.includeConnected[index] = { ...draft.value.query.includeConnected[index], ...patch }
}

// ── Presentation tab ───────────────────────────────────────────────────────
const addPresentation = (representation: Representation) => {
  if (!draft.value) return
  draft.value.presentation = mkPresentation(representation)
}
const removePresentation = () => { if (draft.value) draft.value.presentation = null }
const changeRepresentation = (representation: Representation) => {
  if (!draft.value) return
  draft.value.presentation = mkPresentation(representation)
}
const addColumn = () => { if (draft.value?.presentation) draft.value.presentation.columns = [...(draft.value.presentation.columns ?? []), mkColumn()] }
const removeColumn = (index: number) => {
  if (!draft.value?.presentation?.columns) return
  draft.value.presentation.columns = draft.value.presentation.columns.filter((_, i) => i !== index)
}
const updateColumn = (index: number, column: ColumnSpecNode) => {
  if (!draft.value?.presentation?.columns) return
  const columns = [...draft.value.presentation.columns]
  columns[index] = column
  draft.value.presentation.columns = columns
}
</script>

<template>
  <div class="page">
    <h1>Viewpoints</h1>

    <p
      v-if="loadError"
      class="error"
    >
      {{ loadError }}
    </p>

    <template v-if="mode === 'list'">
      <button
        type="button"
        class="primary-btn"
        :disabled="writeBlocked"
        @click="startCreate"
      >
        + New viewpoint
      </button>
      <table class="def-table">
        <thead>
          <tr>
            <th>Slug</th><th>Name</th><th>Version</th><th>Tier</th><th>Scope</th><th />
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="def in definitions"
            :key="def.slug"
          >
            <td>{{ def.slug }}</td>
            <td>{{ def.name }}</td>
            <td>{{ def.version }}</td>
            <td>
              <span
                class="tier-tag"
                :class="`tier-${def.tier}`"
              >{{ def.tier }}</span>
            </td>
            <td>{{ formatScopeSummary(def.scope_summary) }}</td>
            <td>
              <button
                type="button"
                @click="executeViewpoint(def)"
              >
                Execute
              </button>
              <button
                v-if="def.tier === 'engagement'"
                type="button"
                :disabled="writeBlocked"
                @click="startEdit(def)"
              >
                Edit
              </button>
              <button
                v-if="def.tier === 'engagement'"
                type="button"
                :disabled="writeBlocked"
                @click="deleteDefinition(def)"
              >
                Delete
              </button>
              <button
                v-else
                type="button"
                @click="startEdit(def)"
              >
                View
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </template>

    <template v-else-if="draft && catalog">
      <button
        type="button"
        @click="backToList"
      >
        ← Back
      </button>

      <p
        v-if="showVersionBumpHint"
        class="hint"
      >
        This is a semantic edit (scope/query/presentation/representation types changed) —
        bump the version, or diagrams pinned to the current version will be flagged stale.
        <span v-if="referencers.length > 0">
          Currently pinned: {{ referencers.map((r) => r.artifact_id).join(', ') }}.
        </span>
      </p>

      <ul
        v-if="issues.length > 0"
        class="issue-list"
      >
        <li
          v-for="(issue, i) in issues"
          :key="i"
          :class="issue.severity"
          @click="focusIssue(issue)"
        >
          <b>{{ issue.code }}</b> ({{ issue.path }}): {{ issue.message }}
        </li>
      </ul>

      <div class="tabs">
        <button
          :class="{ sel: activeTab === 'general' }"
          @click="activeTab = 'general'"
        >
          General
        </button>
        <button
          :class="{ sel: activeTab === 'scope' }"
          @click="activeTab = 'scope'"
        >
          Scope
        </button>
        <button
          :class="{ sel: activeTab === 'query' }"
          @click="activeTab = 'query'"
        >
          Query
        </button>
        <button
          :class="{ sel: activeTab === 'presentation' }"
          @click="activeTab = 'presentation'"
        >
          Presentation
        </button>
      </div>

      <div v-if="activeTab === 'general'">
        <label class="field">
          slug
          <input
            v-model="draft.slug"
            class="inp"
            :disabled="!isCreating"
          >
        </label>
        <label class="field">
          version
          <input
            v-model.number="draft.version"
            class="inp"
            type="number"
          >
        </label>
        <label class="field">
          name
          <input
            v-model="draft.name"
            class="inp"
          >
        </label>
        <label class="field">
          description
          <textarea
            v-model="draft.description"
            class="inp"
          />
        </label>
        <label class="field">
          rationale
          <textarea
            v-model="draft.rationale"
            class="inp"
          />
        </label>
        <fieldset>
          <legend>purpose</legend>
          <label
            v-for="value in VALID_PURPOSES"
            :key="value"
          >
            <input
              type="checkbox"
              :checked="draft.purpose.includes(value)"
              @change="togglePurpose(value)"
            > {{ value }}
          </label>
        </fieldset>
        <fieldset>
          <legend>content</legend>
          <label
            v-for="value in VALID_CONTENTS"
            :key="value"
          >
            <input
              type="checkbox"
              :checked="draft.content.includes(value)"
              @change="toggleContent(value)"
            > {{ value }}
          </label>
        </fieldset>
        <label class="field">
          stakeholders (comma-separated)
          <input
            class="inp"
            :value="listToCsv(draft.stakeholders)"
            @change="draft.stakeholders = csvToList(($event.target as HTMLInputElement).value)"
          >
        </label>
        <label class="field">
          concerns (comma-separated)
          <input
            class="inp"
            :value="listToCsv(draft.concerns)"
            @change="draft.concerns = csvToList(($event.target as HTMLInputElement).value)"
          >
        </label>
      </div>

      <div v-else-if="activeTab === 'scope'">
        <fieldset>
          <legend>
            entity_types
            <label><input
              type="checkbox"
              :checked="draft.scope.entityTypes === null"
              @change="draft.scope = { ...draft.scope, entityTypes: draft.scope.entityTypes === null ? [] : null }"
            > unrestricted</label>
          </legend>
          <label
            v-for="t in catalog.entity_types"
            v-show="draft.scope.entityTypes !== null"
            :key="t"
          >
            <input
              type="checkbox"
              :checked="draft.scope.entityTypes?.includes(t)"
              @change="toggleScopeType('entityTypes', t)"
            > {{ t }}
          </label>
        </fieldset>
        <fieldset>
          <legend>
            connection_types
            <label><input
              type="checkbox"
              :checked="draft.scope.connectionTypes === null"
              @change="draft.scope = { ...draft.scope, connectionTypes: draft.scope.connectionTypes === null ? [] : null }"
            > unrestricted</label>
          </legend>
          <label
            v-for="t in catalog.connection_types"
            v-show="draft.scope.connectionTypes !== null"
            :key="t"
          >
            <input
              type="checkbox"
              :checked="draft.scope.connectionTypes?.includes(t)"
              @change="toggleScopeType('connectionTypes', t)"
            > {{ t }}
          </label>
        </fieldset>
      </div>

      <div v-else-if="activeTab === 'query' && draft.query">
        <h3>Show entities where…</h3>
        <CriteriaTreeBuilder
          v-model="draft.query.entityCriteria"
          group-kind="entity"
          :catalog="catalog"
          is-root
        />

        <h3>Neighbor inclusions (widen the population)</h3>
        <div
          v-for="(inclusion, index) in draft.query.includeConnected"
          :key="inclusion.id"
          class="inclusion"
        >
          <select
            :value="inclusion.direction"
            @change="updateInclusion(index, { direction: ($event.target as HTMLSelectElement).value as NeighborInclusionNode['direction'] })"
          >
            <option value="either">
              either direction
            </option>
            <option value="outgoing">
              outgoing — connections FROM the selected entities
            </option>
            <option value="incoming">
              incoming — connections TO the selected entities
            </option>
          </select>
          <button
            type="button"
            @click="removeInclusion(index)"
          >
            ✕ remove
          </button>
          <OptionalCriteriaSlot
            :model-value="inclusion.connectionCriteria"
            group-kind="connection"
            :catalog="catalog"
            :depth="0"
            field-label="connection_criteria"
            unrestricted-label="any connection"
            @update:model-value="updateInclusion(index, { connectionCriteria: $event })"
          />
          <OptionalCriteriaSlot
            :model-value="inclusion.neighborCriteria"
            group-kind="entity"
            :catalog="catalog"
            :depth="0"
            field-label="neighbor_criteria"
            unrestricted-label="any entity"
            @update:model-value="updateInclusion(index, { neighborCriteria: $event })"
          />
        </div>
        <button
          type="button"
          class="add-btn"
          @click="addInclusion"
        >
          + Add neighbor inclusion
        </button>

        <h3>Connections displayed</h3>
        <label>
          <input
            v-model="draft.query.connections.enabled"
            type="checkbox"
          > enabled
        </label>
        <CriteriaTreeBuilder
          v-model="draft.query.connections.criteria"
          group-kind="connection"
          :catalog="catalog"
          is-root
        />

        <div class="summary-panel">
          {{ summary }}
          <span
            v-if="formatPreviewCounts(previewResult)"
            class="preview-counts"
          >— {{ formatPreviewCounts(previewResult) }}</span>
        </div>

        <div class="test-run-row">
          <button
            type="button"
            :disabled="testRunning"
            @click="testRun"
          >
            {{ testRunning ? 'Running…' : 'Test run' }}
          </button>
          <span
            v-if="testRunError"
            class="error"
          >{{ testRunError }}</span>
          <template v-else-if="testRunResult">
            <span class="test-run-counts">
              Entities: {{ testRunResult.returned_entity_count }} / {{ testRunResult.total_entity_count }} ·
              Connections: {{ testRunResult.returned_connection_count }} / {{ testRunResult.total_connection_count }}
            </span>
            <span
              v-for="warning in testRunResult.warnings"
              :key="warning"
              class="test-run-warning"
            >{{ warning }}</span>
          </template>
        </div>
      </div>

      <div v-else-if="activeTab === 'presentation'">
        <div v-if="draft.presentation === null">
          <p>No presentation — this definition is query-only (execution result has no fixed display).</p>
          <select @change="addPresentation(($event.target as HTMLSelectElement).value as Representation)">
            <option value="" />
            <option
              v-for="r in REPRESENTATIONS"
              :key="r"
              :value="r"
            >
              {{ r }}
            </option>
          </select>
        </div>
        <div v-else>
          <label class="field">
            representation
            <select
              :value="draft.presentation.representation"
              @change="changeRepresentation(($event.target as HTMLSelectElement).value as Representation)"
            >
              <option
                v-for="r in REPRESENTATIONS"
                :key="r"
                :value="r"
              >
                {{ r }}
              </option>
            </select>
          </label>
          <button
            type="button"
            @click="removePresentation"
          >
            Remove presentation
          </button>

          <div v-if="draft.presentation.representation === 'table'">
            <h3>Columns</h3>
            <div
              v-for="(column, index) in draft.presentation.columns ?? []"
              :key="column.id"
              class="column-row"
            >
              <input
                :value="column.label"
                placeholder="label"
                @input="updateColumn(index, { ...column, label: ($event.target as HTMLInputElement).value })"
              >
              <input
                :value="column.source"
                placeholder="source (attribute path)"
                @input="updateColumn(index, { ...column, source: ($event.target as HTMLInputElement).value })"
              >
              <button
                type="button"
                @click="removeColumn(index)"
              >
                ✕
              </button>
            </div>
            <button
              type="button"
              class="add-btn"
              @click="addColumn"
            >
              + Add column
            </button>
          </div>

          <div v-if="draft.presentation.representation === 'matrix'">
            <MatrixAxesEditor
              v-model="draft.presentation"
              :catalog="catalog"
            />
          </div>

          <div v-if="draft.presentation.representation === 'exploration' || draft.presentation.representation === 'diagram'">
            <label class="field">
              group_by
              <select
                :value="draft.presentation.groupBy ?? ''"
                @change="draft.presentation.groupBy = ($event.target as HTMLSelectElement).value || null"
              >
                <option value="" />
                <option
                  v-for="d in [...GROUP_BY_DIMENSIONS, ...Object.keys(catalog.entity_attribute_types)]"
                  :key="d"
                  :value="d"
                >
                  {{ d }}
                </option>
              </select>
            </label>
          </div>

          <h3>Style rules</h3>
          <StyleRuleEditor
            v-model="draft.presentation"
            :catalog="catalog"
          />
        </div>
      </div>

      <div class="save-row">
        <button
          type="button"
          class="primary-btn"
          :disabled="saving || writeBlocked"
          @click="save"
        >
          {{ saving ? 'Saving…' : 'Save' }}
        </button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.page { padding: 20px 28px; max-width: 980px; }
.error { color: #991b1b; background: #fee2e2; padding: 8px 12px; border-radius: 6px; }
.primary-btn { background: #6366f1; color: #fff; border: none; border-radius: 7px; padding: 8px 16px; font-weight: 600; cursor: pointer; margin-bottom: 12px; }
.primary-btn:disabled { opacity: .5; cursor: not-allowed; }
.def-table { width: 100%; border-collapse: collapse; }
.def-table th, .def-table td { text-align: left; padding: 6px 10px; border-bottom: 1px solid #e5e7eb; font-size: 13px; }
.tier-tag { font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 99px; }
.tier-engagement { background: #dcfce7; color: #166534; }
.tier-enterprise { background: #dbeafe; color: #1e40af; }
.tier-module { background: #f3f4f6; color: #6b7280; }
.hint { background: #fef3c7; color: #92400e; padding: 8px 12px; border-radius: 6px; }
.issue-list { list-style: none; padding: 0; }
.issue-list li { padding: 6px 10px; border-radius: 6px; margin: 4px 0; cursor: pointer; font-size: 12.5px; }
.issue-list li.error { background: #fee2e2; color: #991b1b; }
.issue-list li.warning { background: #fef3c7; color: #92400e; }
.tabs { display: flex; gap: 4px; border-bottom: 1px solid #d1d5db; margin: 12px 0; }
.tabs button { appearance: none; border: none; background: none; padding: 8px 14px; font-size: 13px; font-weight: 600; color: #9ca3af; cursor: pointer; border-bottom: 2px solid transparent; }
.tabs button.sel { color: #4338ca; border-color: #6366f1; }
.field { display: block; margin: 8px 0; font-size: 12.5px; font-weight: 600; color: #6b7280; }
.inp { display: block; width: 100%; padding: 6px 8px; border-radius: 6px; border: 1px solid #d1d5db; font-size: 13px; font-family: inherit; box-sizing: border-box; margin-top: 3px; }
fieldset { border: 1px solid #d1d5db; border-radius: 8px; margin: 10px 0; padding: 8px 12px; }
.inclusion { border: 1px solid #d1d5db; border-radius: 8px; padding: 10px; margin: 8px 0; }
.summary-panel { margin-top: 12px; padding: 10px 14px; border-radius: 8px; background: #eef2ff; color: #4338ca; font-size: 13px; }
.preview-counts { margin-left: 6px; font-weight: 600; }
.test-run-row { display: flex; align-items: center; gap: 10px; margin-top: 8px; flex-wrap: wrap; }
.test-run-counts { font-size: 12.5px; color: #374151; }
.test-run-warning { font-size: 12px; color: #92400e; background: #fef3c7; padding: 2px 8px; border-radius: 4px; }
.column-row { display: flex; gap: 6px; margin: 4px 0; }
.add-btn { appearance: none; border: 1px dashed #d1d5db; background: #fff; color: #6b7280; border-radius: 7px; padding: 5px 10px; font-size: 12px; font-weight: 600; cursor: pointer; margin-top: 8px; }
.save-row { margin-top: 20px; }
</style>
