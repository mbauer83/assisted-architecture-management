# PROMPT — next session (goal execution)

This is **`scalable-architecture-for-humans-and-ai`**, a platform for managing software /
enterprise **architecture repositories**: the model is versioned Markdown files (entities +
connections + diagrams) authored ONLY through MCP tools (`artifact_*`), served by a
long-running backend with a GUI, REST API, and MCP servers, plus an optional confidential
**assurance** module (STPA/CAST/GRC, security signals, AI-BOM).

**First, discover context from the running self-model via MCP** (the platform models itself).
Start at the motivation layer and walk outward — this orients you better than reading source:
- `artifact_query_search_artifacts(query="…", domain="motivation")` + `artifact_query_list_artifacts`
  to find the goals / requirements / drivers;
- `artifact_query_read_artifact(id, mode="full")` on the key motivation entities, then follow
  `artifact_query_find_connections_for` into strategy → application → technology.

**Goal:** finish the remainder of `TASKS-strategy-and-assurance-uplift.md`. READ its
`⚠ READ FIRST` reconciled-state table before deriving work (checkbox state lags in places).
The three sibling plans (attribute-profile-registry, aibom, OpenAPI) are DONE; only this
plan's tail remains.

**Order (each a committed WU, gates green):**
1. **Stream L — licensing/legal readiness** (PLAN Part L §10b). Publication gate, PRECEDES
   docs. Setup check FIRST: swap the bundled **GPLv3** `plantuml.jar` for a permissive Maven
   variant (`plantuml-mit-light`/`-lgpl`/`-epl`) after a diagram-parity check; keep OpenJDK
   default + add a user-settable JRE; then Python + npm license inventories with CI gates;
   then generate `THIRD-PARTY-NOTICES` + the project LICENSE.
2. **E1 — documentation content** (PLAN §8.1): README amendment, nav/tiers, strategy + the 4
   viewpoints, assurance/security-signals, guidance v2, regenerated MCP tables, upgrade
   operator guide, self-model showcase; link + generated-reference check.
3. **Dev-server / restart-gated batch** (needs an owner backend restart + `npm run dev`):
   - **E2** deterministic screenshots (fail-closed capture harness, synthetic TLP:WHITE
     fixtures, provenance manifest).
   - **G2** crit-21b e2e trace-pattern GUI walk (Playwright).
   - **aibom G3** live: mark an entity → derive → export (REST + MCP after session restart).
   - **security-signals item 7** GUI walk (SecurityFindingsView / VulnerabilityImpact).
   - **U0b live Docker smoke**: rebuild the CURRENT image, mount an old-format data volume
     (reuse the `tests/support/previous_release_deployment.py` shape), run the container,
     assert it reaches healthy (entrypoint upgrades before serving).
4. **WU-X1 — integrated closure (LAST)**: documentation truth-audit, §13.2 layered gates,
   cross-document consistency, current live MCP stats, all gates over the integrated result.

**Gates before every commit, ONE AT A TIME (concurrent heavy jobs hang the WSL2 host):**
`uv run python -m pytest -q` · `uv run ruff check src/ tests/` · `uv run zuban check` ·
frontend from `tools/gui/`: `npm run lint` (NEVER pipe through tail/grep — it masks the exit
code; use `lint:fast` during work, full `npm run lint` read in full at each stream end)
`&& npm run typecheck && npx vitest run`.

**House rules:** model writes ONLY via `artifact_*`/`assurance_*` MCP (dry_run first,
`artifact_verify` after); never `git add -A`; never commit `.arch-assurance/`; 350-line /
120-col source limits (`*.md` exempt); central clock for timestamps; no phase/WU/§ refs in
source or persistent docs (PLAN/TASKS/PROMPT exempt). Backend code changes are inert until an
owner backend restart; new/renamed MCP tools need a Claude session restart — ASK proactively
when a change must take effect for the next step.
