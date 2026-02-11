#!/usr/bin/env python3
"""
Database backup utility for SQLite and PostgreSQL.

Examples:
  python scripts/backup_db.py
  python scripts/backup_db.py --database-url \"postgresql://user:pass@host:5432/lvmh\" --output-dir backups
"""

import argparse
import gzip
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, unquote


def parse_args():
    parser = argparse.ArgumentParser(description="Backup database (SQLite/PostgreSQL)")
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL", "sqlite:///./lvmh.db"),
        help="Database connection URL",
    )
    parser.add_argument("--output-dir", default="backups", help="Backup output directory")
    return parser.parse_args()


def backup_sqlite(database_url: str, output_dir: Path) -> Path:
    db_path = database_url.replace("sqlite:///", "", 1)
    source = Path(db_path).resolve()
    if not source.exists():
        raise FileNotFoundError(f"SQLite database not found: {source}")
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    destination = output_dir / f"{source.stem}_{timestamp}.sqlite3"
    shutil.copy2(source, destination)
    return destination


def backup_postgres(database_url: str, output_dir: Path) -> Path:
    parsed = urlparse(database_url)
    db_name = parsed.path.lstrip("/")
    if not db_name:
        raise ValueError("PostgreSQL URL missing database name")

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    destination = output_dir / f"{db_name}_{timestamp}.sql.gz"

    env = os.environ.copy()
    if parsed.password:
        env["PGPASSWORD"] = unquote(parsed.password)

    pg_dump_cmd = [
        "pg_dump",
        "--host",
        parsed.hostname or "localhost",
        "--port",
        str(parsed.port or 5432),
        "--username",
        unquote(parsed.username or ""),
        "--format=plain",
        "--no-owner",
        "--no-privileges",
        db_name,
    ]

    dump = subprocess.Popen(pg_dump_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    dump_stderr: bytes = b""
    try:
        with gzip.open(destination, "wb") as gz_out:
            assert dump.stdout is not None
            while True:
                chunk = dump.stdout.read(1024 * 1024)
                if not chunk:
                    break
                gz_out.write(chunk)
        _, dump_stderr = dump.communicate()
    finally:
        if dump.stdout:
            dump.stdout.close()
    if dump.returncode != 0:
        raise RuntimeError(f"pg_dump failed: {dump_stderr.decode('utf-8', errors='ignore')}")

    return destination


def main():
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    url = args.database_url.strip()
    if url.startswith("sqlite:///"):
        backup_file = backup_sqlite(url, output_dir)
    elif url.startswith("postgresql://") or url.startswith("postgres://"):
        backup_file = backup_postgres(url, output_dir)
    else:
        raise ValueError(f"Unsupported DATABASE_URL scheme: {url}")

    print(f"Backup created: {backup_file}")


if __name__ == "__main__":
    main()
