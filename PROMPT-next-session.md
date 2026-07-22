# PROMPT — next session (documentation rework + restart-gated closure)

This is **`scalable-architecture-for-humans-and-ai`** (package **Architectonic**): a platform for
managing software / enterprise **architecture repositories** — the model is versioned Markdown
files (entities + connections + diagrams) authored ONLY through MCP tools (`artifact_*`), served
by a long-running backend with a GUI, REST API, and MCP servers, plus an optional confidential
**assurance** module (STPA/CAST/GRC, security signals, AI-BOM).

**Orient first from the running self-model via MCP** (the platform models itself). Start at the
motivation layer and walk outward: `artifact_query_search_artifacts(query=…, domain="motivation")`
+ `artifact_query_list_artifacts`, then `artifact_query_read_artifact(id, mode="full")` on key
motivation entities, then `artifact_query_find_connections_for` into strategy → application →
technology. Live stats via `artifact_query_stats`. This is also the raw material for the doc
showcase, so treat the walk as research for the rework.

**Where things stand:** `TASKS-strategy-and-assurance-uplift.md` Stream L (licensing) is DONE and
committed; the three sibling plans (attribute-profile-registry, aibom, OpenAPI) are DONE. What
remains of this plan is **documentation (E1/E2)**, a **restart-gated verification batch**, and the
**integrated closure (WU-X1)**. Read the ledger's `⚠ READ FIRST` reconciled-state table before
deriving work — checkbox state lags in places.

---

## PRIMARY TASK — thorough documentation evaluation, THEN rework (owner-directed)

Do **not** start editing docs immediately. First produce a written **documentation evaluation**
(a short plan doc, e.g. `PLAN-docs-rework.md`, owner-reviewed before execution) covering:

1. **Gap analysis: what changed vs. what the docs say.** The docs were last shaped before a large
   body of work landed. Enumerate every user-facing capability added/changed and decide, per item,
   whether it needs a new page, an edit, or only a mention. At minimum cover:
   - **Strategy & value self-model** — capabilities, value streams/stages/values, courses of
     action, resource-investment heat-maps.
   - **Assurance explorability** — edge enrichment + ontology-driven edge authoring, neighbor
     traversal + shared graph-explore canvas, deep-linkable assurance node route.
   - **Security signals & virtual attributes** — refresh-run lifecycle, posture metrics, VEX,
     OSV/CVSS acquisition + `tools/ingest_security_signals.py`, the `security-posture` viewpoint,
     the entity derived-attributes panel; both signal-backend configurations.
   - **Guidance pluralism v2** — hierarchy-generic guidance + domain context, default schemata,
     the `arch-import-guidance` flow (guidance is license-separated → must be imported).
   - **Motivation-coverage viewpoint** + the four shipped viewpoints; the viewpoints query model,
     typed let-bindings, derived relationships/impact analysis, traversal-authoring UI,
     witness-chain sidebar.
   - **ArchiMate 4.0 conformance**, specializations, viewpoints, C19C model exchange.
   - **Attribute-profile registry** (named profiles, blast-radius failure semantics), **AI-BOM**
     (model-derived), **OpenAPI** contract — the three done sibling plans.
   - **Upgrade/repair** — `arch-repair upgrade`, format-contract versioning, migrators (operator
     guide).
   - **Licensing & setup (this session)** — MIT license, `THIRD-PARTY-NOTICES.md`, the
     `licenses/` inventories + CI license gate, the user-settable JRE (`ARCH_JAVA`), the GPLv3
     PlantUML discharge, dependency-CVE posture. `docs/reference/licensing.md` is a STUB to be
     expanded into the full page.
   - **Deployment** — Docker Compose, entrypoint, profiles, assurance opt-in.
2. **Structure & IA.** Assess the `docs/` tree against Diátaxis (tutorials / how-to / reference /
   explanation) and the top open-source READMEs. Current shape: a `docs/reference/` set
   (cli-and-backend, configuration, docker-compose, rest-api, viewpoints-schema,
   archimate-4-conformance, git-sync-promotion, licensing-stub) + `docs/03-modeling/…`. Propose the
   target tree, the README's role (concise hub, not a manual), nav, and the tier/facet story.
   Honor the grounding rule: docs must reflect **real code + CLI/MCP + the real GUI**, dogfooded;
   no "AI antithesis" framing.
3. **Screenshot plan (feeds E2).** Decide **which self-model aspects** are worth showing and at
   what surface. Strong candidates: the strategy capability map + a value-stream diagram; the C4
   progression of the platform's own model; the assurance graph-explore canvas + a security-posture
   viewpoint render; the motivation-coverage viewpoint gap result; the guidance wizard showing
   composed domain context; an entity's derived security-attributes panel. For each: the exact
   entity/viewpoint IDs, the surface, and why it earns a spot. Assurance/metrics shots must use
   synthetic TLP:WHITE fixtures with a visible synthetic marker.
4. **Wording & voice.** Where the current prose over-claims, is stale, or drifts from the grounded
   design narrative — list the specific edits.

Then **execute E1** (PLAN §8.1): README amendment (correct any stale claims), nav/tiers, the
strategy + four-viewpoint pages, assurance/security-signals pages, guidance-v2 page, regenerated
MCP reference tables (`uv run tools/generate_mcp_docs.py`), the upgrade operator guide, the
licensing page (expand the stub), and the self-model showcase. Finish with a **link check +
generated-reference check**. (A coverage-semantics page already exists at
`docs/03-modeling/coverage-semantics.md` — cross-link, don't duplicate.)

---

## RESTART-GATED BATCH (needs an owner backend restart + `npm run dev`)

Confirm with the owner that the backend has been restarted (new code + re-read of the v2 guidance
extract) and a GUI dev server is available, then:

- **E2** deterministic screenshots — fail-closed capture harness (block all live
  `/api/assurance/**`, declared TLP:WHITE fixture routes only, fail on unexpected requests, temp
  workspace/store, assert the production connector is never constructed), the screenshot list from
  the plan above, a media provenance manifest, alt-text doc test, denylist scan + manual review.
- **G2** — crit-21b e2e trace-pattern GUI walk (Playwright) for the motivation-coverage viewpoint.
- **aibom G3** — live: mark an entity → derive → export (REST + MCP after a session restart).
- **security-signals GUI walk** — SecurityFindingsView / VulnerabilityImpact against synthetic
  fixtures. (NB: the live assurance store now holds fresh **0-finding** snapshots for both anchors
  after the dependency remediation — see below; seed synthetic findings for the walk.)
- **U0b live Docker smoke** — rebuild the CURRENT image, mount an old-format data volume (reuse the
  `tests/support/previous_release_deployment.py` shape), run the container, assert it reaches
  healthy (entrypoint upgrades before serving).

## WU-X1 — integrated closure (LAST)

Documentation truth-audit (every claim checked against real behaviour), §13.2 layered gates,
cross-document consistency, current live MCP stats, all gates over the integrated result.

---

## Carry-over context from the licensing/remediation session (2026-07-22)

- **License = MIT** (kept; commercial use + product integration intended). `THIRD-PARTY-NOTICES.md`
  is generated by `tools/generate_notices.py` from `licenses/{python,npm,native}.json`
  (`tools/check_licenses.py` regenerates + gates those). CI `licenses` job runs all three
  `--check`s. Regenerate + commit after any dependency change.
- **PlantUML stays GPLv3 1.2026.3** (arm's-length invocation + discharge) — decision pinned in
  `get_plantuml.py`; do NOT swap without re-opening that decision.
- **User-settable JRE**: `ARCH_JAVA` env (then `JAVA_HOME`, then `java`), resolved in
  `artifact_verifier_syntax.resolve_java_executable()` — env-only (application layer may not import
  config).
- **Dependency CVEs remediated to 0** (backend + frontend). Backend self-model entity
  `APP@1777293133.OYEmP1` (Architecture Backend) MCP-version attribute updated to `>=1.28.1`.
- **Live assurance signals re-ingested**: python→Architecture Backend (`APP@1777293133.OYEmP1`),
  npm→GUI Authoring Tool (`APP@1776149382.lmO0mp`); both active snapshots now 0 findings. The store
  is runtime-confidential (never committed).
- **Base-image hardening (done):** bumped the Docker base `slim-bookworm` → `slim-trixie`
  (Debian 13, OpenJDK 21) — verified rendering + venv in-container; OS CVEs 311 → 214 distinct.
  **Minimus** distroless evaluated and ruled out (multi-tool image needs apt-installed
  JRE+graphviz+git); Smetana (drop graphviz) deemed insufficient; JRE must stay. REMAINING future
  hardening (owner-gated): slimmer/custom JRE (jlink) to shed the JRE's cups/alsa closure; a
  rendering sidecar.
- **MCP ergonomics fix queued (restart-gated):** the assurance read surface forces out-of-band
  discovery of which architecture entities have security signals. Fix, using **role-functional
  naming** (the entity a snapshot attaches to = the *assessed entity*, NOT an "anchor" — that term
  is overloaded and unclear in output):
  · `assurance_security_stats` → add `assessed_entities: [{entity_id, entity_name, snapshot_id,
    bom_component_count, finding_count}]` and rename the scalar `anchors_with_active_snapshot` →
    `assessed_entity_count`. (`bom_component_count` disambiguates SBOM packages from the
    architecture application-*component*.) Output-only → backend restart suffices.
  · `assurance_list_vulnerabilities` → make `anchor_entity_id` optional (default = all assessed
    entities) and add `assessed_entity_id` + `assessed_entity_name` to each finding row. Input
    schema change → needs a Claude session restart. Persisted column `anchor_entity_id` may stay;
    map to the role-functional name at the read boundary. Exposure-filter the entity list.
- **Non-blocking:** Starlette 1.3 deprecates `httpx` with `starlette.testclient` (20 test
  warnings) — future test-client migration.
- **Workspace config (RESOLVED 2026-07-22):** the tracked `arch-workspace.yaml` is now
  ENG-ARCH-REPO-only; the full local config (with the private `TECHNOLOGY_ARCHITECTURE` Azure
  engagement) moved to the gitignored `arch-workspace.private.yaml`. **STILL TO REVIEW before
  publishing:** the tracked config's `enterprise.git.url` still points at a personal repo
  (`git@github.com:mbauer83/global-architecture-repository.git`) — a fresh public clone's arch-init
  would try to clone it. Decide whether that repo is a public companion (fine) or should default to
  a local empty enterprise repo (as CI scaffolds).
- **Assurance seed / fresh-install UX (done 2026-07-22):** `seed-assurance.json` regenerated from
  the self-model store (now includes the STPA-Sec analysis; signal_anchors preserved). Fresh
  install: `arch-assurance init && arch-assurance seed --with-signals` (defaults to
  seed-assurance.json). `arch-assurance export` now preserves authored `signal_anchors`.
- **STPA-Sec self-model (done 2026-07-22):** analysis `STPA@1784721732.pflr.3e4395` "PlantUML
  Preprocessor Untrusted-Input Disclosure" — valid, all STPA coverage checks pass, bound to the
  Architecture Backend; captures the PUML file-read finding + its two shipped constraints.

## Gates before every commit — ONE AT A TIME (concurrent heavy jobs hang the WSL2 host)

`uv run python -m pytest -q` · `uv run ruff check src/ tests/` · `uv run zuban check` · frontend
from `tools/gui/`: `npm run lint` (**~7-8 min**, type-aware; NEVER pipe through tail/grep — it
masks the exit code; use `lint:fast` during work, full `npm run lint` read in full at each stream
end) `&& npm run typecheck && npx vitest run`.

## House rules

Model writes ONLY via `artifact_*`/`assurance_*` MCP (dry_run first, `artifact_verify` after);
never `git add -A` (`git add` aborts the whole call on one bad pathspec — stage explicit, existing
paths); never commit `.arch-assurance/`; 350-line / 120-col source limits (`*.md` exempt); central
clock for timestamps; no phase/WU/§ refs in source or persistent docs (PLAN/TASKS/PROMPT exempt).
Backend code changes are inert until an owner backend restart; new/renamed MCP tools need a Claude
session restart — ASK proactively when a change must take effect for the next step.
