from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol, TypeAlias, runtime_checkable

from src.config.workspace_paths import infer_repo_scope

Domain: TypeAlias = str

MountScope = Literal["engagement", "enterprise"]


@dataclass(frozen=True)
class RepoMount:
    root: Path
    scope: MountScope
    engagement_label: str


class DuplicateArtifactIdError(ValueError):
    pass


def infer_engagement_label(root: Path, *, scope: MountScope) -> str:
    if scope == "enterprise":
        return "enterprise"
    parts = root.resolve().parts
    if "engagements" in parts:
        idx = parts.index("engagements")
        if idx + 1 < len(parts):
            return parts[idx + 1]
    return ""


def infer_mount(root: Path) -> RepoMount:
    resolved = root.resolve()
    scope: MountScope = "enterprise" if infer_repo_scope(resolved) == "enterprise" else "engagement"
    return RepoMount(root=resolved, scope=scope, engagement_label=infer_engagement_label(resolved, scope=scope))


@dataclass(frozen=True)
class EntityRecord:
    artifact_id: str
    artifact_type: str
    name: str
    version: str
    status: str
    domain: Domain
    subdomain: str
    path: Path
    keywords: tuple[str, ...]
    extra: dict[str, object]
    content_text: str
    display_blocks: dict[str, str]
    display_label: str
    display_alias: str
    host_diagram_id: str | None = None
    """None for model entities; the owning diagram's artifact_id for diagram-only entities."""
    group: str = "uncategorized"

    def __str__(self) -> str:
        return (
            f"[{self.artifact_id}] {self.name}  "
            f"({self.artifact_type} · {self.domain}/{self.subdomain} · "
            f"status={self.status})"
        )


@dataclass(frozen=True)
class ConnectionRecord:
    artifact_id: str
    source: str
    target: str
    conn_type: str
    version: str
    status: str
    path: Path
    extra: dict[str, object]
    content_text: str
    associated_entities: tuple[str, ...] = field(default_factory=tuple)
    src_cardinality: str = ""
    tgt_cardinality: str = ""
    group: str = "uncategorized"

    @property
    def source_ids(self) -> list[str]:
        return [self.source]

    @property
    def target_ids(self) -> list[str]:
        return [self.target]

    def involves(self, entity_id: str) -> bool:
        return entity_id in self.source_ids or entity_id in self.target_ids

    def __str__(self) -> str:
        return f"[{self.artifact_id}]  {self.source} --{self.conn_type}--> {self.target}  (status={self.status})"


@dataclass(frozen=True)
class DiagramRecord:
    artifact_id: str
    artifact_type: str
    name: str
    diagram_type: str
    version: str
    status: str
    path: Path
    extra: dict[str, object]
    group: str = "uncategorized"

    def __str__(self) -> str:
        return f"[{self.artifact_id}] {self.name}  ({self.diagram_type} · status={self.status})"


@dataclass(frozen=True)
class DocumentRecord:
    artifact_id: str
    doc_type: str
    title: str
    status: str
    path: Path
    keywords: tuple[str, ...]
    sections: tuple[str, ...]  # heading text of ## sections, in order
    content_text: str
    extra: dict[str, object]  # frontmatter fields beyond standard ones
    group: str = "uncategorized"


def summary_from_document(rec: DocumentRecord) -> "ArtifactSummary":
    return ArtifactSummary(
        artifact_id=rec.artifact_id,
        artifact_type=rec.doc_type,
        name=rec.title,
        version=str(rec.extra.get("version", "")),
        status=rec.status,
        record_type="document",
        path=rec.path,
        group=rec.group,
    )


STANDARD_DOCUMENT_FIELDS = frozenset(
    {
        "artifact-id",
        "artifact-type",
        "doc-type",
        "title",
        "status",
        "version",
        "last-updated",
        "keywords",
    }
)


@dataclass
class SearchHit:
    score: float
    record_type: Literal["entity", "connection", "diagram", "document"]
    record: EntityRecord | ConnectionRecord | DiagramRecord | DocumentRecord

    def __str__(self) -> str:
        return f"  score={self.score:.3f}  {self.record}"


@dataclass
class SearchResult:
    query: str
    hits: list[SearchHit] = field(default_factory=list)

    def __str__(self) -> str:
        if not self.hits:
            return f"No results for '{self.query}'"
        lines = [f"Search results for '{self.query}' ({len(self.hits)} hits):"]
        for hit in self.hits:
            lines.append(str(hit))
        return "\n".join(lines)


@dataclass(frozen=True)
class ArtifactSummary:
    artifact_id: str
    artifact_type: str
    name: str
    version: str
    status: str
    record_type: Literal["entity", "connection", "diagram", "document"]
    path: Path
    host_diagram_id: str | None = None
    """None for model entities; the owning diagram's artifact_id for diagram-only entities.

    When present, this entity exists only within that diagram's diagram-entities frontmatter.
    It has no standalone file. The ``path`` field points to the diagram file, not an entity
    file. To author or edit this entity, open the owning diagram.
    """
    group: str = "uncategorized"

    def __str__(self) -> str:
        label = f" {self.name}" if self.name else ""
        scope = f" [diagram-only:{self.host_diagram_id}]" if self.host_diagram_id else ""
        return f"[{self.artifact_id}]{label}  ({self.artifact_type} · {self.record_type} · status={self.status}){scope}"


def summary_from_entity(rec: EntityRecord) -> ArtifactSummary:
    return ArtifactSummary(
        artifact_id=rec.artifact_id,
        artifact_type=rec.artifact_type,
        name=rec.name,
        version=rec.version,
        status=rec.status,
        record_type="entity",
        path=rec.path,
        host_diagram_id=rec.host_diagram_id,
        group=rec.group,
    )


def summary_from_connection(rec: ConnectionRecord) -> ArtifactSummary:
    return ArtifactSummary(
        artifact_id=rec.artifact_id,
        artifact_type="connection",
        name="",
        version=rec.version,
        status=rec.status,
        record_type="connection",
        path=rec.path,
        group=rec.group,
    )


def summary_from_diagram(rec: DiagramRecord) -> ArtifactSummary:
    return ArtifactSummary(
        artifact_id=rec.artifact_id,
        artifact_type=rec.artifact_type,
        name=rec.name,
        version=rec.version,
        status=rec.status,
        record_type="diagram",
        path=rec.path,
        group=rec.group,
    )


@runtime_checkable
class SemanticSearchProvider(Protocol):
    def top_k(self, query: str, k: int, *, threshold: float = 0.75) -> list[tuple[float, str]]: ...


STANDARD_ENTITY_FIELDS = frozenset(
    {
        "artifact-id",
        "artifact-type",
        "name",
        "version",
        "status",
        "last-updated",
        "keywords",
    }
)

STANDARD_OUTGOING_FIELDS = frozenset(
    {
        "source-entity",
        "version",
        "status",
        "last-updated",
    }
)

STANDARD_DIAGRAM_FIELDS = frozenset(
    {
        "artifact-id",
        "artifact-type",
        "name",
        "diagram-type",
        "version",
        "status",
        "last-updated",
        "keywords",
    }
)
