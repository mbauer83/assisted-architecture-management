# README + Documentation Rework — Status & Remaining Plan

Workstream: rework the README into a concise hub plus a multi-page `docs/` tree, with real
screenshots/diagrams, a self-describing assurance example, and supporting fixes. Branding
finalised to **Architectonic** (public slug `mbauer83/architectonic`).

## Done

- **README hub** + `docs/` tree: `01-motivation`, `02-installation`, `03-modeling/*`,
  `04-assurance/*`, `05-extensibility/*`, `reference/*`, `index`. Differentiation (vs
  low-structure tools *and* non-agent-native tools), unified motivation outcomes, and the
  `&nbsp;` section-spacing rhythm applied across all pages.
- **Media:** 13 GUI screenshots + 1 graph GIF (controlled 1440×900); 3 rendered assurance
  diagrams (control structure, bowtie, GSN) + a UCA-matrix markdown grid; sequence + activity
  diagrams. All `docs/**` links and image refs resolve.
- **Self-describing assurance example:** a complete STPA-Sec + GRC analysis of the confidential
  assurance store seeded into the encrypted store (17 nodes / 33 edges; STPA + GRC completeness
  profiles pass). Diagram artifacts authored under `diagram-catalog/diagrams/`.
- **Fixes (all test-green):** backend 422 (`app_bootstrap` runtime `Request` import);
  assurance `analysis-collection` axis (blank `/assurance`); assurance `unlock`/`lock`/`status`
  truthfulness + new `lock` command; C4 projection (component-level persons), navigation
  (drill-down scope resolved from `scoped-by` bindings + `entity-ids-used`), and element/person
  descriptions; `gen_id.py` removed; coverage config (`fail_under = 74`, statement = canonical).
- **CI/quality:** `.github/workflows/ci.yml` (python + frontend + e2e route-walk smoke);
  Playwright e2e harness; frontend lint debt cleared (eslint `--fix`).

## Phase C — remaining verification

- [x] Verified on the live self-model: **component-level persons** render at the context/container
      levels (`amp-containers` shows 5 actors + 3 roles); **drill-down** works for
      `backend-components` (scope = `architecture-backend` container). The
      `assurance-module-components` L3→L2 link was broken (its scope, the `assurance-module`
      group, had no container at L2). **Fixed**: aggregated the assurance module under the
      platform and re-projected `amp-containers`, which now renders it as a peer C4 container;
      the child/parent nav links resolve (commit `cac91e0`).
- [x] **Pre-existing follow-up (WIP fallout) — tool fixed:** `architecture-backend-components`
      pinned `APP@…yNhgdh.model-registry`, renamed to `module-catalog`, so re-projection failed
      (E301/E302). Root cause: `edit_diagram` merged stored + collected refs and never pruned
      dangling ones. Fixed in the writer (`diagram_edit` prunes refs absent from the verifier
      registry's both-repo id set; commit `d16fe6a`), so a re-projection now self-heals.
      **Applied** (commit `a897b1b`): post-restart auto-sync pruned the stale ref and re-bound
      the diagram to `module-catalog`; verifies clean, re-rendered. (Never blocked startup —
      validation checks types, not id existence.)
- [ ] Push → confirm the **CI** Actions badge goes green; connect **Codecov**
      (add `CODECOV_TOKEN`) so the coverage badge resolves. *(User action: push + token.)*
- [x] Markdown link/image check across README + `docs/**` (passes).
- [ ] GitHub render preview of README + docs pages. *(User action.)*
- [ ] Optional: `pngquant` pass over `docs/media/` (~50–65% smaller; needs `sudo apt-get install pngquant`).

## Product gaps — RESOLVED

1. **[DONE] Store-less boot tolerance.** `validate_repo_compatibility` now takes a complete-vocabulary
   registry; artifacts whose types belong to a *known-but-disabled* module (e.g. assurance diagrams
   with no store) warn + stay inert instead of aborting boot. Types no module declares still abort.
   (commit `6ca5e8b`; verified on the live self-model with the store suppressed.)
2. **[DONE] Assurance-context diagram viewer.** `/api/diagram-svg` is the gated viewer: confidential
   assurance diagrams render on demand in memory (never to disk, per G-f) only when the store is
   unlocked; locked → HTTP 403. The GUI (DiagramDetailView/EditDiagramView) already consumes this
   endpoint, so confidential diagrams display when unlocked. (commit for #14.) *Optional polish:* a
   dedicated "unlock to view" CTA on the 403 instead of the generic error surface.
3. **[DONE] Assurance-diagram source confidentiality (TLP-driven).** Confidentiality keys off TLP
   classification, not a blanket per-type rule. Publishable assurance diagrams (TLP:WHITE/GREEN)
   render + persist their source to the shared catalog; confidential ones (above the publishability
   ceiling, or unclassified) redirect their `.puml` to a gitignored `diagram-catalog/diagrams/confidential/`
   root and are withheld from disk rendering. `tlp` exposed on the create/edit MCP tools + GUI bodies;
   classification is store-independent; modelled in ENG-ARCH-REPO as a new requirement. (commits
   `138ddc7`, `a8ad92a`, `a152275`, `f26f363`, the #14 viewer commit, and the classification fix.)

### Restart-gated follow-ups for the public self-describing demo

- **Mark the example assurance diagrams TLP:GREEN.** The bundled bowtie/control-structure/GSN diagrams
  are currently unclassified → treated as confidential (won't render to disk; SVG viewer gates them).
  After a Claude **session restart** (to surface the new MCP `tlp` param), set `tlp: TLP:GREEN` on each
  via `artifact_edit_diagram` so they render + persist publicly, completing the fully-featured public
  assurance example. (Backend restart already done.)
- **Optional #14 frontend polish:** friendly "unlock the assurance store" CTA on a 403 from `/api/diagram-svg`.

## New public repo (later)

History-free push to `github.com/mbauer83/architectonic`; ensure temporary artifacts
(`overview.png`, `coverage.json`, `.coverage`, `.playwright-mcp/`, `plantuml.jar`,
`tools/gui/test-results/`) stay excluded.
