from __future__ import annotations

import hashlib
import logging
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


def import_gpth_output(
    gpth_output_dir: Path, library_dir: Path, state: StateStore, export_ts: str
) -> None:
    """Copy every file gpth produced into the permanent library, skipping
    anything whose content hash is already recorded there. Since Takeout
    re-exports the whole library every cycle, this dedup step is what keeps
    repeated runs from duplicating storage.
    """
    imported, skipped = 0, 0
    for src_path in gpth_output_dir.rglob("*"):
        if not src_path.is_file():
            continue

        file_hash = _hash_file(src_path)
        if state.has_hash(file_hash):
            skipped += 1
            continue

        rel_path = src_path.relative_to(gpth_output_dir)
        dest_path = library_dir / rel_path
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        counter = 1
        while dest_path.exists():
            dest_path = dest_path.with_name(f"{dest_path.stem}_{counter}{dest_path.suffix}")
            counter += 1

        shutil.copy2(src_path, dest_path)
        state.record_hash(file_hash, str(dest_path), export_ts)
        imported += 1

    logger.info("Import complete: %d new files, %d already backed up", imported, skipped)
