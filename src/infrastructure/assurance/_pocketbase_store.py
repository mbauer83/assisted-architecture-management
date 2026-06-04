"""PocketBase-backed confidential assurance store adapter.

PocketBase (https://pocketbase.io) provides a self-hosted REST API with RBAC —
suitable for teams sharing an assurance store without the single-device SQLCipher constraint.

Collections used:
  assurance_nodes  — node records
  assurance_edges  — edge records
  arch_refs        — cross-references to architecture artifacts

Authentication uses the PocketBase Admin API (email+password → Bearer token).
Use `pocketbase_lifecycle.create_collections` to initialise the collections before first use.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from src.infrastructure.assurance._id_utils import make_edge_id, make_node_id

logger = logging.getLogger(__name__)

_LOCKED_MSG = "PocketBase store is locked. Call unlock() first."


class PocketBaseAssuranceStore:
    """Adapter implementing ConfidentialAssuranceStore using PocketBase REST API."""

    def __init__(self, base_url: str, admin_email: str, admin_password: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._admin_email = admin_email
        self._admin_password = admin_password
        self._client: Any = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def is_unlocked(self) -> bool:
        return self._client is not None

    def unlock(self) -> None:
        import httpx  # type: ignore[import-untyped]  # noqa: PLC0415

        resp = httpx.post(
            f"{self._base_url}/api/admins/auth-with-password",
            json={"identity": self._admin_email, "password": self._admin_password},
            timeout=15,
        )
        resp.raise_for_status()
        token = resp.json()["token"]
        self._client = httpx.Client(
            base_url=self._base_url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        logger.info("PocketBase store unlocked at %s", self._base_url)

    def lock(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None
        logger.info("PocketBase store locked")

    def _require_unlocked(self) -> Any:
        if self._client is None:
            raise RuntimeError(_LOCKED_MSG)
        return self._client

    # ── Node helpers ──────────────────────────────────────────────────────────

    def _node_url(self) -> str:
        return "/api/collections/assurance_nodes/records"

    def _edge_url(self) -> str:
        return "/api/collections/assurance_edges/records"

    def _ref_url(self) -> str:
        return "/api/collections/arch_refs/records"

    def _filter(self, **bindings: str) -> dict[str, str]:
        """Build a parameterized PocketBase filter using {:param} binding syntax.

        Each keyword arg becomes `(field = {:field})` in the filter template and
        `field=value` as a separate URL parameter, preventing filter injection.
        """
        if not bindings:
            return {}
        clauses = " && ".join(f"({k} = {{{':' + k}}})" for k in bindings)
        params: dict[str, str] = {"filter": clauses}
        for k, v in bindings.items():
            params[k] = v
        return params

    # ── Node CRUD ─────────────────────────────────────────────────────────────

    def get_node(self, node_id: str) -> dict[str, object] | None:
        client = self._require_unlocked()
        resp = client.get(self._node_url(), params=self._filter(node_id=node_id))
        resp.raise_for_status()
        items = resp.json().get("items", [])
        return items[0] if items else None

    def list_nodes(
        self,
        *,
        node_type: str | None = None,
        status: str | None = None,
        concern_class: str | None = None,
        tlp: str | None = None,
    ) -> list[dict[str, object]]:
        client = self._require_unlocked()
        bindings: dict[str, str] = {}
        if node_type:
            bindings["node_type"] = node_type
        if status:
            bindings["status"] = status
        if concern_class:
            bindings["concern_class"] = concern_class
        if tlp:
            bindings["tlp"] = tlp
        params: dict[str, str | int] = {"perPage": 500}
        params.update(self._filter(**bindings))
        resp = client.get(self._node_url(), params=params)
        resp.raise_for_status()
        return resp.json().get("items", [])

    def create_node(
        self,
        node_type: str,
        name: str,
        *,
        status: str = "draft",
        tlp: str = "TLP:WHITE",
        concern_class: str | None = None,
        disposition: str | None = None,
        uca_type: str | None = None,
        binding_status: str | None = None,
        node_role: str | None = None,
        attributes: dict[str, object] | None = None,
        content: str = "",
    ) -> str:
        import json  # noqa: PLC0415

        client = self._require_unlocked()
        node_id = make_node_id(node_type, name)
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        payload = {
            "node_id": node_id, "node_type": node_type, "name": name,
            "status": status, "tlp": tlp, "concern_class": concern_class or "",
            "disposition": disposition or "", "uca_type": uca_type or "",
            "binding_status": binding_status or "", "node_role": node_role or "",
            "attributes_json": json.dumps(attributes or {}),
            "content_text": content, "created_at": now, "updated_at": now,
        }
        resp = client.post(self._node_url(), json=payload)
        resp.raise_for_status()
        return node_id

    def update_node(self, node_id: str, **attrs: object) -> None:
        import json  # noqa: PLC0415

        client = self._require_unlocked()
        existing = self.get_node(node_id)
        if existing is None:
            raise RuntimeError(f"Node not found: {node_id}")
        pb_id = str(existing["id"])
        allowed = {"name", "status", "tlp", "concern_class", "disposition", "uca_type",
                   "binding_status", "node_role", "content_text"}
        payload: dict[str, object] = {"updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        for k, v in attrs.items():
            if k in allowed:
                payload[k] = v
            elif k == "attributes":
                payload["attributes_json"] = json.dumps(v)
        resp = client.patch(f"{self._node_url()}/{pb_id}", json=payload)
        resp.raise_for_status()

    def delete_node(self, node_id: str) -> None:
        client = self._require_unlocked()
        existing = self.get_node(node_id)
        if existing is None:
            return
        pb_id = str(existing["id"])
        resp = client.delete(f"{self._node_url()}/{pb_id}")
        resp.raise_for_status()

    # ── Edge CRUD ─────────────────────────────────────────────────────────────

    def list_edges(
        self,
        *,
        source_id: str | None = None,
        target_id: str | None = None,
        conn_type: str | None = None,
    ) -> list[dict[str, object]]:
        client = self._require_unlocked()
        bindings: dict[str, str] = {}
        if source_id:
            bindings["source_id"] = source_id
        if target_id:
            bindings["target_id"] = target_id
        if conn_type:
            bindings["conn_type"] = conn_type
        params: dict[str, str | int] = {"perPage": 500}
        params.update(self._filter(**bindings))
        resp = client.get(self._edge_url(), params=params)
        resp.raise_for_status()
        return resp.json().get("items", [])

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        conn_type: str,
        *,
        attributes: dict[str, object] | None = None,
    ) -> str:
        import json  # noqa: PLC0415

        client = self._require_unlocked()
        edge_id = make_edge_id(source_id, target_id, conn_type)
        payload = {
            "edge_id": edge_id, "source_id": source_id, "target_id": target_id,
            "conn_type": conn_type,
            "attributes_json": json.dumps(attributes or {}),
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        resp = client.post(self._edge_url(), json=payload)
        resp.raise_for_status()
        return edge_id

    def remove_edge(self, edge_id: str) -> None:
        client = self._require_unlocked()
        resp = client.get(self._edge_url(), params=self._filter(edge_id=edge_id))
        resp.raise_for_status()
        items = resp.json().get("items", [])
        if items:
            client.delete(f"{self._edge_url()}/{items[0]['id']}").raise_for_status()

    # ── Architecture cross-references ──────────────────────────────────────────

    def register_arch_ref(self, assurance_node_id: str, arch_artifact_id: str, ref_type: str) -> None:
        client = self._require_unlocked()
        existing = self.list_arch_refs(assurance_node_id=assurance_node_id, arch_artifact_id=arch_artifact_id)
        if any(r.get("ref_type") == ref_type for r in existing):
            return
        payload = {
            "assurance_node_id": assurance_node_id,
            "arch_artifact_id": arch_artifact_id,
            "ref_type": ref_type,
            "resolved_at": "",
        }
        client.post(self._ref_url(), json=payload).raise_for_status()

    def mark_arch_ref_resolved(self, assurance_node_id: str, arch_artifact_id: str, ref_type: str) -> None:
        client = self._require_unlocked()
        refs = self.list_arch_refs(assurance_node_id=assurance_node_id, arch_artifact_id=arch_artifact_id)
        for ref in refs:
            if ref.get("ref_type") == ref_type:
                pb_id = str(ref["id"])
                client.patch(
                    f"{self._ref_url()}/{pb_id}",
                    json={"resolved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
                ).raise_for_status()
                return

    def list_arch_refs(
        self,
        *,
        assurance_node_id: str | None = None,
        arch_artifact_id: str | None = None,
    ) -> list[dict[str, object]]:
        client = self._require_unlocked()
        bindings: dict[str, str] = {}
        if assurance_node_id:
            bindings["assurance_node_id"] = assurance_node_id
        if arch_artifact_id:
            bindings["arch_artifact_id"] = arch_artifact_id
        params: dict[str, str | int] = {"perPage": 500}
        params.update(self._filter(**bindings))
        resp = client.get(self._ref_url(), params=params)
        resp.raise_for_status()
        return resp.json().get("items", [])

    # ── Stats ─────────────────────────────────────────────────────────────────

    def stats(self) -> dict[str, object]:
        client = self._require_unlocked()

        def _count(url: str) -> int:
            r = client.get(url, params={"page": 1, "perPage": 1})
            r.raise_for_status()
            return int(r.json().get("totalItems", 0))

        return {
            "node_count": _count(self._node_url()),
            "edge_count": _count(self._edge_url()),
            "arch_ref_count": _count(self._ref_url()),
        }
