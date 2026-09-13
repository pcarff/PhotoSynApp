from pathlib import Path

from app.importer import import_gpth_output
from app.state import StateStore


def _write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def test_new_files_are_copied_and_recorded(tmp_path: Path):
    gpth_out = tmp_path / "gpth-out"
    library = tmp_path / "library"
    _write(gpth_out / "2026" / "03" / "photo.jpg", b"photo-bytes")

    state = StateStore(tmp_path / "state.sqlite3")
    import_gpth_output(gpth_out, library, state, export_ts="takeout-20260830T120000Z")

    assert (library / "2026" / "03" / "photo.jpg").read_bytes() == b"photo-bytes"


def test_rerunning_same_export_does_not_duplicate(tmp_path: Path):
    gpth_out = tmp_path / "gpth-out"
    library = tmp_path / "library"
    _write(gpth_out / "2026" / "03" / "photo.jpg", b"photo-bytes")

    state = StateStore(tmp_path / "state.sqlite3")
    import_gpth_output(gpth_out, library, state, export_ts="takeout-20260830T120000Z")
    import_gpth_output(gpth_out, library, state, export_ts="takeout-20261030T120000Z")

    files = list((library / "2026" / "03").iterdir())
    assert len(files) == 1


def test_same_content_different_path_is_deduped(tmp_path: Path):
    gpth_out_1 = tmp_path / "gpth-out-1"
    gpth_out_2 = tmp_path / "gpth-out-2"
    library = tmp_path / "library"

    _write(gpth_out_1 / "2026" / "03" / "photo.jpg", b"photo-bytes")
    _write(gpth_out_2 / "2026" / "03" / "photo_renamed.jpg", b"photo-bytes")

    state = StateStore(tmp_path / "state.sqlite3")
    import_gpth_output(gpth_out_1, library, state, export_ts="takeout-20260830T120000Z")
    import_gpth_output(gpth_out_2, library, state, export_ts="takeout-20261030T120000Z")

    files = list((library / "2026" / "03").iterdir())
    assert len(files) == 1


def test_ignores_gpth_logs_and_progress_file(tmp_path: Path):
    gpth_out = tmp_path / "gpth-out"
    library = tmp_path / "library"
    _write(gpth_out / "gpth_v6.2.1_20260901.log", b"log data")
    _write(gpth_out / "progress.json", b"{\"progress\": 100}")
    _write(gpth_out / "2026" / "03" / "photo.jpg", b"photo-bytes")

    state = StateStore(tmp_path / "state.sqlite3")
    import_gpth_output(gpth_out, library, state, export_ts="takeout-20260830T120000Z")

    assert not (library / "gpth_v6.2.1_20260901.log").exists()
    assert not (library / "progress.json").exists()
    assert (library / "2026" / "03" / "photo.jpg").exists()


def test_sets_readable_permissions(tmp_path: Path):
    gpth_out = tmp_path / "gpth-out"
    library = tmp_path / "library"
    photo_file = gpth_out / "2026" / "03" / "photo.jpg"
    _write(photo_file, b"photo-bytes")
    # Simulate gpth restrictive 0711 permission
    photo_file.chmod(0o711)

    state = StateStore(tmp_path / "state.sqlite3")
    import_gpth_output(gpth_out, library, state, export_ts="takeout-20260830T120000Z")

    imported = library / "2026" / "03" / "photo.jpg"
    # Ensure readable by group and other (0o664 or at least 0o444)
    mode = imported.stat().st_mode
    assert mode & 0o044 == 0o044  # group and other read bits are set


def test_fix_library_permissions(tmp_path: Path):
    from app.importer import fix_library_permissions

    library = tmp_path / "library"
    photo = library / "sub" / "test.jpg"
    _write(photo, b"data")
    photo.chmod(0o711)
    photo.parent.chmod(0o700)

    fix_library_permissions(library)

    assert photo.stat().st_mode & 0o044 == 0o044
    assert photo.parent.stat().st_mode & 0o055 == 0o055

