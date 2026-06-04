"""Hexagonal ports for the confidential assurance capability.

These Protocols define the boundary between application logic and infrastructure.
Adapters live in src/infrastructure/assurance/.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class ConfidentialAssuranceStore(Protocol):
    """Port for the confidential assurance graph store.

    The live source of truth for all STPA/CAST/GRC entities and edges.
    Adapters: SQLCipherAssuranceStore (default), FakeAssuranceStore (tests).
    """

    def is_unlocked(self) -> bool: ...

    def unlock(self) -> None: ...

    def lock(self) -> None: ...

    # ── Node CRUD ─────────────────────────────────────────────────────────────

    def get_node(self, node_id: str) -> dict[str, object] | None: ...

    def list_nodes(
        self,
        *,
        node_type: str | None = None,
        status: str | None = None,
        concern_class: str | None = None,
        tlp: str | None = None,
    ) -> list[dict[str, object]]: ...

    def create_node(
        self,
        node_type: str,
        name: str,
        *,
        status: str = "draft",
        tlp: str = "TLP:WHITE",
        concern_class: str | None = None,
        disposition: str | None = None,
        uca_type: str | None = None,
        binding_status: str | None = None,
        node_role: str | None = None,
        attributes: dict[str, object] | None = None,
        content: str = "",
    ) -> str: ...

    def update_node(self, node_id: str, **attrs: object) -> None: ...

    def delete_node(self, node_id: str) -> None: ...

    # ── Edge CRUD ─────────────────────────────────────────────────────────────

    def list_edges(
        self,
        *,
        source_id: str | None = None,
        target_id: str | None = None,
        conn_type: str | None = None,
    ) -> list[dict[str, object]]: ...

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        conn_type: str,
        *,
        attributes: dict[str, object] | None = None,
    ) -> str: ...

    def remove_edge(self, edge_id: str) -> None: ...

    # ── Architecture cross-references ──────────────────────────────────────────

    def register_arch_ref(
        self,
        assurance_node_id: str,
        arch_artifact_id: str,
        ref_type: str,
    ) -> None: ...

    def mark_arch_ref_resolved(
        self,
        assurance_node_id: str,
        arch_artifact_id: str,
        ref_type: str,
    ) -> None: ...

    def list_arch_refs(
        self,
        *,
        assurance_node_id: str | None = None,
        arch_artifact_id: str | None = None,
    ) -> list[dict[str, object]]: ...

    # ── Stats ─────────────────────────────────────────────────────────────────

    def stats(self) -> dict[str, object]: ...


@runtime_checkable
class AssuranceArchive(Protocol):
    """Port for the append-only, hash-chained audit log.

    Separate from the live store — immutable records satisfying EU AI Act Art. 12/18/19/26.
    """

    def append(
        self,
        operation: str,
        *,
        node_id: str | None = None,
        payload: dict[str, object] | None = None,
    ) -> dict[str, object]: ...

    def seal_baseline(
        self,
        *,
        notes: str = "",
        analysis_id: str | None = None,
    ) -> dict[str, object]: ...

    def verify_chain(self) -> bool: ...

    def list_entries(
        self,
        *,
        since_seq: int = 0,
        operation: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, object]]: ...

    def list_baselines(self) -> list[dict[str, object]]: ...

    def head(self) -> dict[str, object] | None: ...
