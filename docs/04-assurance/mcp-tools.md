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
