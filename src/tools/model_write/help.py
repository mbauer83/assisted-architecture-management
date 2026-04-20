"""Type catalog for model authoring tools.

Progressive discovery pattern: agents call this to learn valid entity/connection
types before calling create/edit tools.  Grouped by domain for quick scanning.
"""

from src.common.model_write import (
    ARCHIMATE_STEREOTYPE_TO_CONNECTION_TYPE,
    CONNECTION_TYPES,
    ENTITY_TYPES,
)


def write_help() -> dict[str, object]:
    """Return entity/connection type catalog grouped by domain."""
    return {
        "entity_types_by_domain": _entity_types_by_domain(),
        "entity_type_catalog": _entity_type_catalog(),
        "connection_types_by_language": _connection_types_by_language(),
        "connection_type_catalog": _connection_type_catalog(),
        "archimate_stereotypes": sorted(ARCHIMATE_STEREOTYPE_TO_CONNECTION_TYPE.keys()),
        "conventions": {
            "entity_id_format": "TYPE@epoch.random.friendly-name (auto-generated)",
            "puml_alias_format": "TYPE_random (e.g. DRV_Qw7Er1)",
            "statuses": ["draft", "active", "deprecated"],
            "dry_run": "All create/edit tools default to dry_run=true for safe preview",
        },
    }


def _entity_types_by_domain() -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for type_name, info in ENTITY_TYPES.items():
        domain = info.domain_dir
        grouped.setdefault(domain, []).append(type_name)
    return grouped


def _entity_type_catalog() -> dict[str, dict[str, object]]:
    return {
        type_name: {
            "prefix": info.prefix,
            "domain": info.domain_dir,
            "subdir": info.subdir,
            "archimate_domain": info.archimate_domain,
            "archimate_element_type": info.archimate_element_type,
            "element_classes": list(info.element_classes),
        }
        for type_name, info in ENTITY_TYPES.items()
    }


def _connection_types_by_language() -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for type_name, info in CONNECTION_TYPES.items():
        lang = info.conn_lang
        grouped.setdefault(lang, []).append(type_name)
    return grouped


def _connection_type_catalog() -> dict[str, dict[str, object]]:
    return {
        type_name: {
            "language": info.conn_lang,
            "directory": info.conn_dir,
            "archimate_relationship_type": info.archimate_relationship_type,
            "symmetric": info.symmetric,
            "puml_arrow": info.puml_arrow,
        }
        for type_name, info in CONNECTION_TYPES.items()
    }
