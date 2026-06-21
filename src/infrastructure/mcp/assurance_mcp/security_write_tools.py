"""Security-signal write MCP tools.

Tools registered on arch-assurance-write:
  assurance_import_bom            — ingest a CycloneDX/SPDX BOM (inline JSON)
  assurance_import_vulnerabilities — ingest OSV/NVD/GitHub Advisory vulnerability records
  assurance_set_anchor            — map a component PURL to an architecture entity
  assurance_reconcile_aibom       — drift report: modeled vs discovered AI-BOM

All write tools gate on the store being unlocked and append to the audit log.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]

from src.infrastructure.mcp.assurance_mcp.context import get_assurance_context


def register_security_write_tools(server: FastMCP) -> None:
    ctx = get_assurance_context()

    @server.tool(
        name="assurance_import_bom",
        description=(
            "Ingest a CycloneDX or SPDX BOM (as a JSON dict) and map its components to "
            "architecture entities via existing anchor_mappings. "
            "anchor_entity_id is the architecture entity ID this BOM belongs to (e.g. the "
            "application-component or artifact representing the software product). "
            "Re-ingesting the same BOM serial+version is idempotent (upsert). "
            "After ingestion, call assurance_set_anchor to map individual components."
        ),
    )
    def assurance_import_bom(
        bom_data: dict[str, object],
        anchor_entity_id: str,
        source_file: str = "",
        bom_format: str = "cyclonedx",
    ) -> dict[str, object]:
        if not ctx.is_available():
            return ctx.locked_response()
        result = ctx.connector.import_bom(
            bom_data,
            anchor_entity_id=anchor_entity_id,
            bom_format=bom_format,
            source_file=source_file,
        )
        ctx.archive.append(
            "IMPORT_BOM",
            payload={
                "anchor_entity_id": anchor_entity_id,
                "bom_format": bom_format,
                "source_file": source_file,
            },
        )
        return result  # type: ignore[return-value]

    @server.tool(
        name="assurance_import_vulnerabilities",
        description=(
            "Ingest vulnerability records (OSV / NVD / GitHub Advisory / CISA-KEV format). "
            "Each record must have an 'id' or 'ext_id' field (e.g. CVE-2026-xxxxx, GHSA-xxxx). "
            "Optional fields: purl (affected component), severity, cvss_score, vex_status "
            "(affected | not_affected | fixed | under_investigation), vex_justification, "
            "summary/description. "
            "source identifies the feed (osv | nvd | ghsa | cisa-kev | dependencytrack)."
        ),
    )
    def assurance_import_vulnerabilities(
        vuln_records: list[dict[str, object]],
        source: str = "osv",
    ) -> dict[str, object]:
        if not ctx.is_available():
            return ctx.locked_response()
        result = ctx.connector.import_vulnerabilities(vuln_records, source=source)
        ctx.archive.append(
            "IMPORT_VULNERABILITIES",
            payload={"source": source, "record_count": len(vuln_records)},
        )
        return result  # type: ignore[return-value]

    @server.tool(
        name="assurance_set_anchor",
        description=(
            "Map a component reference (typically a Package URL / PURL) to an architecture entity. "
            "Persistent anchor mappings are applied automatically on future BOM re-ingestion, "
            "so the component is linked to the architecture entity without manual intervention. "
            "ref_type: 'purl' (default) | 'cpe' | 'name'. "
            "Example purl: pkg:pypi/requests@2.31.0"
        ),
    )
    def assurance_set_anchor(
        component_ref: str,
        arch_entity_id: str,
        ref_type: str = "purl",
    ) -> dict[str, object]:
        if not ctx.is_available():
            return ctx.locked_response()
        ctx.connector.set_anchor(component_ref, arch_entity_id, ref_type=ref_type)
        ctx.archive.append(
            "SET_ANCHOR",
            payload={
                "component_ref": component_ref,
                "arch_entity_id": arch_entity_id,
                "ref_type": ref_type,
            },
        )
        return {
            "component_ref": component_ref,
            "arch_entity_id": arch_entity_id,
            "ref_type": ref_type,
            "status": "anchored",
        }

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
