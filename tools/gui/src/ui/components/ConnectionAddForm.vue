<script setup lang="ts">
/**
 * "Add connection" form for one type-group in ConnectionsPanel: connection-type/
 * specialization pickers, target search, description, and source/target multiplicity.
 * Fully self-contained — injects the model service, loads the ontology pair and manages
 * its own add-mutation state; the parent mounts/unmounts this per `addingFor` type key and
 * listens for `added`/`cancel`.
 */
import { computed, inject, ref, watch } from 'vue'
import { Exit } from 'effect'
import { modelServiceKey } from '../keys'
import type { AuthoringGuidance, OntologyPair, WriteResult } from '../../domain'
import type { RepoError } from '../../ports/ModelRepository'
import { useQuery } from '../composables/useQuery'
import { useMutation } from '../composables/useMutation'
import {
  connectionMetadataSchema, specializationOptionsForConnectionType, specializationOptionLabel,
} from '../lib/specializationOptions'
import type { SchemaQuarantine } from '../lib/schemaQuarantine'
import EntitySearchInput from './EntitySearchInput.vue'
import SchemaQuarantineBanner from './SchemaQuarantineBanner.vue'
import TypedPropertyInput from './TypedPropertyInput.vue'

const props = defineProps<{
  entityId: string
  entityType: string
  typeKey: string
  direction: 'outgoing' | 'incoming' | 'symmetric'
  adminMode?: boolean
  symmetricConnTypes: ReadonlySet<string>
  guidance: AuthoringGuidance | null
  /** Pre-seed the target/type pickers — e.g. materializing a derived relationship into
   * a real connection, where the source/target/type are already known and only need
   * confirming, not searching for. Left unset, the form starts empty as before. */
  initialTarget?: { id: string; name: string }
  initialConnType?: string
  initialDescription?: string
}>()
const emit = defineEmits<{ added: []; cancel: [] }>()

const svc = inject(modelServiceKey)!

const selectedTarget = ref<{ id: string; name: string } | null>(props.initialTarget ?? null)
const connTypeSelected = ref(props.initialConnType ?? '')
const descInput = ref(props.initialDescription ?? '')
const srcMultInput = ref('')
const tgtMultInput = ref('')
const specSelected = ref('')

const specOptions = computed(() =>
  specializationOptionsForConnectionType(props.guidance, connTypeSelected.value),
)

// The effective metadata schema for the selected (type, specialization) pair, and the rows
// the operator fills in. Rows are rebuilt whenever the pair changes: a different pair is a
// different schema, so carrying values across would carry attributes the new pair may not
// declare. Defaults come from the schema, exactly as on the entity create form.
const metadataSchema = computed(() =>
  connectionMetadataSchema(props.guidance, connTypeSelected.value, specSelected.value),
)
const metadataValues = ref<Record<string, string>>({})

const rebuildMetadataRows = () => {
  const info = metadataSchema.value
  const next: Record<string, string> = {}
  for (const key of info?.properties ?? []) next[key] = info?.descriptors[key]?.default ?? ''
  metadataValues.value = next
}

watch(metadataSchema, rebuildMetadataRows, { immediate: true })
watch(connTypeSelected, () => { specSelected.value = '' })

const metadataQuarantine = computed(
  (): SchemaQuarantine => ({
    quarantined: metadataSchema.value?.quarantined ?? false,
    conflicts: metadataSchema.value?.conflicts ?? [],
  }),
)

const metadataRequiredMissing = computed(() =>
  (metadataSchema.value?.required ?? []).some((key) => !metadataValues.value[key]?.trim()),
)

/** Only non-empty values are sent: an untouched optional attribute is absent, not blank. */
const metadataBody = computed((): Record<string, string> | undefined => {
  const filled = Object.entries(metadataValues.value).filter(([, value]) => value.trim() !== '')
  return filled.length ? Object.fromEntries(filled) : undefined
})

const MULTIPLICITY_RE = /^\d+$|^\d+\.\.\d+$|^\d+\.\.\*$|^\*$/
const multError = (v: string) => v.trim() && !MULTIPLICITY_RE.test(v.trim()) ? 'Use: n, n..m, n..*, or *' : ''
const srcMultError = computed(() => multError(srcMultInput.value))
const tgtMultError = computed(() => multError(tgtMultInput.value))

const pairQuery = useQuery<OntologyPair, RepoError>()
const addMutation = useMutation<WriteResult, RepoError>()

const connTypeOptions = computed((): string[] => {
  const pair = pairQuery.data.value
  if (!pair) return []
  return props.direction === 'symmetric'
    ? pair.connection_types.filter((ct) => props.symmetricConnTypes.has(ct))
    : [...pair.connection_types]
})

watch(() => pairQuery.data.value, (pair) => {
  if (!pair || props.initialConnType) return
  const types = connTypeOptions.value
  if (types.length === 1) connTypeSelected.value = types[0]
  else if (props.direction === 'symmetric') connTypeSelected.value = 'archimate-association'
})

const addBlocked = computed(() =>
  !selectedTarget.value || !connTypeSelected.value || !!srcMultError.value || !!tgtMultError.value
  || addMutation.running.value || metadataQuarantine.value.quarantined || metadataRequiredMissing.value,
)

const addBlockedTitle = computed(() => {
  if (metadataQuarantine.value.quarantined) return 'Resolve the schema conflict shown above before adding'
  return metadataRequiredMissing.value ? 'Fill in all required metadata attributes first' : undefined
})

const addError = computed(() =>
  addMutation.result.value?.wrote === false
    ? (addMutation.result.value.content ?? 'Verification failed')
    : addMutation.errorMessage.value,
)

pairQuery.run(svc.getOntologyPair(props.entityType, props.typeKey))

const onSelectTarget = (id: string, name: string) => {
  selectedTarget.value = { id, name }
}

const confirmAdd = () => {
  if (!selectedTarget.value || !connTypeSelected.value) return
  const isIncoming = props.direction === 'incoming'
  const source = isIncoming ? selectedTarget.value.id : props.entityId
  const target = isIncoming ? props.entityId : selectedTarget.value.id
  const addFn = props.adminMode ? svc.adminAddConnection : svc.addConnection
  void addMutation.run(addFn({
    source_entity: source,
    connection_type: connTypeSelected.value,
    target_entity: target,
    description: descInput.value.trim() || undefined,
    src_multiplicity: srcMultInput.value.trim() || undefined,
    tgt_multiplicity: tgtMultInput.value.trim() || undefined,
    specialization: specSelected.value || undefined,
    metadata: metadataBody.value,
    dry_run: false,
  })).then((exit) => Exit.match(exit, {
    onSuccess: (r) => { if (r.wrote) emit('added') },
    onFailure: () => {},
  }))
}
</script>

<template>
  <div class="add-form">
    <div
      v-if="connTypeOptions.length"
      class="add-row"
    >
      <select
        v-model="connTypeSelected"
        class="conn-type-select"
      >
        <option
          value=""
          disabled
        >
          Select connection type...
        </option>
        <option
          v-for="ct in connTypeOptions"
          :key="ct"
          :value="ct"
        >
          {{ ct.replace('archimate-', '') }}
        </option>
      </select>
    </div>
    <div
      v-else
      class="state-msg"
    >
      Loading connection types...
    </div>
    <div
      v-if="specOptions.length"
      class="add-row"
    >
      <select
        v-model="specSelected"
        class="conn-type-select"
      >
        <option value="">
          No specialization
        </option>
        <option
          v-for="spec in specOptions"
          :key="spec.slug"
          :value="spec.slug"
        >
          {{ specializationOptionLabel(spec) }}
        </option>
      </select>
    </div>
    <SchemaQuarantineBanner
      :quarantine="metadataQuarantine"
      :artifact-type="connTypeSelected"
      :specialization="specSelected"
    />
    <div
      v-for="key in metadataSchema?.properties ?? []"
      :key="key"
      class="add-row add-row--meta"
    >
      <label class="meta-label">
        {{ key }}<span
          v-if="metadataSchema?.required.includes(key)"
          class="meta-required"
        > *</span>
      </label>
      <TypedPropertyInput
        v-model="metadataValues[key]"
        :descriptor="metadataSchema?.descriptors[key] ?? { type: 'string' }"
        :required="metadataSchema?.required.includes(key)"
      />
    </div>
    <div class="add-row">
      <EntitySearchInput
        :artifact-type="typeKey"
        placeholder="Search target entity..."
        @select="onSelectTarget"
      />
    </div>
    <div
      v-if="selectedTarget"
      class="selected-target"
    >
      Selected: <strong>{{ selectedTarget.name }}</strong>
    </div>
    <div class="add-row">
      <input
        v-model="descInput"
        class="desc-input"
        placeholder="Description (optional)"
      >
    </div>
    <div class="add-row add-row--mult">
      <label class="mult-label">source</label>
      <input
        v-model="srcMultInput"
        class="mult-input"
        :class="{ 'mult-input--error': srcMultError }"
        placeholder="e.g. 1..*"
        maxlength="20"
      >
      <span class="mult-sep">→</span>
      <label class="mult-label">target</label>
      <input
        v-model="tgtMultInput"
        class="mult-input"
        :class="{ 'mult-input--error': tgtMultError }"
        placeholder="e.g. 0..*"
        maxlength="20"
      >
      <span class="mult-hint">multiplicity range, e.g. 1, 0..1, 1..*, * (optional)</span>
    </div>
    <div
      v-if="srcMultError || tgtMultError"
      class="state-msg state-msg--error"
    >
      {{ srcMultError || tgtMultError }}
    </div>
    <div class="add-actions">
      <button
        class="cancel-btn"
        @click="emit('cancel')"
      >
        Cancel
      </button>
      <button
        class="add-confirm-btn"
        :disabled="addBlocked"
        :title="addBlockedTitle"
        @click="confirmAdd"
      >
        Add
      </button>
    </div>
    <div
      v-if="addError"
      class="state-msg state-msg--error"
    >
      {{ addError }}
    </div>
  </div>
</template>

<style scoped>
.state-msg { color: #6b7280; padding: 4px 0; font-size: 13px; }
.add-row--meta { display: flex; gap: 8px; align-items: flex-start; }
.meta-label { flex: 0 0 130px; font-size: 12px; font-weight: 500; color: #374151; padding-top: 7px; }
.meta-required { color: #dc2626; }
.state-msg--error { color: #dc2626; }
.mult-label { font-size: 11px; color: #6b7280; white-space: nowrap; }
.mult-input {
  width: 52px; padding: 4px 6px; border-radius: 4px; border: 1px solid #d1d5db;
  font-size: 11px; font-family: monospace; outline: none;
}
.mult-input:focus { border-color: #2563eb; }
.mult-sep { color: #9ca3af; font-size: 11px; margin: 0 2px; }
.mult-hint { font-size: 10px; color: #9ca3af; margin-left: 4px; }

.add-form { margin-top: 8px; padding: 10px; background: #f9fafb; border-radius: 6px; }
.add-row { display: flex; gap: 6px; margin-bottom: 6px; align-items: center; }
.add-row--mult { align-items: center; gap: 4px; }
.conn-type-select {
  flex: 1; padding: 6px 10px; border-radius: 6px; border: 1px solid #d1d5db;
  font-size: 12px; outline: none; background: white;
}
.conn-type-select:focus { border-color: #2563eb; }
.desc-input {
  flex: 1; padding: 6px 10px; border-radius: 6px; border: 1px solid #d1d5db;
  font-size: 12px; outline: none;
}
.desc-input:focus { border-color: #2563eb; }
.add-actions { display: flex; gap: 6px; justify-content: flex-end; margin-top: 4px; }
.add-confirm-btn {
  padding: 6px 14px; background: #2563eb; color: white; border: none;
  border-radius: 6px; font-size: 13px; font-weight: 500; cursor: pointer; white-space: nowrap;
}
.add-confirm-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.add-confirm-btn:hover:not(:disabled) { background: #1d4ed8; }
.cancel-btn {
  padding: 6px 14px; background: #f3f4f6; color: #374151; border: 1px solid #d1d5db;
  border-radius: 6px; font-size: 13px; cursor: pointer;
}
.cancel-btn:hover { background: #e5e7eb; }
.selected-target { font-size: 12px; color: #374151; margin-bottom: 4px; }
</style>
