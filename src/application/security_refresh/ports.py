"""Port for the refresh-run store as the RefreshSecuritySignals command needs
it. Implemented by the SQLCipher refresh-run adapter; low-level lifecycle
transitions exist only here — no transport exposes them directly."""

from __future__ import annotations

from typing import Any, Mapping, Protocol, Sequence


class RefreshRunStore(Protocol):
    def find_run_by_request(self, anchor_entity_id: str, request_id: str) -> Mapping[str, Any] | None: ...

    def create_staging_run(
        self,
        *,
        run_id: str,
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

    def populate_run(
        self,
        run_id: str,
        *,
        components: Sequence[Mapping[str, object]],
        findings: Sequence[Mapping[str, object]],
    ) -> Mapping[str, str]: ...

    def complete_run(self, run_id: str) -> None: ...

    def activate_run(self, run_id: str) -> Mapping[str, Any]: ...

    def fail_run(self, run_id: str, *, reason: str) -> None: ...
