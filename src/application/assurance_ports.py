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

    # ── Analysis aggregate ──────────────────────────────────────────────────────
    # An analysis is the aggregate root of a unit of STPA/CAST/GRC work: every
    # node belongs to one analysis, and an analysis is anchored to one
    # architecture artifact. Application services enforce the invariants.

    def create_analysis(
        self,
        name: str,
        method: str,
        architecture_anchor_id: str = "",
        *,
        tlp: str = "TLP:WHITE",
        status: str = "draft",
    ) -> str: ...

    def get_analysis(self, analysis_id: str) -> dict[str, object] | None: ...

    def list_analyses(
        self,
        *,
        method: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, object]]: ...

    def update_analysis(self, analysis_id: str, **attrs: object) -> None: ...

    # ── Node CRUD ─────────────────────────────────────────────────────────────

    def get_node(self, node_id: str) -> dict[str, object] | None: ...

    def list_nodes(
        self,
        *,
        node_type: str | None = None,
        status: str | None = None,
        concern_class: str | None = None,
        tlp: str | None = None,
        analysis_id: str | None = None,
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
        analysis_id: str | None = None,
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

    def search_nodes(
        self,
        query: str,
        *,
        limit: int = 20,
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


@runtime_checkable
class SecuritySignalConnector(Protocol):
    """Port for external security signals: SBOM, vulnerability feeds, AI-BOM.

    Adapters: SQLiteSecurityConnector (default). Never gates the core assurance flow.
    Read-mostly — importers pull external data in; export_aibom / reconcile_aibom are
    the bidirectional operations (model → CycloneDX, discovered → drift report).
    """

    def import_bom(
        self,
        bom_data: dict[str, object],
        *,
        anchor_entity_id: str,
        bom_format: str = "cyclonedx",
        source_file: str = "",
    ) -> dict[str, object]: ...

    def list_bom_components(
        self,
        *,
        anchor_entity_id: str | None = None,
        purl: str | None = None,
    ) -> list[dict[str, object]]: ...

    def import_vulnerabilities(
        self,
        vuln_records: list[dict[str, object]],
        *,
        source: str = "osv",
    ) -> dict[str, object]: ...

    def list_vulnerabilities(
        self,
        *,
        purl: str | None = None,
        severity: str | None = None,
    ) -> list[dict[str, object]]: ...

    def set_anchor(
        self,
        component_ref: str,
        arch_entity_id: str,
        *,
        ref_type: str = "purl",
    ) -> None: ...

    def list_anchors(
        self,
        *,
        arch_entity_id: str | None = None,
    ) -> list[dict[str, object]]: ...

    def get_stats(self) -> dict[str, object]: ...


@runtime_checkable
class WORMAssuranceArchive(AssuranceArchive, Protocol):
    """Extended archive port with WORM semantics, legal-hold, and crypto-shredding.

    Opt-in for regulated deployments. The base AssuranceArchive stores records;
    this port additionally supports per-subject envelope encryption, legal holds,
    shredding (DEK destruction), and RFC 3161 timestamp tokens on sealed baselines.
    """

    def provision_subject_key(self, subject_id: str) -> str: ...

    def encrypt_payload(self, subject_id: str, plaintext: str) -> str: ...

    def decrypt_payload(self, subject_id: str, ciphertext_hex: str) -> str: ...

    def shred_subject(self, subject_id: str, *, reason: str = "") -> dict[str, object]: ...

    def set_legal_hold(
        self,
        baseline_id: str,
        *,
        held_by: str = "",
        reason: str = "",
    ) -> str: ...

    def release_legal_hold(self, hold_id: str, *, released_by: str = "") -> None: ...

    def list_legal_holds(self, *, active_only: bool = True) -> list[dict[str, object]]: ...

    def add_timestamp_token(self, baseline_id: str, token_der_hex: str) -> None: ...
