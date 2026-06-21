"""Unlock-gated HTTP write endpoints for the confidential assurance store.

All mutation endpoints share one pattern:
  1. Build an AssuranceMutationPolicy from the current context.
  2. Check locked → 423.
  3. Call the shared application use case (assurance_mutations).
  4. Translate MutationOk/MutationLocked/MutationNotFound to HTTP.
  5. Return with Cache-Control: no-store.

Response semantics:
  - Locked store        → 423 Locked
  - Node/edge not found → 404
  - Write TLP > ceiling → 403 (ForbiddenWrite, writes only)
  - Success             → 200 with payload + optional verification_findings
  - All responses       → Cache-Control: no-store
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.application import assurance_model_bind as model_bind
from src.application import assurance_mutations as mutations
from src.infrastructure.gui.routers._arch_entity_creator import GuiArchitectureEntityCreator
from src.infrastructure.mcp.assurance_mcp.context import get_assurance_context

write_router = APIRouter()

_NO_STORE = "no-store"


def _locked() -> JSONResponse:
    return JSONResponse(
        status_code=423,
        content={"error": "assurance_store_locked", "message": (
            "The confidential assurance store is not unlocked. "
            "Run `arch-assurance unlock` to enable assurance tools."
        )},
        headers={"Cache-Control": _NO_STORE},
    )


def _not_found(artifact_id: str) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"error": "not_found", "artifact_id": artifact_id},
        headers={"Cache-Control": _NO_STORE},
    )


def _ok(result: mutations.MutationOk) -> JSONResponse:
    out: dict[str, object] = dict(result.payload)
    if result.findings:
        out["verification_findings"] = result.findings
    return JSONResponse(content=out, headers={"Cache-Control": _NO_STORE})


def _translate(result: mutations.MutationResult) -> JSONResponse:
    if isinstance(result, mutations.MutationLocked):
        return _locked()
    if isinstance(result, mutations.MutationNotFound):
        return _not_found(result.artifact_id)
    return _ok(result)


# ── Request bodies ─────────────────────────────────────────────────────────────


class CreateNodeBody(BaseModel):
    node_type: str
    name: str
    status: str = "draft"
    tlp: str = "TLP:WHITE"
    concern_class: str | None = None
    disposition: str | None = None
    uca_type: str | None = None
    binding_status: str | None = None
    node_role: str | None = None
    analysis_id: str | None = None
    content_text: str = ""
    attributes: dict[str, object] | None = None


class EditNodeBody(BaseModel):
    name: str | None = None
    status: str | None = None
    tlp: str | None = None
    concern_class: str | None = None
    disposition: str | None = None
    uca_type: str | None = None
    binding_status: str | None = None
    node_role: str | None = None
    content_text: str | None = None
    attributes: dict[str, object] | None = None


class AddEdgeBody(BaseModel):
    source_id: str
    target_id: str
    conn_type: str
    attributes: dict[str, object] | None = None


class SealBaselineBody(BaseModel):
    notes: str = ""
    analysis_id: str | None = None


class RegisterArchRefBody(BaseModel):
    assurance_node_id: str
    arch_artifact_id: str
    ref_type: str


class ModelThisBody(BaseModel):
    assurance_node_id: str
    suggested_arch_type: str
    suggested_name: str
    domain: str = "application"
    # When true, do not create the architecture entity here — return a task for an
    # architecture-write session (separation of duties).
    separation_of_duties: bool = False


class ImportBomBody(BaseModel):
    bom_data: dict[str, object]
    anchor_entity_id: str
    source_file: str = ""
    bom_format: str = "cyclonedx"


class ImportVulnsBody(BaseModel):
    vuln_records: list[dict[str, object]]
    source: str = "osv"


class SetAnchorBody(BaseModel):
    component_ref: str
    arch_entity_id: str
    ref_type: str = "purl"


# ── Node endpoints ─────────────────────────────────────────────────────────────


@write_router.post("/api/assurance/nodes", status_code=200)
def create_node(body: CreateNodeBody) -> JSONResponse:
    ctx = get_assurance_context()
    return _translate(mutations.create_node(
        ctx.store, ctx.archive,
        node_type=body.node_type, name=body.name, status=body.status, tlp=body.tlp,
        concern_class=body.concern_class, disposition=body.disposition,
        uca_type=body.uca_type, binding_status=body.binding_status,
        node_role=body.node_role, analysis_id=body.analysis_id,
        content_text=body.content_text, attributes=body.attributes,
    ))


@write_router.patch("/api/assurance/nodes/{node_id}", status_code=200)
def edit_node(node_id: str, body: EditNodeBody) -> JSONResponse:
    ctx = get_assurance_context()
    return _translate(mutations.edit_node(
        ctx.store, ctx.archive,
        node_id=node_id, name=body.name, status=body.status, tlp=body.tlp,
        concern_class=body.concern_class, disposition=body.disposition,
        uca_type=body.uca_type, binding_status=body.binding_status,
        node_role=body.node_role, content_text=body.content_text,
        attributes=body.attributes,
    ))


@write_router.delete("/api/assurance/nodes/{node_id}", status_code=200)
def delete_node(node_id: str) -> JSONResponse:
    ctx = get_assurance_context()
    return _translate(mutations.delete_node(ctx.store, ctx.archive, node_id=node_id))


# ── Edge endpoints ─────────────────────────────────────────────────────────────


@write_router.post("/api/assurance/edges", status_code=200)
def add_edge(body: AddEdgeBody) -> JSONResponse:
    ctx = get_assurance_context()
    return _translate(mutations.add_edge(
        ctx.store, ctx.archive,
        source_id=body.source_id, target_id=body.target_id,
        conn_type=body.conn_type, attributes=body.attributes,
    ))


@write_router.delete("/api/assurance/edges/{edge_id}", status_code=200)
def delete_edge(edge_id: str) -> JSONResponse:
    ctx = get_assurance_context()
    return _translate(mutations.delete_edge(ctx.store, ctx.archive, edge_id=edge_id))


# ── Baselines ─────────────────────────────────────────────────────────────────


@write_router.post("/api/assurance/baselines/seal", status_code=200)
def seal_baseline(body: SealBaselineBody) -> JSONResponse:
    ctx = get_assurance_context()
    if not ctx.is_available():
        return _locked()
    result = ctx.archive.seal_baseline(notes=body.notes, analysis_id=body.analysis_id)
    return JSONResponse(content=result, headers={"Cache-Control": _NO_STORE})  # type: ignore[arg-type]


# ── Architecture references ────────────────────────────────────────────────────


@write_router.post("/api/assurance/arch-refs", status_code=200)
def register_arch_ref(body: RegisterArchRefBody) -> JSONResponse:
    ctx = get_assurance_context()
    return _translate(mutations.register_arch_ref(
        ctx.store, ctx.archive,
        assurance_node_id=body.assurance_node_id,
        arch_artifact_id=body.arch_artifact_id,
        ref_type=body.ref_type,
    ))


# ── Model-this (create+bind, or task for an architecture-write session) ───────────


def _translate_bind(result: model_bind.ModelBindResult) -> JSONResponse:
    if isinstance(result, model_bind.BindLocked):
        return _locked()
    if isinstance(result, model_bind.BindNotFound):
        return _not_found(result.assurance_node_id)
    if isinstance(result, model_bind.BindInvalid):
        status = 409 if result.error == "invalid_binding_status" else 400
        return JSONResponse(
            status_code=status,
            content={"error": result.error, "message": result.message},
            headers={"Cache-Control": _NO_STORE},
        )
    if isinstance(result, model_bind.TaskRequired):
        return JSONResponse(
            content={"outcome": "task_required", **result.spec},
            headers={"Cache-Control": _NO_STORE},
        )
    payload: dict[str, object] = {
        "outcome": "bound",
        "assurance_node_id": result.assurance_node_id,
        "arch_artifact_id": result.arch_artifact_id,
    }
    if result.findings:
        payload["verification_findings"] = result.findings
    return JSONResponse(content=payload, headers={"Cache-Control": _NO_STORE})


@write_router.post("/api/assurance/model-this", status_code=200)
def model_this(body: ModelThisBody) -> JSONResponse:
    ctx = get_assurance_context()
    if not ctx.is_available():
        return _locked()
    creator = None if body.separation_of_duties else GuiArchitectureEntityCreator()
    result = model_bind.model_and_bind(
        ctx.store, ctx.archive,
        assurance_node_id=body.assurance_node_id,
        suggested_arch_type=body.suggested_arch_type,
        suggested_name=body.suggested_name,
        domain=body.domain,
        arch_creator=creator,
    )
    return _translate_bind(result)


# ── Security signals ──────────────────────────────────────────────────────────


@write_router.post("/api/assurance/bom/import", status_code=200)
def import_bom(body: ImportBomBody) -> JSONResponse:
    ctx = get_assurance_context()
    if not ctx.signals_available():
        return _locked()
    result = ctx.connector.import_bom(
        body.bom_data,
        anchor_entity_id=body.anchor_entity_id,
        bom_format=body.bom_format,
        source_file=body.source_file,
    )
    ctx.archive.append(
        "IMPORT_BOM",
        payload={
            "anchor_entity_id": body.anchor_entity_id,
            "bom_format": body.bom_format,
            "source_file": body.source_file,
        },
    )
    return JSONResponse(content=result, headers={"Cache-Control": _NO_STORE})  # type: ignore[arg-type]


@write_router.post("/api/assurance/vulnerabilities/import", status_code=200)
def import_vulnerabilities(body: ImportVulnsBody) -> JSONResponse:
    ctx = get_assurance_context()
    if not ctx.signals_available():
        return _locked()
    result = ctx.connector.import_vulnerabilities(body.vuln_records, source=body.source)
    ctx.archive.append(
        "IMPORT_VULNERABILITIES",
        payload={"source": body.source, "record_count": len(body.vuln_records)},
    )
    return JSONResponse(content=result, headers={"Cache-Control": _NO_STORE})  # type: ignore[arg-type]


@write_router.post("/api/assurance/anchors", status_code=200)
def set_anchor(body: SetAnchorBody) -> JSONResponse:
    ctx = get_assurance_context()
    if not ctx.signals_available():
        return _locked()
    ctx.connector.set_anchor(body.component_ref, body.arch_entity_id, ref_type=body.ref_type)
    ctx.archive.append(
        "SET_ANCHOR",
        payload={
            "component_ref": body.component_ref,
            "arch_entity_id": body.arch_entity_id,
            "ref_type": body.ref_type,
        },
    )
    return JSONResponse(
        content={
            "component_ref": body.component_ref,
            "arch_entity_id": body.arch_entity_id,
            "ref_type": body.ref_type,
            "status": "anchored",
        },
        headers={"Cache-Control": _NO_STORE},
    )
