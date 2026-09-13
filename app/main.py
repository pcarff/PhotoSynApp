from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timedelta, timezone

from . import extractor, gpth_runner, importer
from .config import Config, load_config
from .drive_client import DriveClient
from .logging_setup import setup_logging
from .state import StateStore
from .takeout_group import group_takeout_files, is_group_complete

logger = logging.getLogger(__name__)


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
            archive_paths = []
            for f in group.sorted_files():
                dest = raw_dir / f.name
                drive.download_file(f.file_id, dest)
                archive_paths.append(dest)

            extractor.extract_archives(archive_paths, extracted_dir)
            gpth_runner.run_gpth(cfg.gpth, extracted_dir, gpth_out_dir)
            importer.import_gpth_output(gpth_out_dir, cfg.library_dir, state, group.export_id)

            for f in group.files:
                state.mark_drive_file_processed(f.file_id, group.export_id, now.isoformat())
        finally:
            extractor.cleanup_dir(raw_dir)
            extractor.cleanup_dir(extracted_dir)
            extractor.cleanup_dir(gpth_out_dir)


def main() -> None:
    os.umask(0o002)
    setup_logging(os.environ.get("LOG_LEVEL", "INFO"))
    config_path = os.environ.get("CONFIG_PATH", "/config/config.yaml")
    cfg = load_config(config_path)

    state = StateStore(cfg.state_db_path)
    drive = DriveClient(cfg.drive.token_path)

    # Ensure existing library files have proper permissions
    importer.fix_library_permissions(cfg.library_dir)

    logger.info("PhotoSync starting, poll interval = %d minutes", cfg.poll_interval_minutes)
    while True:
        try:
            run_once(cfg, drive, state)
        except Exception:
            logger.exception("Run failed")
        time.sleep(cfg.poll_interval_minutes * 60)


if __name__ == "__main__":
    main()
