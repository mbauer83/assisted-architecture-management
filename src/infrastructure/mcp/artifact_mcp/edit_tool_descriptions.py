"""MCP edit tool description text."""

EDIT_ENTITY_DESCRIPTION = (
    "Edit an existing entity. Pass only fields to change; omitted fields are preserved. "
    "Supports name, summary, properties, notes, keywords, version, status, "
    "group (str|None — re-home to a different model-project slug). "
    "Bumps last-updated automatically. Regenerates macros if name changes. "
    "artifact_id: full (PREFIX@epoch.random.slug) or short (PREFIX@epoch.random) form."
)

EDIT_CONNECTION_DESCRIPTION = (
    "Edit or remove a connection in an .outgoing.md file. "
    "Identify by source_entity + target_entity + connection_type. "
    "operation='update' (default) changes description, src_multiplicity, and/or "
    "tgt_multiplicity; pass '' to remove an existing multiplicity, omit (null) to "
    "preserve it. operation='remove' deletes the connection. "
    "source_entity/target_entity: full (PREFIX@epoch.random.slug) or short (PREFIX@epoch.random) form."
)

EDIT_CONNECTION_ASSOCIATIONS_DESCRIPTION = (
    "Add or remove second-order association entity IDs from a connection. "
    "Associations link a connection to additional entities beyond source and target "
    "(stored as <!-- §assoc ENTITY_ID --> annotations). "
    "add_entities and remove_entities may both be provided in one call. "
    "source_entity/target_entity: full (PREFIX@epoch.random.slug) or short (PREFIX@epoch.random) form."
)

EDIT_DIAGRAM_DESCRIPTION = (
    "Edit an existing diagram. "
    "Binding modes (pass mode=): 'refresh-derivation'"
    " (requires derivation_id — runs strategy, returns diff + base_revision, no write); "
    "'apply-diff' (requires diff + base_revision — applies diff with stale-write check); "
    "'propose-bindings' (requires entity_ids/connection_ids — returns proposals, no write); "
    "'detach-binding' (requires binding_id — removes binding). "
    "Default (no mode): puml='auto-sync' is projection-aware — scope-bound diagrams "
    "re-run their projector (never deleted on empty result); ArchiMate diagrams reconcile "
    "refs; standalone diagrams re-render. Explicit puml replaces body; frontmatter fields "
    "updated if provided; bindings merges + normalizes shorthand. "
    "ArchiMate occurrence edits may pass diagram_entities={'occurrence': "
    "[{'id': '<occurrence-id>', 'backing_entity_id': '<model-entity-id>'}]}; "
    "the occurrence id distinguishes the diagram element and visual_role is optional metadata. "
    "edge_labels: per-diagram edge-label overrides keyed by '{src_alias}:{tgt_alias}'; "
    "omit to preserve existing overrides; pass {} to clear all. "
    "viewpoint: replace the diagram's ViewpointApplication frontmatter — "
    "{slug, version, enforcement_override?, derivation_params?}; omit to keep the existing "
    "application (if any) unchanged. Call artifact_authoring_guidance to discover slugs/versions "
    "via its 'viewpoints' list. "
    "group (str|None — re-home to a different diagram-collection slug; moves the source "
    "file and its rendered PNG/SVG; only applies to the default write path, not mode= "
    "dispatch or puml='auto-sync'). "
    "Re-verifies and re-renders PNG on every write. "
    "Matrix diagrams (diagram-type: matrix) are markdown tables, not PUML: only "
    "name/keywords/version/status/tlp/group are supported here (metadata + group move, "
    "table content preserved); puml/diagram_entities/diagram_connections/bindings/viewpoint/etc. "
    "are rejected — call artifact_create_matrix with artifact_id set to change table content. "
    "artifact_id: full (PREFIX@epoch.random.slug) or short (PREFIX@epoch.random) form."
)

DELETE_ENTITY_DESCRIPTION = (
    "Delete a single entity (and its own .outgoing.md file, if any). Blocks with a dependency "
    "list if the entity has incoming connections, is referenced by any diagram, or has a global "
    "entity reference — delete or update those first. For a batch, or when dependents should be "
    "deleted/reconciled together in one transaction, use artifact_bulk_delete instead; this tool "
    "is the lighter-weight single-item path (no full-repo staging copy). "
    "artifact_id: full (PREFIX@epoch.random.slug) or short (PREFIX@epoch.random) form."
)

DELETE_DIAGRAM_DESCRIPTION = (
    "Delete a single diagram, including its rendered PNG/SVG output. Blocks if any classifier the "
    "diagram hosts is still referenced by another diagram. For a batch, or a cascade spanning "
    "connections/entities/diagrams together, use artifact_bulk_delete instead; this tool is the "
    "lighter-weight single-item path (no full-repo staging copy). "
    "artifact_id: full (PREFIX@epoch.random.slug) or short (PREFIX@epoch.random) form."
)
