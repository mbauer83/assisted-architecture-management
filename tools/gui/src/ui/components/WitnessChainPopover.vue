<script setup lang="ts">
/** Resolves and renders one derived relationship's witness chain: the ordered real
 * connections that compose it, as prose with every entity name a clickable sidebar link
 * (via `RouterLink`) — never a synthesized diagram, since the chain itself is never
 * persisted. A broken chain (a connection the walk can't resolve) says so plainly rather
 * than rendering a partial chain as if it were complete. */
import { inject, ref, watch } from 'vue'
import { Effect } from 'effect'
import { modelServiceKey } from '../keys'
import { walkWitnessChain, witnessChainProse, type ProseSegment } from '../../domain/witnessChainProse'
import type { ConnectionRecord } from '../../domain/schemas/connections'

const props = defineProps<{ sourceEntityId: string; targetEntityId: string; viaConnectionIds: readonly string[] }>()
defineEmits<{ close: [] }>()
const svc = inject(modelServiceKey)!

const loading = ref(true)
const segments = ref<readonly ProseSegment[]>([])
const broken = ref(false)

/** `via_connection_ids` is not guaranteed to arrive in source-to-target traversal order —
 * the derivation engine can extend a composed chain from either end as it discovers
 * adjacent connections. Resolving the actual `ConnectionRecord` for each id therefore
 * can't walk the array in order either: it has to search outward from both known
 * endpoints (source and target) until every id in the chain is found. */
const resolveChainConnections = async (): Promise<Map<string, ConnectionRecord>> => {
  const remaining = new Set(props.viaConnectionIds)
  const resolved = new Map<string, ConnectionRecord>()
  const visited = new Set<string>()
  let frontier = [props.sourceEntityId, props.targetEntityId]
  while (remaining.size > 0 && frontier.length > 0) {
    const nextFrontier: string[] = []
    for (const entityId of frontier) {
      if (visited.has(entityId)) continue
      visited.add(entityId)
      const connections = await Effect.runPromise(svc.getConnections(entityId, 'any'))
      for (const connection of connections) {
        if (!remaining.has(connection.artifact_id)) continue
        remaining.delete(connection.artifact_id)
        resolved.set(connection.artifact_id, connection)
        const other = connection.source === entityId ? connection.target : connection.source
        if (!visited.has(other)) nextFrontier.push(other)
      }
    }
    frontier = nextFrontier
  }
  return resolved
}

const load = async (): Promise<void> => {
  loading.value = true
  const connectionById = await resolveChainConnections()
  const steps = walkWitnessChain(props.sourceEntityId, props.viaConnectionIds, connectionById)
  segments.value = witnessChainProse(steps)
  broken.value = steps.length < props.viaConnectionIds.length
  loading.value = false
}

watch(() => [props.sourceEntityId, props.targetEntityId, ...props.viaConnectionIds], load, { immediate: true })
</script>

<template>
  <div
    class="witness-popover"
    role="dialog"
    aria-label="Witness chain"
  >
    <div
      v-if="loading"
      class="state-msg"
    >
      Loading witness chain…
    </div>
    <template v-else>
      <p class="chain-prose">
        <template
          v-for="(segment, index) in segments"
          :key="index"
        >
          <RouterLink
            v-if="segment.entityId"
            :to="{ path: '/entity', query: { id: segment.entityId } }"
            class="chain-entity"
          >
            {{ segment.text }}
          </RouterLink>
          <span
            v-else
            class="chain-arrow"
          >{{ segment.text }}</span>
        </template>
      </p>
      <p
        v-if="broken"
        class="chain-broken"
      >
        This witness chain no longer fully resolves — part of it may have changed since it was derived.
      </p>
    </template>
    <button
      class="chain-close"
      @click="$emit('close')"
    >
      Close
    </button>
  </div>
</template>

<style scoped>
.witness-popover {
  position: absolute; z-index: 40; background: white; border: 1px solid #d1d5db; border-radius: 8px;
  padding: 12px 14px; box-shadow: 0 8px 24px rgba(0, 0, 0, .15); max-width: 420px; font-size: 12.5px;
}
.state-msg { color: #6b7280; }
.chain-prose { color: #374151; line-height: 1.6; margin: 0 0 8px; }
.chain-entity { color: #2563eb; font-weight: 600; }
.chain-arrow { color: #6b7280; }
.chain-broken { color: #92400e; background: #fef3c7; padding: 6px 8px; border-radius: 6px; margin: 0 0 8px; }
.chain-close { padding: 4px 10px; border-radius: 6px; border: 1px solid #d1d5db; background: white; font-size: 12px; cursor: pointer; }
</style>
