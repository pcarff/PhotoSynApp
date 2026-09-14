from __future__ import annotations

import argparse
import logging
import os
import time
from datetime import datetime, timedelta, timezone

from . import extractor, gpth_runner, importer
from .config import Config, load_config
from .drive_client import DriveClient
from .logging_setup import setup_logging
from .metadata_tagger import MetadataTagger
from .state import StateStore
from .takeout_group import group_takeout_files, is_group_complete

logger = logging.getLogger(__name__)


MEDIA_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".heic",
    ".mp4", ".mov", ".avi", ".mkv", ".m4v", ".dng", ".raw", ".cr2", ".nef"
}


def _has_media_files(extracted_dir: Path) -> bool:
    for p in extracted_dir.rglob("*"):
        if p.is_file() and p.suffix.lower() in MEDIA_EXTENSIONS:
            return True
    return False


def run_once(cfg: Config, drive: DriveClient, state: StateStore) -> None:
    folder_id = cfg.drive.folder_id or drive.find_folder_id(cfg.drive.folder_name)
    files = drive.list_takeout_files(folder_id)
    groups = group_takeout_files(files)

    now = datetime.now(timezone.utc)
    quiet_period = timedelta(minutes=cfg.quiet_period_minutes)

    for group in groups:
        if all(state.is_drive_file_processed(f.file_id) for f in group.files):
            continue
        if not is_group_complete(group, now, quiet_period):
            logger.info("Export %s still uploading, skipping for now", group.export_id)
            continue

        logger.info("Processing export %s (%d parts)", group.export_id, len(group.files))
        raw_dir = cfg.raw_dir / group.export_id
        extracted_dir = cfg.extracted_dir / group.export_id
        gpth_out_dir = cfg.gpth_output_dir / group.export_id

        try:
            for f in group.sorted_files():
                dest = raw_dir / f.name
                logger.info("Downloading %s ...", f.name)
                drive.download_file(f.file_id, dest)
                extractor.extract_archives([dest], extracted_dir)
                dest.unlink(missing_ok=True)

            if not _has_media_files(extracted_dir):
                logger.info(
                    "Export %s contains no media files (likely index or metadata archive), skipping gpth",
                    group.export_id,
                )
            else:
                logger.info("Scanning Takeout JSON sidecars for favorites and captions...")
                fav_names, descriptions = MetadataTagger.parse_takeout_metadata(extracted_dir)
                if fav_names:
                    logger.info("Found %d favorited items in Takeout metadata", len(fav_names))

                gpth_runner.run_gpth(cfg.gpth, extracted_dir, gpth_out_dir)

                if fav_names or descriptions:
                    tagged = MetadataTagger.tag_favorites_in_directory(gpth_out_dir, fav_names, descriptions)
                    logger.info("Injected 5-star favorite ratings/captions into %d photos", tagged)

                importer.import_gpth_output(gpth_out_dir, cfg.library_dir, state, group.export_id)

            for f in group.files:
                state.mark_drive_file_processed(f.file_id, group.export_id, now.isoformat())
        finally:
            extractor.cleanup_dir(raw_dir)
            extractor.cleanup_dir(extracted_dir)
            extractor.cleanup_dir(gpth_out_dir)


def main() -> None:
    parser = argparse.ArgumentParser(description="PhotoSynApp - Google Photos Takeout backup")
    parser.add_argument(
        "--config",
        default=os.environ.get("CONFIG_PATH", "/config/config.yaml"),
        help="Path to YAML configuration file (default: $CONFIG_PATH or /config/config.yaml)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single check/sync cycle and exit immediately instead of polling continuously",
    )
    args = parser.parse_args()

    os.umask(0o002)
    setup_logging(os.environ.get("LOG_LEVEL", "INFO"))
    cfg = load_config(args.config)

    state = StateStore(cfg.state_db_path)
    drive = DriveClient(cfg.drive.token_path)

    # Ensure existing library files have proper permissions
    importer.fix_library_permissions(cfg.library_dir)

    if args.once:
        logger.info("Running single PhotoSync cycle with config: %s", args.config)
        run_once(cfg, drive, state)
        logger.info("Single cycle complete.")
        return

    logger.info("PhotoSync starting, poll interval = %d minutes", cfg.poll_interval_minutes)
    while True:
        try:
            run_once(cfg, drive, state)
        except Exception:
            logger.exception("Run failed")
        time.sleep(cfg.poll_interval_minutes * 60)


if __name__ == "__main__":
    main()
