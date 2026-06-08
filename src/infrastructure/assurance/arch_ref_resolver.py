"""One-way assurance→architecture reference resolver.

Assurance nodes may reference architecture artifact IDs. Those references can
dangle (the architecture model evolves independently). This resolver:
- looks up each arch_artifact_id in the ArtifactStorePort (if available)
- marks `resolved_at` in the arch_refs table when found
- returns dangling refs as informational (never errors)

Invariant enforced: no architecture artifact stores a back-reference to an
assurance node. That would violate the one-way confidentiality rule.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.application.assurance_ports import ConfidentialAssuranceStore
    from src.application.ports import ArtifactLookup

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def resolve_arch_refs(
    assurance_store: ConfidentialAssuranceStore,
    artifact_store: ArtifactLookup,
) -> dict[str, object]:
    """Resolve dangling assurance→architecture references.

    Returns a summary dict with resolved/dangling counts.
    Never raises — dangling refs are informational.
    """
    if not assurance_store.is_unlocked():
        return {"error": "store_locked", "resolved": 0, "dangling": 0}

    refs = assurance_store.list_arch_refs()
    resolved = 0
    dangling: list[dict[str, object]] = []

    for ref in refs:
        arch_id = str(ref["arch_artifact_id"])
        entity = artifact_store.get_entity(arch_id)
        if entity is not None:
            assurance_store.mark_arch_ref_resolved(
                str(ref["assurance_node_id"]),
                arch_id,
                str(ref["ref_type"]),
            )
            resolved += 1
        else:
            dangling.append(ref)
            logger.debug(
                "Dangling assurance→arch ref: %s → %s (%s)",
                ref["assurance_node_id"],
                arch_id,
                ref["ref_type"],
            )

    if dangling:
        logger.info(
            "%d dangling assurance→architecture references (informational, not errors)",
            len(dangling),
        )

    return {
        "resolved": resolved,
        "dangling": len(dangling),
        "dangling_refs": dangling,
    }
