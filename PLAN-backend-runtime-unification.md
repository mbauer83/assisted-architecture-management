# PLAN — Backend Runtime Unification (single authority for artifact operations)

Status: draft / proposal
Created: 2026-06-06
Owner of: C4 plan prerequisites **P3 (assurance runtime)** and **P4 (CLI unification)**
Related: `PLAN-c4-self-model-narrative.md`, `PLAN-assurance-storage-confidentiality.md`
(SC-5 single composition root), `PLAN-assurance-architecture-model.md` (**supersedes**
its "separate Assurance MCP Server" modelling — see §6).

---

## 1. Principle & motivation

**`arch-backend` is the single runtime authority for every operation that reads or
mutates artifacts** (architecture *and* assurance), across all three human/AI surfaces
(MCP, CLI, REST/GUI). Only **bootstrap/config** commands that must run *before or around*
the backend stay independent.

Why: one composition root → one write queue (serialized human+AI writes), one in-process
cache/index, one verification path, one permission/gating model, and one place to reason
about confidentiality. Today this holds for REST/GUI and the architecture MCP stdio
bridges (which auto-start the backend and call it over HTTP), but **not** uniformly for
assurance MCP or for several CLI commands — they reach the repo/store directly, creating
parallel write paths that the C4 target architecture (and correctness) cannot tolerate.

## 2. Current state (verified)

- **Architecture MCP:** `arch-mcp-stdio-read` / `arch-mcp-stdio-write` bridges auto-start
  the unified backend and connect via HTTP (README). ✅ already routed.
- **Assurance MCP:** `mcp_assurance_server.py` defines two FastMCP servers
  (`/mcp/assurance-read`, `/mcp/assurance-write`, gated on an unlocked store) and a
  **single combined** `arch_mcp_stdio_assurance.py` bridge. Mounting into the unified
  backend and a read/write bridge split are **not** yet aligned with the core pattern.
- **CLI:** a few commands already call the backend; others perform **direct repository /
  config / assurance-store** access (the C4 review §7 flagged this). Bootstrap commands
  (`arch-init`, `arch-switch-engagement`, `arch-assurance init/use-backend/status`)
  legitimately run independently.

## 3. Target

1. **Four MCP endpoints mounted in `arch-backend`:** `/mcp/read`, `/mcp/write`,
   `/mcp/assurance-read`, `/mcp/assurance-write` — one composition root, shared cache +
   write queue + permission model; assurance endpoints return structured
   **unavailable/locked** status when the confidential store is disabled/locked.
2. **Four thin stdio bridges:** architecture read, architecture write, assurance read,
   assurance write — each a stdio↔HTTP shim to its endpoint (split the combined
   assurance bridge). These are the four C4 "bridge" containers.
3. **Artifact-affecting CLI = thin backend clients.** Every CLI command that reads or
   mutates architecture/assurance artifacts calls the backend REST surface (the same
   surface the GUI uses) — no direct repo/store writes.
4. **Bootstrap/config CLI stays independent:** `arch-init`, `arch-switch-engagement`,
   `arch-assurance init` / `use-backend` / `status` (they provision/select backends and
   must work before a backend exists). These are the only artifact-adjacent commands
   that may touch the filesystem directly, and only for provisioning.

## 4. Workstreams

- **W1 — Mount assurance in backend.** Mount the two assurance FastMCP apps in
  `arch-backend` alongside the core endpoints; share lifecycle/cache/queue; gate on
  store unlock; preserve hidden-until-enabled UI behaviour.
- **W2 — Four stdio bridges.** Split `arch_mcp_stdio_assurance` into read/write thin
  bridges; confirm the architecture bridges already conform; standardise the
  auto-start-and-connect transport across all four.
- **W3 — CLI audit & refactor.** Enumerate CLI commands; classify **artifact-affecting**
  (route through backend REST, following the bridge pattern) vs **bootstrap/config**
  (independent). Refactor the artifact-affecting ones; remove direct repo/store writes.
  *(Baseline: query/search/listing already run as backend REST endpoints — e.g. the new
  `entity_search.py` router registered in `gui_server.py` — so read paths are largely
  done; the gap is artifact-mutating CLI commands.)*
- **W4 — Availability & gating.** Artifact-affecting CLI commands **require a running
  backend** and **fail with a clear "start arch-backend" error** when it is absent (no
  auto-start — explicit, avoids surprise process spawns, works for shared/remote setups).
  Bootstrap/config commands are exempt (they run independently). Plus the structured
  unavailable/locked contract for gated assurance.
- **W5 — Tests.** Cross-surface parity (same op via REST/MCP/CLI ⇒ same result + same
  verification); single-writer serialization under concurrency; assurance gating;
  bridge transport.

## 5. Acceptance criteria

- No artifact-mutation path bypasses the backend write queue.
- Four MCP endpoints mounted; four thin stdio bridges; assurance gated.
- Every artifact-affecting CLI command is a thin backend client; only bootstrap/config
  commands run independently.
- Cross-surface parity + concurrency tests green.
- The C4 entities *Architecture/Assurance MCP Endpoint Adapter* (Backend-internal) and
  the four bridge containers reflect this runtime (feeds C4 P3/P4).

## 6. Reconciliations & open decisions

- **Supersede stale assurance modelling:** `PLAN-assurance-architecture-model.md` models
  "one Assurance MCP Server + one Assurance MCP Interface" as a separate runtime. Update
  it to the mounted-in-backend, four-endpoint, four-bridge model (and the Assurance
  Module concern grouping from the C4 plan §3.6).
- **CLI offline behaviour — CLOSED:** artifact-affecting CLI commands **require a
  running backend** and error clearly if absent (no auto-start); bootstrap exempt (W4).
- **Permission / grant model — by design: config-driven + availability-driven gating
  (no runtime auth).** The system is local-first and **intentionally has no
  authentication layer** (verified: only `repo_scope` exists). The four independently-
  grantable boundaries are — **by design, not as an interim measure** — enforced by
  **configuration** (which stdio bridge a client wires into `.mcp.json`) and
  **availability** (the assurance store-unlock gate plus structured *unavailable/locked*
  responses). This is the intended, lasting model; **runtime token/credential auth is
  out of scope and not planned.** The only requirement is that the four boundaries remain
  independently grantable through configuration and availability.
