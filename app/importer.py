from __future__ import annotations

import hashlib
import logging
import os
import shutil
from pathlib import Path

from .state import StateStore

logger = logging.getLogger(__name__)

HASH_CHUNK_SIZE = 1024 * 1024


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(HASH_CHUNK_SIZE), b""):
            h.update(chunk)
    return h.hexdigest()


def fix_library_permissions(library_dir: Path) -> None:
    """Ensure all files and directories in library_dir have readable permissions."""
    if not library_dir.exists():
        return
    for path in library_dir.rglob("*"):
        try:
            if path.is_symlink():
                continue
            elif path.is_file():
                path.chmod(0o664)
            elif path.is_dir():
                path.chmod(0o775)
        except OSError:
            pass


def import_gpth_output(
    gpth_output_dir: Path, library_dir: Path, state: StateStore, export_ts: str
) -> None:
    """Copy every file and symlink gpth produced into the permanent library, skipping
    anything whose content hash is already recorded there. Canonical files land in ALL_PHOTOS,
    while album shortcuts are preserved in Albums/ as symlinks taking zero extra disk space.
    """
    imported, skipped, symlinks_created = 0, 0, 0
    for src_path in gpth_output_dir.rglob("*"):
        # Skip directories
        if src_path.is_dir() and not src_path.is_symlink():
            continue

        # Skip gpth operational artifacts (logs, progress files)
        if src_path.name.endswith(".log") or src_path.name == "progress.json":
            continue

        rel_path = src_path.relative_to(gpth_output_dir)
        dest_path = library_dir / rel_path

        # Case 1: Album shortcut / Symlink
        if src_path.is_symlink():
            link_target = os.readlink(src_path)
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                dest_path.parent.chmod(0o775)
            except OSError:
                pass

            if dest_path.is_symlink() or dest_path.exists():
                dest_path.unlink()

            os.symlink(link_target, dest_path)
            symlinks_created += 1
            continue

        # Case 2: Canonical media file
        if not src_path.is_file():
            continue

        file_hash = _hash_file(src_path)
        if state.has_hash(file_hash):
            skipped += 1
            continue

        dest_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            dest_path.parent.chmod(0o775)
        except OSError:
            pass

        counter = 1
        while dest_path.exists():
            dest_path = dest_path.with_name(f"{dest_path.stem}_{counter}{dest_path.suffix}")
            counter += 1

        shutil.copy2(src_path, dest_path)
        try:
            dest_path.chmod(0o664)
        except OSError:
            pass

        state.record_hash(file_hash, str(dest_path), export_ts)
        imported += 1

    logger.info(
        "Import complete: %d new files, %d already backed up, %d album shortcuts created",
        imported,
        skipped,
        symlinks_created,
    )
