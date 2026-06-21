"""Domain vocabulary for the assurance analysis aggregate.

An analysis is the aggregate root for a unit of STPA/CAST/GRC work. These
constants define its controlled vocabulary; they are pure domain facts with no
storage or transport dependency, so both the application use cases and the
infrastructure store adapters import them from here.
"""

from __future__ import annotations

# Analysis methods. STPA covers STPA and STPA-Sec; CAST is incident analysis;
# GRC is governance/risk/compliance.
ANALYSIS_METHODS: tuple[str, ...] = ("STPA", "CAST", "GRC")

# Lifecycle states of an analysis.
ANALYSIS_STATUSES: tuple[str, ...] = ("draft", "active", "completed", "archived")

# Fields a caller may change after creation. Method and architecture anchor are
# immutable — changing either would re-scope the whole aggregate.
ANALYSIS_UPDATABLE: frozenset[str] = frozenset({"name", "status", "tlp"})
