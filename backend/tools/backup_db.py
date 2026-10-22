#!/usr/bin/env python3
"""SQLite Hot Backup Utility for Project Garuda.

Safely performs atomic hot backups of the SQLite database using Python's
standard library `sqlite3.connect().backup()`. Verifies database integrity
via `PRAGMA integrity_check`, compresses the result using gzip, and maintains
a `*_latest.db.gz` symlink for operational runbooks.

Usage:
    python3 -m tools.backup_db [--db-path PATH] [--output-dir DIR]
"""

import argparse
import gzip
import logging
from datetime import UTC, datetime
from pathlib import Path
import shutil
import sqlite3
import sys
from typing import Optional

logger = logging.getLogger("garuda.backup")


def get_default_db_path() -> Path:
    """Resolve default SQLite database path from application settings or fallback."""
    try:
        from app.core.config import settings

        db_url = settings.DATABASE_URL
        if db_url.startswith("sqlite:///"):
            path_str = db_url[len("sqlite:///") :]
        elif db_url.startswith("sqlite://"):
            path_str = db_url[len("sqlite://") :]
        else:
            path_str = "garuda_local.db"
    except Exception:
        path_str = "garuda_local.db"

    candidate = Path(path_str)
    if candidate.exists():
        return candidate

    # Check relative to working directory or repository root
    cwd_candidate = (Path.cwd() / path_str).resolve()
    if cwd_candidate.exists():
        return cwd_candidate

    parent_candidate = (Path.cwd().parent / path_str).resolve()
    if parent_candidate.exists():
        return parent_candidate

    return candidate


def backup_database(
    db_path: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    keep_uncompressed: bool = False,
) -> Path:
    """Perform hot backup of SQLite database, run integrity check, and compress.

    Args:
        db_path: Path to source SQLite database. If None, resolves from settings.
        output_dir: Directory where backups will be stored. Defaults to Path("backups").
        keep_uncompressed: Whether to keep the uncompressed .db file. Defaults to False.

    Returns:
        Path to the generated .gz backup archive.

    Raises:
        FileNotFoundError: If the source database does not exist.
        RuntimeError: If PRAGMA integrity_check fails on the backup.
    """
    source_path = (db_path or get_default_db_path()).resolve()
    if not source_path.exists() or not source_path.is_file():
        raise FileNotFoundError(f"Source database file not found at: {source_path}")

    target_dir = (output_dir or Path("backups")).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    stem = source_path.stem
    uncompressed_file = target_dir / f"{stem}_{timestamp}.db"
    compressed_file = target_dir / f"{stem}_{timestamp}.db.gz"
    latest_symlink = target_dir / f"{stem}_latest.db.gz"

    logger.info("Initiating hot backup from '%s' to '%s'...", source_path, uncompressed_file)

    # 1. Atomic hot backup using sqlite3.Connection.backup()
    src_conn = sqlite3.connect(str(source_path))
    dest_conn = sqlite3.connect(str(uncompressed_file))
    try:
        src_conn.backup(dest_conn)
    finally:
        dest_conn.close()
        src_conn.close()

    logger.info("Hot backup completed. Running integrity check...")

    # 2. PRAGMA integrity_check verification
    verify_conn = sqlite3.connect(str(uncompressed_file))
    try:
        cursor = verify_conn.cursor()
        cursor.execute("PRAGMA integrity_check;")
        rows = cursor.fetchall()
    finally:
        verify_conn.close()

    if rows != [("ok",)]:
        if uncompressed_file.exists():
            uncompressed_file.unlink()
        raise RuntimeError(f"Integrity check failed on backup {uncompressed_file}: {rows}")

    logger.info("Integrity check passed (PRAGMA integrity_check == ok). Compressing...")

    # 3. Gzip compression (100% standard library)
    with open(uncompressed_file, "rb") as f_in, gzip.open(compressed_file, "wb", compresslevel=9) as f_out:
        shutil.copyfileobj(f_in, f_out)

    if not keep_uncompressed and uncompressed_file.exists():
        uncompressed_file.unlink()

    # 4. Update 'latest' pointer (relative symlink)
    try:
        if latest_symlink.is_symlink() or latest_symlink.exists():
            latest_symlink.unlink()
        latest_symlink.symlink_to(compressed_file.name)
    except OSError:
        pass  # Best effort on platforms that restrict symlinks

    size_bytes = compressed_file.stat().st_size
    logger.info("Backup successful: %s (%d bytes)", compressed_file, size_bytes)
    return compressed_file


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Safely perform hot backups of SQLite database using standard library."
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=None,
        help="Path to source SQLite database file (defaults to config settings.DATABASE_URL)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("backups"),
        help="Directory to save backup archives (default: backups/)",
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    args = parse_args(argv)
    try:
        compressed_path = backup_database(
            db_path=args.db_path,
            output_dir=args.output_dir,
        )
        print(f"Hot backup created successfully: {compressed_path}")
        return 0
    except Exception as err:
        logger.error("Hot backup failed: %s", err)
        return 1


if __name__ == "__main__":
    sys.exit(main())
