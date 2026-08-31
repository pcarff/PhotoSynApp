from __future__ import annotations

import logging
import shutil
import tarfile
import zipfile
from pathlib import Path

logger = logging.getLogger(__name__)


def extract_archives(archive_paths: list[Path], dest_dir: Path) -> Path:
    """Extract every archive into the same dest_dir. Google Takeout's
    multi-part exports are independent, standalone zips that each contain a
    slice of the overall folder tree, so extracting them all into one
    directory reassembles the full export.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    for archive_path in sorted(archive_paths):
        logger.info("Extracting %s -> %s", archive_path, dest_dir)
        if archive_path.suffix == ".zip":
            with zipfile.ZipFile(archive_path) as zf:
                zf.extractall(dest_dir)
        elif archive_path.name.endswith(".tgz") or archive_path.name.endswith(".tar.gz"):
            with tarfile.open(archive_path) as tf:
                tf.extractall(dest_dir)
        else:
            raise ValueError(f"Unsupported archive type: {archive_path}")
    return dest_dir


def cleanup_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
