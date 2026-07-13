<script setup lang="ts">
/**
 * Diagram detail's right-hand sidebar: entity list plus whichever detail panel is active
 * (a viewer-extension sub-part, a selected connection with its inline edge-label editor, or
 * a selected entity). All selection *state* is owned by `useDiagramSvgSelection` in the
 * parent view — this component only renders it and emits the click/edit intents back up.
 */
import { computed } from 'vue'
import type { DiagramConnection, EntityDetail, EntitySummary } from '../../domain'
import type { DiagramViewerExtension } from '../lib/diagramViewerExtensions'
import type { QueryHandle } from '../composables/useQuery'
import type { RepoError } from '../../ports/ModelRepository'
import type { NotFoundError } from '../../domain'
import type { MarkdownError } from '../../application/MarkdownService'
import { getDomainColor } from '../lib/domains'
import { toGlyphKey } from '../lib/glyphKey'
import ArchimateTypeGlyph from './ArchimateTypeGlyph.vue'

const props = defineProps<{
  entities: readonly EntitySummary[]
  viewerExtension: DiagramViewerExtension | undefined
  selectedId: string | null
  selectedConnection: DiagramConnection | null
  selectedSubPart: unknown
  entityQuery: QueryHandle<EntityDetail, RepoError | NotFoundError | MarkdownError>
  edgeLabelInput: string
  edgeLabelError: string | null
}>()
const emit = defineEmits<{
  'select-entity': [id: string]
  'clear-connection': []
  'clear-sub-part': []
  'update:edgeLabelInput': [value: string]
  'save-edge-label': []
}>()

/** Strips a first-heading duplicate of the entity's own name — the raw markdown-rendered
 * content otherwise repeats the title the panel already shows above it. */
const selectedEntityDetailHtml = computed(() => {
  const entity = props.entityQuery.data.value
  const html = entity?.content_html
  if (!entity || !html) return null
  if (typeof window === 'undefined') return html

  const doc = new DOMParser().parseFromString(`<div>${html}</div>`, 'text/html')
  const wrapper = doc.body.firstElementChild
  if (!wrapper) return html
  const firstHeading = wrapper.querySelector('h1, h2, h3, h4, h5, h6')
  if (!firstHeading) return html

  const headingText = firstHeading.textContent?.trim().replace(/\s+/g, ' ') ?? ''
  const entityName = entity.name.trim().replace(/\s+/g, ' ')
  if (headingText === entityName) firstHeading.remove()
  return wrapper.innerHTML
})
</script>

<template>
  <aside class="sidebar card">
    <div class="sb-hdr">
      <span class="sb-title">Entities</span>
      <span class="sb-count">{{ entities.length }}</span>
    </div>
    <ul class="ent-list">
      <li
        v-for="e in entities"
        :key="e.artifact_id"
        class="ent-item"
        :class="{ 'ent--active': selectedId === e.artifact_id }"
        @click="emit('select-entity', e.artifact_id)"
      >
        <span
          class="ent-glyph"
          :title="e.artifact_type"
        >
          <ArchimateTypeGlyph
            :type="toGlyphKey(e.artifact_type)"
            :size="13"
          />
        </span>
        <span
          class="ent-dot"
          :style="{ background: getDomainColor(e.domain) }"
        />
        <span class="ent-name">{{ e.name }}</span>
      </li>
    </ul>

    <component
      :is="viewerExtension.detailComponent"
      v-if="selectedSubPart && viewerExtension"
      :detail="selectedSubPart"
      @close="emit('clear-sub-part')"
    />

    <div
      v-if="selectedConnection"
      class="ent-det"
    >
      <div class="det-hdr">
        <span class="det-name">{{ selectedConnection.conn_type }}</span>
        <button
          class="det-close"
          @click="emit('clear-connection')"
        >
          ×
        </button>
      </div>
      <div class="conn-flow">
        {{ selectedConnection.source_name }} → {{ selectedConnection.target_name }}
      </div>
      <div
        v-if="selectedConnection.content_text?.trim()"
        class="det-content"
      >
        {{ selectedConnection.content_text }}
      </div>
      <div
        v-if="selectedConnection.edge_key"
        class="det-edge-label"
      >
        <label class="det-label-text">Diagram label</label>
        <input
          :value="edgeLabelInput"
          class="det-label-input"
          placeholder="(derived)"
          @input="emit('update:edgeLabelInput', ($event.target as HTMLInputElement).value)"
          @keydown.enter.prevent="emit('save-edge-label')"
          @blur="emit('save-edge-label')"
        >
        <div
          v-if="edgeLabelError"
          class="det-label-err"
        >
          {{ edgeLabelError }}
        </div>
      </div>
    </div>
    <div
      v-if="selectedId && entityQuery.loading.value"
      class="ent-det ent-det--loading"
    >
      Loading…
    </div>
    <div
      v-if="entityQuery.data.value"
      class="ent-det"
    >
      <div class="det-hdr">
        <RouterLink
          :to="{ path: '/entity', query: { id: entityQuery.data.value.artifact_id } }"
          class="det-name"
        >
          {{ entityQuery.data.value.name }}
        </RouterLink>
        <button
          class="det-close"
          @click="emit('select-entity', selectedId!)"
        >
          ×
        </button>
      </div>
      <div class="det-chips">
        <span
          class="chip"
          :class="`domain--${entityQuery.data.value.domain}`"
        >{{ entityQuery.data.value.domain }}</span>
        <span
          class="chip"
          :class="`status--${entityQuery.data.value.status}`"
        >{{ entityQuery.data.value.status }}</span>
        <span class="chip chip-type">{{ entityQuery.data.value.artifact_type }}</span>
      </div>
      <div
        v-if="selectedEntityDetailHtml"
        class="det-content markdown-body"
        v-html="selectedEntityDetailHtml"
      />
      <RouterLink
        :to="{ path: '/graph', query: { id: entityQuery.data.value.artifact_id } }"
        class="explore-lnk"
      >
        Explore in graph →
      </RouterLink>
    </div>
  </aside>
</template>

<style scoped>
.card { background: white; border-radius: 8px; border: 1px solid #e5e7eb; }
.sidebar { display: flex; flex-direction: column; position: sticky; top: 16px; margin-left: 16px; min-width: 0; }
@media (max-width: 800px) {
  .sidebar { margin-left: 0; margin-top: 16px; position: static; }
}
.sb-hdr { display: flex; align-items: center; justify-content: space-between; padding: 10px 12px 8px; border-bottom: 1px solid #f3f4f6; }
.sb-title { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: .05em; color: #6b7280; }
.sb-count { font-size: 11px; color: #9ca3af; }
.ent-list { list-style: none; overflow-y: auto; max-height: 320px; padding: 4px 0; margin: 0; }
.ent-item { display: flex; align-items: center; gap: 5px; padding: 5px 10px; cursor: pointer; font-size: 12px; color: #374151; }
.ent-item:hover { background: #f9fafb; }
.ent--active { background: #eff6ff; color: #1d4ed8; }
.ent-glyph { display: flex; align-items: center; flex-shrink: 0; color: #6b7280; }
.ent-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
.ent-name { flex: 1; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.ent-det { padding: 10px 12px 12px; border-top: 1px solid #e5e7eb; }
.conn-flow { font-size: 12px; color: #374151; margin-bottom: 6px; }
.ent-det--loading { color: #9ca3af; font-size: 12px; }
.det-hdr { display: flex; align-items: flex-start; gap: 4px; margin-bottom: 12px; }
.det-name { font-size: 18px; font-weight: 700; color: #1d4ed8; flex: 1; line-height: 1.25; text-decoration: none; }
.det-name:hover { text-decoration: underline; }
.det-close { background: none; border: none; font-size: 16px; cursor: pointer; color: #9ca3af; line-height: 1; padding: 0 2px; flex-shrink: 0; } .det-close:hover { color: #374151; }
.det-chips { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 8px; }
.chip { font-size: 10px; padding: 2px 6px; border-radius: 3px; font-weight: 500; background: #f3f4f6; color: #374151; }
.det-content { font-size: 12px; line-height: 1.5; color: #374151; margin-bottom: 8px; max-height: 220px; overflow-y: auto; }
.det-edge-label { margin-top: 8px; }
.det-label-text { display: block; font-size: 11px; color: #6b7280; margin-bottom: 3px; }
.det-label-input { width: 100%; padding: 4px 6px; font-size: 12px; border: 1px solid #d1d5db; border-radius: 4px; box-sizing: border-box; }
.det-label-input:focus { outline: none; border-color: #2563eb; }
.det-label-err { font-size: 11px; color: #dc2626; margin-top: 3px; }
.det-content :deep(p) { margin: 0.35rem 0; }
.det-content :deep(h1),
.det-content :deep(h2),
.det-content :deep(h3) { margin-top: 0; }
.explore-lnk { font-size: 12px; color: #2563eb; } .explore-lnk:hover { text-decoration: underline; }
</style>
