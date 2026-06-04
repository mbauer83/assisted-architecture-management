"""Security-signal read-only MCP tools.

Tools registered on arch-assurance-read:
  assurance_list_bom_components  — query ingested BOM components
  assurance_list_vulnerabilities — query vuln findings by PURL/severity
  assurance_security_stats       — counts of BOM/vuln/anchor data
  assurance_scan_ai_candidates   — heuristic AI-BOM candidate scan
  assurance_aibom_export         — emit CycloneDX 1.6 ML-BOM from provided components
  assurance_aibom_coverage       — coverage/gap report for AI-BOM marking
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]

from src.infrastructure.mcp.assurance_mcp.context import get_assurance_context


def register_security_read_tools(server: FastMCP) -> None:
    ctx = get_assurance_context()

    @server.tool(
        name="assurance_list_bom_components",
        description=(
            "List BOM components ingested via assurance_import_bom. "
            "Filter by anchor_entity_id (the architecture entity the BOM is anchored to) "
            "or purl (Package URL for a specific component)."
        ),
    )
    def assurance_list_bom_components(
        anchor_entity_id: str | None = None,
        purl: str | None = None,
    ) -> dict[str, object]:
        components = ctx.connector.list_bom_components(
            anchor_entity_id=anchor_entity_id,
            purl=purl,
        )
        return {"components": components, "count": len(components)}

    @server.tool(
        name="assurance_list_vulnerabilities",
        description=(
            "List vulnerability findings ingested via assurance_import_vulnerabilities. "
            "Filter by purl (Package URL of the affected component) or severity "
            "(CRITICAL, HIGH, MEDIUM, LOW, NONE). "
            "Contextualise these findings against STPA-Sec hazards and loss-scenarios."
        ),
    )
    def assurance_list_vulnerabilities(
        purl: str | None = None,
        severity: str | None = None,
    ) -> dict[str, object]:
        vulns = ctx.connector.list_vulnerabilities(purl=purl, severity=severity)
        return {"vulnerabilities": vulns, "count": len(vulns)}

    @server.tool(
        name="assurance_security_stats",
        description=(
            "Return counts of security signal data: BOM ingests, BOM components, "
            "vulnerability records, and anchor mappings."
        ),
    )
    def assurance_security_stats() -> dict[str, object]:
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
            "Use this to identify where AI-component marking is incomplete."
        ),
    )
    def assurance_aibom_coverage() -> dict[str, object]:
        components = ctx.connector.list_bom_components()
        anchors = ctx.connector.list_anchors()
        unanchored = [c for c in components if not c.get("arch_entity_id")]
        anchor_entity_ids = {str(a["arch_entity_id"]) for a in anchors}
        unanchored_page = unanchored[:50]
        return {
            "total_bom_components": len(components),
            "unanchored_components": len(unanchored),
            "unanchored_truncated": len(unanchored) > 50,
            "anchor_mappings": len(anchors),
            "unanchored": unanchored_page,
            "anchored_entity_ids": sorted(anchor_entity_ids),
            "summary": (
                f"{len(unanchored)} BOM component(s) not linked to an architecture entity. "
                f"Call assurance_set_anchor to map them, or assurance_scan_ai_candidates to "
                f"find candidates."
            ),
        }
