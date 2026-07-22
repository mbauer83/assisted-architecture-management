# REST API

The backend serves a live, self-describing REST API. The interactive docs and the machine
contract are always available from a running backend:

- **`/docs`** — interactive Swagger UI (try requests, see schemas).
- **`/redoc`** — reference-style rendering of the same spec.
- **`/openapi.json`** — the OpenAPI 3 document, for generating clients or contract checks.

## Fidelity guarantee (modeling & querying surface)

The modeling and querying operations — entities, connections, diagrams, viewpoints,
documents, groups, and the taxonomy/guidance reads — are documented to a fixed standard,
enforced by a contract test (`tests/tools/test_openapi_modeling_query_contract.py`) so it
cannot silently regress:

- every operation carries a **tag** (grouping it by concept in `/docs`) and a **summary**;
- every operation documents its **200 response body** with a schema derived from a typed
  response model — never a bare untyped `200`;
- **write** operations declare the error contract they can return: `400` (validation),
  `403` (forbidden), `409` (conflict), `423` (write-gate retryable), plus FastAPI's
  automatic `422` for request-body validation;
- **id-lookup reads** declare `404`.

Response schemas come from the handlers' **typed response models**, not hand-written JSON —
the type is the contract, and FastAPI generates the schema from it. Models declare the
fields worth documenting and allow additional properties, so a response is documented
without its payload ever being filtered.

## Deferred (second pass)

The assurance/security, promotion, sync, admin, and events endpoints are documented to
FastAPI's defaults today; giving them the same fidelity is a planned follow-up.
Generating a typed client SDK from the now-faithful spec is possible once that lands.

---

*See also: [CLI & backend](cli-and-backend.md) · [Configuration](configuration.md)*
