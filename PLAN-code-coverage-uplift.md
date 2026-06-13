# PLAN — Code-Coverage Uplift to >85%

Status: draft · Owner: engineering · Created: 2026-06-09
Baseline at authoring: **66.6%** combined line+branch (`pytest --cov`), 1728 tests green.
Target: **>85%** combined, enforced by a ratcheting `fail_under`.

## Motivation

Coverage was just introduced (`pytest-cov`, `[tool.coverage.*]` in `pyproject.toml`,
`fail_under = 65`). 66.6% is the honest starting point. The gap to 85% is ~5,750
covered units (lines+branches) out of ~10,400 currently missing. This plan closes
the **cheapest, most safety-relevant** half of that gap first, so each hour of test
work protects the most central code.

**Prioritise by centrality × gap, not by gap alone.** A 0%-covered network installer
matters far less than a 63%-covered write path. Tiers below are ordered by how much a
defect there would cost (data loss, corruption, security) and how many callers depend
on the code.

## Locked decisions

1. **Measurement integrity was verified before planning** (Phase 0, done). The numbers
   in this plan are trustworthy: there is no subprocess coverage loss and thread-run code
   is captured (see Phase 0 for the evidence). The low-coverage modules are therefore
   *genuinely untested*, not mis-measured — so the prioritised gaps below are real.
2. **Coverage stays opt-in** in the default run (no `--cov` in `addopts`); the
   quality-gate command remains fast. CI and milestone checks pass `--cov`.
3. **`fail_under` ratchets up, never down**: 65 → 72 → 78 → 82 → 85 as phases land.
   A phase is "done" only when the ratchet is raised and green.
4. **Test organisation follows project convention**: one test file per
   component/use-case (see existing `tests/` layout), not omnibus files.
5. **`# pragma: no cover` is allowed only with a one-line justification** and only for
   genuinely unreachable-in-test code (network/OS package installers, hardware probes).
   Every use is reviewed; it is not a coverage-number shortcut.
6. **Run tests with `uv sync --all-groups`** — the plain `uv sync` prunes the `gui`
   group (fastapi) and breaks collection.

## Baseline by criticality tier (authoring snapshot)

| Tier | Component | stmts | cov% | missing (ln+br) |
|------|-----------|------:|-----:|----------------:|
| 1 | write-path (`write/artifact_write/*`) | 3641 | 63.2 | 1970 |
| 1 | verify-path (`application/verification/*`) | 2144 | 80.7 | 695 |
| 1 | confidential/assurance (`infrastructure/assurance/*`) | 2358 | 77.0 | 763 |
| 2 | index/git/backend | 2471 | 70.5 | 1025 |
| 2 | bootstrap/startup | 498 | 42.2 | 367 |
| 3 | application-core | 1945 | 73.1 | 824 |
| 3 | domain | 1367 | 90.4 | 254 |
| 3 | config | 288 | 81.9 | 78 |
| 4 | mcp-surface | 2583 | 66.8 | 1236 |
| 4 | gui-routers | 2049 | 47.7 | 1428 |
| 5 | render/diagram | 2905 | 87.9 | 607 |
| 5 | ontologies | 287 | 93.0 | 27 |
| 6 | cli | 596 | **0.0** | 708 |
| 6 | workspace | 582 | 59.1 | 364 |

Regenerate this table anytime with:
```
uv run pytest --cov --cov-report=json:coverage.json -q
python3 - <<'PY'  # tier aggregation script lives in this plan's git history
PY
```

---

## Phase 0 — Measurement integrity (DONE — verified, not assumed)

**Why first:** writing tests against untrustworthy measurement wastes effort. Before
planning the uplift, the measurement setup was audited and proven sound. Findings:

- **No subprocess coverage loss.** Every test that calls `subprocess`/`Popen` spawns
  **git** or **node**, uses a **mocked** `subprocess.run`, or merely **asserts on a
  constructed command string** (e.g. `arch-backend --port …` is checked, never executed).
  Grep for `sys.executable | python -m | console-scripts` in `tests/` returns only
  assertions and docstrings. ⇒ No `parallel`/`COVERAGE_PROCESS_START` machinery is needed;
  adding it would have solved a non-problem.
- **Thread coverage is captured.** Thread-run modules report real numbers
  (`_rwlock.py` 94.7%, `coordination.py` 73.6%, `write_queue.py` 67.6%); the rwlock figure
  is only reachable if thread lines are traced. ⇒ No `concurrency = ["thread"]` needed.
- **Config is correct.** `source = ["src"]` reports never-imported files as 0% (so genuine
  gaps surface rather than vanish); branch coverage on; `exclude_also` audited down to four
  justified patterns (TYPE_CHECKING / abstractmethod / `__main__` guard / bare-line `...`).
- **Conclusion:** the 66.6% baseline is honest. Modules at 0% (`group_ops`,
  `cascade_delete`, `_cascade_helpers`, `_group_fs`, the entire CLI tier) are **genuinely
  untested** and flow straight into Phase 1+. No code in `src/` was changed for measurement.

**Re-verify cheaply** if the test suite later starts launching real Python children:
```
grep -rnE "sys\.executable|python3? -m|Popen\(" tests/ | grep -vE "git|node|assert|==|patch|mock"
```
If that yields real spawns, only then add `parallel = true` + a `COVERAGE_PROCESS_START`
startup hook.

---

## Phase 1 — Write-path (most critical, biggest tier-1 gap: 1970 missing)

Corruption or a missing rollback here loses user model data. Highest priority.

Target each file to **≥90%**. Genuinely-untested first:

- **`group_ops.py` (0%)** + **`_group_fs.py` (0%)** — unit-test every action of
  `group_op` dispatch (create/rename/archive/unarchive/delete/update) per axis
  (model-project, diagram-collection, document-collection), incl. the confirm-guard and
  uncategorized-protection error paths. Use a tmp repo fixture.
- **`cascade_delete.py` (0%)** + **`_cascade_helpers.py` (0%)** — preflight scans
  (owned/foreign connections, foreign diagrams, blocking docs), the apply path with
  rollback-on-verify-failure, and `apply_blocked_by`. Assert git staging via a tmp git repo.
- **`connection_edit.py` (26%)**, **`matrix.py` (37%)**, **`materialization.py` (46%)** —
  cover the `_UNSET`-merge branches, cardinality edits, and dry-run vs write vs
  rollback. Property-test connection-id round-tripping with `hypothesis`.
- **`_promote_groups.py` (11%)**, **`promote_execute.py` (64%)**, **`_promote_file_ops.py`
  (61%)**, **`_sync_helpers.py` (72%)** — promotion conflict resolutions
  (accept-engagement / accept-enterprise / merge), GAR replacement, and the
  verify-then-rollback branch. Reuse the two-repo fixture from `test_two_repo_and_grf`.

**Technique:** prefer one new `tests/.../test_<module>.py` per module; drive through the
public `artifact_write_ops` facade where possible so router/MCP callers are covered too.
**Exit:** write-path tier ≥88%; `fail_under` → 75.

---

## Phase 2 — Verify-path (correctness gate; 695 missing)

The verifier is the integrity guarantee; weak coverage here lets bad data through.

- **`_verifier_serde.py` (9%)** — serialize/deserialize round-trips for every record
  kind; ideal for `hypothesis` property tests (parse∘format == identity).
- **`artifact_verifier_syntax.py` (25%)** — PlantUML syntax batch checks: valid, invalid,
  and the graphviz-missing fallback. Stub the external `dot`/PlantUML call so it runs
  without the jar.
- **`artifact_verifier_incremental.py` (73%)** and **`artifact_verifier.py` (77%)** —
  the incremental re-verify diff paths and the per-rule dispatch branches not yet hit.

**Exit:** verify-path tier ≥90%; `fail_under` → 78.

---

## Phase 3 — Confidential / assurance (security-critical; 763 missing)

Defects risk leaking or losing protected assurance data.

- **`_credential_store.py` (33%)** — key derivation, set/get/delete, and the
  wrong-key / missing-key error branches (use a tmp keyring backend; never real secrets).
- **`_encrypted_private_git_store.py` (69%)**, **`_private_git_store.py`**,
  **`_encrypted_git_archive.py`** — lock/unlock, commit, and tamper/parse-failure paths.
- **WORM archives** — `_worm_archive`/`_s3_worm_archive` with `moto` (already a dep);
  **`_azure_blob_worm_archive.py` (0%)** behind an availability skip if the azure extra
  is absent. Mark cloud-SDK-only branches `# pragma: no cover` with justification when a
  local fake is infeasible.

**Exit:** assurance tier ≥88%; `fail_under` stays 78 (counts toward Phase 4 raise).

---

## Phase 4 — Index / git / backend + bootstrap (1392 missing)

Central infrastructure. These are real gaps (Phase 0 confirmed nothing here is merely
mis-measured), so each needs genuine tests.

- **`git_sync.py` (13%)** — engagement/enterprise sync state machine: clean/dirty
  transitions, ahead/behind pull decisions, conflict-abort, auto-unblock. Drive against a
  tmp git repo with a fake remote; no network.
- **`enterprise_git_ops.py` (26%)**, **`git_auth.py` (42%)** — credential resolution and
  push/clone command construction (assert argv, don't hit the network).
- **`artifact_index` / `backend_*`** — several are already 76–88%; fill the residual
  branch gaps in `_service_incremental`, `_sqlite_queries`, `backend_state`,
  `backend_process` (the process-matching predicates are heavily asserted but some
  branches remain).
- **Bootstrap installers** (`get_diagram_runtime`, `get_plantuml`, `check_diagram_runtime`,
  all 0%): test the **pure** parts (version parsing, plan selection, the
  `_GRAPHVIZ_INSTALL_PLANS` lookup) directly; wrap the actual `subprocess.run`/download
  calls behind `# pragma: no cover` with justification — exercising real package managers
  in CI is out of scope and low-value.

**Exit:** index/git/backend tier ≥85%, bootstrap pure-logic ≥80%; `fail_under` → 82.

---

## Phase 5 — Surfaces: mcp + gui routers (2664 missing, high-leverage fixture)

- **Build one shared ASGI `TestClient` fixture** (httpx `ASGITransport` against the
  FastAPI app from `arch_backend_app._build_app`). Only `test_http_concurrent` uses the
  HTTP layer today. A reusable client lets router tests cover gui-routers (47.7%) **and
  transitively** exercise write-path/promote/group code through the real call chain.
- Cover each router's happy path + primary error (404/validation/boundary) per resource
  (entities, connections, diagrams, documents, groups, promote, sync, admin, assurance).
- MCP surface (66.8%): test tool registration and the read/write tool handlers via the
  in-process server, not subprocess.

**Exit:** gui-routers ≥80%, mcp-surface ≥80%; `fail_under` → 84.

---

## Phase 6 — CLI, workspace, render/diagram (remainder to clear 85%)

- **CLI tier (0%, 596 stmts)** — argument parsing and command dispatch for
  `arch-write-cli`, `arch-assurance`, query CLI. Invoke `main(argv=[...])` **in-process**
  (not via subprocess) so coverage attributes correctly; assert on captured stdout/exit.
- **`workspace` (59%)** — `workspace_init`, `switch_engagement` resolution branches.
  Their git interactions can be driven against a tmp git repo (the existing tests already
  do this with real `git` subprocesses, which is fine — git is external).
- **render/diagram (88%)** — top up residual branches in the activity/sequence/c4
  renderers; these are near target already.

**Exit:** overall **>85%**; set the final gate so coverage runs **fail below 85%** —
`[tool.coverage.report] fail_under = 85` in `pyproject.toml`. Any `--cov` run (local or CI)
now exits non-zero under 85%. This is the terminal ratchet: it never drops again.

---

## Execution rules (per phase)

1. `uv sync --all-groups` first.
2. Write tests; keep one file per component.
3. `uv run pytest --cov --cov-report=term-missing -q` — read the **missing-line** column
   to target branches precisely; don't write blind tests.
4. Run `ruff check src/ tests/` is **not** required for tests, but `ruff check` on any
   touched `src/` must stay clean; `uv run zuban check` green.
5. Raise `fail_under` to the new floor; commit with the coverage delta in the message.
6. Never lower a floor; never `# pragma: no cover` without a justification comment.

## Definition of done

- **The coverage gate fails the build below 85%**: `[tool.coverage.report] fail_under = 85`
  is committed, and a `--cov` run is part of CI so any drop under 85% exits non-zero.
- Combined coverage **>85%** and green at that gate.
- No tier-1 (write / verify / confidential) file below 85%.
- Every `# pragma: no cover` carries a one-line reason and was reviewed.
- `coverage.json` / `htmlcov/` remain git-ignored.
