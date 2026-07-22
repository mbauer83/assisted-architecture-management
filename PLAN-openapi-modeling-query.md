# PLAN — OpenAPI fidelity for the modeling & querying REST surface

Owner sign-off 2026-07-22: **modeling + query endpoints only** (assurance/security,
promotion, sync, admin deferred). Sits between the attribute-profile plan and AIBOM because
both reshape entity/connection payloads — publishing the contract now documents shapes about
to change under a stable discipline.

## 1. Problem (measured, not assumed)

FastAPI already serves `/openapi.json` + `/docs` dynamically, so **exposure is not the gap —
fidelity is.** Against the live backend: 145 operations; only 10 carry a real 200 response
schema; **135 return a bare `JSONResponse`/`dict[str, Any]` with no `response_model`**; 39/145
have a description; **8/145 are tagged**; **0 declare any non-200 status** even though
423/403/409/404/400 are routinely returned by the write path and lookups.

The consequence: `/docs` is a list of untyped operations. A REST client (or a generated SDK)
learns nothing about response shapes or the error contract from the spec, and must read the
Vue adapter or the handler source instead. The Effect schemas in `tools/gui/src/domain/
schemas/*` are the *de facto* contract; the OpenAPI document should carry the same shapes so
the contract is published once, at the boundary, rather than mirrored by hand in the client.

## 2. Scope (this plan)

The **71 modeling/query operations** across these routers (counted 2026-07-22):

| Router | Ops | Router | Ops |
|---|---|---|---|
| `diagrams` | 12 | `documents` | 7 |
| `entities` | 9 | `groups` | 6 |
| `viewpoint_authoring` | 9 | `connections` / `connection_read_routes` | 5 / 5 |
| `viewpoints` | 5 | `diagram_types` | 4 |
| `entity_search` | 3 | `_diagram_serving` | 3 |
| `modules` / `authoring_guidance` / `identifiers` | 1 each | | |

Out of scope (deferred, tracked as a follow-up): `_assurance_*`, `promote`, `sync*`, `admin`,
`events`.

## 3. Locked decisions

- **D1 — Publish the shapes the GUI already trusts.** Response models mirror the Effect
  schemas in `tools/gui/src/domain/schemas/*`; the OpenAPI document and the frontend schema
  are two projections of ONE contract, not two hand-kept copies. Where a handler returns a
  shape a Pydantic model can express, declare `response_model`; where it returns an
  open/dynamic map (e.g. `authoring-guidance`), declare a documented `dict` response with a
  description rather than fake precision.
- **D2 — Tags group by surface.** One FastAPI tag per router-family (`entities`,
  `connections`, `diagrams`, `viewpoints`, `documents`, `groups`, `taxonomy`), so `/docs`
  reads as a navigable API, not a flat list. Tags declared once via `APIRouter(tags=[…])`
  where a router is single-purpose, per-operation where a router mixes concerns.
- **D3 — The error contract is declared, not implicit.** A shared `responses=` fragment
  documents the statuses the mutation manifest + lookups actually return: 400 (validation),
  404 (not found), 422 (FastAPI body validation — automatic), 423 (write gate retryable),
  403 (forbidden), 409 (conflict). Attached to the operations that can emit each — read
  operations get 404 where they look up by id; write operations get the write-gate set.
- **D4 — No behaviour change.** This is a documentation/typing pass. `response_model` must
  match what the handler already returns byte-for-byte (FastAPI validates the return against
  the model in tests); if a handler's real shape differs from the GUI schema, that is a
  found defect — record it in TASKS and fix the shape, never loosen the model to hide it.
- **D5 — A contract test locks it.** A test asserts the generated `/openapi.json` has: a
  `response_model` (non-empty 200 schema) for every in-scope operation, a tag, a summary, and
  at least the applicable declared error statuses. The test enumerates the in-scope routers
  so a new untyped modeling endpoint fails until documented — the fidelity cannot regress.

## 4. Work streams

- **OA1 — Response models.** Define Pydantic response models (or reuse existing body models)
  for the in-scope read shapes, mirroring the Effect schemas: entity detail/list/schemata,
  connection read, diagram read/context, viewpoint read/list, document read, group list,
  taxonomy, entity search. Attach `response_model=` to each GET/POST that returns one.
  Dynamic maps get a described `dict` response.
- **OA2 — Tags + summaries.** One tag per surface; a one-line `summary` per operation
  (imperative, e.g. "Read an entity by id"); promote the existing docstring first line to
  `description` where present.
- **OA3 — Error responses.** Shared `responses` fragments (`READ_RESPONSES`,
  `WRITE_RESPONSES`) declared once and spread onto operations per D3.
- **OA4 — Contract test + docs.** The D5 enumerating test; a short reference doc
  (`docs/reference/rest-api.md`) pointing at `/docs` and `/openapi.json` and stating the
  fidelity guarantee. Regenerate nothing client-side (the frontend already has its schemas);
  note the option of generating an SDK from the now-faithful spec as future work.

## 5. Non-goals / deferred

- The assurance/security, promotion, sync, and admin surfaces (a second pass).
- Generating a typed client SDK from the spec (possible once fidelity lands; not this plan).
- Changing any endpoint's behaviour, path, or payload.

## 6. Standing checklist verdicts

- **Self-model sync:** none required — this documents the existing REST surface; the "unified
  backend / thin surfaces" ADR already covers the architecture. A one-line note in
  `docs/reference/` suffices (OA4).
- **Documentation:** `docs/reference/rest-api.md` (OA4).
- **Upgrade/repair path:** none — no stored data or repo format changes; a doc/typing pass.

## 7. Acceptance

- Every in-scope operation has a `response_model` (or a documented dynamic-map response), a
  tag, and a summary; applicable error statuses are declared.
- The D5 contract test passes and fails on a new untyped in-scope endpoint.
- Full backend + ruff + zuban green; `/openapi.json` regenerates cleanly (no runtime error);
  frontend gates unaffected (no client change).
