"""Security-signal write MCP tools.

Tools registered on arch-assurance-write:
  assurance_ingest_security_signals — submit a CycloneDX BOM (+ optional OSV
                                      advisories) as one ingest → active snapshot
  assurance_reconcile_aibom         — drift report: modeled vs discovered AI-BOM

Ingestion never writes signal rows directly: the tool assembles a typed bundle and
hands it to the IngestSecuritySignals command, which owns the snapshot lifecycle
(staging → populate → complete → atomic activation) and the mutation+audit
transaction boundary. The signal-mutation capability gate is consulted first, so an
MCP ingest is denied in exactly the configurations a REST or CLI one is.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]

from src.infrastructure.mcp.assurance_mcp.context import get_assurance_context


def register_security_write_tools(server: FastMCP) -> None:
    ctx = get_assurance_context()

    @server.tool(
        name="assurance_ingest_security_signals",
        description=(
            "Ingest security signals for one architecture anchor: submit a CycloneDX BOM "
            "document (and, optionally, the OSV advisory records for its components) as a "
            "single ingest, producing a new ACTIVE signal snapshot that supersedes the "
            "anchor's previous one. Components are classified (directness from the BOM's "
            "dependency graph); each advisory is matched to its component by package "
            "identity and version-range applicability, so not-applicable advisories are "
            "excluded and counted rather than stored as findings. "
            "bom: a parsed CycloneDX 1.x JSON document. vulnerabilities: OSV-schema records "
            "(each needs 'id' and 'affected'); omit for a BOM-only inventory snapshot. "
            "request_id: an idempotency key — resubmitting the same id with the same payload "
            "returns the original outcome and writes nothing; with a different payload it is "
            "a typed conflict. Omit it and one is generated (every call then ingests anew). "
            "Requires the assurance store unlocked with co-located signals."
        ),
    )
    def assurance_ingest_security_signals(
        anchor_entity_id: str,
        bom: dict[str, Any],
        vulnerabilities: list[dict[str, Any]] | None = None,
        request_id: str = "",
        source: str = "",
    ) -> dict[str, object]:
        from src.application.security_signals.capability import SignalMutationDenied  # noqa: PLC0415
        from src.infrastructure.assurance.signal_gate import (  # noqa: PLC0415
            current_signal_mutation_capability,
        )
        from src.infrastructure.assurance.signal_ingest import (  # noqa: PLC0415
            ingest_outcome_payload,
            ingest_supplied_bom,
        )

        capability = current_signal_mutation_capability(unlocked=ctx.is_available())
        if isinstance(capability, SignalMutationDenied):
            if capability.reason_code == "store_locked":
                return ctx.locked_response()
            return {
                "error": "signal_mutation_denied",
                "reason_code": capability.reason_code,
                "message": capability.message,
            }
        snapshot_store = ctx.snapshot_store
        if snapshot_store is None:  # unreachable once the capability allowed the write
            return ctx.locked_response()
        return ingest_outcome_payload(ingest_supplied_bom(
            anchor_entity_id,
            bom,
            records=vulnerabilities or [],
            snapshot_store=snapshot_store,
            request_id=request_id,
            source=source,
        ))

    @server.tool(
        name="assurance_reconcile_aibom",
        description=(
            "Diff a modeled AI-BOM (from the architecture model) against a discovered one "
            "(from a runtime discovery tool or an imported BOM file). "
            "Returns: added (in discovered but not modeled), removed (modeled but not discovered), "
            "and matched components. "
            "modeled_components: list of component dicts from assurance_aibom_export or manually. "
            "discovered_components: list of component dicts from an external AI discovery tool. "
            "Each component needs at least 'name'; 'purl' is used as the identity key if present."
        ),
    )
    def assurance_reconcile_aibom(
        modeled_components: list[dict[str, object]],
        discovered_components: list[dict[str, object]],
    ) -> dict[str, object]:
        from src.infrastructure.assurance._aibom_exporter import reconcile_aibom  # noqa: PLC0415

        return reconcile_aibom(modeled_components, discovered_components)
