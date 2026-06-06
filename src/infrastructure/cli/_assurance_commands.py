"""Command handler implementations for the arch-assurance CLI."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _workspace_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _default_db_path() -> Path:
    return _workspace_root() / ".arch-assurance" / "store.db"


def _default_signals_for(store_backend: str) -> str:
    if store_backend == "sqlcipher":
        return "sqlcipher-colocated"
    return "sqlite"


def write_storage_config(store_backend: str, signals_backend: str) -> None:
    import yaml  # noqa: PLC0415

    config_path = _workspace_root() / "config" / "settings.yaml"
    data: dict[str, object]
    if config_path.exists():
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    else:
        data = {}
    storage: dict[str, object] = data.setdefault("storage", {})  # type: ignore[assignment]
    assurance: dict[str, object] = storage.setdefault("assurance", {})  # type: ignore[assignment]
    assurance["store_backend"] = store_backend
    assurance["signals_backend"] = signals_backend
    dumped = str(yaml.dump(data, default_flow_style=False, allow_unicode=True) or "")
    config_path.write_text(dumped, encoding="utf-8")


def cmd_init(args: argparse.Namespace) -> int:
    from src.infrastructure.assurance.lifecycle import init_store  # noqa: PLC0415

    backend = getattr(args, "backend", None) or "sqlcipher"
    signals = getattr(args, "signals", None) or "sqlcipher-colocated"
    db_path = Path(args.db_path) if args.db_path else _default_db_path()

    if backend == "private-git":
        result = _init_private_git(args, db_path)
    else:
        try:
            result = init_store(db_path, force=args.force)
        except FileExistsError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1

    write_storage_config(backend, signals)
    result["store_backend"] = backend
    result["signals_backend"] = signals
    print(json.dumps(result, indent=2))
    return 0


def _init_private_git(args: argparse.Namespace, db_path: Path) -> dict:
    import secrets  # noqa: PLC0415

    import keyring  # type: ignore[import-untyped]  # noqa: PLC0415
    from cryptography.fernet import Fernet  # type: ignore[import-untyped]  # noqa: PLC0415

    repo_path = db_path.parent.parent / ".arch-assurance-git"
    if repo_path.exists() and not getattr(args, "force", False):
        print(f"Error: Private-git store already exists at {repo_path}. Use --force.", file=sys.stderr)
        sys.exit(1)
    for subdir in ("nodes", "edges", "refs"):
        (repo_path / subdir).mkdir(parents=True, exist_ok=True)
    (repo_path / "log").mkdir(parents=True, exist_ok=True)
    (repo_path / "log" / "baselines").mkdir(parents=True, exist_ok=True)
    key = Fernet.generate_key().decode()
    recovery_key = secrets.token_hex(32)
    keyring.set_password("arch-assurance", "private-git-encryption-key", key)
    keyring.set_password("arch-assurance", "private-git-recovery-key", recovery_key)
    return {
        "status": "initialised",
        "repo_path": str(repo_path),
        "note": "Encrypted private-git store ready. Recovery key stored in OS keychain.",
    }


def cmd_use_backend(args: argparse.Namespace) -> int:
    backend = args.backend
    signals = getattr(args, "signals", None) or _default_signals_for(backend)
    write_storage_config(backend, signals)

    from src.infrastructure.mcp.assurance_mcp.context import clear_context_cache  # noqa: PLC0415

    clear_context_cache()
    result = {
        "status": "backend_switched",
        "store_backend": backend,
        "signals_backend": signals,
        "note": "Restart arch-backend for changes to take effect.",
    }
    print(json.dumps(result, indent=2))
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    from src.config.settings import (  # noqa: PLC0415
        storage_assurance_max_classification,
        storage_assurance_signals_backend,
        storage_assurance_store_backend,
    )

    db_path = Path(args.db_path) if args.db_path else _default_db_path()

    try:
        store_backend = storage_assurance_store_backend()
        signals_backend = storage_assurance_signals_backend()
        max_cls = storage_assurance_max_classification()
    except ValueError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 2

    key_present = False
    try:
        import keyring  # type: ignore[import-untyped]

        key_account = "private-git-encryption-key" if store_backend == "private-git" else "db-encryption-key"
        key_present = keyring.get_password("arch-assurance", key_account) is not None
    except Exception:  # noqa: BLE001
        pass

    unlocked = False
    status_str = "not_initialised"
    if key_present:
        status_str = "locked"
    if store_backend == "sqlcipher" and db_path.exists() and key_present:
        from src.infrastructure.assurance._sqlcipher_store import SQLCipherAssuranceStore  # noqa: PLC0415

        unlocked = SQLCipherAssuranceStore(db_path).is_unlocked()
        if unlocked:
            status_str = "unlocked"
    elif store_backend == "private-git":
        git_repo = _workspace_root() / ".arch-assurance-git"
        if not git_repo.exists():
            status_str = "not_initialised"

    print(json.dumps({
        "store_backend": store_backend, "signals_backend": signals_backend,
        "max_classification": max_cls, "db_path": str(db_path),
        "db_exists": db_path.exists(), "key_in_keychain": key_present,
        "unlocked": unlocked, "status": status_str,
    }, indent=2))
    return 0


def cmd_unlock(args: argparse.Namespace) -> int:
    from src.infrastructure.assurance._sqlcipher_store import SQLCipherAssuranceStore  # noqa: PLC0415

    db_path = Path(args.db_path) if args.db_path else _default_db_path()
    store = SQLCipherAssuranceStore(db_path)
    try:
        store.unlock()
        stats = store.stats()
        store.lock()
        result = {
            "status": "unlocked_and_verified", "db_path": str(db_path), "stats": stats,
            "note": "Key verified. Restart arch-backend to reload the assurance module.",
        }
        print(json.dumps(result, indent=2))
        return 0
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def cmd_backup(args: argparse.Namespace) -> int:
    from src.infrastructure.assurance.lifecycle import backup_store  # noqa: PLC0415

    db_path = Path(args.db_path) if args.db_path else _default_db_path()
    backup_path = Path(args.backup_path) if args.backup_path else None
    try:
        result = backup_store(db_path, backup_path=backup_path)
        print(json.dumps(result, indent=2))
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
        print(json.dumps(result, indent=2))
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
        result = rotate_key(db_path)
        print(json.dumps(result, indent=2))
        return 0
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def cmd_export_key(_args: argparse.Namespace) -> int:
    from src.infrastructure.assurance.lifecycle import export_recovery_key  # noqa: PLC0415

    try:
        result = export_recovery_key()
        print(json.dumps(result, indent=2))
        print("\nSTORE THIS KEY SECURELY OFFLINE.", file=sys.stderr)
        return 0
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def cmd_pocketbase_init(args: argparse.Namespace) -> int:
    from src.infrastructure.assurance.pocketbase_lifecycle import create_collections  # noqa: PLC0415

    try:
        result = create_collections(args.base_url, args.admin_token)
        print(json.dumps(result, indent=2))
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def cmd_pocketbase_status(args: argparse.Namespace) -> int:
    from src.infrastructure.assurance.pocketbase_lifecycle import check_health  # noqa: PLC0415

    healthy = check_health(args.base_url)
    print(json.dumps({"base_url": args.base_url, "healthy": healthy}, indent=2))
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
    """Backend-aware chain integrity check. No key required for private-git."""
    from src.config.settings import storage_assurance_store_backend  # noqa: PLC0415

    try:
        store_backend = storage_assurance_store_backend()
    except ValueError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 2

    if store_backend == "private-git":
        return _verify_private_git(args)

    from src.infrastructure.assurance._archive import SQLCipherAssuranceArchive  # noqa: PLC0415
    from src.infrastructure.assurance._sqlcipher_store import SQLCipherAssuranceStore  # noqa: PLC0415

    db_path = Path(args.db_path) if args.db_path else _default_db_path()
    store = SQLCipherAssuranceStore(db_path)
    try:
        store.unlock()
        archive = SQLCipherAssuranceArchive(lambda: store._conn)  # noqa: SLF001
        ok = archive.verify_chain()
        entries = archive.list_entries(limit=100_000)
        print(json.dumps({"chain_valid": ok, "entry_count": len(entries), "db_path": str(db_path)}, indent=2))
        return 0 if ok else 2
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        store.lock()


def _verify_private_git(args: argparse.Namespace) -> int:
    repo_path = _workspace_root() / ".arch-assurance-git"
    chain_path = repo_path / "log" / "chain.jsonl"
    if not chain_path.exists():
        result = {"chain_valid": True, "entry_count": 0, "backend": "private-git",
                  "note": "No chain.jsonl found — log is empty."}
        print(json.dumps(result, indent=2))
        return 0
    lines = [json.loads(r) for raw in chain_path.read_text(encoding="utf-8").splitlines() if (r := raw.strip())]
    prev_hash = ""
    ok = True
    for row in lines:
        row_ok = bool(row.get("entry_hash")) and str(row.get("prev_hash", "")) == prev_hash
        print(f"  seq={row.get('seq')}: {'OK' if row_ok else 'FAIL'}")
        if not row_ok:
            ok = False
        prev_hash = str(row.get("entry_hash", ""))
    print(json.dumps({"chain_valid": ok, "entry_count": len(lines), "backend": "private-git"}, indent=2))
    return 0 if ok else 2


def cmd_verify_chain(args: argparse.Namespace) -> int:
    from src.infrastructure.assurance._archive import SQLCipherAssuranceArchive  # noqa: PLC0415
    from src.infrastructure.assurance._sqlcipher_store import SQLCipherAssuranceStore  # noqa: PLC0415

    db_path = Path(args.db_path) if args.db_path else _default_db_path()
    store = SQLCipherAssuranceStore(db_path)
    try:
        store.unlock()
        archive = SQLCipherAssuranceArchive(lambda: store._conn)  # noqa: SLF001
        ok = archive.verify_chain()
        print(json.dumps({"chain_valid": ok, "db_path": str(db_path)}, indent=2))
        return 0 if ok else 2
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        store.lock()
