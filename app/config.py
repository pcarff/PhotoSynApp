from __future__ import annotations

import dataclasses
from pathlib import Path

import yaml


@dataclasses.dataclass
class DriveConfig:
    folder_name: str
    folder_id: str | None
    token_path: Path


@dataclasses.dataclass
class GpthConfig:
    binary_path: Path
    extra_args: list[str]


@dataclasses.dataclass
class Config:
    drive: DriveConfig
    poll_interval_minutes: int
    quiet_period_minutes: int
    staging_dir: Path
    library_dir: Path
    state_db_path: Path
    gpth: GpthConfig

    @property
    def raw_dir(self) -> Path:
        return self.staging_dir / "raw"

    @property
    def extracted_dir(self) -> Path:
        return self.staging_dir / "extracted"

    @property
    def gpth_output_dir(self) -> Path:
        return self.staging_dir / "gpth-out"


def load_config(path: str | Path) -> Config:
    data = yaml.safe_load(Path(path).read_text())

    drive_data = data["drive"]
    drive = DriveConfig(
        folder_name=drive_data["folder_name"],
        folder_id=drive_data.get("folder_id"),
        token_path=Path(drive_data["token_path"]),
    )

    gpth_data = data.get("gpth", {})
    gpth = GpthConfig(
        binary_path=Path(gpth_data.get("binary_path", "/usr/local/bin/gpth")),
        extra_args=list(gpth_data.get("extra_args", [])),
    )

    return Config(
        drive=drive,
        poll_interval_minutes=int(data.get("poll_interval_minutes", 360)),
        quiet_period_minutes=int(data.get("quiet_period_minutes", 45)),
        staging_dir=Path(data["staging_dir"]),
        library_dir=Path(data["library_dir"]),
        state_db_path=Path(data["state_db_path"]),
        gpth=gpth,
    )
