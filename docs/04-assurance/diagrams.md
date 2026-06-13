# Assurance Diagrams

Four diagram families visualise an assurance analysis, each a diagram type module under
`src/diagram_types/`. Three render to PlantUML (control structure, bowtie, GSN); the UCA
matrix is an interactive frontend grid with no PlantUML body.

| Diagram | Module | Reads from |
|---|---|---|
| STAMP control structure | `control_structure` | Control-structure nodes + control actions |
| UCA matrix | `uca_matrix` | Control actions × STPA guidewords |
| Bowtie | `bowtie` | A hazard, its threats, consequences, and barriers |
| Assurance case (GSN) | `gsn` | Goals, strategies, solutions/evidence |

Assurance diagrams are **never written as plaintext to disk** — the renderer refuses to emit
into `diagram-catalog/rendered/`, keeping confidential analysis out of the clear. The figures
below are the project's **own** STPA-Sec analysis of its confidential assurance store
(a worked, self-describing example), rendered for this documentation.

&nbsp;

## STAMP control structure

The backbone of an STPA/STAMP analysis: controllers, controlled processes, and the control
actions and feedback between them. Binding a node to an architecture entity ties the analysis
to the real system; an unbound node renders as a visible modelling gap. Here the **Architecture
Backend** controls *Open store / release key* over the **SQLCipher store** and the **OS
credential backend**.

![STAMP control structure for confidential-store access — the backend controller, the open/release-key control action, and the store and credential-backend controlled processes](../media/assurance-control-structure.png)

&nbsp;

## UCA matrix

Every control action against the four STPA guidewords. A populated cell is an unsafe control
action; an empty cell is a context that is safe (or still to analyse). For the single control
action above:

| Control action | Not provided | Provided | Wrong timing | Stopped too soon |
|---|---|---|---|---|
| **Open store / release key** | — *(store stays locked — safe)* | **UCA1** — opens for a requestor whose clearance is below the entry's TLP → *plaintext-disclosure hazard* | **UCA2** — opens before the clearance check completes → *plaintext-disclosure hazard* | **UCA3** — kept open past the authorized activation window → *auto-unlocked-too-long hazard* |

&nbsp;

## Bowtie

A bowtie centres on a hazard (the "top event"), with threat pathways on the left and
consequences on the right, and the barriers that interrupt each pathway between. It reads well
for communicating one hazard's risk picture to stakeholders who do not work in STAMP terms.

![Bowtie centred on plaintext disclosure of the assurance store, with preventive barriers on the left and a detective barrier before the disclosure consequence](../media/assurance-bowtie.png)

&nbsp;

## Assurance case (GSN)

A Goal Structuring Notation view of the argument that the system is acceptably safe or secure:
top-level goals, the strategies that decompose them, and the solutions and evidence that
discharge them. This is the artifact a regulator or auditor expects, assembled from the same
store as the analysis it argues over.

![GSN assurance case: the top protection goal argued via the STPA-Sec constraints down to evidence solutions](../media/assurance-gsn.png)

&nbsp;

---

*Next: [Storage & confidentiality →](storage-and-confidentiality.md)*
