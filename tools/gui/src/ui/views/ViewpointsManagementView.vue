<script setup lang="ts">
/**
 * Viewpoint definitions management view: list the effective merged catalog (engagement
 * definitions editable, enterprise/module read-only), and create/edit through the
 * criteria-tree builder — one save path (`persist_edit`-mode validation) shared with the
 * MCP authoring tool. No raw-YAML editing surface anywhere.
 *
 * Orchestrates state shared across the edit-mode tabs (the draft itself, validation issues,
 * the highlighted-node overlay, save); each tab owns its own tab-local concerns (see
 * ViewpointGeneralTab/ViewpointScopeTab/ViewpointQueryTab/ViewpointPresentationTab).
 */
import { computed, inject, onMounted, provide, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Effect } from 'effect'
import { modelServiceKey } from '../keys'
import { useWriteBlock } from '../composables/useWriteBlock'
import { readErrorMessage } from '../lib/errors'
import type {
  CriteriaCatalog, ViewpointDefinitionEnvelope, ViewpointPersistResult, ViewpointReferencer, ViewpointValidationIssue,
} from '../../domain'
import { mkDefinitionDraft } from '../../domain/viewpointDefinitionDraft'
import type { ViewpointDefinitionDraft } from '../../domain/viewpointDefinitionDraft'
import { definitionFromMapping, definitionToMapping } from '../../domain/viewpointDefinitionSerialization'
import { attributeTypeTablesFromCatalog } from '../../domain/viewpointBindings'
import { groupFromMapping } from '../../domain/viewpointCriteriaSerialization'
import { resolveIssuePathNodeId } from '../../domain/viewpointIssuePath'
import { HIGHLIGHTED_NODE_ID_KEY } from '../components/CriteriaTreeBuilder.helpers'
import { firstErrorNodeId, isSemanticEdit } from './ViewpointsManagementView.helpers'
import ViewpointDefinitionsList from '../components/ViewpointDefinitionsList.vue'
import ViewpointGeneralTab from '../components/ViewpointGeneralTab.vue'
import ViewpointScopeTab from '../components/ViewpointScopeTab.vue'
import ViewpointQueryTab from '../components/ViewpointQueryTab.vue'
import ViewpointPresentationTab from '../components/ViewpointPresentationTab.vue'

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
const saveError = ref<string | null>(null)

const draft = ref<ViewpointDefinitionDraft | null>(null)
const originalDraft = ref<ViewpointDefinitionDraft | null>(null)
const isCreating = ref(false)
const viewingTier = ref<ViewpointDefinitionEnvelope['tier'] | null>(null)
const isReadOnly = computed(() => viewingTier.value !== null && viewingTier.value !== 'engagement')
const activeTab = ref<'general' | 'scope' | 'query' | 'presentation'>('general')
const issues = ref<readonly ViewpointValidationIssue[]>([])
const referencers = ref<readonly ViewpointReferencer[]>([])
const saving = ref(false)

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
  viewingTier.value = 'engagement'
  issues.value = []
  referencers.value = []
  saveError.value = null
  activeTab.value = 'general'
  mode.value = 'edit'
}

const startEdit = (envelope: ViewpointDefinitionEnvelope) => {
  draft.value = definitionFromMapping(envelope)
  originalDraft.value = definitionFromMapping(envelope)
  isCreating.value = false
  viewingTier.value = envelope.tier
  issues.value = []
  saveError.value = null
  activeTab.value = 'general'
  mode.value = 'edit'
  void Effect.runPromise(svc.getViewpointReferencers(envelope.slug)).then((r) => { referencers.value = r })
}

const backToList = () => {
  mode.value = 'list'
  draft.value = null
  originalDraft.value = null
  viewingTier.value = null
  void loadDefinitions()
}

const isSemantic = computed(() => draft.value && originalDraft.value && isSemanticEdit(draft.value, originalDraft.value))
const versionBumped = computed(() => draft.value && originalDraft.value && draft.value.version > originalDraft.value.version)
const showVersionBumpHint = computed(() => !isCreating.value && isSemantic.value && !versionBumped.value)

const save = () => {
  if (!draft.value || !catalog.value || isReadOnly.value) return
  saving.value = true
  saveError.value = null
  const body = { definition: definitionToMapping(draft.value, attributeTypeTablesFromCatalog(catalog.value)), dry_run: false }
  const call = isCreating.value ? svc.createViewpointDefinition(body) : svc.editViewpointDefinition(body)
  Effect.runPromise(call).then((result: ViewpointPersistResult) => {
    saving.value = false
    if (result.ok) { backToList(); return }
    issues.value = result.issues
    referencers.value = result.referencers.length > 0 ? result.referencers : referencers.value
    highlightedNodeId.value = draft.value ? firstErrorNodeId(result.issues, draft.value) : null
  }).catch((reason: unknown) => {
    saving.value = false
    saveError.value = readErrorMessage(reason)
  })
}

const focusIssue = (issue: ViewpointValidationIssue) => {
  if (!draft.value) return
  highlightedNodeId.value = resolveIssuePathNodeId(issue.path, draft.value)
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

    <ViewpointDefinitionsList
      v-if="mode === 'list'"
      :definitions="definitions"
      @create="startCreate"
      @edit="startEdit"
      @refresh="loadDefinitions"
      @error="loadError = $event"
    />

    <template v-else-if="draft && catalog">
      <button
        type="button"
        class="back-btn"
        @click="backToList"
      >
        ← Back
      </button>

      <p
        v-if="isReadOnly"
        class="hint hint--readonly"
      >
        This is a {{ viewingTier }}-tier definition — only engagement-tier definitions can be
        edited here. Promote a copy into the engagement repository to customize it.
      </p>

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

      <ViewpointGeneralTab
        v-if="activeTab === 'general'"
        :draft="draft"
        :is-creating="isCreating"
        @update="Object.assign(draft, $event)"
      />
      <ViewpointScopeTab
        v-else-if="activeTab === 'scope'"
        v-model="draft.scope"
        :catalog="catalog"
      />
      <ViewpointQueryTab
        v-else-if="activeTab === 'query'"
        :draft="draft"
        :catalog="catalog"
        :is-creating="isCreating"
        @update:query="draft.query = $event"
        @issues="issues = $event"
      />
      <ViewpointPresentationTab
        v-else-if="activeTab === 'presentation'"
        v-model="draft.presentation"
        :catalog="catalog"
      />

      <p
        v-if="saveError"
        class="error save-error"
      >
        {{ saveError }}
        <button
          type="button"
          class="retry-btn"
          @click="save"
        >
          ↻ Retry
        </button>
      </p>

      <div
        v-if="!isReadOnly"
        class="save-row"
      >
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
.save-error { display: flex; align-items: center; gap: 10px; justify-content: space-between; }
.retry-btn { appearance: none; border: 1px solid #991b1b; border-radius: 6px; background: #fff; color: #991b1b; font-size: 12px; padding: 3px 10px; cursor: pointer; flex-shrink: 0; }
.retry-btn:hover { background: #fef2f2; }
.primary-btn { background: #6366f1; color: #fff; border: none; border-radius: 7px; padding: 8px 16px; font-weight: 600; cursor: pointer; margin-bottom: 12px; }
.primary-btn:disabled { opacity: .5; cursor: not-allowed; }
.hint { background: #fef3c7; color: #92400e; padding: 8px 12px; border-radius: 6px; }
.hint--readonly { background: #f3f4f6; color: #374151; }
.issue-list { list-style: none; padding: 0; }
.issue-list li { padding: 6px 10px; border-radius: 6px; margin: 4px 0; cursor: pointer; font-size: 12.5px; }
.issue-list li.error { background: #fee2e2; color: #991b1b; }
.issue-list li.warning { background: #fef3c7; color: #92400e; }
.tabs { display: flex; gap: 4px; border-bottom: 1px solid #d1d5db; margin: 12px 0; }
.tabs button { appearance: none; border: none; background: none; padding: 8px 14px; font-size: 13px; font-weight: 600; color: #9ca3af; cursor: pointer; border-bottom: 2px solid transparent; }
.tabs button.sel { color: #4338ca; border-color: #6366f1; }
.save-row { margin-top: 20px; }
.back-btn { appearance: none; border: 1px solid #d1d5db; background: #fff; color: #374151; border-radius: 6px; padding: 5px 12px; font-size: 12.5px; font-weight: 600; cursor: pointer; }
.back-btn:hover { border-color: #6366f1; color: #4338ca; }
</style>
