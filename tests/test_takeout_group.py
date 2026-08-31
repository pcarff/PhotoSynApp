from datetime import datetime, timedelta, timezone

from app.takeout_group import DriveFile, group_takeout_files, is_group_complete


def _ago(minutes: int, now: datetime) -> datetime:
    return now - timedelta(minutes=minutes)


def test_groups_by_export_id():
    now = datetime.now(timezone.utc)
    files = [
        DriveFile("id1", "takeout-20260830T120000Z-001.zip", _ago(60, now)),
        DriveFile("id2", "takeout-20260830T120000Z-002.zip", _ago(50, now)),
        DriveFile("id3", "takeout-20260101T000000Z-001.zip", _ago(200, now)),
        DriveFile("id4", "not-a-takeout-file.txt", _ago(10, now)),
    ]

    groups = group_takeout_files(files)
    ids = sorted(g.export_id for g in groups)
    assert ids == ["takeout-20260101T000000Z", "takeout-20260830T120000Z"]

    group_a = next(g for g in groups if g.export_id == "takeout-20260830T120000Z")
    assert len(group_a.files) == 2
    assert [f.file_id for f in group_a.sorted_files()] == ["id1", "id2"]


def test_group_complete_after_quiet_period():
    now = datetime.now(timezone.utc)
    files = [
        DriveFile("id1", "takeout-20260830T120000Z-001.zip", _ago(60, now)),
        DriveFile("id2", "takeout-20260830T120000Z-002.zip", _ago(50, now)),
    ]
    group = group_takeout_files(files)[0]

    assert is_group_complete(group, now, timedelta(minutes=45)) is True
    assert is_group_complete(group, now, timedelta(minutes=55)) is False


def test_group_incomplete_with_recent_part():
    now = datetime.now(timezone.utc)
    files = [
        DriveFile("id1", "takeout-20260830T120000Z-001.zip", _ago(60, now)),
        DriveFile("id2", "takeout-20260830T120000Z-002.zip", _ago(5, now)),
    ]
    group = group_takeout_files(files)[0]

    assert is_group_complete(group, now, timedelta(minutes=45)) is False


def test_groups_by_export_id_multi_segment():
    now = datetime.now(timezone.utc)
    files = [
        DriveFile("id1", "takeout-20260830T185305Z-1-001.zip", _ago(60, now)),
        DriveFile("id2", "takeout-20260830T185305Z-1-002.zip", _ago(50, now)),
        DriveFile("id3", "takeout-20260830T185305Z-2-001.zip", _ago(40, now)),
    ]

    groups = group_takeout_files(files)
    assert len(groups) == 1
    group = groups[0]
    assert group.export_id == "takeout-20260830T185305Z"
    assert [f.file_id for f in group.sorted_files()] == ["id1", "id2", "id3"]
