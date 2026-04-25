# Effect Frontend Refactor Spec

## Goal

Increase the value of `effect` in `tools/gui` where it improves:

- workflow composition
- typed error handling
- cancellation / lifecycle safety
- reduction of repetitive `Effect.runPromise(...).then(...).catch(...)` plumbing

Do **not** force effect-style abstractions into simple presentational Vue code where Vue refs/computed already express the logic clearly.

## Current State

The frontend already uses `effect` well at the transport boundary:

- [tools/gui/src/adapters/http/HttpModelRepository.ts](./tools/gui/src/adapters/http/HttpModelRepository.ts)
- [tools/gui/src/domain/schemas.ts](./tools/gui/src/domain/schemas.ts)
- [tools/gui/src/domain/errors.ts](./tools/gui/src/domain/errors.ts)

But most SFCs immediately collapse effects to promises via `Effect.runPromise(...)`, which loses many of the compositional benefits.

Current bridge:

- [tools/gui/src/ui/composables/useAsync.ts](./tools/gui/src/ui/composables/useAsync.ts)

This is useful, but too narrow:

- read-oriented only
- stringifies errors early
- does not model mutation flows
- does not address cancellation / stale result races

## Refactor Principles

1. Keep `effect` strongest in the application/workflow layer.
2. Keep Vue refs/computed/template code idiomatic and direct.
3. Do not introduce full DI / `Layer` complexity unless it materially reduces local complexity.
4. Prefer a small number of reusable composables/helpers over many bespoke patterns.
5. Preserve typed error information until the rendering boundary whenever practical.
6. Avoid introducing ceremony that is larger than the problem it solves.

## Non-Goals

Do **not**:

- rewrite the entire frontend around effect-ts
- replace ordinary `ref` / `computed` usage with effect-based state machines
- add abstractions to trivial screens just for consistency
- add `Layer` / service-environment machinery unless clearly justified

## High-Value Target Areas

These are the primary candidates for improvement because they contain multi-step workflows, branching behavior, repeated error handling, or lifecycle complexity.

### 1. Save Workflow

Target:

- [tools/gui/src/ui/components/SaveChangesDialog.vue](./tools/gui/src/ui/components/SaveChangesDialog.vue)

Why:

- mode-dependent branching
- multiple mutation paths with similar handling
- manual loading / result / error transitions

Desired outcome:

- replace imperative branching with a small set of app-level effect programs
- centralize success/result formatting
- standardize typed mutation execution

### 2. Promote Workflow

Target:

- [tools/gui/src/ui/views/PromoteView.vue](./tools/gui/src/ui/views/PromoteView.vue)

Why:

- discovery -> plan -> execute flow
- fallback logic
- likely best example of workflow composition

Desired outcome:

- represent the workflow as explicit effect programs
- isolate orchestration from template/UI state
- make retry/error behavior easier to understand

### 3. Diagram Edit Workflow

Target:

- [tools/gui/src/ui/views/EditDiagramView.vue](./tools/gui/src/ui/views/EditDiagramView.vue)

Why:

- many interacting async operations
- discovery, load, preview, save, selection state
- lifecycle sensitivity around SVG and route changes

Desired outcome:

- separate workflow logic from view logic
- reduce duplicated async/error state code
- improve stale-result/cancellation safety

### 4. Diagram Detail Screen

Target:

- [tools/gui/src/ui/views/DiagramDetailView.vue](./tools/gui/src/ui/views/DiagramDetailView.vue)

Why:

- context load + SVG load + interactivity attach
- selection / detail loading
- delete flow

Desired outcome:

- treat screen loading as a composed program
- make SVG/resource lifecycle safer and more explicit

### 5. Connections Workflow

Target:

- [tools/gui/src/ui/components/ConnectionsPanel.vue](./tools/gui/src/ui/components/ConnectionsPanel.vue)

Why:

- multiple related reads and writes
- ontology + write-help + add/edit/remove/associate flows
- repeated state transitions

Desired outcome:

- unify query/mutation handling
- reduce imperative repetition
- keep typed domain failures available longer

## Low-Value / Leave Mostly Alone

These areas should stay mostly idiomatic Vue unless a tiny improvement falls out naturally.

- [tools/gui/src/ui/views/HomeView.vue](./tools/gui/src/ui/views/HomeView.vue)
- [tools/gui/src/ui/views/EntitiesView.vue](./tools/gui/src/ui/views/EntitiesView.vue)
- simple filters, computed labels, lightweight local form state
- presentational components with minimal async behavior

## Recommended Architecture Changes

### A. Replace `useAsync` with More Capable Primitives

Current:

- [tools/gui/src/ui/composables/useAsync.ts](./tools/gui/src/ui/composables/useAsync.ts)

Introduce:

- `useEffectQuery`
- `useEffectMutation`
- optional `useEffectTask` or `useEffectResource`

Minimum requirements:

- typed success state
- typed error state retained internally
- exposed rendering helpers or derived string output
- built-in loading state
- support for stale result suppression or cancellation
- no unhandled floating promises

Suggested shape:

```ts
type QueryState<A, E> = {
  data: Ref<A | null>
  error: Ref<E | null>
  loading: Ref<boolean>
  run: (effect: Effect.Effect<A, E, never>) => void
}

type MutationState<A, E> = {
  result: Ref<A | null>
  error: Ref<E | null>
  running: Ref<boolean>
  run: (effect: Effect.Effect<A, E, never>) => Promise<Exit.Exit<A, E>>
}
```

Do not copy this shape blindly if a better local design emerges.

### B. Move Multi-Step Logic into Application-Layer Programs

`ModelService` is currently a thin forwarder:

- [tools/gui/src/application/ModelService.ts](./tools/gui/src/application/ModelService.ts)

Add application-layer functions/modules for workflows such as:

- `loadDiagramDetailScreen`
- `loadEditableDiagram`
- `saveChangesByMode`
- `planPromotionWorkflow`
- `executePromotionWorkflow`

Use `Effect.gen` / composition instead of nested promise control flow.

### C. Standardize Error Mapping

Current user-facing error handling is inconsistent and often stringifies errors ad hoc.

Relevant files:

- [tools/gui/src/ui/lib/errors.ts](./tools/gui/src/ui/lib/errors.ts)
- [tools/gui/src/domain/errors.ts](./tools/gui/src/domain/errors.ts)

Desired outcome:

- consistent app-level mapping from typed domain error -> UI message
- preserve structured errors until the display boundary
- avoid early `String(error)` except at the final rendering step

### D. Improve Cancellation / Stale Result Safety

Apply especially to:

- route-dependent loads
- debounced searches
- SVG attach workflows
- parallel load sequences

Minimum acceptable behavior:

- old requests must not overwrite newer state
- no hidden race between route changes and async completion

Implementation options:

- monotonically increasing request token
- `AbortController`
- scoped effect helper if done cleanly

Choose the simplest approach that actually works in this codebase.

## Recommended Order of Work

1. Introduce composables/helpers
   - build `useEffectQuery` / `useEffectMutation`
   - keep them small and well-typed
2. Refactor `SaveChangesDialog`
   - smallest high-value proving ground
3. Refactor `PromoteView`
   - best workflow-heavy screen
4. Refactor `DiagramDetailView`
5. Refactor `EditDiagramView`
6. Refactor `ConnectionsPanel`
7. Remove or reduce old promise-based duplication

## Guardrails

### Keep

- schema decoding in repository layer
- existing typed domain models
- existing sanitized `v-html` approach and SVG sanitization
- straightforward Vue template state when it is already simple

### Avoid

- effect-based wrappers for every computed/ref
- abstraction layers that hide simple business logic
- converting all component methods into opaque helper modules

## Acceptance Criteria

The refactor is successful if:

1. High-value workflow screens have less repeated async boilerplate.
2. Error handling is more uniform and remains typed longer.
3. Route/load/search races are reduced or eliminated in touched areas.
4. The resulting code is easier to follow, not more abstract.
5. Existing checks still pass:
   - `npm run lint` in `tools/gui`
   - `npm run typecheck` in `tools/gui`

## Evaluation Criteria for Each Refactor

For each touched file, ask:

1. Did this remove duplicated async state management?
2. Did this preserve or improve typed error information?
3. Did this reduce nested branching / imperative flow control?
4. Did this improve cancellation or stale-state safety?
5. Is the new code easier for a senior Vue/TS engineer to maintain?

If the answer is mostly "no", revert the abstraction and keep the simpler Vue code.

## Suggested Deliverables

- New composables under:
  - `tools/gui/src/ui/composables/`
- Optional new application workflow modules under:
  - `tools/gui/src/application/`
- Refactors of the target components/views listed above
- Removal of replaced promise-based boilerplate where practical

## Notes for the Implementing Agent

- Treat this as a selective architectural refactor, not a library evangelism exercise.
- Prefer a few strong patterns over broad but shallow effect adoption.
- Keep the public behavior stable unless a change is clearly an improvement in correctness.
- If a screen becomes harder to understand after refactoring, the refactor is wrong.
