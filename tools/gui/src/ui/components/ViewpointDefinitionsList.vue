<script setup lang="ts">
/**
 * List mode of the viewpoints management view: browse the effective merged catalog and
 * route each definition to its representation-appropriate execution surface. Fully
 * self-contained — injects the model service itself for delete, and emits only the two
 * things the parent must react to: switching into create/edit mode, and a delete having
 * changed the catalog.
 */
import { inject } from 'vue'
import { useRouter } from 'vue-router'
import { Effect } from 'effect'
import { modelServiceKey } from '../keys'
import { useWriteBlock } from '../composables/useWriteBlock'
import { readErrorMessage } from '../lib/errors'
import type { ViewpointDefinitionEnvelope } from '../../domain'
import { presentationFromMapping } from '../../domain/viewpointPresentationSerialization'
import type { Representation } from '../../domain/viewpointPresentation'
import { formatScopeSummary } from '../views/ViewpointsManagementView.helpers'

defineProps<{ definitions: readonly ViewpointDefinitionEnvelope[] }>()
const emit = defineEmits<{ create: []; edit: [envelope: ViewpointDefinitionEnvelope]; refresh: []; error: [message: string] }>()

const svc = inject(modelServiceKey)!
const writeBlocked = useWriteBlock()
const router = useRouter()

/** Route to the representation-appropriate execution surface, pre-loaded with this
 * viewpoint's repository-context population — no separate anchor entity required. */
const EXECUTION_ROUTE_BY_REPRESENTATION: Record<Representation, string> = {
  exploration: '/graph', table: '/entities', matrix: '/viewpoints/matrix', diagram: '/viewpoints/diagram',
}

const executeViewpoint = (envelope: ViewpointDefinitionEnvelope) => {
  const representation = presentationFromMapping(envelope.presentation)?.representation ?? 'exploration'
  void router.push({ path: EXECUTION_ROUTE_BY_REPRESENTATION[representation], query: { viewpoint: envelope.slug } })
}

const deleteDefinition = (envelope: ViewpointDefinitionEnvelope) => {
  if (!window.confirm(`Delete viewpoint '${envelope.slug}'?`)) return
  Effect.runPromise(svc.deleteViewpointDefinition({ slug: envelope.slug, dry_run: false })).then((result) => {
    if (result.ok) { emit('refresh'); return }
    emit('error', result.issues[0]?.message ?? 'Delete failed')
  }).catch((reason: unknown) => { emit('error', readErrorMessage(reason)) })
}
</script>

<template>
  <div>
    <button
      type="button"
      class="primary-btn"
      :disabled="writeBlocked"
      @click="emit('create')"
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
              @click="emit('edit', def)"
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
              @click="emit('edit', def)"
            >
              View
            </button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.primary-btn { background: #6366f1; color: #fff; border: none; border-radius: 7px; padding: 8px 16px; font-weight: 600; cursor: pointer; margin-bottom: 12px; }
.primary-btn:disabled { opacity: .5; cursor: not-allowed; }
.def-table { width: 100%; border-collapse: collapse; }
.def-table th, .def-table td { text-align: left; padding: 6px 10px; border-bottom: 1px solid #e5e7eb; font-size: 13px; }
.tier-tag { font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 99px; }
.tier-engagement { background: #dcfce7; color: #166534; }
.tier-enterprise { background: #dbeafe; color: #1e40af; }
.tier-module { background: #f3f4f6; color: #6b7280; }
</style>
