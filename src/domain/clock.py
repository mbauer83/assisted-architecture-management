"""Central, timezone-safe clock for IDs and timestamps.

Every artifact, entity, assurance node, baseline, and audit entry derives its
epoch and ISO timestamp from this module, so the values are identical regardless
of the host machine's timezone or locale.

Guarantees:
  * ``epoch_seconds()`` returns POSIX seconds (UTC by definition — independent of
    ``TZ``).
  * ``utc_now_iso()`` returns a UTC ISO-8601 instant with a trailing ``Z``.
  * ``utc_now_compact()`` returns a filename-safe UTC stamp (``YYYYMMDDTHHMMSSZ``).

Never use ``time.localtime``, ``datetime.now()`` without a tzinfo, ``mktime`` or
``fromtimestamp`` for persisted values — those depend on the local timezone and
will diverge across deployments. Route all such needs through this module.
"""

from __future__ import annotations

import time

_ISO_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
_COMPACT_FORMAT = "%Y%m%dT%H%M%SZ"


def epoch_seconds() -> int:
    """Return the current time as integer POSIX seconds (UTC, timezone-independent)."""
    return int(time.time())


def utc_now_iso() -> str:
    """Return the current UTC instant as ``YYYY-MM-DDTHH:MM:SSZ``."""
    return time.strftime(_ISO_FORMAT, time.gmtime())


def utc_now_compact() -> str:
    """Return the current UTC instant as a filename-safe ``YYYYMMDDTHHMMSSZ`` stamp."""
    return time.strftime(_COMPACT_FORMAT, time.gmtime())
