"""SBOM parsing — CycloneDX JSON and SPDX JSON component extraction.

Returns a normalised list of component dicts regardless of input format.
Each component dict has: purl, cpe, name, version, component_type, group_name.
"""

from __future__ import annotations


def _normalise_cdx_component(comp: dict[str, object]) -> dict[str, object]:
    return {
        "purl": str(comp.get("purl") or ""),
        "cpe": str(comp.get("cpe") or ""),
        "name": str(comp.get("name") or ""),
        "version": str(comp.get("version") or ""),
        "component_type": str(comp.get("type") or "library"),
        "group_name": str(comp.get("group") or ""),
    }


def parse_cyclonedx(data: dict[str, object]) -> tuple[dict[str, object], list[dict[str, object]]]:
    """Parse a CycloneDX JSON BOM.

    Returns (metadata, components) where metadata contains serialNumber and version.
    """
    meta: dict[str, object] = {
        "bom_serial": str(data.get("serialNumber") or ""),
        "bom_version": str(data.get("version") or "1"),
        "bom_format": "cyclonedx",
    }
    raw_components = data.get("components")
    if not isinstance(raw_components, list):
        raw_components = []
    components = [
        _normalise_cdx_component(c) for c in raw_components if isinstance(c, dict)
    ]
    # Also pick up top-level metadata.component if present (the root component)
    meta_block = data.get("metadata")
    if isinstance(meta_block, dict):
        root_comp = meta_block.get("component")
        if isinstance(root_comp, dict):
            components.insert(0, _normalise_cdx_component(root_comp))
    return meta, components


def _purl_from_spdx_package(pkg: dict[str, object]) -> str:
    """Best-effort PURL extraction from an SPDX package record."""
    ext_refs = pkg.get("externalRefs")
    if isinstance(ext_refs, list):
        for ref in ext_refs:
            if not isinstance(ref, dict):
                continue
            if str(ref.get("referenceCategory") or "").upper() == "PACKAGE-MANAGER":
                locator = str(ref.get("referenceLocator") or "")
                if locator.startswith("pkg:"):
                    return locator
    return ""


def _parse_spdx_version(pkg: dict[str, object]) -> str:
    ver = pkg.get("versionInfo")
    if ver:
        return str(ver)
    name = str(pkg.get("name") or "")
    if "@" in name:
        return name.split("@", 1)[1]
    return ""


def parse_spdx(data: dict[str, object]) -> tuple[dict[str, object], list[dict[str, object]]]:
    """Parse an SPDX JSON BOM.

    Returns (metadata, components).
    """
    meta: dict[str, object] = {
        "bom_serial": str(data.get("SPDXID") or ""),
        "bom_version": str(data.get("spdxVersion") or ""),
        "bom_format": "spdx",
    }
    raw_packages = data.get("packages")
    if not isinstance(raw_packages, list):
        raw_packages = []
    components: list[dict[str, object]] = []
    for pkg in raw_packages:
        if not isinstance(pkg, dict):
            continue
        name = str(pkg.get("name") or "")
        if not name:
            continue
        components.append({
            "purl": _purl_from_spdx_package(pkg),
            "cpe": "",
            "name": name,
            "version": _parse_spdx_version(pkg),
            "component_type": "library",
            "group_name": "",
        })
    return meta, components


def parse_bom(data: dict[str, object]) -> tuple[dict[str, object], list[dict[str, object]]]:
    """Detect format and parse a BOM dict. Falls back to CycloneDX for unknown formats."""
    bom_format = str(data.get("bomFormat") or "").lower()
    spdx_version = str(data.get("spdxVersion") or "")
    if bom_format == "cyclonedx" or "components" in data:
        return parse_cyclonedx(data)
    if spdx_version.startswith("SPDX") or "packages" in data:
        return parse_spdx(data)
    # Last-resort: try CycloneDX
    return parse_cyclonedx(data)
