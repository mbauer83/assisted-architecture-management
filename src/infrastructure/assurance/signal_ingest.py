"""The one submission boundary for security-signal ingestion.

Every ingest surface — the dogfooding script, the MCP tool — assembles a typed
bundle here and submits it through the same serialised write, so run-id policy
and the single-writer boundary have exactly one definition. Acquisition is
injected (`acquire`): live OSV querying for the script, caller-supplied records
for the MCP tool. Neither surface touches the run lifecycle directly — the
RefreshSecuritySignals command owns staging → populate → complete → activate.
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
    RefreshBundle,
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
