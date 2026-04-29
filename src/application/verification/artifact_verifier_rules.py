import re
from typing import Literal

from src.application.modeling.artifact_write import ARCHIMATE_STEREOTYPE_TO_CONNECTION_TYPE
from src.application.verification.artifact_verifier_registry import ArtifactRegistry
from src.application.verification.artifact_verifier_types import (
    DIAGRAM_ARTIFACT_TYPES,
    ENTITY_ID_RE,
    Issue,
    Severity,
    VerificationResult,
    entity_id_from_path,
)
from src.config.repo_paths import MODEL

_REL_MACRO_RE = re.compile(
    r"^\s*Rel_(?P<rel>[A-Za-z0-9]+)(?:_(?:Up|Down|Left|Right))?"
    r"\(\s*(?P<src>[A-Za-z0-9_-]+)\s*,\s*(?P<tgt>[A-Za-z0-9_-]+)",
    re.MULTILINE,
)
_REL_LINE_RE = re.compile(
    r"^\s*(?P<src>[A-Za-z0-9_-]+)\s+[-.*|o<>][^\n:]*\s+(?P<tgt>[A-Za-z0-9_-]+)\s*:\s*<<(?P<rel>[A-Za-z]+)>>",
    re.MULTILINE,
)
_STD_ALIAS_RE = re.compile(r"^(?P<prefix>[A-Z]{2,6})_(?P<random>[A-Za-z0-9_-]{4,})$")


def check_required_fields(fm: dict, required: frozenset[str], result: VerificationResult, loc: str) -> None:
    for field_name in sorted(required):
        if field_name not in fm or fm[field_name] is None:
            result.issues.append(
                Issue(
                    Severity.ERROR,
                    "E021",
                    f"Required frontmatter field '{field_name}' is missing or null",
                    loc,
                )
            )


def check_artifact_id_entity(fm: dict, result: VerificationResult, loc: str) -> None:
    if "artifact-id" not in fm:
        return
    aid = str(fm["artifact-id"])
    if not ENTITY_ID_RE.match(aid):
        result.issues.append(
            Issue(
                Severity.ERROR,
                "E101",
                f"artifact-id '{aid}' does not match TYPE@epoch.random.name pattern",
                loc,
            )
        )
        return

    file_id = entity_id_from_path(result.path)
    if file_id != aid:
        result.issues.append(
            Issue(
                Severity.ERROR,
                "E104",
                f"entity filename stem '{file_id}' does not match artifact-id '{aid}'",
                loc,
            )
        )


def check_artifact_type(
    fm: dict,
    valid: frozenset[str],
    label: str,
    result: VerificationResult,
    loc: str,
) -> None:
    if "artifact-type" not in fm:
        return
    artifact_type = str(fm["artifact-type"])
    if artifact_type not in valid:
        result.issues.append(
            Issue(
                Severity.ERROR,
                "E102",
                f"artifact-type '{artifact_type}' is not a recognised {label}",
                loc,
            )
        )


def check_enum(
    fm: dict,
    field_name: str,
    valid: frozenset[str],
    result: VerificationResult,
    loc: str,
) -> None:
    if field_name not in fm or fm[field_name] is None:
        return
    value = str(fm[field_name])
    if value not in valid:
        result.issues.append(
            Issue(
                Severity.ERROR,
                "E022",
                (f"Field '{field_name}' has invalid value '{value}'; expected one of: {sorted(valid)}"),
                loc,
            )
        )


def check_section(
    content: str,
    section: str,
    *,
    required: bool,
    result: VerificationResult,
    loc: str,
) -> None:
    marker = f"<!-- {section} -->"
    if marker in content:
        return
    severity = Severity.ERROR if required else Severity.WARNING
    code = "E031" if required else "W031"
    msg = f"Section marker '{marker}' is {'absent' if required else 'absent (optional for connections)'}"
    result.issues.append(Issue(severity, code, msg, loc))


def check_diagram_references_scoped(
    fm: dict,
    registry: ArtifactRegistry,
    file_scope: Literal["enterprise", "engagement", "unknown"],
    result: VerificationResult,
    loc: str,
) -> None:
    diagram_is_baselined = str(fm.get("status", "")) == "baselined"

    allowed_entities = registry.enterprise_entity_ids() if file_scope == "enterprise" else registry.entity_ids()
    allowed_connections = (
        registry.enterprise_connection_ids() if file_scope == "enterprise" else registry.connection_ids()
    )
    all_entities = registry.entity_ids()
    all_connections = registry.connection_ids()

    _check_entity_ids_used(
        fm,
        registry,
        file_scope,
        allowed_entities,
        all_entities,
        diagram_is_baselined,
        result,
        loc,
    )
    _check_connection_ids_used(
        fm,
        registry,
        file_scope,
        allowed_connections,
        all_connections,
        diagram_is_baselined,
        result,
        loc,
    )


def check_diagram_relation_references(
    content: str,
    fm: dict,
    registry: ArtifactRegistry,
    file_scope: Literal["enterprise", "engagement", "unknown"],
    result: VerificationResult,
    loc: str,
) -> None:
    allowed_connections = (
        registry.enterprise_connection_ids() if file_scope == "enterprise" else registry.connection_ids()
    )
    all_connections = registry.connection_ids()
    alias_to_entity_id = _build_alias_lookup(content, fm, registry)

    for src_alias, tgt_alias, conn_type in _iter_declared_relations(content):
        src_id = alias_to_entity_id.get(src_alias) or alias_to_entity_id.get(_normalize_puml_alias(src_alias))
        tgt_id = alias_to_entity_id.get(tgt_alias) or alias_to_entity_id.get(_normalize_puml_alias(tgt_alias))
        if src_id is None:
            result.issues.append(
                Issue(
                    Severity.ERROR,
                    "E311",
                    f"diagram relation references unknown source alias '{src_alias}'",
                    loc,
                )
            )
            continue
        if tgt_id is None:
            result.issues.append(
                Issue(
                    Severity.ERROR,
                    "E311",
                    f"diagram relation references unknown target alias '{tgt_alias}'",
                    loc,
                )
            )
            continue

        conn_id = f"{src_id}---{tgt_id}@@{conn_type}"
        if conn_id in allowed_connections:
            continue

        # Realization is often drawn concrete -> abstract in PUML even when the
        # stored model edge is abstract -> concrete.
        reverse_conn_id = f"{tgt_id}---{src_id}@@{conn_type}"
        if conn_type == "archimate-realization" and reverse_conn_id in allowed_connections:
            continue

        if conn_id in all_connections or reverse_conn_id in all_connections:
            result.issues.append(
                Issue(
                    Severity.ERROR,
                    "E313",
                    (
                        f"diagram relation '{conn_type}' between '{src_alias}' and '{tgt_alias}' "
                        "is out of scope for this repository"
                    ),
                    loc,
                )
            )
            continue

        result.issues.append(
            Issue(
                Severity.ERROR,
                "E312",
                (f"diagram relation '{conn_type}' between '{src_alias}' and '{tgt_alias}' does not exist in the model"),
                loc,
            )
        )


def _check_entity_ids_used(
    fm: dict,
    registry: ArtifactRegistry,
    file_scope: Literal["enterprise", "engagement", "unknown"],
    allowed_entities: set[str],
    all_entities: set[str],
    diagram_is_baselined: bool,
    result: VerificationResult,
    loc: str,
) -> None:
    if "entity-ids-used" not in fm:
        return
    entity_ids = fm["entity-ids-used"]
    if not isinstance(entity_ids, list):
        if entity_ids is not None:
            result.issues.append(Issue(Severity.WARNING, "W303", "entity-ids-used should be a YAML list", loc))
        return

    for eid in entity_ids:
        eid_str = str(eid)
        if eid_str not in allowed_entities:
            if eid_str in all_entities and file_scope == "enterprise":
                msg = (
                    f"entity-ids-used references non-enterprise entity '{eid_str}' "
                    "— enterprise diagrams may only reference enterprise entities"
                )
                result.issues.append(Issue(Severity.ERROR, "E310", msg, loc))
            else:
                result.issues.append(
                    Issue(
                        Severity.ERROR,
                        "E301",
                        f"entity-ids-used references unknown entity '{eid_str}'",
                        loc,
                    )
                )
            continue

        if diagram_is_baselined and registry.entity_status(eid_str) == "draft":
            result.issues.append(
                Issue(
                    Severity.ERROR,
                    "E306",
                    (
                        "baselined diagram references draft entity "
                        f"'{eid_str}' — all entities in a baselined diagram "
                        "must be baselined"
                    ),
                    loc,
                )
            )


def _check_connection_ids_used(
    fm: dict,
    registry: ArtifactRegistry,
    file_scope: Literal["enterprise", "engagement", "unknown"],
    allowed_connections: set[str],
    all_connections: set[str],
    diagram_is_baselined: bool,
    result: VerificationResult,
    loc: str,
) -> None:
    if "connection-ids-used" not in fm:
        return
    conn_ids = fm["connection-ids-used"]
    if not isinstance(conn_ids, list):
        if conn_ids is not None:
            result.issues.append(Issue(Severity.WARNING, "W304", "connection-ids-used should be a YAML list", loc))
        return

    for cid in conn_ids:
        cid_str = str(cid)
        if cid_str not in allowed_connections:
            if cid_str in all_connections and file_scope == "enterprise":
                msg = (
                    f"connection-ids-used references non-enterprise connection '{cid_str}' "
                    "— enterprise diagrams may only reference enterprise connections"
                )
                result.issues.append(Issue(Severity.ERROR, "E320", msg, loc))
            else:
                result.issues.append(
                    Issue(
                        Severity.ERROR,
                        "E302",
                        f"connection-ids-used references unknown connection '{cid_str}'",
                        loc,
                    )
                )
            continue

        if diagram_is_baselined and registry.connection_status(cid_str) == "draft":
            result.issues.append(
                Issue(
                    Severity.ERROR,
                    "E307",
                    (
                        f"baselined diagram references draft connection '{cid_str}' — "
                        "all connections in a baselined diagram must be baselined"
                    ),
                    loc,
                )
            )


def check_puml_structure(content: str, fm: dict, result: VerificationResult, loc: str) -> None:
    if "@startuml" not in content:
        result.issues.append(Issue(Severity.ERROR, "E304", "@startuml marker is missing", loc))
    if "@enduml" not in content:
        result.issues.append(Issue(Severity.ERROR, "E305", "@enduml marker is missing", loc))

    body_lines = [line for line in content.splitlines() if not line.lstrip().startswith("'")]
    has_visible_title = any(re.match(r"^\s*title(\s|$)", line, flags=re.IGNORECASE) for line in body_lines)
    if not has_visible_title:
        result.issues.append(
            Issue(
                Severity.ERROR,
                "E308",
                "Diagram must include a visible title line (for example: 'title <diagram name>')",
                loc,
            )
        )

    diagram_type = str(fm.get("diagram-type", ""))
    if "archimate" in diagram_type or "usecase" in diagram_type:
        has_macros = "_macros.puml" in content
        has_stereotypes = "_archimate-stereotypes.puml" in content
        has_inlined_archimate = "skinparam rectangle<<" in content and "hide stereotype" in content
        if not has_macros and not has_stereotypes and not has_inlined_archimate:
            result.issues.append(
                Issue(
                    Severity.ERROR,
                    "E303",
                    (
                        "ArchiMate/use-case diagram must include "
                        "_macros.puml, _archimate-stereotypes.puml, or an inlined "
                        "Archimate stereotype block"
                    ),
                    loc,
                )
            )

    _check_entity_aliases_declared(content, fm, result, loc)


def _check_entity_aliases_declared(content: str, fm: dict, result: VerificationResult, loc: str) -> None:
    entity_ids = fm.get("entity-ids-used")
    if not isinstance(entity_ids, list):
        return

    declared_aliases = _extract_declared_puml_aliases(content)
    for eid in entity_ids:
        eid_str = str(eid)
        entity_path = result.path.parents[2] / MODEL
        matches = list(entity_path.rglob(f"{eid_str}.md"))
        if not matches:
            continue
        try:
            entity_text = matches[0].read_text(encoding="utf-8")
        except OSError:
            continue
        alias = _extract_entity_display_alias(entity_text)
        if alias and _normalize_puml_alias(alias) not in declared_aliases:
            result.issues.append(
                Issue(
                    Severity.ERROR,
                    "E309",
                    (
                        f"entity-ids-used references '{eid_str}' with display alias '{alias}', "
                        "but that alias is not declared in the PUML body"
                    ),
                    loc,
                )
            )


def _normalize_puml_alias(alias: str) -> str:
    return alias.strip().replace("-", "_")


def _extract_declared_puml_aliases(content: str) -> set[str]:
    aliases: set[str] = set()
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("'"):
            continue
        m = re.search(r"\bas\s+([A-Za-z0-9_-]+)\s*\{?\s*$", stripped)
        if m:
            aliases.add(_normalize_puml_alias(m.group(1)))
    return aliases


def _extract_entity_display_alias(entity_text: str) -> str:
    marker = "<!-- §display -->"
    pos = entity_text.find(marker)
    if pos == -1:
        return ""
    display_body = entity_text[pos + len(marker) :]
    m = re.search(r"alias:\s*([A-Za-z0-9_-]+)", display_body)
    return _normalize_puml_alias(m.group(1)) if m else ""


def _build_alias_lookup(content: str, fm: dict, registry: ArtifactRegistry) -> dict[str, str]:
    alias_map: dict[str, str] = {}
    display_alias_to_entity_id: dict[str, str] = {}

    for entity_id in registry.entity_ids():
        path = registry.find_file_by_id(entity_id)
        if path is None:
            continue
        try:
            entity_text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        alias = _extract_entity_display_alias(entity_text)
        if alias:
            display_alias_to_entity_id.setdefault(_normalize_puml_alias(alias), entity_id)

    for eid in fm.get("entity-ids-used", []) if isinstance(fm.get("entity-ids-used"), list) else []:
        eid_str = str(eid)
        std_alias = _normalize_standard_alias(eid_str)
        if std_alias:
            alias_map[std_alias] = eid_str
            alias_map[_normalize_puml_alias(std_alias)] = eid_str
        alias = display_alias_to_entity_id.get(_normalize_puml_alias(std_alias), "")
        if alias:
            alias_map[_normalize_puml_alias(std_alias)] = alias
        display_alias = ""
        path = registry.find_file_by_id(eid_str)
        if path is not None:
            try:
                entity_text = path.read_text(encoding="utf-8")
            except OSError:
                entity_text = ""
            display_alias = _extract_entity_display_alias(entity_text) if entity_text else ""
        if display_alias:
            alias_map[display_alias] = eid_str

    aliases_to_resolve = set(_extract_declared_puml_aliases(content))
    for src_alias, tgt_alias, _conn_type in _iter_declared_relations(content):
        aliases_to_resolve.add(src_alias)
        aliases_to_resolve.add(tgt_alias)

    for alias in aliases_to_resolve:
        normalized = _normalize_puml_alias(alias)
        if alias in alias_map or normalized in alias_map:
            continue
        resolved = display_alias_to_entity_id.get(normalized)
        if resolved is not None:
            alias_map[alias] = resolved
            alias_map[normalized] = resolved
            continue
        resolved = _resolve_standard_alias(alias, registry.entity_ids())
        if resolved is None:
            resolved = _resolve_standard_alias(normalized, registry.entity_ids())
        if resolved is not None:
            alias_map[alias] = resolved
            alias_map[normalized] = resolved

    return alias_map


def _normalize_standard_alias(artifact_id: str) -> str:
    parts = artifact_id.split(".")
    if len(parts) < 2 or "@" not in parts[0]:
        return ""
    prefix = parts[0].split("@", 1)[0]
    return f"{prefix}_{parts[1]}"


def _resolve_standard_alias(alias: str, entity_ids: set[str]) -> str | None:
    match = _STD_ALIAS_RE.match(alias)
    if match is None:
        return None
    prefix = match.group("prefix")
    random = match.group("random")
    needle = f".{random}."
    for entity_id in entity_ids:
        if entity_id.startswith(f"{prefix}@") and needle in entity_id:
            return entity_id
    return None


def _iter_declared_relations(content: str) -> list[tuple[str, str, str]]:
    relations: list[tuple[str, str, str]] = []
    for match in _REL_MACRO_RE.finditer(content):
        conn_type = ARCHIMATE_STEREOTYPE_TO_CONNECTION_TYPE.get(match.group("rel").lower())
        if conn_type is None:
            continue
        relations.append((match.group("src"), match.group("tgt"), conn_type))
    for match in _REL_LINE_RE.finditer(content):
        conn_type = ARCHIMATE_STEREOTYPE_TO_CONNECTION_TYPE.get(match.group("rel").lower())
        if conn_type is None:
            continue
        relations.append((match.group("src"), match.group("tgt"), conn_type))
    return relations


def check_diagram_artifact_type(fm: dict, result: VerificationResult, loc: str) -> None:
    check_artifact_type(fm, DIAGRAM_ARTIFACT_TYPES, "diagram artifact type", result, loc)
