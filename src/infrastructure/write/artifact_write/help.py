"""Type catalog for model authoring tools.

Progressive discovery pattern: agents call this to learn valid entity/connection
types before calling create/edit tools.  Grouped by domain for quick scanning.
"""

from functools import lru_cache

from src.application.modeling.artifact_write import ARCHIMATE_STEREOTYPE_TO_CONNECTION_TYPE
from src.domain.module_types import ElementClassName


@lru_cache(maxsize=1)
def _registry():
    from src.infrastructure.app_bootstrap import get_module_registry  # noqa: PLC0415
    return get_module_registry()


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
    internal = _registry().entity_types_with_class(ElementClassName("internal"))
    grouped: dict[str, list[str]] = {}
    for type_name, info in _registry().all_entity_types().items():
        if type_name in internal:
            continue
        domain = info.domain_dir
        grouped.setdefault(domain, []).append(str(type_name))
    return grouped


def _entity_type_catalog() -> dict[str, dict[str, object]]:
    return {
        str(type_name): {
            "prefix": info.prefix,
            "domain": info.domain_dir,
            "subdir": info.subdir,
            "archimate_domain": info.domain_dir.capitalize(),
            "archimate_element_type": info.archimate_element_type,
            "element_classes": list(info.element_classes),
        }
        for type_name, info in _registry().all_entity_types().items()
    }


def _connection_types_by_language() -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for type_name, info in _registry().all_connection_types().items():
        lang = info.conn_lang
        grouped.setdefault(lang, []).append(str(type_name))
    return grouped


def _connection_type_catalog() -> dict[str, dict[str, object]]:
    return {
        str(type_name): {
            "language": info.conn_lang,
            "archimate_relationship_type": info.archimate_relationship_type,
            "symmetric": info.symmetric,
            "puml_arrow": info.puml_arrow,
        }
        for type_name, info in _registry().all_connection_types().items()
    }
