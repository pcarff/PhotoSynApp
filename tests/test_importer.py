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
