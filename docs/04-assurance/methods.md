# Assurance Methods

The assurance capability is **guidance-first**: each method has create-when / never-create
guidance on every entity type, and a method-completion verifier reports what a given analysis
still needs. The aim is to let a small team run a rigorous analysis without a resident
specialist.

&nbsp;

## STPA (System-Theoretic Process Analysis)

A top-down safety analysis built on the STAMP model. The flow follows the entity graph:

1. **Losses** — name the unacceptable, stakeholder-level outcomes. Everything traces back
   here.
2. **Hazards** — system states that, under worst-case conditions, can lead to a loss.
3. **Control structure** — model controllers and controlled processes as
   `control-structure-node`s, and the `control-action`s that flow between them. Binding a
   node to an architecture entity ties the analysis to the real system; an unbound node
   flags a modelling gap.
4. **Unsafe control actions (UCAs)** — for each control action, work the four STPA
   guidewords: *not provided*, *provided when it should not be*, *wrong timing*, *stopped too
   soon*. Each UCA references one control action and its controller.
5. **Loss scenarios** — the causal pathways explaining how a UCA leads to a hazard.
6. **Assurance constraints** — derived from scenarios; carry the safety/security framing,
   disposition, and integrity level. A constraint links to an ArchiMate requirement via a
   one-way `refines` edge rather than being merged into it.

&nbsp;

## STPA-Sec (security)

The same machinery, framed for security: a hazard is also a vulnerable system state
exploitable by a threat actor. The `concern_class` field distinguishes safety from security
on hazards and constraints, so a single control structure can carry both analyses.

&nbsp;

## CAST (Causal Analysis based on System Theory)

Retrospective analysis of an event that actually happened. An **incident** anchors a
reconstruction of the control structure *as it existed*, against a sealed analysis baseline.
UCAs and loss scenarios created in CAST are marked `mode=observed` (versus `hypothesized` for
STPA). **Corrective actions** capture recommendations and derive assurance constraints that
then enter the GRC lifecycle.

&nbsp;

## GRC (Governance, Risk & Compliance)

Two overlays on top of the safety/security model:

- **Risk** — an evaluation overlay that *assesses* a hazard or loss scenario and records a
  treatment (`mitigate` / `transfer` / `avoid` / `accept`). A risk entity is optional and can
  never be a precondition for a constraint, and `accept` is unavailable for safety
  concern-classes — this is where *safety is never subordinate to risk* is enforced.
- **Obligation** — a compliance instance: "does the system comply with requirement X of
  standard/regulation Y?" It cites a public framework code (for example `ISO26262:6-8`) while
  keeping status and evidence confidential in the assurance store.

&nbsp;

## Supply-chain signals

External supply-chain and cybersecurity signals are ingested as **signal
snapshots** anchored on architecture entities, then read back as component
inventories, vulnerability findings, and impact analysis. See
[Security signals](security-signals.md) for the full capability.

```bash
arch-assurance seed --with-signals  # bootstrap a store, then ingest for its declared anchors
uv run tools/ingest_security_signals.py --target python --anchor <entity-id>
arch-assurance export-aibom         # emit a CycloneDX 1.6 AI-BOM from component data
arch-assurance scan-ai-candidates   # heuristic scan of architecture entities for AI-BOM relevance
```

&nbsp;

## Working an analysis end to end

Every method runs through the same workflow surfaces:

1. **Create an analysis.** An *analysis* is the aggregate a method's content lives in.
   Create one from the method's wizard in the GUI, or with `assurance_create_analysis`
   (MCP). Each analysis names its method, so the completion checks know what "done"
   means for it.
2. **Work the guided wizard.** Each method has a guided flow — `/assurance/stpa`,
   `/assurance/cast`, `/assurance/grc`, `/assurance/gsn`, and
   `/assurance/supply-chain` — that walks the method's steps in order, creating the
   typed nodes and edges as you go, with the per-type guidance inline. The wizards
   author ordinary store content: anything they create is equally editable from the
   browse/detail views or via the MCP write tools.
3. **Review completeness.** The method-completion verifier (below) reports what the
   analysis still needs; the wizards surface the same checks as you work, and agents
   read them via `assurance_stpa_complete`, `assurance_cast_complete`,
   `assurance_grc_complete`, and `assurance_case_completeness` (GSN), plus
   `assurance_coverage` for how much of the architecture the analysis touches.
4. **Seal a baseline.** `/assurance/baselines` (GUI) or `assurance_seal_baseline`
   (MCP) seals the analysis state into the tamper-evident archive — the reference
   point a CAST reconstruction or a later review compares against.

&nbsp;

## Method-completion verification

Beyond per-write validation, the assurance verifier reports whether a method is *complete* —
for example, hazards without scenarios, UCAs without a referenced control action, or
constraints lacking an accountable party. This guidance is what makes the analysis tractable
without a method expert in the room, and it doubles as a checklist for review.

---

*Next: [Diagrams →](diagrams.md)*
