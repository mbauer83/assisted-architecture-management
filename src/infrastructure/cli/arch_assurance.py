"""arch-assurance CLI — confidential assurance store lifecycle management.

Commands:
  init                  Initialise a new encrypted assurance store
  status                Show store configuration and lock status
  unlock                Verify the encryption key works and report store stats
  backup                Copy the encrypted DB to a timestamped backup file
  export                Export all assurance data to a JSON file (plaintext)
  rotate-key            Generate new encryption key and re-encrypt the store
  export-key            Print recovery key from the OS keychain
  verify-chain          Verify the audit log hash chain integrity
  pocketbase-init       Initialise PocketBase collections
  pocketbase-status     Check PocketBase health
  import-sbom           Ingest a CycloneDX or SPDX BOM file
  export-aibom          Emit a CycloneDX 1.6 AI-BOM from provided components JSON
  scan-ai-candidates    Heuristic scan of architecture entities for AI-BOM relevance
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _workspace_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _default_db_path() -> Path:
    return _workspace_root() / ".arch-assurance" / "store.db"


def _cmd_init(args: argparse.Namespace) -> int:
    from src.infrastructure.assurance.lifecycle import init_store  # noqa: PLC0415

    db_path = Path(args.db_path) if args.db_path else _default_db_path()
    try:
        result = init_store(db_path, force=args.force)
        print(json.dumps(result, indent=2))
        return 0
    except FileExistsError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def _cmd_status(args: argparse.Namespace) -> int:
    from src.infrastructure.assurance._sqlcipher_store import SQLCipherAssuranceStore  # noqa: PLC0415

    db_path = Path(args.db_path) if args.db_path else _default_db_path()
    store = SQLCipherAssuranceStore(db_path)
    try:
        import keyring  # type: ignore[import-untyped]

        key_present = keyring.get_password("arch-assurance", "db-encryption-key") is not None
    except Exception:  # noqa: BLE001
        key_present = False

    status = {
        "db_path": str(db_path),
        "db_exists": db_path.exists(),
        "key_in_keychain": key_present,
        "unlocked": store.is_unlocked(),
        "status": (
            "unlocked"
            if store.is_unlocked()
            else ("locked" if db_path.exists() and key_present else "not_initialised")
        ),
    }
    print(json.dumps(status, indent=2))
    return 0


def _cmd_unlock(args: argparse.Namespace) -> int:
    from src.infrastructure.assurance._sqlcipher_store import SQLCipherAssuranceStore  # noqa: PLC0415

    db_path = Path(args.db_path) if args.db_path else _default_db_path()
    store = SQLCipherAssuranceStore(db_path)
    try:
        store.unlock()
        stats = store.stats()
        store.lock()
        result = {
            "status": "unlocked_and_verified",
            "db_path": str(db_path),
            "stats": stats,
            "note": "Key verified. Restart arch-backend to reload the assurance module.",
        }
        print(json.dumps(result, indent=2))
        return 0
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def _cmd_backup(args: argparse.Namespace) -> int:
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


def _cmd_export(args: argparse.Namespace) -> int:
    from src.infrastructure.assurance._sqlcipher_store import SQLCipherAssuranceStore  # noqa: PLC0415
    from src.infrastructure.assurance.lifecycle import export_store  # noqa: PLC0415

    db_path = Path(args.db_path) if args.db_path else _default_db_path()
    output_path = Path(args.output)
    store = SQLCipherAssuranceStore(db_path)
    try:
        store.unlock()
        result = export_store(store, output_path)
        print(json.dumps(result, indent=2))
        return 0
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        store.lock()


def _cmd_rotate_key(args: argparse.Namespace) -> int:
    from src.infrastructure.assurance.lifecycle import rotate_key  # noqa: PLC0415

    db_path = Path(args.db_path) if args.db_path else _default_db_path()
    try:
        result = rotate_key(db_path)
        print(json.dumps(result, indent=2))
        return 0
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def _cmd_export_key(_args: argparse.Namespace) -> int:
    from src.infrastructure.assurance.lifecycle import export_recovery_key  # noqa: PLC0415

    try:
        result = export_recovery_key()
        print(json.dumps(result, indent=2))
        print("\nSTORE THIS KEY SECURELY OFFLINE.", file=sys.stderr)
        return 0
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def _cmd_pocketbase_init(args: argparse.Namespace) -> int:
    from src.infrastructure.assurance.pocketbase_lifecycle import create_collections  # noqa: PLC0415

    try:
        result = create_collections(args.base_url, args.admin_token)
        print(json.dumps(result, indent=2))
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def _cmd_pocketbase_status(args: argparse.Namespace) -> int:
    from src.infrastructure.assurance.pocketbase_lifecycle import check_health  # noqa: PLC0415

    healthy = check_health(args.base_url)
    result = {"base_url": args.base_url, "healthy": healthy}
    print(json.dumps(result, indent=2))
    return 0 if healthy else 1


def _cmd_import_sbom(args: argparse.Namespace) -> int:
    from src.infrastructure.cli._security_commands import cmd_import_sbom  # noqa: PLC0415

    return cmd_import_sbom(args, _workspace_root())


def _cmd_export_aibom(args: argparse.Namespace) -> int:
    from src.infrastructure.cli._security_commands import cmd_export_aibom  # noqa: PLC0415

    return cmd_export_aibom(args)


def _cmd_scan_ai_candidates(args: argparse.Namespace) -> int:
    from src.infrastructure.cli._security_commands import cmd_scan_ai_candidates  # noqa: PLC0415

    return cmd_scan_ai_candidates(args)


def _cmd_verify_chain(args: argparse.Namespace) -> int:
    from src.infrastructure.assurance._archive import SQLCipherAssuranceArchive  # noqa: PLC0415
    from src.infrastructure.assurance._sqlcipher_store import SQLCipherAssuranceStore  # noqa: PLC0415

    db_path = Path(args.db_path) if args.db_path else _default_db_path()
    store = SQLCipherAssuranceStore(db_path)
    try:
        store.unlock()
        archive = SQLCipherAssuranceArchive(lambda: store._conn)  # noqa: SLF001
        ok = archive.verify_chain()
        result = {"chain_valid": ok, "db_path": str(db_path)}
        print(json.dumps(result, indent=2))
        return 0 if ok else 2
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        store.lock()


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="arch-assurance",
        description="Manage the confidential assurance store lifecycle.",
    )
    parser.add_argument("--db-path", metavar="PATH", help="Override default DB path")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Initialise a new encrypted assurance store")
    p_init.add_argument("--force", action="store_true", help="Overwrite existing store")

    sub.add_parser("status", help="Show store configuration and lock status")
    sub.add_parser("unlock", help="Verify the encryption key works and report store stats")

    p_backup = sub.add_parser("backup", help="Backup the encrypted DB")
    p_backup.add_argument("--backup-path", metavar="PATH", help="Destination path")

    p_export = sub.add_parser("export", help="Export all data to JSON (decrypted — handle carefully)")
    p_export.add_argument("--output", required=True, metavar="PATH", help="Output JSON file path")

    sub.add_parser("rotate-key", help="Generate new encryption key and re-encrypt the store")
    sub.add_parser("export-key", help="Print recovery key from the OS keychain")
    sub.add_parser("verify-chain", help="Verify the audit log hash chain integrity")

    p_pb_init = sub.add_parser("pocketbase-init", help="Initialise PocketBase collections for assurance")
    p_pb_init.add_argument("--base-url", required=True, metavar="URL", help="PocketBase base URL")
    p_pb_init.add_argument("--admin-token", required=True, metavar="TOKEN", help="PocketBase admin Bearer token")

    p_pb_status = sub.add_parser("pocketbase-status", help="Check PocketBase health")
    p_pb_status.add_argument("--base-url", required=True, metavar="URL", help="PocketBase base URL")

    p_import_sbom = sub.add_parser("import-sbom", help="Ingest a CycloneDX or SPDX BOM file")
    p_import_sbom.add_argument("file", metavar="FILE", help="Path to the BOM JSON file")
    p_import_sbom.add_argument("--anchor", metavar="ENTITY_ID", help="Architecture entity ID to anchor this BOM to")
    p_import_sbom.add_argument("--signals-db-path", metavar="PATH", help="Override security signals DB path")

    p_export_aibom = sub.add_parser("export-aibom", help="Emit a CycloneDX 1.6 AI-BOM")
    p_export_aibom.add_argument("--components-file", metavar="PATH", help="JSON file with AI-component dicts")
    p_export_aibom.add_argument("--output", metavar="PATH", help="Output file (default: stdout)")

    p_scan = sub.add_parser("scan-ai-candidates", help="Heuristic AI-BOM candidate scan")
    p_scan.add_argument("--entities-file", metavar="PATH", help="JSON file with architecture entity dicts")

    args = parser.parse_args()
    dispatch = {
        "init": _cmd_init,
        "status": _cmd_status,
        "unlock": _cmd_unlock,
        "backup": _cmd_backup,
        "export": _cmd_export,
        "rotate-key": _cmd_rotate_key,
        "export-key": _cmd_export_key,
        "verify-chain": _cmd_verify_chain,
        "pocketbase-init": _cmd_pocketbase_init,
        "pocketbase-status": _cmd_pocketbase_status,
        "import-sbom": _cmd_import_sbom,
        "export-aibom": _cmd_export_aibom,
        "scan-ai-candidates": _cmd_scan_ai_candidates,
    }
    sys.exit(dispatch[args.command](args))


if __name__ == "__main__":
    main()
