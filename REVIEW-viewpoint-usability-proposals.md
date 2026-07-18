# Adversarial review — viewpoint usability proposals

## Verdict

The set has a sound overall direction, but is not execution-ready. Four Critical defects remain: P-17 applies the agreed realization rule to only one of three realization views; P-09 would publish false “honest-empty” copy and reintroduce forbidden catalog counts; P-02 preserves a demonstrated scope/query contradiction; and the FMEA cards relitigate an explicitly unresolved severity decision. Eight Major and four Moderate issues follow. The recurrent problem is a UI-level recommendation without the projection, migration, provenance, result-schema, or lifecycle contract needed to implement it correctly.

## Issues and opportunities

### R-01 · P-17 repairs only one realization view despite a family-wide owner rule · **Severity: Critical**

**Target:** P-17, realization re-scoping and gaps presentation.

**Claim:** P-17 implements anchored/unanchored semantics only for requirements-realization, leaving goal-realization and outcome-realization as unqualified all-model views. It therefore fails the fixed realization behavior for most of the affected family.

**Evidence:** I verified P-17 says “anchored → realization selected entities; unanchored → both realized/unrealized entities visibly separated,” but its implementation says only “Re-scope requirements-realization.” In src/ontologies/archimate_4/viewpoints.yaml lines 815–864, goal-realization has only a type filter (goal/outcome/principle/requirement), no realization predicate. gui-engine-pairs.csv PE1 rows report 352/352 for goal-realization and 731/731 for outcome-realization. I inspected PA-PA1-03-outcome-realization.png: it shows 242/242 and 461/461 in an unpartitioned dense graph. P-17 says “five personas” expected realization views; s1-scoring.md instead identifies PA1, PE1, PE3, PK1, with PC3 a layered-view trap.

**Reasoning:** The binding rule is semantic-family behavior, not a requirements-only UI. A requirements gap view cannot make goal/outcome views honest; the persona count also overstates the record.

**Counter-argument considered:** Broad standard realization overviews might be retained while only requirements gets gaps. That fails unless explicitly exempted, because the owner fixed the behavior and the outcome screenshot exhibits the same defect.

**Remediation:** Rewrite P-17 as a realization-family contract for goal-, outcome-, and requirements-realization: anchor resolution, stated direct/derived/both condition, and mutually exclusive realized/unrealized bands when unanchored. If broad views remain, give them explicit distinct slugs and owner approval. Test each member for union/exclusivity and anchored/unanchored screenshots. **Effort: M.**

### R-02 · P-09’s “honest-empty” copy is false, and P-12 contradicts the no-count rule · **Severity: Critical**

**Target:** P-09 and P-12, empty-state and catalog work.

**Claim:** P-09 proposes exact copy that contradicts capability-map’s result, while P-12 proposes a catalog count cache after the owner prohibited catalog overview counts.

**Evidence:** I ran read-only uv run python tools/usability_test/execution_probe.py capability-map. It returned 22 entities: 15 outcomes, one grouping, six junctions; it reports the drifted investment_level scale. P-09’s exact message says there are “22 structural elements (junctions/groupings) only.” HB-13-capability-map.png visibly contains OUT nodes plus JNA/JNO/GRP. viewpoints.yaml lines 1041–1065 includes junctions, grouping, outcome, capability, and resource. P-12 repeats “Catalog overview shows NO counts” but implements an “optional generation-keyed count cache.”

**Reasoning:** Target strategy elements can be empty by design, but 15 motivation outcomes are substantive content, not structural helpers. A cached display count is still a catalog count.

**Counter-argument considered:** “Structural” might mean non-target-domain and the cache might be internal. The supplied text is user-facing and false; “no counts” leaves no displayed-cache exception.

**Remediation:** Define target population plus target-domain, substantive-incidental, and helper classifications. Replace hard-coded copy with e.g. no strategy elements, while named incidental content remains visible; never call outcomes structural. Remove catalog count work from P-12. Test target-empty with incidental items, helpers only, target-present, active selection mode, and parameterized definitions. **Effort: S.**

### R-03 · P-02’s heuristic preserves a known contradiction and lacks safe migration · **Severity: Critical**

**Target:** P-02, selection_mode migration/validation.

**Claim:** Query-first inference selects the presently conflicting query in PA-A1, silently discards scope, and retains the failure. P-02 also overclaims that scope is never evaluated.

**Evidence:** oracle-flags.md PA-A1 records scope 5 and query 7. P-02 selects query when criteria are non-trivial. src/application/viewpoints/scope_query.py lines 18–22 use scope when query is absent; tests/application/viewpoints/test_scope_fallback.py lines 55–76 proves scope-only evaluation. P-02 says the engine “never evaluates scope.”

**Reasoning:** A non-trivial query is not evidence of intended semantics; raw evidence proves it differs. Implicit selection causes irreversible semantic loss and gives no path for divergent engagement, fixed, parameterized, or saved definitions.

**Counter-argument considered:** Query-first minimizes conversion. It fails on the very contradictory definitions under review; owner policy requires an explicit active alternative, not a guessed winner.

**Remediation:** Add a migration manifest for every definition source. Convert scope-only/query-only mechanically; mark dual-equivalent as mechanical; mark dual-divergent migration_required, showing both populations and requiring choice. Persist selection_mode and source digest. Validate contradictions only in active content. Test PA-A1, scope-only, dual-equivalent/divergent, parameterized and saved engagement recipes. **Effort: M.**

### R-04 · FMEA cards convert an unresolved severity anchor into settled priority · **Severity: Critical**

**Target:** P-01, P-03, P-05 evaluation/sequencing.

**Claim:** These cards state S8 and “highest priority” as settled despite the owner’s dual-reading adjudication.

**Evidence:** P-01 says F1 “S8/O9/D9 — highest priority”; P-03 says F3 S8/O5/D9; P-05 says F5 S8/O3/D9. Owner adjudications says F1/F3/F5 are S8–9 literal versus S7 primary-result reading and “High order provisional.” fmea-calibration.json owner_review_outcome says the same.

**Reasoning:** A numeric priority claim resolves the deliberately unresolved calibration and can distort ordering.

**Counter-argument considered:** The old S8 may be retained for traceability. Traceability is valid; “highest priority” is not.

**Remediation:** State “S8–9 literal / S7 primary-result; anchor unresolved,” remove priority claims, and order work by technical dependency and harm until the owner resolves the anchor. Add a consistency gate across register, cards, and release plan. **Effort: S.**

### R-05 · P-01 confuses anchor-relative modeled hops with a derived attribute · **Severity: Major**

**Target:** P-01, hop-distance repair.

**Claim:** P-01 assigns BFS styling to an impact-distance attribute, but the required number is relative to the selected anchor and witness chain, so it cannot generally be a global derived relationship attribute.

**Evidence:** I ran uv run python tools/usability_test/execution_probe.py element-dependents --param entity_id=gui. It still reports “up to 1 steps” but returns h2/h4 provenance. probe-PG3-dependents-gui.json has seven length-2 and three length-4 witnesses. The relevant YAML comment says per-node anchor distance is computed by exploration, while impact-distance derives from incident relationships. P-01 says to make impact-distance and BFS consume witness hops.

**Reasoning:** The same node can have different shortest distances under different anchors. Reusing impact-distance will be intermittently plausible but wrong and violates modeled-hop semantics.

**Counter-argument considered:** It could mean a new contextual attribute. The card names the existing attribute and omits anchor/tie/direct-edge semantics.

**Remediation:** Require a projection-time anchor_modeled_distance: anchor 0, direct 1, otherwise minimum ordered witness length. Define ties/no-witness handling and bind styling only to it. Test rings 0/1/2/4 and multiple witnesses. **Effort: M.**

### R-06 · P-05 promises a traversal condition the predicate model cannot express · **Severity: Major**

**Target:** P-05, connection-predicate traversal.

**Claim:** P-05 treats direct/indirect/both as a field migration, but IncidentConnectionCondition only supports direct/derived; it also migrates all legacy predicates to both without evidence.

**Evidence:** src/domain/viewpoint_criteria.py lines 20–21 and 94–107 define IncidentConnectionCondition direct/derived; criteria_parsing.py lines 79–82 rejects other values. A different ConnectionSelection enum has direct/derived/both (viewpoint_criteria.py lines 110–121). viewpoint_criteria_evaluation.py lines 180–226 evaluates derived incidents separately. P-05 says direct/indirect/both and “migrate existing predicates to both.”

**Reasoning:** A selector without evaluator union semantics may reject or collapse both. Blanket broadening changes negative predicates and saved recipes, contrary to per-condition owner policy.

**Counter-argument considered:** Both could be a simple union. It still needs union-before-negation, de-duplication, serialization compatibility, and a justified legacy choice.

**Remediation:** Add traversal=both to IncidentConnectionCondition as union of direct and derived before negation, deduplicated by connection identity with provenance retained. Preserve old direct/derived values; resolve legacy absent values from old schema/default or require review. Test positive/negated predicates, duplicates, saved parameterized recipes, and P-17 conditions. **Effort: M.**

### R-07 · P-16 lacks a lossless aggregation contract · **Severity: Major**

**Target:** P-16, scale-adaptive presentation.

**Claim:** P-16’s only acceptance test is equal counts. It omits aggregate identity, homogeneity rules, drill-down, and whether aggregation happens before result limits, permitting semantic loss.

**Evidence:** P-16 requires server aggregation but accepts it when aggregate counts “equal the flat result.” probe-PE-A1-limit10.json returns 10/242 entities and 10/461 connections; the limit100 probe returns 100/242 and 120/461. viewpoint_projection.py lines 34–47 already carries connection provenance. oracle-flags.md records 1,318 motivation-tech support relationships versus 778 raw relationships.

**Reasoning:** Equal counts allow merges of direct/derived, type, direction, or uncertain provenance. Aggregating after limiting is not a faithful overview; P-06 drilldown and P-08 also depend on the contract.

**Counter-argument considered:** Detailed aggregation can wait for implementation. Grouping keys, limit order, and drilldown are semantics, not cosmetic details.

**Remediation:** Define AggregateItem: immutable group key including type, direction, provenance/certainty and visual inputs; member count; stable member reference. Aggregate complete projection before presentation limits. Distinguish aggregate/flat table/export modes. Test membership conservation, no mixed direct/derived/type group, limit10, and P-06 drilldown. **Effort: L.**

### R-08 · P-03/P-11 request result and export data that does not exist · **Severity: Major**

**Target:** P-03 and P-11, table/CSV/export.

**Claim:** Status, version, last_updated, and complete exports are proposed without a result schema or snapshot contract that supplies them.

**Evidence:** probe-PE-A1.json entity items expose id, name, type, specialization_slugs, group, membership. execution_result.py lines 13–25 fixes the same EntityItemSummary shape. oracle-flags.md records missing status. P-03 requests status/version/last_updated and says index includes last_updated; inspected SQLite schema has version/status but no last_updated. P-11 permits client CSV but does not define complete versus visible-page output.

**Reasoning:** A client join produces N+1 reads and inconsistent snapshots; visible-page CSV can look complete while omitting most 242-item results.

**Counter-argument considered:** The frontend can fetch missing metadata. That is an untested second contract and does not satisfy a result table/export guarantee.

**Remediation:** Add server-resolved typed column_values with explicit missing values. Decide whether last_updated exists; remove it or persist defined semantics. Define either server-generated full generation-pinned export or prominently labeled page export. Test fields/missingness, 242-item completeness, aggregate/flat mode, and generation change during export. **Effort: M.**

### R-09 · SM-01–03 misread motivation evidence and prescribe an infeasible type edit · **Severity: Major**

**Target:** SM-01, SM-02, SM-03.

**Claim:** The cards call valid assessment-mediated driver-to-goal paths a missing stakeholder-driver rule, misstate counts/types, and direct a type conversion unavailable in the authoring API.

**Evidence:** Read-only artifact queries show each assurance stakeholder has two goal associations and no driver association. oracle-data-2.json PE3 records five drivers, not SM-02’s 3/6, and seven driver_goal_edges of archimate-influence, not SM-03’s symmetric associations. It records paths expanding demand → assessment → First-class assurance, GRC gap → assessment → Lower barrier, and AI risk → assessments → goals. SM-02 says direct only if no assessment path, then says ×3 direct. Modeling guidance says goals link stakeholder and driver or assessment; external drivers need not link stakeholders, and connection editing cannot change type.

**Reasoning:** The proposals duplicate legitimate mediation while mislabeling it nonconformant; the prescribed API action is impossible.

**Counter-argument considered:** Direct links may improve readability. That needs a new convention and per-driver rationale, not a claimed correction.

**Remediation:** Merge SM-01–03 into a motivation-convention review. Decide whether assessment mediation is accepted; list each of five drivers’ retained path and any justified direct influence. Correct counts/types. Replace type conversion with remove/recreate instructions including endpoints, type, provenance, and approval. **Effort: S.**

### R-10 · SM-05 has no disposition for 23 conformance exceptions · **Severity: Major**

**Target:** SM-05, conformance cleanup.

**Claim:** It correctly rejects parent inheritance and adopts forward structural derivation, but still says exceptions are “governed via parent requirements” and does not classify each of 27 candidates.

**Evidence:** SM-05 says parent inheritance rescues zero, reports 27 candidates/23 exceptions, and uses parent-governance wording. Owner fixed forward composition/aggregation/assignment/realization derivation. P-05 can change saved recipe traversal but SM-05 specifies no re-run.

**Reasoning:** Parent governance is not a forward structural proof. Without exclusive statuses, every scan leaves unactionable permanent debt.

**Counter-argument considered:** A card need not enumerate fixes. It must at least define worklist fields and completion criteria.

**Remediation:** Add a register where every candidate is conforming with ordered witness, repair-needed with named relationship, waived with owner/rationale/expiry, or false-positive with rule correction. Re-run after P-05 and assert exact partition of 27. **Effort: M.**

### R-11 · P-13 promises pins/forks but provides only a weak Save As label · **Severity: Major**

**Target:** P-13, lineage.

**Claim:** forked_from slug/version cannot identify immutable definition content, model generation, parameters, or result snapshot.

**Evidence:** P-13 implements forked_from slug/version, Save As, badge. viewpoint_projection.py lines 49–56 exposes stale_pin. A valid read-only from-blank artifact result has no lineage object. The proposal does not assert immutable versions or content digests.

**Reasoning:** A mutable version label cannot establish reproducibility; P-07 links do not fix that.

**Counter-argument considered:** Slug/version may be immutable. The proposal does not specify or test it, and it still omits execution context.

**Remediation:** Add lineage on all authoring routes: parent immutable digest, slug/version, creation generation, normalized parameters, optional result digest. Make GUI/MCP use one service and test later revision, stale versus reproducible pin. **Effort: M.**

### R-12 · F11, F20, F31, H3 and part of F16 have no accountable owner · **Severity: Major**

**Target:** coverage gap (no proposal).

**Claim:** Missing read-only visibility, discard/cancel protection, grouping visibility, grammar correction, and a creation route have no explicit proposal/disposition.

**Evidence:** REPORT-viewpoint-usability-stress-test.md records F11 read-only mode, F16 grouping visibility, F20 discard/no cancel, F31 “an connection,” H3 no create route. Logs HA-6/HB-8 record read-only; HA-10/HB-7 discard/no-cancel; PG-A1 has four group-by clusters without visible grouping; HA-28 records grammar. No proposal owns F11/F20/F31/H3. P-07 covers addressability, not creation or unsaved-change handling.

**Reasoning:** Deferral can be valid, but unowned findings vanish from delivery and have no acceptance test.

**Counter-argument considered:** They may be implicit editor polish. Independent observed task failures require explicit ownership.

**Remediation:** Add a disposition row for every F/H: proposal, accepted risk, deferred date/rationale, or closed. Add cards/P-07 amendments for persistent read-only indicator, cancel/keep-editing confirmation, group labels/boundaries, copy fix, and permission-aware create entry. Test GUI/MCP as applicable. **Effort: M.**

### R-13 · P-04 turns healthy zero-gap rules into warnings · **Severity: Moderate**

**Target:** P-04, styling diagnostics.

**Claim:** Warning on every zero-match style rule will flag healthy negated gap rules, including P-17’s no-gap state, and ignores precedence/shadowing.

**Evidence:** P-04 proposes warning when a style rule matches zero. P-17 requires gap rules whose correct healthy result is zero. The report concerns unknowable/inactive styles, not every empty selector.

**Reasoning:** Zero matches can mean error, expected-empty, or shadowed. Blanket warnings create normal-state noise.

**Counter-argument considered:** Advisory warnings maximize visibility. Noise makes diagnostics less credible.

**Remediation:** Define unresolvable, expected-empty, shadowed, applied; warn only unresolvable/shadowed by default. Include selection mode/count and test healthy no-gap plus precedence overlap. **Effort: S.**

### R-14 · SM-08 makes ordinary save look like promotion · **Severity: Moderate**

**Target:** SM-08, lifecycle/status.

**Claim:** Conflating save with review/promotion risks activating unreviewed drafts.

**Evidence:** SM-08 says artifact_save_changes/review/promotion will make active maintenance. interfaces-and-mcp.md line 59 says save commits changes. entity_edit.py lines 315–347 has explicit draft → active → deprecated transitions. Oracle status data is 343 draft, nine active.

**Reasoning:** Owner required bulk-correct active then workflow maintenance, not silent activation through edit.

**Counter-argument considered:** A reviewer may promote after save. The card must name that separate actor/transition.

**Remediation:** Save preserves status; reviewed explicit promotion activates; deprecation separate; bulk correction auditable. Test draft save, rejected/approved promotion, rollback/audit. **Effort: S.**

### R-15 · P-07 deep links re-execute live state, not historical evidence · **Severity: Moderate**

**Target:** P-07, URL-addressable results.

**Claim:** A URL with slug/parameters alone silently changes result when model/definition changes.

**Evidence:** The report addendum records generation drift. P-07 has no generation, definition digest, or result identity. projection code exposes stale_pin.

**Reasoning:** Navigation and evidence reproduction differ; calling a live URL reproducible undermines P-13.

**Counter-argument considered:** Live links are useful and pins costly. Keep live links, but label them and offer optional verified reference.

**Remediation:** Specify live links (slug, normalized parameters, selection_mode) and verified links (definition digest, model generation, result digest/retention). On mismatch show re-executed/different generation. Test changed model/definition, expiry, parameters, forks. **Effort: M.**

### R-16 · P-06 calls unordered provenance IDs a witness chain · **Severity: Moderate**

**Target:** P-06, evidence inspection.

**Claim:** P-06 requires a witness chain but not ordered/directed steps. Raw via_connection_ids are not guaranteed source-to-target order.

**Evidence:** docs/reference/viewpoints-schema.md says via connection IDs are not guaranteed source-to-target and consuming code reconstructs them. P-06 requests witness-chain links without reconstruction/direction/tie semantics. The dependents probe includes multi-hop provenance.

**Reasoning:** IDs establish membership, not a readable path; incorrect ordering defeats modeled-hop validation.

**Counter-argument considered:** Some backend consumers may reconstruct. The schema says it is not contractual, so P-06 must require it.

**Remediation:** Projection emits ordered witness_steps with connection_id, source, target, relationship type, direction, hop index; define shortest deterministic tie-break and alternates. Test reversed stored IDs render correctly. **Effort: M.**

## Coverage matrix appendix

| Finding | Proposal trace | Disposition |
|---|---|---|
| F1 | P-01 | R-04, R-05 |
| F2 | P-02 | R-03 |
| F3 | P-03 | R-04, R-08 |
| F4 | P-04 | R-13 |
| F5 | P-05 | R-04, R-06 |
| F6 | P-06 | R-16 |
| F7 | P-07 | R-15 |
| F8 | P-08 | P-16 interaction in R-07 |
| F9 | P-09 | R-02 |
| F10 | P-10 | no material defect found |
| F11 | — | orphan; R-12 |
| F12 | P-11 | R-08 |
| F13 | P-12 | R-02 |
| F14 | P-13 | R-11 |
| F15 | P-14 | no material defect found |
| F16 | P-07 only by implication | partial orphan; R-12 |
| F17 | P-15 | no material defect found |
| F18 | P-16 | R-07 |
| F19 | P-17 | R-01 |
| F20 | — | orphan; R-12 |
| F21–F23 | P-02/P-05/P-17 | R-03, R-06, R-01 |
| F24–F29 | SM-01–SM-05 | R-09, R-10 |
| F30 | SM-06 | no material defect found |
| F31 | — | orphan; R-12 |
| F32–F34 | SM-07/SM-08 | R-14 for status; remainder on record |
| H1 | P-02/P-05 | R-03, R-06 |
| H2 | P-01/P-06/P-16 | R-05, R-07, R-16 |
| H3 | — | orphan; R-12 |
| H4 | P-13 | R-11 |

Proposal-to-evidence trace: P-01→F1/dependents probe; P-02→F2/H1/PA-A1 oracle; P-03→F3/PE-A1 oracle; P-04→F4; P-05→F5/H1/criterion code; P-06→F6/provenance schema; P-07→F7/F16/addendum; P-08→F8; P-09→F9/capability probe; P-10→F10; P-11→F12/result schema; P-12→F13/owner rule; P-13→F14/H4; P-14→F15; P-15→F17; P-16→F18/limit probes; P-17→F19/F21–23; SM-01–03→F24–26/oracle data; SM-04→F27; SM-05→F28–29; SM-06→F30; SM-07→F32/F34; SM-08→F33. Unowned rows are the two-way-trace orphans.

## What I could not verify

No browser or mutating tool was used. I verified live capability-map and dependents probes; the backend was available. Persona narratives, several screenshot labels, FMEA calibration, and oracle adjudications are taken on record except where raw probes/logs/schema/source are named above. I did not run every probe variant, inspect every PNG, or full-scan raw model files; SM-01–03 model facts were checked through read-only artifact queries and oracle data. P-08, P-10, P-14, P-15, SM-04, SM-06, and SM-07 are not endorsements: no significant independently supportable defect emerged in this pass.
