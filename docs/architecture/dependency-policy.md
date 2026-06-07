# Dependency Policy

Enforced by `tests/architecture/test_dependency_policy.py` (AST-based, baseline mode).

---

## Package roles

| Package | Role | Notes |
|---------|------|-------|
| `src/domain/` | Core domain | Pure business concepts and contracts. No outward dependencies. |
| `src/application/` | Application layer | Orchestrates domain objects and ports. |
| `src/config/` | Configuration leaf | Workspace / repo path resolution; reads YAML. |
| `src/ontologies/*/` | Pure ontology plugins | Provide ArchiMate / SysML data to the registry. |
| `src/diagram_types/*/` | Adapter-plugins | Diagram type descriptors and renderer adapters. |
| `src/infrastructure/` | Infrastructure | FastAPI, SQLite, MCP, CLI, rendering, Git I/O. |
| composition roots | Composition only | Entry-point modules that wire the object graph. |

Composition roots (allowed to import from all packages):
- `src/infrastructure/app_bootstrap.py`
- `src/infrastructure/cli/artifact_query_cli.py`
- `src/infrastructure/cli/arch_assurance.py`
- `src/infrastructure/cli/_assurance_commands.py`
- `src/infrastructure/cli/_security_commands.py`
- `src/infrastructure/mcp/arch_mcp_stdio.py`
- `src/infrastructure/mcp/arch_mcp_stdio_write.py`
- `src/infrastructure/mcp/arch_mcp_stdio_assurance.py`
- `src/infrastructure/mcp/mcp_artifact_server.py`
- `src/infrastructure/mcp/mcp_assurance_server.py`
- `src/infrastructure/gui/gui_server.py`
- `src/infrastructure/backend/arch_backend.py`
- `src/infrastructure/backend/arch_backend_app.py`

---

## Dependency matrix

```
package          may import from
──────────────   ────────────────────────────────────────────────
domain        →  domain, stdlib/third-party
application   →  domain, application, stdlib/third-party
config        →  config, domain (value types only), stdlib/third-party
ontologies/*  →  domain (contracts + types), stdlib/third-party
diagram_types/* → domain (contracts + types), infrastructure renderers, stdlib/third-party
infrastructure → application, domain, ontologies/*, diagram_types/*, config,
                  infrastructure, stdlib/third-party
composition   →  all packages
```

---

## Burn-down

Known violations are recorded in `tests/architecture/architecture_baseline.json`.
The test fails only on *new* violations. The baseline must be **empty** by the time
all plan phases (WU-01 through WU-08) are complete.

Current violation categories and their planned remediation:

| Category | Files | Remediated by |
|----------|-------|---------------|
| `domain → infrastructure` | `ontology_catalog.py`, `connection_ontology.py`, `archimate_relation_rendering.py` (lazy `get_module_registry`); `ontology_protocol.py` (`GenericPumlRenderer`) | Phase B/C (WU-02–06) |
| `domain → config` | `artifact_types.py` (`infer_repo_scope`) | Phase D (WU-07) |
| `domain → ontologies` | `ontology_catalog.py` (`matrix_abbreviations`) | Phase D (WU-07) |
| `domain → application` | `view_projection.py` (`derivation.types`) | Phase B/C (WU-02–06) |
| `application → infrastructure` | `entity_type_predicates.py`, `_verifier_rules_bindings.py`, `_verifier_rules_semantic.py` (lazy `get_module_registry`) | Phase C (WU-05–06) |
| `application → config` | `artifact_document_schema.py`, `group_registry.py`, `group_registry_validation.py`, `repo_path_helpers.py`, `artifact_verifier.py`, `artifact_verifier_incremental.py`, `artifact_verifier_rules.py` | Phase C/D (WU-05–07) |
| `diagram_types → application` | `c4/_projection.py`, `c4/_type.py` (`derivation.*`) | Phase C/E (WU-05, WU-08) |
| `ontologies → infrastructure` | `archimate_next/_loader.py` (lazy `_svg_sprite_convert`) | Phase D (WU-07) |
