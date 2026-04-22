from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class ReadModelVersion:
    generation: int
    etag: str


def build_read_model_etag(scope_key: str, generation: int) -> str:
    digest = hashlib.blake2b(
        f"{scope_key}:{generation}".encode("utf-8"),
        digest_size=10,
    ).hexdigest()
    return f'W/"model-{generation}-{digest}"'
