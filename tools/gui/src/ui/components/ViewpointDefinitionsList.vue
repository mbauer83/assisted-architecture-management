<script setup lang="ts">
/**
 * List mode of the viewpoints management view: browse the effective merged catalog and
 * route each definition to its representation-appropriate execution surface. Fully
 * self-contained — injects the model service itself for delete, and emits only the two
 * things the parent must react to: switching into create/edit mode, and a delete having
 * changed the catalog.
 */
import { inject, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Effect } from 'effect'
import { modelServiceKey } from '../keys'
import { useWriteBlock } from '../composables/useWriteBlock'
import { readErrorMessage } from '../lib/errors'
import type { ViewpointDefinitionEnvelope, ViewpointReferencer } from '../../domain'
import { executionRouteFor, formatScopeSummary } from '../views/ViewpointsManagementView.helpers'

defineProps<{ definitions: readonly ViewpointDefinitionEnvelope[] }>()
const emit = defineEmits<{ create: []; edit: [envelope: ViewpointDefinitionEnvelope]; refresh: []; error: [message: string] }>()

const svc = inject(modelServiceKey)!
const writeBlocked = useWriteBlock()
const router = useRouter()

const executeViewpoint = (envelope: ViewpointDefinitionEnvelope) => void router.push(executionRouteFor(envelope))

// ── Pins (Home quick access) ─────────────────────────────────────────────────
const pinnedSlugs = ref<Set<string>>(new Set())
onMounted(() => {
  void Effect.runPromise(svc.getViewpointPins()).then((pins) => { pinnedSlugs.value = new Set(pins.slugs) })
})
const isPinned = (slug: string) => pinnedSlugs.value.has(slug)
const togglePin = (slug: string) => {
  const next = new Set(pinnedSlugs.value)
  if (next.has(slug)) next.delete(slug)
  else next.add(slug)
  void Effect.runPromise(svc.setViewpointPins([...next])).then((pins) => { pinnedSlugs.value = new Set(pins.slugs) })
}

/** Delete-blocked-while-referenced state: kept local (not just bubbled up as a flat error
 * string) so the referencers can be rendered as actionable links to the diagram/matrix
 * pinning this definition, not just named in prose. */
const blockedDelete = ref<{ slug: string; referencers: readonly ViewpointReferencer[] } | null>(null)

const openReferencer = (referencer: ViewpointReferencer) => {
  void router.push({ path: '/diagram', query: { id: referencer.artifact_id } })
}

const deleteDefinition = (envelope: ViewpointDefinitionEnvelope) => {
  if (!window.confirm(`Delete viewpoint '${envelope.slug}'?`)) return
  blockedDelete.value = null
  Effect.runPromise(svc.deleteViewpointDefinition({ slug: envelope.slug, dry_run: false })).then((result) => {
    if (result.ok) { emit('refresh'); return }
    if (result.referencers.length > 0) { blockedDelete.value = { slug: envelope.slug, referencers: result.referencers }; return }
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
    <div
      v-if="blockedDelete"
      class="blocked-panel"
    >
      <p>
        Can't delete '{{ blockedDelete.slug }}' — still referenced by:
      </p>
      <ul>
        <li
          v-for="referencer in blockedDelete.referencers"
          :key="referencer.artifact_id"
        >
          <button
            type="button"
            class="referencer-link"
            @click="openReferencer(referencer)"
          >
            {{ referencer.artifact_id }} ({{ referencer.target_kind }})
          </button>
        </li>
      </ul>
      <button
        type="button"
        class="btn"
        @click="blockedDelete = null"
      >
        Dismiss
      </button>
    </div>
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
            <div class="row-actions">
              <button
                type="button"
                class="pin-btn"
                :class="{ 'pin-btn--active': isPinned(def.slug) }"
                :aria-label="isPinned(def.slug) ? `Unpin ${def.slug}` : `Pin ${def.slug}`"
                :aria-pressed="isPinned(def.slug)"
                @click="togglePin(def.slug)"
              >
                {{ isPinned(def.slug) ? '★' : '☆' }}
              </button>
              <button
                type="button"
                class="btn"
                @click="executeViewpoint(def)"
              >
                Execute
              </button>
              <button
                v-if="def.tier === 'engagement'"
                type="button"
                class="btn"
                :disabled="writeBlocked"
                @click="emit('edit', def)"
              >
                Edit
              </button>
              <button
                v-if="def.tier === 'engagement'"
                type="button"
                class="btn btn--danger"
                :disabled="writeBlocked"
                @click="deleteDefinition(def)"
              >
                Delete
              </button>
              <button
                v-else
                type="button"
                class="btn"
                @click="emit('edit', def)"
              >
                View
              </button>
            </div>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.primary-btn { background: #6366f1; color: #fff; border: none; border-radius: 7px; padding: 8px 16px; font-weight: 600; cursor: pointer; margin-bottom: 12px; }
.primary-btn:disabled { opacity: .5; cursor: not-allowed; }
.blocked-panel { background: #fee2e2; color: #991b1b; border-radius: 8px; padding: 10px 14px; margin-bottom: 12px; font-size: 13px; }
.blocked-panel ul { margin: 6px 0; padding-left: 18px; }
.referencer-link { appearance: none; border: none; background: none; color: #991b1b; text-decoration: underline; cursor: pointer; font-size: 13px; padding: 0; }
.def-table { width: 100%; border-collapse: collapse; }
.def-table th, .def-table td { text-align: left; padding: 6px 10px; border-bottom: 1px solid #e5e7eb; font-size: 13px; }
.tier-tag { font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 99px; }
.tier-engagement { background: #dcfce7; color: #166534; }
.tier-enterprise { background: #dbeafe; color: #1e40af; }
.tier-module { background: #f3f4f6; color: #6b7280; }
.pin-btn { border: none; background: none; cursor: pointer; font-size: 15px; color: #d1d5db; padding: 0 4px; }
.pin-btn--active { color: #d97706; }
.def-table td:last-child { white-space: nowrap; }
.row-actions { display: flex; align-items: center; gap: 6px; }
.btn { appearance: none; border: 1px solid #d1d5db; background: #fff; color: #374151; border-radius: 6px; padding: 5px 12px; font-size: 12.5px; font-weight: 600; cursor: pointer; }
.btn:hover:not(:disabled) { border-color: #6366f1; color: #4338ca; }
.btn:disabled { opacity: .5; cursor: not-allowed; }
.btn--danger:hover:not(:disabled) { border-color: #dc2626; color: #b91c1c; background: #fef2f2; }
</style>
