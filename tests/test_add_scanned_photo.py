import hashlib
import sqlite3
from pathlib import Path
import pytest
from PIL import Image

from scripts.add_scanned_photo import sha256_file, ingest_photo


@pytest.fixture
def temp_environment(tmp_path, monkeypatch):
    laura_root = tmp_path / "Laura_Only"
    paul_root = tmp_path / "Paul_Combined"
    db_dir = tmp_path / "state"
    db_dir.mkdir(parents=True)
    db_laura = db_dir / "state_laura.sqlite3"
    db_paul = db_dir / "state.sqlite3"

    schema = """
    CREATE TABLE library_files (
        hash TEXT PRIMARY KEY,
        path TEXT NOT NULL,
        first_seen_export_ts TEXT NOT NULL
    );
    """
    for db in [db_laura, db_paul]:
        conn = sqlite3.connect(db)
        conn.execute(schema)
        conn.commit()
        conn.close()

    # Create dummy test image
    img_path = tmp_path / "scan_sample.png"
    img = Image.new("RGB", (100, 100), color="blue")
    img.save(img_path)

    # Monkeypatch paths in ingest_photo for testing
    import scripts.add_scanned_photo as asp
    def custom_ingest(src_path, target, year, month, move=False, custom_name=None):
        src = Path(src_path).resolve()
        year_str = str(int(year))
        month_str = f"{int(month):02d}"
        if target.lower() == "laura":
            dest_root = laura_root
            db_path = db_laura
            nas_base = "/volume1/PhotoSync/Laura/ALL_PHOTOS"
        else:
            dest_root = paul_root
            db_path = db_paul
            nas_base = "/volume1/PhotoSync/ALL_PHOTOS"

        dest_dir = dest_root / year_str / month_str
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_filename = custom_name or src.name
        dest_path = dest_dir / dest_filename

        file_hash = sha256_file(src)
        import shutil
        if move:
            shutil.move(str(src), str(dest_path))
        else:
            shutil.copy2(str(src), str(dest_path))

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute(
            "INSERT OR IGNORE INTO library_files (hash, path, first_seen_export_ts) VALUES (?, ?, ?)",
            (file_hash, f"{nas_base}/{year_str}/{month_str}/{dest_path.name}", "test_export"),
        )
        conn.commit()
        conn.close()
        return dest_path

    return {
        "img_path": img_path,
        "laura_root": laura_root,
        "db_laura": db_laura,
        "ingest_fn": custom_ingest,
    }


def test_sha256_file(temp_environment):
    img_path = temp_environment["img_path"]
    expected_hash = hashlib.sha256(img_path.read_bytes()).hexdigest()
    assert sha256_file(img_path) == expected_hash


def test_ingest_photo(temp_environment):
    img_path = temp_environment["img_path"]
    ingest_fn = temp_environment["ingest_fn"]
    db_laura = temp_environment["db_laura"]

    dest = ingest_fn(img_path, target="laura", year="1924", month="8")
    assert dest.exists()
    assert dest.parent.name == "08"
    assert dest.parent.parent.name == "1924"

    conn = sqlite3.connect(db_laura)
    cur = conn.cursor()
    f_hash = sha256_file(dest)
    row = cur.execute("SELECT hash, path FROM library_files WHERE hash = ?", (f_hash,)).fetchone()
    conn.close()

    assert row is not None
    assert row[0] == f_hash
    assert "1924/08/scan_sample.png" in row[1]
