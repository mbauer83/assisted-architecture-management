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

- [ ] After backend restart: verify on the live self-model that C4 **drill-down** links render
      and **component-level persons** appear. Check whether `assurance-module-components`'s scope
      is a container in `amp-containers`; if not, that L3 won't link (a content/modelling gap to close).
- [ ] Push a branch → confirm the **CI** Actions badge goes green; connect **Codecov**
      (add `CODECOV_TOKEN`) so the coverage badge resolves.
- [x] Markdown link/image check across README + `docs/**` (passes).
- [ ] GitHub render preview of README + docs pages.
- [ ] Optional: `pngquant` pass over `docs/media/` (~50–65% smaller; needs `sudo apt-get install pngquant`).

## Product gaps (follow-ups, not built)

1. **Assurance-context diagram viewer.** Assurance diagrams render only via the generic
   architecture Diagrams view, and rule **G-f** blocks writing rendered assurance plaintext to
   disk — so the GUI cannot display them. Add an in-memory/gated assurance viewer (render on
   demand inside the confidential context).
2. **Assurance-diagram source confidentiality.** G-f gates the *rendered* output, but the
   source `.puml` (with diagram-owned content) still persists to the non-confidential git
   `diagram-catalog/`. For sensitive analyses, gate or redirect the source too.

## New public repo (later)

History-free push to `github.com/mbauer83/architectonic`; ensure temporary artifacts
(`overview.png`, `coverage.json`, `.coverage`, `.playwright-mcp/`, `plantuml.jar`,
`tools/gui/test-results/`) stay excluded.
