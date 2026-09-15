from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path

import piexif
import pytest
from PIL import Image

from gui.core.exif_manager import ExifManager


@pytest.fixture
def sample_jpeg():
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        img = Image.new("RGB", (100, 100), color="blue")
        img.save(f.name)
        p = Path(f.name)
    yield p
    if p.exists():
        p.unlink()


@pytest.fixture
def sample_png():
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        img = Image.new("RGB", (100, 100), color="red")
        img.save(f.name)
        p = Path(f.name)
    yield p
    if p.exists():
        p.unlink()


def test_png_date_and_rating(sample_png: Path):
    # 1. Initial state
    info0 = ExifManager.get_image_info(sample_png)
    assert info0["exif_date"] is None
    assert info0["rating"] is None
    assert info0["is_favorite"] is False

    # 2. Set date and rating (5 stars)
    target_dt = datetime(1968, 7, 20, 20, 17, 40)
    success = ExifManager.update_metadata(sample_png, new_dt=target_dt, rating=5)
    assert success is True

    # 3. Read back info
    info1 = ExifManager.get_image_info(sample_png)
    assert info1["has_exif"] is True
    assert info1["exif_date"] == "1968:07:20 20:17:40"
    assert info1["rating"] == 5
    assert info1["is_favorite"] is True

    # 4. Clear rating (unfavorite)
    success2 = ExifManager.set_rating(sample_png, 0)
    assert success2 is True

    info2 = ExifManager.get_image_info(sample_png)
    assert info2["exif_date"] == "1968:07:20 20:17:40"
    assert info2["rating"] is None
    assert info2["is_favorite"] is False


def test_jpeg_date_and_rating(sample_jpeg: Path):
    target_dt = datetime(1985, 10, 26, 1, 21, 0)
    success = ExifManager.update_metadata(sample_jpeg, new_dt=target_dt, rating=5)
    assert success is True

    info = ExifManager.get_image_info(sample_jpeg)
    assert info["exif_date"] == "1985:10:26 01:21:00"
    assert info["rating"] == 5
    assert info["is_favorite"] is True


def test_clear_scanner_tags_png(sample_png: Path):
    # Inject scanner metadata into PNG
    exif_dict = {
        "0th": {
            piexif.ImageIFD.Make: b"Epson Scanner Corp",
            piexif.ImageIFD.Model: b"Perfection V600 Photo",
            piexif.ImageIFD.Software: b"Epson Scan v3.9",
        },
        "Exif": {},
        "GPS": {},
        "1st": {},
    }
    raw_bytes = piexif.dump(exif_dict)
    assert ExifManager._write_png_exif(sample_png, raw_bytes) is True

    info_before = ExifManager.get_image_info(sample_png)
    assert info_before["camera_make"] == "Epson Scanner Corp"
    assert info_before["camera_model"] == "Perfection V600 Photo"
    assert info_before["software"] == "Epson Scan v3.9"

    # Now clear scanner tags
    assert ExifManager.clear_scanner_tags(sample_png) is True

    info_after = ExifManager.get_image_info(sample_png)
    assert info_after["camera_make"] is None
    assert info_after["camera_model"] is None
    assert info_after["software"] is None


def test_shift_exif_date_png(sample_png: Path):
    dt = datetime(1990, 1, 1, 12, 0, 0)
    ExifManager.set_exif_date(sample_png, dt)

    # Shift forward by 2 years and 15 days
    assert ExifManager.shift_exif_date(sample_png, years=2, days=15) is True

    info = ExifManager.get_image_info(sample_png)
    assert info["exif_date"] == "1992:01:16 12:00:00"


def test_filename_date_extraction():
    assert ExifManager.extract_date_from_filename("1978-08-14_FamilyPic.png") == datetime(1978, 8, 14, 12, 0, 0)
    assert ExifManager.extract_date_from_filename("Scan_19650325_001.png") == datetime(1965, 3, 25, 12, 0, 0)
    assert ExifManager.extract_date_from_filename("Vacation_1952.jpg") == datetime(1952, 1, 1, 12, 0, 0)
    assert ExifManager.extract_date_from_filename("random_name_no_date.png") is None
