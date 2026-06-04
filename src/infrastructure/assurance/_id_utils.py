"""Shared ID-generation helpers for assurance store adapters."""

from __future__ import annotations

import hashlib
import random
import string
import time

_NODE_PREFIXES: dict[str, str] = {
    "loss": "LSS",
    "hazard": "HAZ",
    "control-structure-node": "CSN",
    "control-action": "CAC",
    "unsafe-control-action": "UCA",
    "assurance-constraint": "ACN",
    "risk": "RSK",
    "incident": "INC",
    "corrective-action": "CRA",
    "obligation": "OBL",
}


def make_node_id(node_type: str, name: str) -> str:
    prefix = _NODE_PREFIXES.get(node_type, node_type[:3].upper())
    epoch = int(time.time())
    rand = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
    slug = hashlib.md5(name.encode()).hexdigest()[:6]
    return f"{prefix}@{epoch}.{rand}.{slug}"


def make_edge_id(source_id: str, target_id: str, conn_type: str) -> str:
    raw = f"{source_id}--{target_id}--{conn_type}--{time.time()}"
    return "EDG@" + hashlib.sha256(raw.encode()).hexdigest()[:12]
