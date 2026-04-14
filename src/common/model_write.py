"""model_write.py — Model artifact generation helpers.

This module contains the reusable logic needed to generate model artifacts:
- entity/connection type catalogs (writer-side path mapping)
- ID generation using epoch + random
- deterministic formatting of entity markdown, .outgoing.md, and diagram PUML
- best-effort inference of referenced IDs from PUML

I/O (writing files, cache invalidation, macro regeneration, verifier execution)
belongs in tooling/infrastructure (see src/tools/model_write_ops.py).
"""


import re
import secrets
import string
import time

from src.common.model_write_catalog import (
    ARCHIMATE_STEREOTYPE_TO_CONNECTION_TYPE,
    CONNECTION_TYPES,
    ENTITY_TYPES,
    ConnectionTypeInfo,
    DiagramConnectionInferenceMode,
    EntityTypeInfo,
)
from src.common.model_write_formatting import (
    format_diagram_puml,
    format_entity_markdown,
    format_matrix_markdown,
    format_outgoing_markdown,
)


# ---------------------------------------------------------------------------
# Deterministic helpers
# ---------------------------------------------------------------------------

_ID_ALPHABET = string.ascii_letters + string.digits + "-_"


def slugify(value: str) -> str:
    s = value.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "entity"


def generate_entity_id(prefix: str, friendly_name: str, *, random_length: int = 6) -> str:
    """Generate an artifact-id in the new convention: TYPE@epoch.random.friendly-name"""
    epoch = int(time.time())
    random_part = "".join(secrets.choice(_ID_ALPHABET) for _ in range(random_length))
    slug = slugify(friendly_name)
    return f"{prefix}@{epoch}.{random_part}.{slug}"


# ---------------------------------------------------------------------------
# PUML inference
# ---------------------------------------------------------------------------


def infer_entity_ids_from_puml(puml: str) -> tuple[set[str], list[str]]:
    """Infer entity IDs from PUML.

    Returns (ids, warnings). Looks for alias tokens like ``DRV_Qw7Er1`` and
    maps them back to entity IDs by searching for the full artifact-id containing
    the random part.
    """
    warnings: list[str] = []
    ids: set[str] = set()

    # Match aliases: TYPE_random (e.g. DRV_Qw7Er1, APP_kRZYOA)
    for m in re.finditer(r"\b([A-Z]{2,6})_([A-Za-z0-9_-]{4,})\b", puml):
        alias = f"{m.group(1)}_{m.group(2)}"
        ids.add(alias)

    if not ids:
        warnings.append(
            "No entity aliases found in PUML. "
            "For best discoverability, use standard aliases like DRV_Qw7Er1."
        )

    return ids, warnings


def infer_archimate_connection_ids_from_puml(
    puml: str,
    *,
    mode: DiagramConnectionInferenceMode,
) -> tuple[list[dict[str, str]], list[str]]:
    """Infer ArchiMate connections from PUML lines with <<relationship>> stereotypes.

    Returns (connections, warnings) where each connection is a dict with
    ``source_alias``, ``target_alias``, and ``connection_type``.
    """
    warnings: list[str] = []
    connections: list[dict[str, str]] = []

    # Pattern matches e.g. DRV_Qw7Er1 -[#color]-> GOL_Po1Qw3 : <<realization>>
    pat = re.compile(
        r"\b(?P<src>[A-Z]{2,6}_[A-Za-z0-9_-]+)\b.*?\b(?P<tgt>[A-Z]{2,6}_[A-Za-z0-9_-]+)\b\s*:\s*<<(?P<rel>[A-Za-z]+)>>",
        flags=re.IGNORECASE,
    )

    for m in pat.finditer(puml):
        src = m.group("src")
        tgt = m.group("tgt")
        rel = m.group("rel").strip().lower()
        conn_type = ARCHIMATE_STEREOTYPE_TO_CONNECTION_TYPE.get(rel)
        if conn_type is None:
            msg = f"Unknown ArchiMate relationship stereotype <<{m.group('rel')}>>"
            if mode == "strict":
                raise ValueError(msg)
            warnings.append(msg)
            continue

        connections.append({
            "source_alias": src,
            "target_alias": tgt,
            "connection_type": conn_type,
        })

    return connections, warnings
