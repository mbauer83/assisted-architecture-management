# Assurance MCP Tools

The assurance MCP surface is split from the architecture servers so an agent can hold
read-only or read-write assurance access independently of its architecture permissions.

```json
{
  "mcpServers": {
    "arch-assurance-read":  { "command": "uv", "args": ["run", "arch-mcp-stdio-assurance-read"] },
    "arch-assurance-write": { "command": "uv", "args": ["run", "arch-mcp-stdio-assurance-write"] }
  }
}
```

The store must be unlocked before the tools become operational; auto-unlock handles this on
every backend start after the first `arch-assurance unlock`.

&nbsp;

## What the tools cover

Agents create and query the assurance graph and have it linked to architecture entities by
cross-reference:

- **STPA** — losses, hazards, control-structure nodes, control actions, unsafe control
  actions, loss scenarios, and derived assurance constraints.
- **CAST** — incidents (against a sealed baseline), observed UCAs and scenarios, and
  corrective actions.
- **GRC** — risk evaluations and compliance obligations citing public framework codes.
- **Supply chain** — ingested SBOM / signal data.

Each write runs through the same verifier and safety-disposition safeguard as the GUI, so an
agent cannot, for example, mark a safety constraint as `accept`-risk-treated.

&nbsp;

## `arch-assurance-read`

<!-- mcp-tools:begin assurance-read -->
| Capability | Tool | Access | Purpose |
|---|---|---|---|
| STPA / CAST / GRC authoring | `assurance_guidance` | Read-only | Return per-step STPA/CAST/GRC method guidance: what the step means, why it matters, and which standard applies. |
| Completeness & coverage | `assurance_verify` | Read-only | Run §17(A) hard structural validity checks on all assurance entities in the store. |
| Completeness & coverage | `assurance_coverage` | Read-only | Return a coverage/gap summary across the assurance store: constraints without evidence, hazards without constraints, obligations without constraints, risks without treatment, unbound-pending CSNs, and orphan corrective-actions. |
| Completeness & coverage | `assurance_stpa_complete` | Read-only | Run the §17(B) stpa-basic-complete coverage profile check on the assurance store. |
| Completeness & coverage | `assurance_cast_complete` | Read-only | Run the §17(B) cast-complete coverage profile check. |
| Completeness & coverage | `assurance_grc_complete` | Read-only | Run the §17(B) grc-control-coverage-complete profile check. |
| Completeness & coverage | `assurance_case_completeness` | Read-only | Run argument-completeness checks for an assurance case. |
| Completeness & coverage | `assurance_draft_gsn` | Read-only | Scaffold a GSN (Goal Structuring Notation) argument structure from the assurance store. |
| Supply chain / AIBOM | `assurance_aibom_export` | Read-only | Emit a CycloneDX 1.6 ML-BOM/ASBOM JSON document from a list of AI-component dicts. |
| Supply chain / AIBOM | `assurance_scan_ai_candidates` | Read-only | Heuristic AI-BOM candidate scan over a list of architecture entity dicts. |
| Security signals | `assurance_list_bom_components` | Read-only | List the software components of the ACTIVE security signal snapshot for an architecture anchor (the current SBOM). |
| Security signals | `assurance_list_vulnerabilities` | Read-only | List vulnerability findings of the ACTIVE signal snapshot for an architecture anchor, each carrying its component name/purl/directness, severity band, CVSS score, and applicability. |
| Security signals | `assurance_security_stats` | Read-only | Snapshot aggregate counts: total_snapshots, active_snapshots, anchors_with_active_snapshot, and the component/finding totals across the active snapshots. |
| Security signals | `assurance_security_metrics` | Read-only | Security posture metrics for one architecture anchor, computed from the single ACTIVE signal snapshot plus visible VEX assessments, exposure-filtered before any aggregation. |
| Security signals | `assurance_risk_register` | Read-only | Return a tabular view of all risk entities with their treatment, owner status, linked hazards/loss-scenarios (via assesses), and treating constraints (via treated-by). |
| Store administration | `assurance_store_status` | Read-only | Return the current status of the confidential assurance store: whether it is configured, locked, or unlocked. |
| Store administration | `assurance_stats` | Read-only | Return counts of assurance nodes and edges by type. |
| Store administration | `assurance_list_analyses` | Read-only | List assurance analyses — the aggregate roots for units of STPA/CAST/GRC work. |
| Store administration | `assurance_list_nodes` | Read-only | List assurance entities (losses, hazards, UCAs, constraints, etc.). |
| Store administration | `assurance_read_node` | Read-only | Read a single assurance entity by node_id. |
| Store administration | `assurance_list_edges` | Read-only | List assurance connections. |
<!-- mcp-tools:end assurance-read -->

## `arch-assurance-write`

<!-- mcp-tools:begin assurance-write -->
| Capability | Tool | Access | Purpose |
|---|---|---|---|
| STPA / CAST / GRC authoring | `assurance_create_analysis` | Write | Create an assurance analysis — the aggregate root for a unit of STPA/CAST/GRC work; every node is created within one analysis. |
| STPA / CAST / GRC authoring | `assurance_update_analysis` | Write | Update an analysis's name, status (draft/active/completed/archived), or tlp. |
| STPA / CAST / GRC authoring | `assurance_delete_analysis` | Destructive | Delete an assurance analysis. |
| STPA / CAST / GRC authoring | `assurance_create_node` | Write | Create an assurance entity (loss, hazard, control-structure-node, control-action, unsafe-control-action, loss-scenario, assurance-constraint, risk, incident, corrective-action, obligation). |
| STPA / CAST / GRC authoring | `assurance_edit_node` | Write | Update attributes of an existing assurance node. |
| STPA / CAST / GRC authoring | `assurance_delete_node` | Destructive | Delete an assurance node and all its incoming/outgoing edges. |
| STPA / CAST / GRC authoring | `assurance_add_edge` | Write | Add a typed assurance connection between two nodes. |
| STPA / CAST / GRC authoring | `assurance_delete_edge` | Destructive | Delete a single assurance edge by its edge_id. |
| STPA / CAST / GRC authoring | `assurance_seal_baseline` | Write | Seal a signed baseline of the current assurance analysis state. |
| Completeness & coverage | `assurance_promotion_preflight` | Write | Pre-check safety/security assurance-constraints before promoting findings to a wider audience tier. |
| Supply chain / AIBOM | `assurance_reconcile_aibom` | Write | Diff a modeled AI-BOM (from the architecture model) against a discovered one (from a runtime discovery tool or an imported BOM file). |
| Security signals | `assurance_ingest_security_signals` | Write | Ingest security signals for one architecture anchor: submit a CycloneDX BOM document (and, optionally, the OSV advisory records for its components) as a single ingest, producing a new ACTIVE signal snapshot that supersedes the anchor's previous one. |
| Security signals | `assurance_register_arch_ref` | Write | Record an assurance→architecture cross-reference. |
| Security signals | `assurance_model_this` | Write | Propose an architecture entity to bind an unbound-pending control-structure-node. |
<!-- mcp-tools:end assurance-write -->

The tables above are generated from the registered assurance MCP servers by
`uv run tools/generate_mcp_docs.py`. Tool names and descriptions are the same metadata that
an MCP client receives during handshake; they do not expose assurance-store contents.

&nbsp;

## Classification gating

The `max_classification` ceiling in `config/settings.yaml` (default `TLP:RED`) controls the
highest TLP level the assurance servers expose to agents. Entries above the ceiling are
withheld from tool responses, so an agent operating in a lower-trust context never receives
content above the configured level.

```yaml
storage:
  assurance:
    max_classification: TLP:AMBER   # withhold TLP:RED entries from agents
```

&nbsp;

## Inspecting the live surface

The exact tool list is browsable with the MCP Inspector once the servers are registered —
swap `arch-mcp-stdio-read` for `arch-mcp-stdio-assurance-read` in the
[Inspector recipe](../03-modeling/interfaces-and-mcp.md#inspecting-the-live-tool-surface).

---

*Back to [Assurance overview](index.md) · Next section: [Extensibility →](../05-extensibility/index.md)*
