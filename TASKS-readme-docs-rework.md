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

## Product gaps (follow-ups, not built)

1. **Store-less boot fails on optional-module artifacts.** A clone *without* a configured
   confidential store cannot boot the backend if the repo contains assurance diagrams: their
   source files persist to the non-confidential git `diagram-catalog/` (see gap 3), but their
   diagram/connection/entity types are unknown when the assurance module is disabled, so
   startup repo-compatibility validation aborts ("Unknown diagram type 'bowtie'", …). The
   principled fix is **validation tolerance**: treat artifacts whose types belong to a
   *known-but-disabled* optional module as inert (warn + hide) instead of refusing startup —
   compare repo types against the complete vocabulary (`build_module_registry(complete_vocabulary=True)`)
   and only abort for types no module declares. (Worked around in CI by provisioning an empty
   store; the underlying product behaviour still needs fixing.)
2. **Assurance-context diagram viewer.** Assurance diagrams render only via the generic
   architecture Diagrams view, and rule **G-f** blocks writing rendered assurance plaintext to
   disk — so the GUI cannot display them. Add an in-memory/gated assurance viewer (render on
   demand inside the confidential context).
3. **Assurance-diagram source confidentiality.** G-f gates the *rendered* output, but the
   source `.puml` (with diagram-owned content) still persists to the non-confidential git
   `diagram-catalog/`. For sensitive analyses, gate or redirect the source too.

## New public repo (later)

History-free push to `github.com/mbauer83/architectonic`; ensure temporary artifacts
(`overview.png`, `coverage.json`, `.coverage`, `.playwright-mcp/`, `plantuml.jar`,
`tools/gui/test-results/`) stay excluded.
