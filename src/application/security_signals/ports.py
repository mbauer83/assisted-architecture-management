"""Port for the signal-snapshot store as the IngestSecuritySignals command needs
it. Implemented by the SQLCipher signal-snapshot adapter; low-level lifecycle
transitions exist only here — no transport exposes them directly."""

from __future__ import annotations

from typing import Any, Mapping, Protocol, Sequence

from src.domain.security_signal_snapshot import SnapshotPopulation


class SnapshotStore(Protocol):
    def find_snapshot_by_request(self, anchor_entity_id: str, request_id: str) -> Mapping[str, Any] | None: ...

    def create_staging_snapshot(
        self,
        *,
        snapshot_id: str,
        anchor_entity_id: str,
        request_id: str,
        request_payload_digest: str,
        bom_digest: str = "",
        bom_serial: str = "",
        bom_version: str = "",
        generator_metadata: Mapping[str, object] | None = None,
        source_metadata: Mapping[str, object] | None = None,
        diagnostics: Mapping[str, object] | None = None,
    ) -> None: ...

    def populate_snapshot(
        self,
        snapshot_id: str,
        *,
        components: Sequence[Mapping[str, object]],
        findings: Sequence[Mapping[str, object]],
    ) -> SnapshotPopulation: ...

    def complete_snapshot(self, snapshot_id: str) -> None: ...

    def activate_snapshot(self, snapshot_id: str) -> Mapping[str, Any]: ...

    def fail_snapshot(self, snapshot_id: str, *, reason: str) -> None: ...
