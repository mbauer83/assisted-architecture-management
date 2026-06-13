"""Command handler implementations for the arch-assurance CLI."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.infrastructure.assurance import _credential_store as creds
from src.infrastructure.cli._config_helpers import write_storage_config


def _workspace_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _default_db_path() -> Path:
    return _workspace_root() / ".arch-assurance" / "store.db"


def _default_signals_for(store_backend: str) -> str:
    if store_backend == "sqlcipher":
        return "sqlcipher-colocated"
    return "sqlite"


def _print_yaml(data: object) -> None:
    import yaml  # noqa: PLC0415

    print((yaml.dump(data, default_flow_style=False, allow_unicode=True) or "").rstrip())


def cmd_init(args: argparse.Namespace) -> int:
    from src.infrastructure.assurance.lifecycle import init_store  # noqa: PLC0415

    backend = getattr(args, "backend", None) or "sqlcipher"
    signals = getattr(args, "signals", None) or "sqlcipher-colocated"
    archive = getattr(args, "archive_backend", None)
    db_path = Path(args.db_path) if args.db_path else _default_db_path()

    if backend == "private-git":
        from src.infrastructure.cli._private_git_commands import init_private_git  # noqa: PLC0415

        result = init_private_git(args, db_path)
    else:
        try:
            result = init_store(db_path, force=args.force)
        except FileExistsError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1

    # --force re-init: clear the setup-confirmed marker so unlock is required again.
    if getattr(args, "force", False):
        try:
            creds.delete("setup-confirmed")
        except Exception:  # noqa: BLE001
            pass

    write_storage_config(backend, signals, archive)
    result["store_backend"] = backend
    result["signals_backend"] = signals
    if archive:
        result["archive_backend"] = archive
    _print_yaml(result)
    return 0


def cmd_use_backend(args: argparse.Namespace) -> int:
    backend = args.backend
    signals = getattr(args, "signals", None) or _default_signals_for(backend)
    archive = getattr(args, "archive_backend", None)
    write_storage_config(backend, signals, archive)

    from src.infrastructure.mcp.assurance_mcp.context import clear_context_cache  # noqa: PLC0415

    clear_context_cache()
    print(f"Switched to {backend} (signals: {signals}). Restart arch-backend for changes to take effect.")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    from src.config.settings import (  # noqa: PLC0415
        storage_assurance_max_classification,
        storage_assurance_signals_backend,
        storage_assurance_store_backend,
    )

    db_path = Path(args.db_path) if args.db_path else _default_db_path()

    try:
        from src.config.settings import storage_assurance_archive_backend  # noqa: PLC0415

        store_backend = storage_assurance_store_backend()
        signals_backend = storage_assurance_signals_backend()
        archive_backend = storage_assurance_archive_backend()
        max_cls = storage_assurance_max_classification()
    except ValueError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 2

    key_present = False
    setup_confirmed = False
    try:
        key_account = "private-git-encryption-key" if store_backend == "private-git" else "db-encryption-key"
        key_present = creds.get(key_account) is not None
        setup_confirmed = creds.get("setup-confirmed") is not None
    except Exception:  # noqa: BLE001
        pass

    # The store is "unlocked" in the only persistent sense that matters when its key is in
    # the OS keychain AND `unlock` has set the setup-confirmed gate: it then opens in every
    # process and across restarts without ceremony. We report that truthfully by running the
    # SAME auto-unlock gate the backend uses against a throwaway probe — not the (always
    # false) in-memory state of a freshly built store.
    unlocked = False
    status_str = "not_initialised"
    if key_present:
        status_str = "locked"
    if store_backend == "sqlcipher" and db_path.exists() and key_present:
        from src.infrastructure.assurance._sqlcipher_store import SQLCipherAssuranceStore  # noqa: PLC0415
        from src.infrastructure.assurance.store_factory import try_auto_unlock  # noqa: PLC0415

        probe = SQLCipherAssuranceStore(db_path)
        try_auto_unlock(probe, "sqlcipher")
        unlocked = probe.is_unlocked()
        probe.lock()
        if unlocked:
            status_str = "unlocked"
        elif not setup_confirmed:
            status_str = "locked_needs_activation"
    elif store_backend == "private-git":
        git_repo = _workspace_root() / ".arch-assurance-git"
        if not git_repo.exists():
            status_str = "not_initialised"

    _print_yaml({
        "store_backend": store_backend,
        "signals_backend": signals_backend,
        "archive_backend": archive_backend,
        "max_classification": max_cls,
        "db_path": str(db_path),
        "db_exists": db_path.exists(),
        "key_in_keychain": key_present,
        "setup_confirmed": setup_confirmed,
        "unlocked": unlocked,
        "status": status_str,
    })
    return 0


def _notify_backend_reload() -> None:
    """Best-effort POST to the running backend to reload the assurance bundle."""
    import urllib.request  # noqa: PLC0415

    try:
        from src.config.settings import backend_port  # noqa: PLC0415

        port = backend_port()
        req = urllib.request.Request(
            f"http://localhost:{port}/api/assurance/reload",
            data=b"",
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=3):
            pass
    except Exception:  # noqa: BLE001
        pass  # Backend not running — auto-unlock applies on next restart.


def cmd_unlock(args: argparse.Namespace) -> int:
    from src.infrastructure.assurance._sqlcipher_store import SQLCipherAssuranceStore  # noqa: PLC0415

    db_path = Path(args.db_path) if args.db_path else _default_db_path()
    store = SQLCipherAssuranceStore(db_path)
    try:
        store.unlock()
        stats = store.stats()
        store.lock()
        # Mark as explicitly activated — enables auto-unlock on subsequent backend starts.
        creds.set_credential("setup-confirmed", "1")
        # Signal the running backend (if any) to reload its cached bundle immediately.
        _notify_backend_reload()
        _print_yaml({
            "status": "unlocked_and_verified",
            "db_path": str(db_path),
            "stats": stats,
            "note": (
                "Store activated. Backend will auto-unlock from OS keychain on start. "
                "Run `arch-assurance export-key` to save your recovery key offline."
            ),
        })
        return 0
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def cmd_lock(_args: argparse.Namespace) -> int:
    """Persistently disable auto-unlock by clearing the setup-confirmed gate.

    The inverse of `unlock`. The encryption key stays in the OS keychain (so `unlock`
    re-enables access without the recovery key), but the backend will no longer open the
    store automatically until `unlock` is run again — fail-closed.
    """
    try:
        creds.delete("setup-confirmed")
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    _notify_backend_reload()
    _print_yaml({
        "status": "locked",
        "note": (
            "Auto-unlock disabled. The backend will not open the store until you run "
            "`arch-assurance unlock` again. The encryption key remains in the OS keychain."
        ),
    })
    return 0


def cmd_backup(args: argparse.Namespace) -> int:
    from src.infrastructure.assurance.lifecycle import backup_store  # noqa: PLC0415

    db_path = Path(args.db_path) if args.db_path else _default_db_path()
    backup_path = Path(args.backup_path) if args.backup_path else None
    try:
        result = backup_store(db_path, backup_path=backup_path)
        print(f"Backed up to {result['backup_path']}.")
        return 0
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def cmd_export(args: argparse.Namespace) -> int:
    from src.infrastructure.assurance._sqlcipher_store import SQLCipherAssuranceStore  # noqa: PLC0415
    from src.infrastructure.assurance.lifecycle import export_store  # noqa: PLC0415

    db_path = Path(args.db_path) if args.db_path else _default_db_path()
    store = SQLCipherAssuranceStore(db_path)
    try:
        store.unlock()
        result = export_store(store, Path(args.output))
        print(f"Exported {result['node_count']} nodes to {result['output_path']}.")
        return 0
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        store.lock()


def cmd_rotate_key(args: argparse.Namespace) -> int:
    from src.infrastructure.assurance.lifecycle import rotate_key  # noqa: PLC0415

    db_path = Path(args.db_path) if args.db_path else _default_db_path()
    try:
        rotate_key(db_path)
        print("Key rotated. Store re-encrypted.")
        return 0
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def cmd_export_key(_args: argparse.Namespace) -> int:
    from src.infrastructure.assurance.lifecycle import export_recovery_key  # noqa: PLC0415

    try:
        result = export_recovery_key()
        print(result["recovery_key"])
        print("STORE THIS KEY SECURELY OFFLINE.", file=sys.stderr)
        return 0
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def cmd_pocketbase_init(args: argparse.Namespace) -> int:
    from src.infrastructure.assurance.pocketbase_lifecycle import create_collections  # noqa: PLC0415

    try:
        result = create_collections(args.base_url, args.admin_token)
        _print_yaml(result)
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def cmd_pocketbase_status(args: argparse.Namespace) -> int:
    from src.infrastructure.assurance.pocketbase_lifecycle import check_health  # noqa: PLC0415

    healthy = check_health(args.base_url)
    state = "healthy" if healthy else "unhealthy"
    print(f"PocketBase at {args.base_url}: {state}.")
    return 0 if healthy else 1


def cmd_import_sbom(args: argparse.Namespace) -> int:
    from src.infrastructure.cli._security_commands import cmd_import_sbom  # noqa: PLC0415

    return cmd_import_sbom(args, _workspace_root())


def cmd_export_aibom(args: argparse.Namespace) -> int:
    from src.infrastructure.cli._security_commands import cmd_export_aibom  # noqa: PLC0415

    return cmd_export_aibom(args)


def cmd_scan_ai_candidates(args: argparse.Namespace) -> int:
    from src.infrastructure.cli._security_commands import cmd_scan_ai_candidates  # noqa: PLC0415

    return cmd_scan_ai_candidates(args)


def cmd_verify(args: argparse.Namespace) -> int:
    """Backend-aware chain integrity check. No key required for private-git or cloud backends."""
    from src.config.settings import (  # noqa: PLC0415
        storage_assurance_archive_backend,
        storage_assurance_store_backend,
    )

    try:
        store_backend = storage_assurance_store_backend()
        archive_backend = storage_assurance_archive_backend()
    except ValueError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 2

    if store_backend == "private-git":
        from src.infrastructure.cli._private_git_commands import verify_private_git  # noqa: PLC0415

        return verify_private_git(args)

    if archive_backend in ("s3-worm", "azure-blob-worm"):
        from src.infrastructure.assurance.store_factory import get_assurance_bundle  # noqa: PLC0415

        db_path = Path(args.db_path) if args.db_path else None
        try:
            bundle = get_assurance_bundle(_workspace_root(), db_path=db_path)
            ok = bundle.archive.verify_chain()
            entries = bundle.archive.list_entries(limit=100_000)
            _print_yaml({"chain_valid": ok, "entry_count": len(entries), "archive_backend": archive_backend})
            return 0 if ok else 2
        except RuntimeError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1

    from src.infrastructure.assurance._archive import SQLCipherAssuranceArchive  # noqa: PLC0415
    from src.infrastructure.assurance._sqlcipher_store import SQLCipherAssuranceStore  # noqa: PLC0415

    db_path = Path(args.db_path) if args.db_path else _default_db_path()
    store = SQLCipherAssuranceStore(db_path)
    try:
        store.unlock()
        archive = SQLCipherAssuranceArchive(lambda: store._conn)  # noqa: SLF001
        ok = archive.verify_chain()
        entries = archive.list_entries(limit=100_000)
        _print_yaml({"chain_valid": ok, "entry_count": len(entries), "db_path": str(db_path)})
        return 0 if ok else 2
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        store.lock()


def cmd_verify_chain(args: argparse.Namespace) -> int:
    from src.infrastructure.assurance._archive import SQLCipherAssuranceArchive  # noqa: PLC0415
    from src.infrastructure.assurance._sqlcipher_store import SQLCipherAssuranceStore  # noqa: PLC0415

    db_path = Path(args.db_path) if args.db_path else _default_db_path()
    store = SQLCipherAssuranceStore(db_path)
    try:
        store.unlock()
        archive = SQLCipherAssuranceArchive(lambda: store._conn)  # noqa: SLF001
        ok = archive.verify_chain()
        _print_yaml({"chain_valid": ok, "db_path": str(db_path)})
        return 0 if ok else 2
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        store.lock()
