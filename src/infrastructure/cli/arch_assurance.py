"""arch-assurance CLI — confidential assurance store lifecycle management.

Commands:
  init                  Initialise a new encrypted assurance store
  status                Show store configuration, backends, and lock status
  use-backend           Switch the active storage backend in config (writes settings.yaml)
  unlock                Verify the encryption key works and report store stats
  backup                Copy the encrypted DB to a timestamped backup file
  export                Export all assurance data to a JSON file (plaintext)
  rotate-key            Generate new encryption key and re-encrypt the store
  export-key            Print recovery key from the OS keychain
  verify                Backend-aware chain integrity check (private-git: no key required)
  verify-chain          Verify the audit log hash chain integrity (sqlcipher only)
  pocketbase-init       Initialise PocketBase collections
  pocketbase-status     Check PocketBase health
  import-sbom           Ingest a CycloneDX or SPDX BOM file
  export-aibom          Emit a CycloneDX 1.6 AI-BOM from provided components JSON
  scan-ai-candidates    Heuristic scan of architecture entities for AI-BOM relevance
"""

from __future__ import annotations

import argparse
import sys

from src.infrastructure.cli._assurance_commands import (
    cmd_backup,
    cmd_export,
    cmd_export_aibom,
    cmd_export_key,
    cmd_import_sbom,
    cmd_init,
    cmd_pocketbase_init,
    cmd_pocketbase_status,
    cmd_rotate_key,
    cmd_scan_ai_candidates,
    cmd_status,
    cmd_unlock,
    cmd_use_backend,
    cmd_verify,
    cmd_verify_chain,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="arch-assurance",
        description="Manage the confidential assurance store lifecycle.",
    )
    parser.add_argument("--db-path", metavar="PATH", help="Override default DB path")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Initialise a new encrypted assurance store")
    p_init.add_argument("--force", action="store_true", help="Overwrite existing store")
    p_init.add_argument(
        "--backend", metavar="BACKEND",
        choices=["sqlcipher", "pocketbase", "private-git"], default="sqlcipher",
        help="Store backend (default: sqlcipher)",
    )
    p_init.add_argument(
        "--signals", metavar="SIGNALS",
        choices=["sqlcipher-colocated", "sqlite", "encrypted"], default=None,
        help="Signals backend (default: sqlcipher-colocated for sqlcipher, sqlite otherwise)",
    )

    p_use_backend = sub.add_parser("use-backend", help="Switch the active storage backend in config/settings.yaml")
    p_use_backend.add_argument(
        "backend", choices=["sqlcipher", "pocketbase", "private-git"],
        help="Store backend to activate",
    )
    p_use_backend.add_argument(
        "--signals", metavar="SIGNALS",
        choices=["sqlcipher-colocated", "sqlite", "encrypted"], default=None,
        help="Signals backend to activate (default: auto-selected for backend)",
    )

    sub.add_parser("status", help="Show store configuration, backends, and lock status")
    sub.add_parser("unlock", help="Verify the encryption key works and report store stats")

    p_backup = sub.add_parser("backup", help="Backup the encrypted DB")
    p_backup.add_argument("--backup-path", metavar="PATH", help="Destination path")

    p_export = sub.add_parser("export", help="Export all data to JSON (decrypted — handle carefully)")
    p_export.add_argument("--output", required=True, metavar="PATH", help="Output JSON file path")

    sub.add_parser("rotate-key", help="Generate new encryption key and re-encrypt the store")
    sub.add_parser("export-key", help="Print recovery key from the OS keychain")
    sub.add_parser("verify", help="Backend-aware chain integrity check (private-git: no key required)")
    sub.add_parser("verify-chain", help="Verify the audit log hash chain integrity (sqlcipher only)")

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
        "init": cmd_init, "status": cmd_status, "use-backend": cmd_use_backend,
        "unlock": cmd_unlock, "backup": cmd_backup, "export": cmd_export,
        "rotate-key": cmd_rotate_key, "export-key": cmd_export_key,
        "verify": cmd_verify, "verify-chain": cmd_verify_chain,
        "pocketbase-init": cmd_pocketbase_init, "pocketbase-status": cmd_pocketbase_status,
        "import-sbom": cmd_import_sbom, "export-aibom": cmd_export_aibom,
        "scan-ai-candidates": cmd_scan_ai_candidates,
    }
    sys.exit(dispatch[args.command](args))


if __name__ == "__main__":
    main()
