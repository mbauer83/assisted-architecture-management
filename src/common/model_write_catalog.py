
from dataclasses import dataclass
from typing import Literal


DiagramConnectionInferenceMode = Literal["none", "auto", "strict"]


@dataclass(frozen=True)
class EntityTypeInfo:
    """Canonical metadata for a single entity type.

    Loaded from config/entity_ontology.yaml via ontology_loader.
    """

    artifact_type: str
    prefix: str
    domain_dir: str
    subdir: str
    archimate_domain: str
    archimate_element_type: str
    element_category: str  # active | behavioral | passive | motivation | strategy | implementation | composite
    element_classes: tuple[str, ...]  # ArchiMate NEXT classification classes


@dataclass(frozen=True)
class ConnectionTypeInfo:
    """Canonical metadata for a single connection type.

    Loaded from config/connection_ontology.yaml via ontology_loader.
    """

    artifact_type: str
    conn_lang: str
    conn_dir: str
    archimate_relationship_type: str | None = None
    symmetric: bool = False
