from __future__ import annotations

import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import piexif
from PIL import Image

EXIF_DATE_FORMAT = "%Y:%m:%d %H:%M:%S"

FILENAME_DATE_PATTERNS = [
    # YYYY-MM-DD or YYYY_MM_DD or YYYY.MM.DD
    re.compile(r"(?P<year>19\d\d|20\d\d)[-_/.](?P<month>0[1-9]|1[0-2])[-_/.](?P<day>0[1-9]|[12]\d|3[01])"),
    # YYYYMMDD
    re.compile(r"(?P<year>19\d\d|20\d\d)(?P<month>0[1-9]|1[0-2])(?P<day>0[1-9]|[12]\d|3[01])"),
    # YYYY-MM
    re.compile(r"(?P<year>19\d\d|20\d\d)[-_/.](?P<month>0[1-9]|1[0-2])"),
    # Just year YYYY
    re.compile(r"\b(?P<year>19\d\d|20\d\d)\b"),
]


class ExifManager:
    @staticmethod
    def get_image_info(file_path: Path | str) -> Dict[str, Any]:
        """Returns metadata dictionary including dimensions, file size, mtime, and EXIF tags."""
        p = Path(file_path)
        stat = p.stat()
        info: Dict[str, Any] = {
            "path": str(p),
            "filename": p.name,
            "size_bytes": stat.st_size,
            "size_human": ExifManager._human_size(stat.st_size),
            "modified_time": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            "width": 0,
            "height": 0,
            "exif_date": None,
            "camera_make": None,
            "camera_model": None,
            "software": None,
            "orientation": 1,
            "has_exif": False,
        }

        try:
            with Image.open(p) as img:
                info["width"], info["height"] = img.size
                exif_data = img.getexif()
                if exif_data:
                    info["has_exif"] = True
                    # 0x0112 is Orientation
                    info["orientation"] = exif_data.get(0x0112, 1)
                    # 0x010F is Make
                    info["camera_make"] = str(exif_data.get(0x010F, "")).strip() or None
                    # 0x0110 is Model
                    info["camera_model"] = str(exif_data.get(0x0110, "")).strip() or None
                    # 0x0131 is Software
                    info["software"] = str(exif_data.get(0x0131, "")).strip() or None

            # Check piexif for DateTimeOriginal
            if p.suffix.lower() in {".jpg", ".jpeg", ".tiff", ".tif"}:
                try:
                    exif_dict = piexif.load(str(p))
                    exif_sub = exif_dict.get("Exif", {})
                    dt_orig = exif_sub.get(piexif.ExifIFD.DateTimeOriginal) or exif_sub.get(piexif.ExifIFD.DateTimeDigitized)
                    if not dt_orig:
                        dt_orig = exif_dict.get("0th", {}).get(piexif.ImageIFD.DateTime)
                    if dt_orig:
                        val = dt_orig.decode("ascii", errors="ignore").strip()
                        info["exif_date"] = val

                    # Check Rating tag (18246 = 0x4746)
                    info["rating"] = exif_dict.get("0th", {}).get(piexif.ImageIFD.Rating, None)
                    info["is_favorite"] = (info["rating"] == 5)
                except Exception:
                    pass
        except Exception as e:
            info["error"] = str(e)

        return info

    @staticmethod
    def set_exif_date(file_path: Path | str, new_dt: datetime) -> bool:
        """Sets DateTimeOriginal, DateTimeDigitized, and DateTime to new_dt."""
        p = Path(file_path)
        date_str = new_dt.strftime(EXIF_DATE_FORMAT).encode("ascii")
        try:
            if p.suffix.lower() in {".jpg", ".jpeg"}:
                try:
                    exif_dict = piexif.load(str(p))
                except Exception:
                    exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}}
                
                if "0th" not in exif_dict:
                    exif_dict["0th"] = {}
                if "Exif" not in exif_dict:
                    exif_dict["Exif"] = {}

                exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = date_str
                exif_dict["Exif"][piexif.ExifIFD.DateTimeDigitized] = date_str
                exif_dict["0th"][piexif.ImageIFD.DateTime] = date_str

                exif_bytes = piexif.dump(exif_dict)
                piexif.insert(exif_bytes, str(p))
                return True
            else:
                # Pillow fallback for non-JPEG formats
                with Image.open(p) as img:
                    exif = img.getexif()
                    # 306 = DateTime, 36867 = DateTimeOriginal
                    exif[306] = new_dt.strftime(EXIF_DATE_FORMAT)
                    exif[36867] = new_dt.strftime(EXIF_DATE_FORMAT)
                    img.save(p, exif=exif)
                return True
        except Exception:
            return False

    @staticmethod
    def shift_exif_date(file_path: Path | str, years: int = 0, months: int = 0, days: int = 0, hours: int = 0) -> bool:
        """Shifts existing EXIF date by delta values."""
        info = ExifManager.get_image_info(file_path)
        current_str = info.get("exif_date")
        if not current_str:
            return False
        try:
            dt = datetime.strptime(current_str, EXIF_DATE_FORMAT)
        except ValueError:
            return False

        # Approximate shift for years/months
        new_year = dt.year + years
        new_month = dt.month + months
        while new_month > 12:
            new_year += 1
            new_month -= 12
        while new_month < 1:
            new_year -= 1
            new_month += 12

        try:
            dt = dt.replace(year=new_year, month=new_month)
        except ValueError:
            # Day out of range (e.g. Feb 30) -> snap to 28
            dt = dt.replace(year=new_year, month=new_month, day=28)

        dt += timedelta(days=days, hours=hours)
        return ExifManager.set_exif_date(file_path, dt)

    @staticmethod
    def extract_date_from_filename(filename: str) -> Optional[datetime]:
        """Tries to extract a year, month, and day from common filename patterns."""
        for pat in FILENAME_DATE_PATTERNS:
            m = pat.search(filename)
            if m:
                d = m.groupdict()
                year = int(d.get("year", 1970))
                month = int(d.get("month", 1)) if "month" in d else 1
                day = int(d.get("day", 1)) if "day" in d else 1
                try:
                    return datetime(year, month, day, 12, 0, 0)
                except ValueError:
                    continue
        return None

    @staticmethod
    def clear_scanner_tags(file_path: Path | str) -> bool:
        """Clears hardware scanner metadata strings from Make, Model, and Software."""
        p = Path(file_path)
        try:
            if p.suffix.lower() in {".jpg", ".jpeg"}:
                try:
                    exif_dict = piexif.load(str(p))
                except Exception:
                    return False
                
                # Wipe scanner hardware fields in 0th IFD
                zeroth = exif_dict.get("0th", {})
                for tag in [piexif.ImageIFD.Make, piexif.ImageIFD.Model, piexif.ImageIFD.Software]:
                    if tag in zeroth:
                        del zeroth[tag]

                exif_bytes = piexif.dump(exif_dict)
                piexif.insert(exif_bytes, str(p))
                return True
        except Exception:
            pass
        return False

    @staticmethod
    def set_rating(file_path: Path | str, rating: int = 5) -> bool:
        """Sets 0th IFD Rating (0 to 5 stars). 5 = Favorite."""
        p = Path(file_path)
        try:
            if p.suffix.lower() in {".jpg", ".jpeg"}:
                try:
                    exif_dict = piexif.load(str(p))
                except Exception:
                    exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}}

                if "0th" not in exif_dict:
                    exif_dict["0th"] = {}

                if rating <= 0:
                    exif_dict["0th"].pop(piexif.ImageIFD.Rating, None)
                else:
                    exif_dict["0th"][piexif.ImageIFD.Rating] = rating

                exif_bytes = piexif.dump(exif_dict)
                piexif.insert(exif_bytes, str(p))
                return True
        except Exception:
            pass
        return False

    @staticmethod
    def _human_size(size_bytes: int) -> str:
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} PB"
