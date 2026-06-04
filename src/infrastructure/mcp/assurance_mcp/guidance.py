"""Per-step STPA/CAST/GRC method guidance content."""

from __future__ import annotations

_GUIDANCE: dict[str, dict[str, object]] = {
    "stpa-losses": {
        "step": "STPA Step 1 — Identify Losses",
        "what": (
            "A loss is an unacceptable outcome stakeholders must avoid: loss of life, injury, "
            "property damage, mission failure, privacy violation, regulatory non-compliance."
        ),
        "why": (
            "Losses anchor the entire analysis. Every hazard, UCA, and constraint traces back "
            "to one or more losses. Without losses, STPA has no direction."
        ),
        "how": (
            "Brainstorm stakeholder-relevant outcomes to avoid. Use broad categories first "
            "(safety, security, financial, privacy). Each loss should be a noun phrase, "
            "e.g. 'Loss of vehicle control', 'Breach of personal data'."
        ),
        "standards": [
            "STPA Handbook (Leveson & Thomas) §2.2",
            "ISO 26262 Part 3 §6 (hazard analysis and risk assessment)",
        ],
    },
    "stpa-hazards": {
        "step": "STPA Step 2 — Identify System-Level Hazards",
        "what": (
            "A hazard is a system state that, with worst-case environment, leads to a loss. "
            "It describes the system state, not the cause or outcome."
        ),
        "why": (
            "Hazards bridge losses and the control structure. They are system-level "
            "(not component-level) to remain stable across design changes."
        ),
        "how": (
            "For each loss, ask: what system state could produce this loss? "
            "Write hazards as system states, e.g. 'Vehicle moves at unsafe speed for road conditions'."
        ),
        "standards": ["STPA Handbook §2.3", "ISO/SAE 21434 Clause 9 (TARA)"],
    },
    "stpa-control-structure": {
        "step": "STPA Step 3 — Model the Control Structure",
        "what": (
            "The control structure is a hierarchical diagram of controllers and controlled "
            "processes connected by control actions and feedback — the STAMP governance model."
        ),
        "why": (
            "UCAs can only be identified with respect to a specific control action on a specific "
            "control loop. The control structure makes those loops explicit."
        ),
        "how": (
            "Identify controllers (issue commands), controlled processes (receive commands), "
            "control actions (specific commands), and feedback signals. Mark binding_status for each node."
        ),
        "standards": ["STPA Handbook §2.4", "STAMP/STPA overview (UL)"],
    },
    "stpa-ucas": {
        "step": "STPA Step 4 — Identify Unsafe Control Actions (UCAs)",
        "what": (
            "A UCA is a specific control action unsafe in a particular context. "
            "Four types: (1) not provided, (2) provided when unsafe, "
            "(3) wrong timing, (4) stopped too soon / applied too long."
        ),
        "why": (
            "UCAs are the direct cause of hazards in STAMP. Systematically applying "
            "the four guidewords to each control action ensures completeness."
        ),
        "how": (
            "For each control action on each controller, apply all four guidewords. Record the "
            "context (state variables) under which each guideword produces a UCA. "
            "Each UCA must reference exactly one control-action."
        ),
        "standards": ["STPA Handbook §2.5", "UCA guideword guide"],
    },
    "stpa-constraints": {
        "step": "STPA Step 5 — Derive Safety/Security Constraints",
        "what": (
            "An assurance-constraint is a requirement derived from UCAs: "
            "'The controller must/must not issue action X in context Y.' "
            "Constraints are the actionable output of STPA."
        ),
        "why": (
            "Constraints are directly implementable and testable. They link hazard analysis "
            "to system requirements (via refines) and to evidence (via evidenced-by)."
        ),
        "how": (
            "For each UCA, derive its negation as a constraint. Set concern_class, disposition, level. "
            "Link to an ArchiMate requirement via refines. Assign an owner via accountable-to."
        ),
        "standards": ["STPA Handbook §2.6", "ISO 26262 Part 4 §6 (functional safety concept)"],
    },
    "grc-risk": {
        "step": "GRC — Risk Evaluation",
        "what": (
            "A risk entity evaluates a hazard or loss-scenario: likelihood × impact = risk score. "
            "OPTIONAL — constraints are valid without a risk entity (§9 anti-subordination safeguard)."
        ),
        "why": (
            "Risk prioritises which constraints to treat first, but never closes a safety/security "
            "constraint. treatment=accept cannot be the sole disposition of a safety hazard."
        ),
        "how": (
            "Create a risk entity, set likelihood and impact, connect via assesses→hazard "
            "and treated-by→assurance-constraint. Assign an owner. Set review_date."
        ),
        "standards": ["ISO 31000:2018 §6 (risk treatment)", "Cerrix risk register best practices"],
    },
    "grc-obligations": {
        "step": "GRC — Compliance Obligations",
        "what": (
            "An obligation entity represents a compliance instance: 'Does our system comply "
            "with clause X of standard Y?' Status and evidence are assurance-owned and confidential."
        ),
        "why": (
            "Obligations close the loop between technical constraints and regulatory requirements. "
            "They enable an auditable compliance statement."
        ),
        "how": (
            "Create an obligation, set cites to a scheme:code reference (e.g. ISO26262:6-8). "
            "Link assurance-constraints via complies-with. Add evidenced-by connections for evidence."
        ),
        "standards": [
            "ISO 27001:2022 Annex A controls",
            "GDPR Art. 5 (data processing principles)",
            "EU AI Act Art. 12/18/19/26",
        ],
    },
    "cast-investigation": {
        "step": "CAST — Incident/Accident Investigation",
        "what": (
            "CAST (Causal Analysis using System Theory) is the reactive counterpart of STPA. "
            "It reconstructs the control structure as-existed at the incident and derives corrective constraints."
        ),
        "why": (
            "CAST reuses the STAMP model and adds incident entity, observed UCAs (mode=observed), "
            "and corrective-actions. Corrective constraints enter the same GRC lifecycle as STPA constraints."
        ),
        "how": (
            "Create an incident entity, seal an analysis_baseline to pin the model state, "
            "then trace observed UCAs and loss-scenarios back to the incident. "
            "Derive corrective-action entities and then constraints."
        ),
        "standards": ["CAST Handbook (Leveson)", "STPA/CAST overview (UL)"],
    },
}


def lookup(topic: str) -> dict[str, object]:
    """Return guidance for *topic*, fuzzy-matching against available keys."""
    normalized = topic.lower().strip().replace(" ", "-")
    for key, value in _GUIDANCE.items():
        if key == normalized or normalized in key or key in normalized:
            return {"topic": key, **value}
    return {
        "topic": topic,
        "available_topics": list(_GUIDANCE.keys()),
        "message": f"No guidance found for '{topic}'. Try one of the available topics.",
    }
