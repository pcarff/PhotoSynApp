#!/usr/bin/env python3
"""
add_scanned_photo.py - Ingest scanned photos into the photo library and update the PhotoSynApp SQLite hash database.

Usage:
    add_scanned_photo.py <photo_path> --target <laura|paul> --year <YYYY> --month <MM> [--move]
"""

import argparse
import hashlib
import os
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

HASH_CHUNK_SIZE = 1024 * 1024


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(HASH_CHUNK_SIZE):
            h.update(chunk)
    return h.hexdigest()


def ingest_photo(
    src_path: Path,
    target: str,
    year: str,
    month: str,
    move: bool = False,
    custom_name: str | None = None,
) -> Path:
    src = Path(src_path).resolve()
    if not src.is_file():
        raise FileNotFoundError(f"Source file not found: {src}")

    # Format year and month (ensure 2-digit month)
    year_str = str(int(year))
    month_str = f"{int(month):02d}"

    # Determine destination root & state DB based on target
    if target.lower() == "laura":
        dest_root = Path("/Workspaces/Photos/Laura_Only")
        db_path = Path("/workspaces_nvme/PhotoSynApp/state/state_laura.sqlite3")
        nas_base = "/volume1/PhotoSync/Laura/ALL_PHOTOS"
    elif target.lower() == "paul":
        dest_root = Path("/Workspaces/Photos/Paul_Combined")
        db_path = Path("/workspaces_nvme/PhotoSynApp/state/state.sqlite3")
        nas_base = "/volume1/PhotoSync/ALL_PHOTOS"
    else:
        raise ValueError(f"Unknown target: {target}. Must be 'laura' or 'paul'.")

    dest_dir = dest_root / year_str / month_str
    dest_dir.mkdir(parents=True, exist_ok=True)
    try:
        dest_dir.chmod(0o2775)
    except OSError:
        pass

    dest_filename = custom_name or src.name
    dest_path = dest_dir / dest_filename

    # Avoid accidental overwrites
    counter = 1
    stem = Path(dest_filename).stem
    suffix = Path(dest_filename).suffix
    while dest_path.exists():
        # If it's already identical content, alert
        if sha256_file(dest_path) == sha256_file(src):
            print(f"ℹ️  Exact file already exists at: {dest_path}")
            break
        dest_path = dest_dir / f"{stem}_{counter}{suffix}"
        counter += 1

    # 1. Compute SHA-256 Hash
    file_hash = sha256_file(src)

    # 2. Copy or Move the file
    if not dest_path.exists() or sha256_file(dest_path) != file_hash:
        if move:
            shutil.move(str(src), str(dest_path))
            print(f"🚚 Moved: {src.name} -> {dest_path}")
        else:
            shutil.copy2(str(src), str(dest_path))
            print(f"📋 Copied: {src.name} -> {dest_path}")

    # 3. Fix permissions for Samba & local user
    try:
        dest_path.chmod(0o664)
    except OSError:
        pass

    # 4. Update SQLite State Database
    export_ts = f"manual_scan-{datetime.now().strftime('%Y%m%d')}"
    # Record both local and NAS-equivalent path for consistency
    nas_rel_path = f"{nas_base}/{year_str}/{month_str}/{dest_path.name}"

    if db_path.exists():
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        # Check if already present
        cur.execute("SELECT path FROM library_files WHERE hash = ?", (file_hash,))
        existing = cur.fetchone()
        if existing:
            print(f"ℹ️  Hash {file_hash[:12]}... already recorded in DB (path: {existing[0]}).")
        else:
            cur.execute(
                "INSERT OR IGNORE INTO library_files (hash, path, first_seen_export_ts) VALUES (?, ?, ?)",
                (file_hash, nas_rel_path, export_ts),
            )
            conn.commit()
            print(f"✅ Hash DB updated: {file_hash[:12]}... registered in {db_path.name}")
        conn.close()
    else:
        print(f"⚠️ Warning: Database {db_path} not found.")

    return dest_path


def main():
    parser = argparse.ArgumentParser(description="Ingest photo and update PhotoSynApp hash database.")
    parser.add_argument("photo", help="Path to photo file")
    parser.add_argument("--target", choices=["laura", "paul"], default="laura", help="Target library (default: laura)")
    parser.add_argument("--year", required=True, help="Year (e.g. 1924)")
    parser.add_argument("--month", required=True, help="Month (e.g. 8 or 08)")
    parser.add_argument("--move", action="store_true", help="Move file instead of copy")
    parser.add_argument("--name", help="Custom destination filename")

    args = parser.parse_args()
    ingest_photo(
        src_path=Path(args.photo),
        target=args.target,
        year=args.year,
        month=args.month,
        move=args.move,
        custom_name=args.name,
    )


if __name__ == "__main__":
    main()
