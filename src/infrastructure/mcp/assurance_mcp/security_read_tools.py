"""Security-signal read-only MCP tools (SC-2/SC-4 updates).

Tools registered on arch-assurance-read:
  assurance_list_bom_components  — query ingested BOM components
  assurance_list_vulnerabilities — query vuln findings by PURL/severity
  assurance_security_stats       — counts of BOM/vuln/anchor data
  assurance_scan_ai_candidates   — heuristic AI-BOM candidate scan
  assurance_aibom_export         — emit CycloneDX 1.6 ML-BOM from provided components JSON
  assurance_aibom_coverage       — coverage/gap report for AI-BOM marking

SC-2: BOM/vuln tools are gated behind store-unlock when signals_backend is
      confidential (sqlcipher-colocated or encrypted). Locked ⇒ signals_locked_response.
SC-4: Results are filtered by max_classification TLP ceiling before return;
      withheld counts are emitted to the exposure log.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]

from src.application.assurance_exposure import AssuranceExposurePolicy
from src.infrastructure.mcp.assurance_mcp.context import (
    _exposure_log,
    get_assurance_context,
)


def register_security_read_tools(server: FastMCP) -> None:
    ctx = get_assurance_context()

    @server.tool(
        name="assurance_list_bom_components",
        description=(
            "List BOM components ingested via assurance_import_bom. "
            "Filter by anchor_entity_id (the architecture entity the BOM is anchored to) "
            "or purl (Package URL for a specific component). "
            "Requires the assurance store to be unlocked when using confidential signals storage."
        ),
    )
    def assurance_list_bom_components(
        anchor_entity_id: str | None = None,
        purl: str | None = None,
    ) -> dict[str, object]:
        if not ctx.signals_available():
            return ctx.signals_locked_response()
        policy = AssuranceExposurePolicy(ctx.max_classification, True)
        components = ctx.connector.list_bom_components(
            anchor_entity_id=anchor_entity_id,
            purl=purl,
        )
        kept, withheld = policy.filter_security_records(components)
        if withheld:
            _exposure_log.info(
                "list_bom_components: ceiling=%s returned=%d withheld=%d",
                ctx.max_classification, len(kept), withheld,
            )
        return {"components": kept, "count": len(kept), "withheld": withheld}

    @server.tool(
        name="assurance_list_vulnerabilities",
        description=(
            "List vulnerability findings ingested via assurance_import_vulnerabilities. "
            "Filter by purl (Package URL of the affected component) or severity "
            "(CRITICAL, HIGH, MEDIUM, LOW, NONE). "
            "Contextualise these findings against STPA-Sec hazards and loss-scenarios. "
            "Requires the assurance store to be unlocked when using confidential signals storage."
        ),
    )
    def assurance_list_vulnerabilities(
        purl: str | None = None,
        severity: str | None = None,
    ) -> dict[str, object]:
        if not ctx.signals_available():
            return ctx.signals_locked_response()
        policy = AssuranceExposurePolicy(ctx.max_classification, True)
        vulns = ctx.connector.list_vulnerabilities(purl=purl, severity=severity)
        kept, withheld = policy.filter_security_records(vulns)
        if withheld:
            _exposure_log.info(
                "list_vulnerabilities: ceiling=%s returned=%d withheld=%d",
                ctx.max_classification, len(kept), withheld,
            )
        return {"vulnerabilities": kept, "count": len(kept), "withheld": withheld}

    @server.tool(
        name="assurance_security_stats",
        description=(
            "Return counts of security signal data: BOM ingests, BOM components, "
            "vulnerability records, and anchor mappings. "
            "Requires the assurance store to be unlocked when using confidential signals storage."
        ),
    )
    def assurance_security_stats() -> dict[str, object]:
        if not ctx.signals_available():
            return ctx.signals_locked_response()
        return ctx.connector.get_stats()

    @server.tool(
        name="assurance_scan_ai_candidates",
        description=(
            "Heuristic AI-BOM candidate scan over a list of architecture entity dicts. "
            "Ranks entities by name patterns (gpt/claude/llm/embedding/mcp-server/agent/rag/vector), "
            "type, and connection structure. Returns a ranked list for the user/agent to confirm. "
            "Results are assistive, never authoritative — confirm before marking. "
            "Pass the output of arch-repo-read list/query tools as 'entities'."
        ),
    )
    def assurance_scan_ai_candidates(
        entities: list[dict[str, object]],
    ) -> dict[str, object]:
        from src.infrastructure.assurance.ai_candidate_scanner import scan_candidates  # noqa: PLC0415

        candidates = scan_candidates(entities)
        return {
            "candidates": candidates,
            "count": len(candidates),
            "note": (
                "These are heuristic suggestions only. "
                "Confirm each candidate before calling assurance_mark_ai_component."
            ),
        }

    @server.tool(
        name="assurance_aibom_export",
        description=(
            "Emit a CycloneDX 1.6 ML-BOM/ASBOM JSON document from a list of AI-component dicts. "
            "Each component dict should have: name (required), purl, cpe, ai_role "
            "(machine-learning-model | dataset | inference-service | mcp-server | tool | "
            "agent | orchestrator | prompt | guardrail | vector-store | rag-pipeline), "
            "version, provider, hosted, external, arch_entity_id. "
            "The emitted BOM can be sealed into the archive via assurance_seal_baseline."
        ),
    )
    def assurance_aibom_export(
        ai_components: list[dict[str, object]],
        notes: str = "",
    ) -> dict[str, object]:
        from src.infrastructure.assurance._aibom_exporter import build_cyclonedx_16  # noqa: PLC0415

        bom = build_cyclonedx_16(ai_components, notes=notes)
        return {"bom": bom, "component_count": len(ai_components)}

    @server.tool(
        name="assurance_aibom_coverage",
        description=(
            "AI-BOM coverage/gap report: shows BOM components that have no anchor mapping "
            "(not linked to an architecture entity) and anchor mappings for entities "
            "that are not yet marked with an ai_role. "
            "Use this to identify where AI-component marking is incomplete. "
            "Requires the assurance store to be unlocked when using confidential signals storage."
        ),
    )
    def assurance_aibom_coverage() -> dict[str, object]:
        if not ctx.signals_available():
            return ctx.signals_locked_response()
        from src.application.assurance_queries import aibom_coverage  # noqa: PLC0415

        policy = AssuranceExposurePolicy(ctx.max_classification, True)
        components, comp_withheld = policy.filter_security_records(ctx.connector.list_bom_components())
        anchors, _ = policy.filter_security_records(ctx.connector.list_anchors())
        report = aibom_coverage(components, anchors)
        report["withheld_components"] = comp_withheld
        report["summary"] = (
            f"{report['summary']} "
            "Call assurance_set_anchor to map them, or assurance_scan_ai_candidates to "
            "find candidates."
        )
        return report
