"""The one submission boundary for security-signal ingestion.

Every ingest surface — the dogfooding script, the REST route, the MCP tool —
assembles a typed bundle here, submits it through the same serialised write, and
renders the outcome through the same projection, so run-id policy, the
single-writer boundary, and the response shape each have exactly one definition.
Acquisition is injected (`acquire`): live OSV querying for the script,
caller-supplied records for the REST/MCP surfaces. No surface touches the run
lifecycle directly — the RefreshSecuritySignals command owns staging → populate
→ complete → activate.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any, Callable, Mapping, Sequence

from src.application.security_refresh.bundle_assembly import (
    AcquisitionInputs,
    attach_findings,
    prepare_components,
)
from src.application.security_refresh.command import (
    RefreshActivated,
    RefreshBundle,
    RefreshConflict,
    RefreshFailed,
    RefreshInvalid,
    RefreshReplayed,
    RefreshResult,
    refresh_security_signals,
)
from src.application.security_refresh.ports import RefreshRunStore

Acquire = Callable[[Sequence[Mapping[str, str]]], AcquisitionInputs]


def new_run_id() -> str:
    return f"RUN@{uuid.uuid4().hex[:16]}"


def new_request_id() -> str:
    return f"ingest-{uuid.uuid4()}"


def assemble_bundle(
    anchor_entity_id: str,
    sbom_data: Mapping[str, Any],
    *,
    acquire: Acquire,
    request_id: str = "",
    generator_metadata: Mapping[str, object] | None = None,
    source_metadata: Mapping[str, object] | None = None,
) -> RefreshBundle:
    """Parse a CycloneDX document, classify its components, acquire vulnerability
    data through the injected strategy, and return the complete typed bundle."""
    from src.infrastructure.assurance._sbom_parser import parse_bom  # noqa: PLC0415

    bom_digest = hashlib.sha256(
        json.dumps(dict(sbom_data), sort_keys=True, default=str).encode()).hexdigest()
    meta, parsed = parse_bom(dict(sbom_data))
    assembled = prepare_components(meta, parsed)
    attach_findings(assembled, acquire(assembled.queryable))
    return RefreshBundle(
        anchor_entity_id=anchor_entity_id,
        request_id=request_id or new_request_id(),
        components=tuple(assembled.components),
        findings=tuple(assembled.findings),
        diagnostics=assembled.diagnostics,
        generator_metadata=dict(generator_metadata or {}),
        source_metadata=dict(source_metadata or {}),
        bom_digest=bom_digest,
        bom_serial=str(meta.get("bom_serial") or ""),
        bom_version=str(meta.get("bom_version") or ""),
    )


def submit_bundle(bundle: RefreshBundle, *, run_store: RefreshRunStore) -> RefreshResult:
    """Execute one ingest on the serialised assurance writer."""
    from src.infrastructure.assurance.write_serialization import run_write  # noqa: PLC0415

    return run_write(lambda: refresh_security_signals(
        bundle, store=run_store, new_run_id=new_run_id,
    ))


def ingest_supplied_bom(
    anchor_entity_id: str,
    bom: Mapping[str, Any],
    *,
    records: Sequence[Mapping[str, Any]],
    run_store: RefreshRunStore,
    request_id: str = "",
    source: str = "",
) -> RefreshResult:
    """Ingest a caller-supplied BOM (+ advisories) for one anchor.

    The whole act behind both the REST route and the MCP tool: assemble the bundle
    with supplied-record acquisition, then submit it. Callers gate on the
    signal-mutation capability first — they render a denial differently, but the
    ingest itself is defined once, here.
    """
    from src.application.security_refresh.supplied_acquisition import (  # noqa: PLC0415
        acquisition_from_records,
    )

    bundle = assemble_bundle(
        anchor_entity_id,
        bom,
        acquire=lambda queryable: acquisition_from_records(queryable, records),
        request_id=request_id,
        generator_metadata={"generator": "supplied-bom"},
        source_metadata={"vulnerability_source": source or "caller-supplied"},
    )
    return submit_bundle(bundle, run_store=run_store)


# HTTP status per ingest outcome; the MCP surface reports the same `status`
# string and ignores the code, so both transports stay in lockstep.
INGEST_STATUS_CODES: Mapping[str, int] = {
    "activated": 200,
    "replayed": 200,  # idempotent replay: the stored outcome, nothing written
    "invalid": 422,
    "conflict": 409,  # request_id reused with a different payload
    "failed": 500,
}


def ingest_outcome_payload(result: RefreshResult) -> dict[str, object]:
    """Project the command's typed outcome onto the shared response body."""
    match result:
        case RefreshActivated(run_id, superseded, components, findings):
            return {
                "status": "activated",
                "snapshot_id": run_id,
                "superseded_snapshot_id": superseded,
                "component_count": components,
                "finding_count": findings,
            }
        case RefreshInvalid(errors):
            return {
                "status": "invalid",
                "errors": [{"field": e.field, "message": e.message} for e in errors],
            }
        case RefreshReplayed(run_id, outcome, message):
            return {
                "status": "replayed",
                "snapshot_id": run_id,
                "stored_outcome": outcome,
                "message": message,
            }
        case RefreshConflict(run_id, message):
            return {"status": "conflict", "snapshot_id": run_id, "message": message}
        case RefreshFailed(run_id, reason):
            return {"status": "failed", "snapshot_id": run_id, "reason": reason}
