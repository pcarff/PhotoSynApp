from __future__ import annotations

import dataclasses
import re
from datetime import datetime, timedelta

TAKEOUT_FILENAME_RE = re.compile(
    r"^(?P<export_id>takeout-\d{8}T\d{6}Z)(?:-(?P<part_info>\d+(?:-\d+)*))\.(?P<ext>zip|tgz)$"
)


@dataclasses.dataclass
class DriveFile:
    file_id: str
    name: str
    modified_time: datetime  # tz-aware


@dataclasses.dataclass
class TakeoutGroup:
    export_id: str
    files: list[DriveFile]

    @property
    def latest_modified_time(self) -> datetime:
        return max(f.modified_time for f in self.files)

    def sorted_files(self) -> list[DriveFile]:
        def sort_key(f: DriveFile) -> tuple[int, ...]:
            m = TAKEOUT_FILENAME_RE.match(f.name)
            if not m or not m.group("part_info"):
                return (0,)
            return tuple(int(n) for n in m.group("part_info").split("-"))

        return sorted(self.files, key=sort_key)


def group_takeout_files(files: list[DriveFile]) -> list[TakeoutGroup]:
    """Group Drive files by Takeout export id, ignoring anything that
    doesn't match the expected `takeout-<timestamp>-<part>.(zip|tgz)` pattern.
    """
    groups: dict[str, list[DriveFile]] = {}
    for f in files:
        m = TAKEOUT_FILENAME_RE.match(f.name)
        if not m:
            continue
        groups.setdefault(m.group("export_id"), []).append(f)

    return [TakeoutGroup(export_id=eid, files=fs) for eid, fs in groups.items()]


def is_group_complete(group: TakeoutGroup, now: datetime, quiet_period: timedelta) -> bool:
    """A Takeout export uploads its parts sequentially with no reliable
    total-part-count signal, so we treat a group as fully uploaded once its
    most recently modified part has sat untouched for `quiet_period`.
    """
    return now - group.latest_modified_time >= quiet_period
