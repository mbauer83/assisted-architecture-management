"""Tests for EncryptedPrivateGitAssuranceStore (SC-3).

Covers:
  - Encrypted round-trip: write → reload → read (decrypt-on-load)
  - On-disk files are ciphertext (not plaintext JSON)
  - Locked store raises RuntimeError on all operations
  - All CRUD operations (nodes, edges, refs)
  - Wrong key returns None on read (graceful skip)
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch


def _make_store(tmpdir: str) -> tuple:
    """Return (store, fernet_key) with keychain mocked."""
    from cryptography.fernet import Fernet  # type: ignore[import-untyped]

    from src.infrastructure.assurance._encrypted_private_git_store import EncryptedPrivateGitAssuranceStore

    key = Fernet.generate_key().decode()
    repo_path = Path(tmpdir) / ".arch-assurance-git"
    store = EncryptedPrivateGitAssuranceStore(repo_path)
    return store, key


# ── Basic lifecycle ───────────────────────────────────────────────────────────


class TestEncryptedGitLifecycle:
    def test_initially_locked(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store, _ = _make_store(tmpdir)
            assert not store.is_unlocked()

    def test_unlock_with_valid_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store, key = _make_store(tmpdir)
            with patch("keyring.get_password", return_value=key):
                store.unlock()
            assert store.is_unlocked()

    def test_unlock_missing_key_raises(self) -> None:
        import pytest
        with tempfile.TemporaryDirectory() as tmpdir:
            store, _ = _make_store(tmpdir)
            with patch("keyring.get_password", return_value=None):
                with pytest.raises(RuntimeError, match="not found in OS keychain"):
                    store.unlock()

    def test_lock_clears_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store, key = _make_store(tmpdir)
            with patch("keyring.get_password", return_value=key):
                store.unlock()
            store.lock()
            assert not store.is_unlocked()


# ── Encrypted round-trip ─────────────────────────────────────────────────────


class TestEncryptedRoundTrip:
    def _unlocked_store(self, tmpdir: str):
        store, key = _make_store(tmpdir)
        with patch("keyring.get_password", return_value=key):
            store.unlock()
        return store

    def test_node_write_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._unlocked_store(tmpdir)
            nid = store.create_node("loss", "L-1 — Data breach", status="draft")
            node = store.get_node(nid)
            assert node is not None
            assert node["name"] == "L-1 — Data breach"
            assert node["node_type"] == "loss"

    def test_on_disk_is_not_plaintext(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._unlocked_store(tmpdir)
            store.create_node("loss", "SecretLoss", status="draft")
            # All .enc files should not contain the plaintext name
            enc_files = list((Path(tmpdir) / ".arch-assurance-git" / "nodes").glob("*.enc"))
            assert len(enc_files) == 1
            raw_bytes = enc_files[0].read_bytes()
            # Ciphertext must not contain the plaintext name
            assert b"SecretLoss" not in raw_bytes
            # Also not valid JSON
            try:
                json.loads(raw_bytes)
                is_json = True
            except (json.JSONDecodeError, UnicodeDecodeError):
                is_json = False
            assert not is_json, "On-disk file should not be plaintext JSON"

    def test_decrypt_on_reload(self) -> None:
        from cryptography.fernet import Fernet  # type: ignore[import-untyped]

        from src.infrastructure.assurance._encrypted_private_git_store import EncryptedPrivateGitAssuranceStore

        with tempfile.TemporaryDirectory() as tmpdir:
            key = Fernet.generate_key().decode()
            repo_path = Path(tmpdir) / ".arch-assurance-git"

            # Write with store1
            store1 = EncryptedPrivateGitAssuranceStore(repo_path)
            with patch("keyring.get_password", return_value=key):
                store1.unlock()
            nid = store1.create_node("hazard", "H-1 — System unavailable")
            store1.lock()

            # Read back with a fresh store2 (same key, same path)
            store2 = EncryptedPrivateGitAssuranceStore(repo_path)
            with patch("keyring.get_password", return_value=key):
                store2.unlock()
            node = store2.get_node(nid)
            assert node is not None
            assert node["name"] == "H-1 — System unavailable"

    def test_wrong_key_returns_none(self) -> None:
        from cryptography.fernet import Fernet  # type: ignore[import-untyped]

        from src.infrastructure.assurance._encrypted_private_git_store import EncryptedPrivateGitAssuranceStore

        with tempfile.TemporaryDirectory() as tmpdir:
            key1 = Fernet.generate_key().decode()
            key2 = Fernet.generate_key().decode()
            repo_path = Path(tmpdir) / ".arch-assurance-git"

            store1 = EncryptedPrivateGitAssuranceStore(repo_path)
            with patch("keyring.get_password", return_value=key1):
                store1.unlock()
            nid = store1.create_node("loss", "L-1")
            store1.lock()

            # Try to read with wrong key
            store2 = EncryptedPrivateGitAssuranceStore(repo_path)
            with patch("keyring.get_password", return_value=key2):
                store2.unlock()
            node = store2.get_node(nid)
            assert node is None  # graceful skip on invalid token


# ── Locked gating ─────────────────────────────────────────────────────────────


class TestLockedGating:
    def test_locked_raises_on_create_node(self) -> None:
        import pytest
        with tempfile.TemporaryDirectory() as tmpdir:
            store, _ = _make_store(tmpdir)
            with pytest.raises(RuntimeError, match="locked"):
                store.create_node("loss", "L-1")

    def test_locked_raises_on_list_nodes(self) -> None:
        import pytest
        with tempfile.TemporaryDirectory() as tmpdir:
            store, _ = _make_store(tmpdir)
            with pytest.raises(RuntimeError, match="locked"):
                store.list_nodes()

    def test_locked_raises_on_stats(self) -> None:
        import pytest
        with tempfile.TemporaryDirectory() as tmpdir:
            store, _ = _make_store(tmpdir)
            with pytest.raises(RuntimeError, match="locked"):
                store.stats()


# ── Edge + Ref CRUD ───────────────────────────────────────────────────────────


class TestEdgeAndRefCRUD:
    def _store(self, tmpdir: str):
        store, key = _make_store(tmpdir)
        with patch("keyring.get_password", return_value=key):
            store.unlock()
        return store

    def test_edge_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir)
            nid1 = store.create_node("loss", "L-1")
            nid2 = store.create_node("hazard", "H-1")
            eid = store.add_edge(nid1, nid2, "leads-to")
            edges = store.list_edges(source_id=nid1)
            assert len(edges) == 1
            assert edges[0]["edge_id"] == eid
            assert edges[0]["conn_type"] == "leads-to"

    def test_remove_edge(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir)
            nid1 = store.create_node("loss", "L-1")
            nid2 = store.create_node("hazard", "H-1")
            eid = store.add_edge(nid1, nid2, "leads-to")
            store.remove_edge(eid)
            assert store.list_edges(source_id=nid1) == []

    def test_arch_ref_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir)
            nid = store.create_node("hazard", "H-1")
            store.register_arch_ref(nid, "ACP@123", "mitigates")
            refs = store.list_arch_refs(assurance_node_id=nid)
            assert len(refs) == 1
            assert refs[0]["arch_artifact_id"] == "ACP@123"
            assert refs[0]["resolved_at"] is None

    def test_mark_arch_ref_resolved(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir)
            nid = store.create_node("hazard", "H-1")
            store.register_arch_ref(nid, "ACP@123", "mitigates")
            store.mark_arch_ref_resolved(nid, "ACP@123", "mitigates")
            refs = store.list_arch_refs(assurance_node_id=nid)
            assert refs[0]["resolved_at"] is not None
