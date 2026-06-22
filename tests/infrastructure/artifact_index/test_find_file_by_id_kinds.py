"""find_file_by_id resolves every standalone artifact kind, group subdirectories included.

Regression guard: the resolver previously consulted only the entity map, so diagrams and
documents in a group collection (a subdirectory of the catalog) could not be resolved by
id — the write/refresh layer then fell back to a flat path and 404'd. It must resolve
entities, diagrams, and documents at whatever path the index recorded.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from src.infrastructure.artifact_index._mem_store import _MemStore
from src.infrastructure.artifact_index._rwlock import _RWLock
from src.infrastructure.artifact_index._scope_registry import _ScopeRegistry


def _registry(mem: _MemStore) -> _ScopeRegistry:
    return _ScopeRegistry(mem, _RWLock(), lambda: None, lambda _p: "engagement")


def test_resolves_entity_diagram_and_document_in_subdirectories() -> None:
    # find_file_by_id reads only `.path`; lightweight stand-ins keep the test focused.
    mem = _MemStore()
    ent_path = Path("/repo/projects/grp/model/motivation/STK@1.a.s.md")
    diag_path = Path("/repo/diagram-catalog/diagrams/meta-ontology/DATATY@1.b.d.puml")
    doc_path = Path("/repo/document-catalog/documents/grp/DOC@1.c.x.md")
    mem.entities["STK@1.a.s"] = SimpleNamespace(path=ent_path)  # type: ignore[assignment]
    mem.diagrams["DATATY@1.b.d"] = SimpleNamespace(path=diag_path)  # type: ignore[assignment]
    mem.documents["DOC@1.c.x"] = SimpleNamespace(path=doc_path)  # type: ignore[assignment]
    reg = _registry(mem)

    assert reg.find_file_by_id("STK@1.a.s") == ent_path
    assert reg.find_file_by_id("DATATY@1.b.d") == diag_path
    assert reg.find_file_by_id("DOC@1.c.x") == doc_path
    assert reg.find_file_by_id("MISSING@9.z.z") is None
