# Document Support Feature — Implementation Progress

## Overview

Documents are first-class artifacts alongside entities, connections, and diagrams. They live in `documents/{doc_type}/` inside the architecture repository. Document types are defined by JSON schemata in `.arch-repo/documents/{doc_type}.json`. First supported type: ADR (Architecture Decision Record).

---

## DONE ✅ — Python Backend (complete, 174 tests passing)

### Rename: `model_` → `artifact_`
All Python code, MCP tools, test files, and CLI renamed from `model_*` to `artifact_*`. `.mcp.json` server key updated to `arch-artifacts`. pyproject.toml entry point updated.

### Document Schema Format
- `src/common/artifact_document_schema.py` — `load_document_schemata(repo_root)`, `get_document_schema(repo_root, doc_type)`
- `engagements/ENG-ARCH-REPO/architecture-repository/.arch-repo/documents/adr.json` — ADR schema with `abbreviation`, `name`, `frontmatter_schema`, `required_sections`

### Domain Types
- `src/common/artifact_types.py` — `DocumentRecord` dataclass, `summary_from_document`, `STANDARD_DOCUMENT_FIELDS`. `SearchHit.record_type` and `ArtifactSummary.record_type` Literals extended to `"document"`.

### Parsing / Scoring / Read Helpers
- `src/common/artifact_parsing.py` — `parse_document(path) -> DocumentRecord | None`
- `src/common/artifact_scoring.py` — `score_document(rec, query_lc, tokens) -> float`
- `src/common/_artifact_query_helpers.py` — `read_document(rec, *, mode, section) -> dict`, `_extract_section(content, section) -> str`

### SQLite Index (schema / storage / service / context / queries)
- `src/common/artifact_index/schema.py` — `documents` table + `documents_fts` FTS5 virtual table
- `src/common/artifact_index/storage.py` — `upsert_document_record`, `delete_document_record`, `_document_row`, `rebuild_sqlite` extended
- `src/common/artifact_index/service.py` — `_documents` dict, `_scan_mount` scans `documents/`, `_is_document_path`, `apply_document_file_change`, `document_records()`, `get_document()`, extended search + apply_file_changes
- `src/common/artifact_index/context.py` — `apply_document_file_change`
- `src/common/artifact_index/queries.py` — `include_documents: bool = True` added to `search_artifacts`, UNION `documents_fts`

### ArtifactRepository
- `src/common/artifact_repository.py` — `_documents` property, `get_document`, `list_documents`, `apply_file_change` extended, `read_artifact(section=)`, `summarize_artifact`, `list_artifacts(include_documents=)`, `search_artifacts(include_documents=)`, `search(include_documents=)`, `stats()` extended, `_search_documents` fallback

### Document Write Operations
- `src/tools/artifact_write/document.py` — `create_document`, `edit_document`, `delete_document`
- `src/tools/artifact_write/__init__.py` — exports added
- `src/tools/artifact_write_ops.py` — re-exports added

### MCP Write Tools
- `src/tools/artifact_mcp/write/document.py` — `artifact_create_document`, `artifact_edit_document`, `artifact_delete_document`, `register(mcp)`
- `src/tools/artifact_mcp/write_tools.py` — re-exports + document.register(mcp)
- `src/tools/mcp_artifact_server.py` — re-exports added

### MCP Query Tools
- `src/tools/artifact_mcp/query_list_read_tools.py` — `include_documents=False` param on `artifact_query_list_artifacts`, `section=` param on `artifact_query_read_artifact`
- `src/tools/artifact_mcp/query_search_tools.py` — `include_documents=True` param on `artifact_query_search_artifacts`

### REST Router
- `src/tools/gui_routers/documents.py` — `GET /api/document-types`, `GET /api/document-schemata`, `GET /api/documents`, `GET /api/document`, `POST /api/document`, `PUT /api/document/{id}`, `DELETE /api/document/{id}`
- `src/tools/arch_backend.py` — `documents_router` registered
- `src/tools/gui_routers/entities.py` — `GET /api/artifact-search` unified cross-artifact search

### Verifier Rules
- `src/common/artifact_verifier.py` — `verify_document_file()` method with E153 (frontmatter schema), E154 (required sections), W155 (unresolvable internal links), `_verify_all_full` and `_verify_all_incremental` extended to include `documents/`

---

## NOT DONE — Frontend

All frontend work is pending. **Do not rename the service layer files** (ModelRepository, HttpModelRepository, ModelService) — that's unnecessary churn. Add new methods alongside existing ones.

Key existing file locations:
- Port (interface): `tools/gui/src/ports/ModelRepository.ts`
- HTTP adapter: `tools/gui/src/adapters/http/HttpModelRepository.ts`
- Domain schemas: `tools/gui/src/domain/schemas.ts` (re-exported via `tools/gui/src/domain/index.ts`)
- Router: `tools/gui/src/ui/router/index.ts`
- Views: `tools/gui/src/ui/views/`
- Components: `tools/gui/src/ui/components/`
- App nav: `tools/gui/src/ui/App.vue`

### 1. Install dependencies [ ]

```bash
cd tools/gui && npm install @codemirror/view @codemirror/state @codemirror/lang-markdown @codemirror/commands codemirror
```

Note: `marked` and `dompurify` are already in `package.json` — use them for markdown preview. **Do not install `markdown-it`**.

### 2. Add domain types to `tools/gui/src/domain/schemas.ts` [ ]

Append after the existing `SearchResultSchema` block (around line 152):

```typescript
// ── Document types ────────────────────────────────────────────────────────────

export const DocumentTypeSchema = Schema.Struct({
  doc_type: Schema.String,
  abbreviation: Schema.String,
  name: Schema.String,
  required_sections: Schema.Array(Schema.String),
})
export type DocumentType = typeof DocumentTypeSchema.Type

export const DocumentTypesSchema = Schema.Array(DocumentTypeSchema)

export const DocumentSummarySchema = Schema.Struct({
  artifact_id: Schema.String,
  doc_type: Schema.String,
  title: Schema.String,
  status: Schema.String,
  path: Schema.String,
  keywords: Schema.Array(Schema.String),
  sections: Schema.Array(Schema.String),
})
export type DocumentSummary = typeof DocumentSummarySchema.Type

export const DocumentListSchema = Schema.Struct({
  total: Schema.Number,
  items: Schema.Array(DocumentSummarySchema),
})
export type DocumentList = typeof DocumentListSchema.Type

export const DocumentDetailSchema = Schema.Struct({
  artifact_id: Schema.String,
  artifact_type: Schema.Literal('document'),
  doc_type: Schema.String,
  title: Schema.String,
  status: Schema.String,
  record_type: Schema.Literal('document'),
  path: Schema.String,
  keywords: Schema.Array(Schema.String),
  sections: Schema.Array(Schema.String),
  content_snippet: Schema.String,
  content_text: Schema.optional(Schema.String),
  extra: Schema.optional(Schema.Record({ key: Schema.String, value: Schema.Unknown })),
})
export type DocumentDetail = typeof DocumentDetailSchema.Type

// ── Artifact search (cross-type) ──────────────────────────────────────────────

export const ArtifactSearchHitSchema = Schema.Struct({
  score: Schema.Number,
  record_type: Schema.Union(
    Schema.Literal('entity'), Schema.Literal('connection'),
    Schema.Literal('diagram'), Schema.Literal('document'),
  ),
  artifact_id: Schema.String,
  name: Schema.String,
  status: Schema.String,
  path: Schema.String,
})
export type ArtifactSearchHit = typeof ArtifactSearchHitSchema.Type

export const ArtifactSearchResultSchema = Schema.Struct({
  query: Schema.String,
  hits: Schema.Array(ArtifactSearchHitSchema),
})
export type ArtifactSearchResult = typeof ArtifactSearchResultSchema.Type
```

Also extend `StatsSchema` (around line 5) to add:
```typescript
  documents: Schema.optional(Schema.Number),
  documents_by_type: Schema.optional(Schema.Record({ key: Schema.String, value: Schema.Number })),
```

Also update `tools/gui/src/domain/index.ts` to re-export all new types.

### 3. Extend port `tools/gui/src/ports/ModelRepository.ts` [ ]

Add to the `ModelRepository` interface (after line 178, before closing `}`):

```typescript
  // ── Document methods ──────────────────────────────────────────────────────
  readonly listDocumentTypes: () => Effect.Effect<DocumentType[], RepoError>
  readonly listDocuments: (params?: {
    doc_type?: string; status?: string; limit?: number; offset?: number;
  }) => Effect.Effect<DocumentList, RepoError>
  readonly getDocument: (id: string) => Effect.Effect<DocumentDetail, RepoError | NotFoundError>
  readonly createDocument: (body: {
    doc_type: string; title: string; body?: string;
    keywords?: string[]; extra_frontmatter?: Record<string, unknown>;
    version?: string; status?: string; dry_run?: boolean;
  }) => Effect.Effect<WriteResult, RepoError>
  readonly editDocument: (id: string, body: {
    title?: string; body?: string; keywords?: string[];
    extra_frontmatter?: Record<string, unknown>;
    status?: string; version?: string; dry_run?: boolean;
  }) => Effect.Effect<WriteResult, RepoError>
  readonly deleteDocument: (id: string, dry_run?: boolean) => Effect.Effect<WriteResult, RepoError>
  readonly artifactSearch: (q: string, params?: {
    limit?: number; include_documents?: boolean; include_diagrams?: boolean;
  }) => Effect.Effect<ArtifactSearchResult, RepoError>
```

Add to the import block at top of file:
```typescript
import type {
  DocumentType, DocumentList, DocumentDetail, ArtifactSearchResult,
} from '../domain'
```

### 4. Extend HTTP adapter `tools/gui/src/adapters/http/HttpModelRepository.ts` [ ]

Add schema imports to the existing import block:
```typescript
import {
  DocumentTypesSchema, DocumentListSchema, DocumentDetailSchema,
  ArtifactSearchResultSchema, WriteResultSchema,
} from '../../domain/schemas'
```

Add helper for PUT/DELETE (after the existing `postJson` at line ~109):
```typescript
const putJson = <A, I>(
  url: string,
  body: unknown,
  schema: Schema.Schema<A, I>,
): Effect.Effect<A, NetworkError | ParseResult.ParseError> =>
  Effect.tryPromise({
    try: async () => {
      const resp = await fetch(url, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!resp.ok) {
        const text = await resp.text().catch(() => resp.statusText)
        throw new NetworkError({ status: resp.status, message: text })
      }
      return resp.json() as Promise<unknown>
    },
    catch: (e) =>
      e instanceof NetworkError ? e : new NetworkError({ status: 0, message: String(e) }),
  }).pipe(Effect.flatMap(Schema.decodeUnknown(schema)))

const deleteReq = <A, I>(
  url: string,
  schema: Schema.Schema<A, I>,
): Effect.Effect<A, NetworkError | ParseResult.ParseError> =>
  Effect.tryPromise({
    try: async () => {
      const resp = await fetch(url, { method: 'DELETE' })
      if (!resp.ok) {
        const text = await resp.text().catch(() => resp.statusText)
        throw new NetworkError({ status: resp.status, message: text })
      }
      return resp.json() as Promise<unknown>
    },
    catch: (e) =>
      e instanceof NetworkError ? e : new NetworkError({ status: 0, message: String(e) }),
  }).pipe(Effect.flatMap(Schema.decodeUnknown(schema)))
```

Add to the object returned by `makeHttpModelRepository()` (before the closing `}`):
```typescript
  listDocumentTypes: () =>
    fetchJson(buildUrl('/document-types'), DocumentTypesSchema),
  listDocuments: (params = {}) =>
    fetchJson(buildUrl('/documents', params), DocumentListSchema),
  getDocument: (id) =>
    fetchJsonNotFound(buildUrl('/document', { id }), DocumentDetailSchema, id),
  createDocument: (body) =>
    postJson(buildUrl('/document'), body, WriteResultSchema),
  editDocument: (id, body) =>
    putJson(buildUrl(`/document/${encodeURIComponent(id)}`), body, WriteResultSchema),
  deleteDocument: (id, dry_run) =>
    deleteReq(buildUrl(`/document/${encodeURIComponent(id)}`, { dry_run }), WriteResultSchema),
  artifactSearch: (q, params = {}) =>
    fetchJson(buildUrl('/artifact-search', { q, ...params }), ArtifactSearchResultSchema),
```

### 5. MarkdownEditor.vue component [ ]

Create `tools/gui/src/ui/components/MarkdownEditor.vue`:

```typescript
// Props
interface Props {
  modelValue: string
  readonly?: boolean
  placeholder?: string
  minHeight?: string  // CSS value, default '200px'
}
// Emits: 'update:modelValue' (string)
```

Implementation:
- Two tabs: "Edit" and "Preview"
- **Edit tab**: CodeMirror 6 editor. Setup:
  ```typescript
  import { EditorView, basicSetup } from 'codemirror'
  import { markdown } from '@codemirror/lang-markdown'
  // extensions: [basicSetup, markdown(), EditorView.updateListener.of(update => { if (update.docChanged) emit('update:modelValue', update.state.doc.toString()) })]
  ```
  When `readonly=true`, add `EditorView.editable.of(false)` to extensions.
  Update editor when `modelValue` prop changes externally (use `view.dispatch({ changes: ... })` only if content differs).
- **Preview tab**: render with `marked(modelValue)`, sanitize with `DOMPurify.sanitize(html)`, bind to `<div v-html="...">`.
  ```typescript
  import { marked } from 'marked'
  import DOMPurify from 'dompurify'
  ```
- Store active tab in `ref<'edit' | 'preview'>('edit')`.
- Mount/unmount CodeMirror in the edit tab's container div using `onMounted`/`onUnmounted`.

### 6. ArtifactReferenceInput.vue component [ ]

Create `tools/gui/src/ui/components/ArtifactReferenceInput.vue`:

```typescript
// Props
interface Props {
  currentPath?: string  // absolute path of the document being edited (for relative link calc)
}
// Emits
// 'insert' (markdownLink: string) — emitted when user picks a reference
// 'close' () — emitted when dismissed
```

Implementation:
- Text `<input>` with debounced (300ms) calls to `repo.artifactSearch(q, { limit: 10, include_documents: true, include_diagrams: true })`.
- Results list grouped by `record_type`: entity, diagram, document.
- For each hit: show name + type badge.
- For `record_type === 'document'` hits with `sections.length > 0`: show expand chevron. On expand, fetch sections from the hit (they come from `DocumentSummary.sections` in the `artifactSearch` result — but the search endpoint returns `ArtifactSearchHit` which doesn't include sections). Two options:
  - Option A (simpler): call `getDocument(id)` on expand to get sections.
  - Option B: always include sections in artifact-search result (requires backend change to `GET /api/artifact-search` — NOT recommended).
  Use Option A.
- On click of a result (or a section): compute relative link from `currentPath` to `hit.path`, then emit `insert('[Title](relative/path.md)')` or `insert('[Title](relative/path.md#section-anchor)')`.
  - Section anchor: `section.toLowerCase().replace(/\s+/g, '-').replace(/[^\w-]/g, '')`.
  - Relative path: use `path.relative(path.dirname(currentPath), hit.path)` logic in TS (use string manipulation since paths are repo-relative strings).
- Reference `tools/gui/src/ui/components/EntitySearchInput.vue` for the debounce/inject pattern.

### 7. Document views [ ]

#### `tools/gui/src/ui/views/DocumentsView.vue`
- On mount: call `repo.listDocumentTypes()` + `repo.listDocuments()`.
- Filter bar: `<select>` for `doc_type` (populated from `listDocumentTypes()`), text filter on title.
- Table/list: columns = title (link to `/documents/{artifact_id}`), doc_type badge, status badge.
- "New Document" button → `router.push('/documents/new')`.

#### `tools/gui/src/ui/views/DocumentCreateView.vue`
- On mount: call `repo.listDocumentTypes()` to populate doc_type selector.
- Form fields:
  - `doc_type` — `<select>` from `listDocumentTypes()`; on change, update placeholder body.
  - `title` — `<input type="text">`
  - `status` — `<select>` with options: draft, accepted, rejected, superseded
  - `keywords` — simple comma-separated `<input>` (split on submit)
  - `body` — `<MarkdownEditor>` pre-populated with placeholder sections:
    ```typescript
    const placeholderBody = (requiredSections: string[]) =>
      requiredSections.map(s => `## ${s}\n\n`).join('\n')
    ```
- Submit: `repo.createDocument({ doc_type, title, body, keywords, status, dry_run: false })`.
- On success: `router.push('/documents/' + result.artifact_id)`.

#### `tools/gui/src/ui/views/DocumentDetailView.vue`
- Route param: `:id` → `useRoute().params.id as string`.
- On mount: `repo.getDocument(id)`.
- Fields (all editable inline):
  - `title` — `<input type="text">`
  - `doc_type` — read-only badge
  - `status` — `<select>` with options: draft, accepted, rejected, superseded
  - `keywords` — comma-separated `<input>`
  - `body` (`content_text`) — `<MarkdownEditor :modelValue="body" @update:modelValue="body = $event">`
- Toolbar above editor: "Insert Reference" button → opens `<ArtifactReferenceInput>` overlay; on `insert` event, insert the link at cursor position (use CodeMirror dispatch or append to body string).
- "Save" button: `repo.editDocument(id, { title, status, keywords, body, dry_run: false })`.
- "Delete" button (with confirmation): `repo.deleteDocument(id, false)` → `router.push('/documents')`.

### 8. Router and navigation [ ]

`tools/gui/src/ui/router/index.ts` — add routes (use lazy imports):
```typescript
{ path: '/documents', component: () => import('../views/DocumentsView.vue') },
{ path: '/documents/new', component: () => import('../views/DocumentCreateView.vue') },
{ path: '/documents/:id', component: () => import('../views/DocumentDetailView.vue') },
```

`tools/gui/src/ui/App.vue` — add "Documents" nav item alongside existing Entities/Diagrams links. Follow the existing pattern for nav items (look at how Diagrams nav item is structured).

### 9. MarkdownEditor in EntityDetailView (optional, do last) [ ]

`tools/gui/src/ui/views/EntityDetailView.vue`:
- Replace `<textarea>` for `summary` and `notes` fields with `<MarkdownEditor>`.
- Add "Insert Reference" button via `<ArtifactReferenceInput>` above the notes editor.

---

## Implementation Order

Do tasks in this order to minimize re-work:

1. Install npm deps (step 1)
2. Domain schemas (step 2) — compile-checks everything downstream
3. Port interface (step 3) — TypeScript errors guide adapter work
4. HTTP adapter (step 4) — enables all views to work
5. MarkdownEditor component (step 5) — needed by views
6. Document views + router + nav (steps 7, 8) — can test E2E at this point
7. ArtifactReferenceInput (step 6) — wire into DocumentDetailView
8. EntityDetailView markdown upgrade (step 9) — optional polish

---

## File ID Format

Documents follow the same pattern as entities:
`{ABBREVIATION}@{epoch}.{6-char-random}.{friendly-slug}.md`

Example: `ADR@1776857796.mvQlgb.use-adr-format.md`

## Document Schema Format

`.arch-repo/documents/{doc_type}.json`:
```json
{
  "abbreviation": "ADR",
  "name": "Architecture Decision Record",
  "frontmatter_schema": { /* JSON Schema for frontmatter fields */ },
  "required_sections": ["Context", "Decision", "Consequences"]
}
```

## REST Endpoints Reference

| Method | Path | Handler |
|--------|------|---------|
| GET | `/api/document-types` | `list_document_types()` → `[{doc_type, abbreviation, name, required_sections}]` |
| GET | `/api/document-schemata` | `get_document_schemata()` → `{doc_type: schema_dict}` |
| GET | `/api/documents?doc_type=&status=&limit=&offset=` | `list_documents()` → `{total, items: [DocumentSummary]}` |
| GET | `/api/document?id=` | `read_document(id)` → `DocumentDetail` |
| POST | `/api/document` | `create_document(body)` → `WriteResult` |
| PUT | `/api/document/{id}` | `edit_document(id, body)` → `WriteResult` |
| DELETE | `/api/document/{id}?dry_run=` | `delete_document(id)` → `WriteResult` |
| GET | `/api/artifact-search?q=&limit=&include_documents=&include_diagrams=` | `search_artifacts()` → `{query, hits: [ArtifactSearchHit]}` |

## Verifier Error Codes

- `E153` — frontmatter schema violation (missing required field or wrong type)
- `E154` — required section missing (e.g. `## Decision` not found)
- `W155` — unresolvable internal `.md` link (warning, not error)
