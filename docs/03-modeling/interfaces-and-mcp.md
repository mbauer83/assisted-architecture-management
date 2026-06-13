# Interfaces & MCP

Three surfaces sit over one artifact store: an **MCP server** for AI agents, a **REST API**
for programmatic access, and a **browser GUI** for people. The GUI is built on the REST API,
so anything a human can do in the browser can be automated through REST or MCP.

The principle behind this is deliberate: *architecture work is reachable through both human
and agent interfaces*, without claiming identical depth on every feature. Agent access is
designed in from the start — typed tools with built-in schema validation and verification, an
authoring surface an agent can write to safely — rather than an export or read-only API
bolted onto a human-first tool.

&nbsp;

## MCP tool surface

The MCP interface is split into two servers so an agent can be constrained by capability.
Configure them in `.mcp.json` — see [Installation §5](../02-installation.md#5-configure-mcp-access-for-ai-agents).

### `arch-repo-read` (query, navigate, verify)

| Tool | Purpose |
|---|---|
| `artifact_query_stats` | Counts and breakdowns by domain / type / connection type / group |
| `artifact_query_list_artifacts` | Metadata-only listing with AND-semantics filters and field projection |
| `artifact_query_search_artifacts` | Ranked full-text search (with optional semantic supplement) |
| `artifact_query_read_artifact` | Read one artifact (summary or full) by id |
| `artifact_query_find_connections_for` | Connections touching an entity (inbound / outbound / any) |
| `artifact_query_find_neighbors` | Graph neighbours for relationship walking |
| `artifact_diagram_scaffold` | Generate a starting diagram skeleton for a type |
| `artifact_verify` | Run the verifier over a scope and return structured findings |

### `arch-repo-write` (author, edit, promote)

| Group | Tools |
|---|---|
| **Entities** | `artifact_create_entity`, `artifact_edit_entity` |
| **Connections** | `artifact_add_connection`, `artifact_edit_connection`, `artifact_edit_connection_associations` |
| **Diagrams** | `artifact_create_diagram`, `artifact_edit_diagram`, `artifact_create_matrix` |
| **Documents** | `artifact_create_document`, `artifact_edit_document` |
| **Bulk** | `artifact_bulk_write`, `artifact_bulk_delete` |
| **Grouping** | `artifact_group` |
| **Promotion & sync** | `artifact_promote_to_enterprise`, `artifact_save_changes`, `artifact_submit_for_review`, `artifact_withdraw_changes` |
| **Guidance & ops** | `artifact_authoring_guidance`, `artifact_help`, `artifact_get_operation` |

The tool count is kept small with clear descriptions on purpose — fewer, well-described
tools let an agent pick correctly. Every write tool validates against the verifier, supports
a dry-run preview, and returns structured error codes with locations on failure. Structured
output is returned as YAML for token efficiency.

> The optional **assurance** MCP servers (`arch-assurance-read` / `arch-assurance-write`)
> are documented separately under [Assurance MCP tools](../04-assurance/mcp-tools.md).

&nbsp;

## Inspecting the live tool surface

To browse the running MCP surface with the MCP Inspector over stdio:

```bash
tmp_cfg="$(mktemp)"
cat >"$tmp_cfg" <<JSON
{
  "mcpServers": {
    "default-server": {
      "type": "stdio",
      "command": "uv",
      "args": ["--directory", "$(pwd)", "run", "arch-mcp-stdio-read"]
    }
  }
}
JSON
npx -y @modelcontextprotocol/inspector@latest --config "$tmp_cfg" --server default-server
```

Swap `arch-mcp-stdio-read` for `arch-mcp-stdio-write` to inspect the write server. The
explicit `stdio` config avoids stale persisted transport state in the Inspector UI.

&nbsp;

## REST API

`arch-backend` exposes the same capability set at `http://localhost:<backend-port>/api/`.
Because the GUI is built on it, the REST surface covers querying, authoring, verification,
promotion, grouping, and the save/submit/review sync lifecycle. A Server-Sent Events stream
at `GET /api/events` carries sync progress and write-lock state.

&nbsp;

## Browser GUI

`arch-backend` serves the Vue SPA at `/`. It covers:

- **Overview** — engagement vs. enterprise summary, domain and connection-type breakdowns
- **Exploration** — entity / diagram / document catalogs with filtering, search, treemap,
  and graph navigation
- **Authoring** — schema-aware entity / diagram / document creation and editing with live
  preview
- **Verification** — real-time validation feedback and promotion conflict detection
- **Promotion** — explicit entity/connection curation with conflict-resolution strategies

---

*Back to [Architecture Modeling](index.md) · Next section: [Assurance →](../04-assurance/index.md)*
