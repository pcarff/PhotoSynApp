from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from .config import GpthConfig

logger = logging.getLogger(__name__)


def run_gpth(cfg: GpthConfig, input_dir: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(cfg.binary_path.resolve()),
        "--input", str(input_dir),
        "--output", str(output_dir),
        # 2 = year/month folders, matching the existing library's layout.
        "--divide-to-dates", "2",
        # Album folders with symlinks to canonical photos in ALL_PHOTOS
        "--albums", "shortcut",
        *cfg.extra_args,
    ]
    logger.info("Running gpth: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error("gpth stdout:\n%s", result.stdout)
        logger.error("gpth stderr:\n%s", result.stderr)
        raise RuntimeError(f"gpth failed with exit code {result.returncode}")
    logger.info("gpth completed successfully")
