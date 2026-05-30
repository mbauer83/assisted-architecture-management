# Formalization We Will Actually Implement

Companion to `PLAN-meta-ontology-v2.md`, "Categorical/Formalization Research Synthesis".

That section surveys a large body of category theory. This document answers the practical
question: **which of it do we formalize, because each piece yields an executable check that
makes our design precise and lets us verify soundness — and which stays vocabulary.**

Guiding rule: we formalize a concept only when it produces (a) a precise definition that
removes ambiguity from the plan, and (b) a predicate we implement as a Python verifier rule
or a property-based test. We are **not** building a theorem prover. The "model-check
harness" is `pytest` + `hypothesis` over the registry and over diagram/model instances.

There are exactly four formalizations worth implementing. They line up 1:1 with work
already in the phase plans, so formalizing them costs little beyond writing the definitions
and the tests down precisely.

---

## F1. Signature + instance typing (a fibration)

**Definition.** A module signature is
`Σ = (E, C, K, ε, B, S)` where `E` = entity types, `C` = connection types, `K` = classes,
`ε: C → ℘(E) × ℘(E)` = endpoint constraints (the `permitted_relationships`), `B` = binding
target forms, `S` = derivation strategies. The registry is a finite family `{Σ_i}` with
globally-unique type names, so the combined signature `Σ*` is their disjoint union with
identification only at declared bridges (F2). Every artifact (entity, connection, binding,
diagram element) carries a typing map `p: Instances → Σ*`.

**Soundness predicate (implemented).** `p` is total: every indexed artifact's type symbol
exists in `Σ*`. This is exactly `startup_validation.py` today; F1 just states it as the
fibration property "every instance lives in the fiber over its type." Test: index a repo
with an unknown type ⇒ startup aborts with the offending type + example id.

**Why this and not "institutions in full":** we need typedness and class membership, which
is the base category + fibers. We do not need a satisfaction relation over a logic; our
"satisfaction" is just the verifier rules (F3), implemented directly.

---

## F2. Bridge morphism with class preservation

**Definition.** A bridge is a partial map on type symbols `β: Σ_from ⇀ ℘(Σ_to)` decorated
with a set of preserved classes. The preservation **law**:
`∀ c ∈ preserves_classes, ∀ t ∈ β(x): c ∈ classes(t)`.

**Soundness predicate (implemented).** The Phase 4 §3.2 *minimum bridge check*: existence
of `from`/`to` types, the preservation law, admissible correspondence kind, and agreement
with `allowed_bindings` (a descent-style overlap check between two declarations of the same
fact). This is the first executable slice, not full coherence — endpoint compatibility,
cardinality/property preservation, directionality, and connection-type bridges are deferred
(Phase 4 §3.3). Test: a coherent bridge fixture passes; a bridge claiming a class its
targets lack aborts startup.

**Why this and not "general functors / colimit module merge":** a bridge is a span/partial
map with a preservation law — that is all cross-ontology reuse (C4↔ArchiMate, SysML↔
ArchiMate) needs. We do not compute colimits of theories; names are globally unique, so
composition is disjoint union plus the bridge map.

---

## F3. Bindings as a constrained relation (profunctor / span)

**Definition.** The set of bindings is a relation
`Bnd ⊆ Subjects × CorrespondenceKind × Targets`, where `Subjects` ranges over diagram
elements *and the diagram itself* (`kind: diagram`), and `Targets` ranges over model
entities/connections/sets/(Phase 3) paths *and* diagram-local references. It is
deliberately a relation (not a function) so it expresses many-to-many, partial,
abstraction-like correspondence. The constraints are first-order predicates over `Bnd`.

**Soundness predicates (implemented)** — these are exactly the verifier rules in the main
plan's "Identity, Integrity, and Verifier Rules":

- subject resolution: an element subject resolves to a live element of its kind; a
  `kind: diagram` subject has no element;
- target resolution (entity id / connection id / connection_ids set / diagram_local /
  Phase 3 path) — total on `Bnd`;
- `correspondence_kind` admissible per the diagram type's `allowed_bindings` for the
  subject's type and target form;
- at most one `represents` per element subject (unless composite allowed); at most one
  diagram-level `scoped-by` per diagram;
- at most one `represents` occurrence per model target per diagram unless the module
  declares `visual_roles` (then distinct `visual_role` labels);
- no binding outlives its subject element (cascade on delete).

Tests: one per rule, asserting both the passing and the rejected case.

**Why a relation and not a lens/bidirectional transform:** lenses imply get/put write-back.
We forbid silent write-back (F4). A binding only *states* correspondence; mutation is the
separate, explicit materialization op. Lenses apply only if and when an explicit
`sync_policy` is added.

---

## F4. Derivation as a pure function + selection, with refresh laws

**Definition.** A derivation strategy is a pure function `F_θ: ModelInstance → CandidateSet`
(`θ` = parameters). The persisted view is `V = apply(selection, F_θ(M))`. Refresh is
`Refresh(M, V) = diff(F_θ(M), snapshot(V))`.

**Soundness properties (implemented as `hypothesis` property tests):**

- **Determinism**: `F_θ(M) == F_θ(M)`. For `path-projection` this requires the
  lexicographic tie-break (SPEC-phase-3 §1.3); without it the property fails and the test
  catches non-determinism.
- **Refresh idempotence**: if `M` is unchanged and no new selection is applied,
  `Refresh(M, V)` is the empty diff.
- **Selection monotonicity**: a candidate excluded in `selection` stays excluded across
  refreshes until explicitly re-included.
- **No silent mutation**: neither `F_θ` nor `Refresh` writes `M`; `V` changes only on an
  explicit accept. (Enforced structurally — derivation/refresh live on the read surface —
  and asserted by a test that runs refresh and checks the model store is byte-identical.)

**Why a function + stored selection and not "double-pushout rewriting":** DPO is a precise
account of *edits*, but our edits are already mediated by the explicit write path and its
dry-run/commit. The derivation needs determinism and idempotent refresh, which a pure
function + persisted selection gives directly and testably.

---

## What stays vocabulary (deliberately not implemented now)

Institutions as a satisfaction system over a logic; descent/sheaf gluing beyond the single
overlap check in F2; colimit/pushout module merging; decorated/structured cospans as
constructed objects; triple-graph-grammar machinery; topos or dependent-type semantics;
Lean 4 / Agda proofs. These are valuable for *naming and reasoning* about the design and may
return once F1–F4 plus the phase work are in place and there is a small, stable core worth
proving. Re-evaluate after Phase 3.

**Net:** formalizing F1–F4 gives a typing-soundness check, a cross-module coherence check, a
binding-constraint suite, and four testable derivation laws — enough to make the plan's
claims precise and machine-verifiable, with no new heavyweight machinery.
