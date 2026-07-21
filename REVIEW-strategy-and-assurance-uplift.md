# Mechanical GO Confirmation — Strategy and Assurance Uplift

## Decision: GO

The `strategy-and-assurance-uplift` PLAN/TASKS/PROMPT trio is ready for
implementation.

The exact final closure conditions from the preceding review now pass. No
remaining finding requires another plan-adaptation cycle. This verdict confirms
planning readiness; implementation must still satisfy the work-unit gates,
acceptance criteria, FMEA controls, and owner checkpoints already specified in
the trio.

---

## Scope of this confirmation

This was the deliberately narrow mechanical confirmation requested by the
previous review. It rechecked:

1. the `DeploymentLayout` manifest and cloud-adapter source mapping;
2. Q11 and Part G vocabulary/contract consistency;
3. CLI exit-state separation;
4. rejected vocabulary, decision-ledger completeness, malformed text, and
   whitespace integrity.

Previously accepted architecture was not reopened.

---

## Closure-condition results

| Closure condition | Result | Confirmation |
|---|---|---|
| Exact `DeploymentLayout` contract | **PASS** | Host bind-source and process settings paths are distinct; the eight-row manifest is explicit; cloud variables and identity tuples are source-aligned. |
| Q11 and Part G agreement | **PASS** | Public above-WHITE handling remains blocking; WU-G3 uses authoritative-verdict and diagnostic-observation cells from the discriminated `PatternResult` union. |
| Disjoint exit states | **PASS** | Codes 1, 3, 20, and 21 have distinct states, precedence, write semantics, and Docker outcomes. |
| Document integrity | **PASS** | D1–D21 and Q1–Q12 are complete; rejected terms occur only in the rejection rule; malformed phrases are absent; `git diff --check` is clean. |

---

## Evidence

### 1. Host and container settings paths are no longer conflated

PLAN §9.2 now preserves the current meaning of:

- `ARCH_SETTINGS_FILE`: host-side Docker Compose bind-mount source;
- `ARCH_SETTINGS_PATH`: new process/container settings-document selector.

The Docker contract explicitly maps the selected host file onto
`/app/config/settings.yaml` and supplies that container-valid path to runtime,
CLI, and upgrade processing. The plan also warns against interpreting the
host-relative `ARCH_SETTINGS_FILE` value inside the container.

This closes the prior risk that upgrade and runtime would open different
settings documents.

### 2. Cloud adapter fields and identities are exact

The plan's cloud subtable contains exactly the `ARCH_S3_*` and
`ARCH_AZURE_*` variables present in:

- `src/infrastructure/assurance/_s3_worm_archive.py`;
- `src/infrastructure/assurance/_azure_blob_worm_archive.py`.

A set comparison found no missing or extra cloud variable.

Canonical identities are now explicit:

- S3: `(bucket, prefix)`;
- Azure: `(storage account, archive container, state container)`.

Operational settings, credential sources, reporting restrictions, preflight
checks, and deduplication behavior are distinguished. In particular, S3
namespaces in one bucket cannot collapse together, and Azure deployments cannot
silently share a mutable state container.

### 3. Q11 remains consistent

The three documents consistently require:

- only TLP:WHITE legacy rows may be administratively quarantined in the public
  SQLite file;
- any above-WHITE public row is a blocking preflight finding;
- the report exposes metadata, never the raw payload;
- resolution is secure import into the co-located store or verified purge;
- the public file remains `no_active_run` and has no refresh path;
- public and co-located migration fixtures are separate.

Q12's dogfooding scope does not weaken these shipped-product invariants. It
only permits migration or recreation of this project's non-public example
self-model and assurance data.

### 4. Part G has one result model

The active PLAN, TASKS, and PROMPT instructions use one row projection
containing a discriminated `PatternResult` union:

- authoritative patterns provide verdicts;
- diagnostic patterns provide observations.

WU-G3 now requires its preview to render one authoritative verdict cell and one
diagnostic observation cell. The obsolete undifferentiated “verdict DTO”
wording survives only as text rejected by the consistency sweep.

### 5. Upgrade exit outcomes are disjoint

The normative state table preserves existing automation while adding distinct
new failure outcomes:

- `0`: successful evaluation/apply as defined, including dry-run reporting;
- `1`: grandfathered repository-internal step errors;
- `3`: unresolved blocking migration;
- `20`: at least one complete target committed before a later target failed;
- `21`: infrastructure or credential failure before any target commit.

Code 20 has explicit precedence over code 1 when both conditions occur. The
table separates migration writes from pre-existing consistency-repair writes,
and Docker maps every non-success outcome to a halt with the report reason.

### 6. Mechanical integrity checks pass

The confirmation found:

- PLAN: 2,760 lines;
- TASKS: 559 lines;
- PROMPT: 190 lines;
- locked decisions: exactly D1 through D21;
- question ledger: exactly Q1 through Q12;
- cloud adapter variable-set difference: empty;
- stale/malformed phrase search: empty;
- `git diff --check` over the trio: clean.

The rejected-vocabulary hits for `step editing`, `one verdict DTO`,
`the verdict DTO`, and `block/quarantine` are confined to the rule that bans
those forms.

---

## Residual implementation risks

There are no residual **planning blockers**. The meaningful remaining risks are
implementation risks already controlled by the plan:

- faithfully transcribing the normative contracts without reviving superseded
  wording or behavior;
- keeping runtime, Docker, CLI, and upgrade discovery on the same resolved
  `DeploymentLayout` manifest;
- preserving atomicity, classification, omission, audit, and migration
  invariants through real-store and fault-injection tests;
- validating the new trace grammar and result projection identically across
  loader, GUI, REST, CSV, and upgrade detection;
- producing deterministic synthetic documentation media without a live
  assurance connector.

The dependency graph, boundary gates, local/regional/global criteria, FMEA
controls, fixture requirements, and definition of done provide sufficient
controls for these risks.

---

## Final assessment

**GO.**

The plan is architecturally sound, actionable, migration-complete, and
sufficiently specific for a fresh implementation session. The review/adaptation
cycle is closed. Further changes should arise only from implementation evidence
or an explicit new requirement—not from another pre-implementation review pass.
