from __future__ import annotations

import os
import re
import struct
import zlib
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
    re.compile(r"(?<!\d)(?P<year>19\d\d|20\d\d)(?P<month>0[1-9]|1[0-2])(?P<day>0[1-9]|[12]\d|3[01])(?!\d)"),
    # YYYY-MM
    re.compile(r"(?P<year>19\d\d|20\d\d)[-_/.](?P<month>0[1-9]|1[0-2])"),
    # Just year YYYY
    re.compile(r"(?<!\d)(?P<year>19\d\d|20\d\d)(?!\d)"),
]


class ExifManager:
    @staticmethod
    def _read_png_exif(file_path: Path | str) -> Optional[bytes]:
        """Reads raw EXIF bytes from a PNG file's eXIf chunk without decoding image pixels."""
        try:
            with open(file_path, "rb") as f:
                sig = f.read(8)
                if sig != b"\x89PNG\r\n\x1a\n":
                    return None
                while True:
                    len_bytes = f.read(4)
                    if len(len_bytes) < 4:
                        break
                    length = struct.unpack(">I", len_bytes)[0]
                    chunk_type = f.read(4)
                    if chunk_type == b"eXIf":
                        data = f.read(length)
                        return data
                    f.seek(length + 4, 1)  # Skip payload and 4-byte CRC
        except Exception:
            return None
        return None

    @staticmethod
    def _write_png_exif(file_path: Path | str, exif_bytes: bytes) -> bool:
        """
        Losslessly inserts or replaces the eXIf chunk in a PNG file without re-encoding pixels.
        Executes in milliseconds even on large 50MB+ scans.
        """
        p = Path(file_path)
        try:
            with open(p, "rb") as f:
                sig = f.read(8)
                if sig != b"\x89PNG\r\n\x1a\n":
                    return False
                chunks = []
                while True:
                    len_bytes = f.read(4)
                    if len(len_bytes) < 4:
                        break
                    length = struct.unpack(">I", len_bytes)[0]
                    chunk_type = f.read(4)
                    data = f.read(length)
                    crc = f.read(4)
                    if chunk_type == b"eXIf":
                        continue  # Strip existing eXIf chunk to replace it
                    chunks.append((chunk_type, data))
                    if chunk_type == b"IEND":
                        break

            # PNG eXIf chunk begins directly with the TIFF header (II or MM),
            # without the 6-byte JPEG "Exif\0\0" prefix.
            if exif_bytes.startswith(b"Exif\x00\x00"):
                raw_payload = exif_bytes[6:]
            else:
                raw_payload = exif_bytes

            exif_chunk_type = b"eXIf"
            exif_crc = zlib.crc32(exif_chunk_type + raw_payload) & 0xFFFFFFFF
            exif_chunk = struct.pack(">I", len(raw_payload)) + exif_chunk_type + raw_payload + struct.pack(">I", exif_crc)

            out_buf = bytearray()
            out_buf.extend(b"\x89PNG\r\n\x1a\n")
            ihdr_found = False
            for c_type, c_data in chunks:
                c_crc = zlib.crc32(c_type + c_data) & 0xFFFFFFFF
                out_buf.extend(struct.pack(">I", len(c_data)) + c_type + c_data + struct.pack(">I", c_crc))
                if c_type == b"IHDR":
                    out_buf.extend(exif_chunk)
                    ihdr_found = True

            if not ihdr_found:
                return False

            temp_path = p.with_suffix(p.suffix + f".tmp_{os.getpid()}")
            with open(temp_path, "wb") as f:
                f.write(out_buf)
            temp_path.replace(p)
            return True
        except Exception:
            return False

    @staticmethod
    def _load_exif_dict(p: Path) -> Tuple[Dict[str, Any], str]:
        """
        Loads the EXIF dictionary for JPEG, PNG, TIFF, or other image files.
        Returns (exif_dict, format_name).
        """
        ext = p.suffix.lower()
        default_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}}

        if ext in {".jpg", ".jpeg"}:
            try:
                return piexif.load(str(p)), "jpeg"
            except Exception:
                return default_dict, "jpeg"

        elif ext == ".png":
            raw = ExifManager._read_png_exif(p)
            if raw:
                try:
                    return piexif.load(raw), "png"
                except Exception:
                    try:
                        return piexif.load(b"Exif\x00\x00" + raw), "png"
                    except Exception:
                        pass
            # Fallback: check Pillow's raw exif info
            try:
                with Image.open(p) as img:
                    raw_info = img.info.get("exif")
                    if raw_info:
                        try:
                            return piexif.load(raw_info), "png"
                        except Exception:
                            try:
                                return piexif.load(b"Exif\x00\x00" + raw_info), "png"
                            except Exception:
                                pass
            except Exception:
                pass
            return default_dict, "png"

        elif ext in {".tiff", ".tif"}:
            try:
                return piexif.load(str(p)), "tiff"
            except Exception:
                return default_dict, "tiff"

        return default_dict, "other"

    @staticmethod
    def _save_exif_dict(p: Path, exif_dict: Dict[str, Any], fmt: str) -> bool:
        """Saves EXIF dictionary to the image file depending on format."""
        try:
            exif_bytes = piexif.dump(exif_dict)
        except Exception:
            return False

        if fmt == "jpeg" or p.suffix.lower() in {".jpg", ".jpeg"}:
            try:
                piexif.insert(exif_bytes, str(p))
                return True
            except Exception:
                return False

        elif fmt == "png" or p.suffix.lower() == ".png":
            return ExifManager._write_png_exif(p, exif_bytes)

        elif fmt in {"tiff", "other"} or p.suffix.lower() in {".tiff", ".tif"}:
            try:
                with Image.open(p) as img:
                    exif = Image.Exif()
                    exif.load(exif_bytes)
                    img.save(p, exif=exif)
                return True
            except Exception:
                return False

        return False

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
            "rating": None,
            "is_favorite": False,
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
                    info["orientation"] = exif_data.get(0x0112, 1)
                    info["camera_make"] = str(exif_data.get(0x010F, "")).strip() or None
                    info["camera_model"] = str(exif_data.get(0x0110, "")).strip() or None
                    info["software"] = str(exif_data.get(0x0131, "")).strip() or None

                    # If Rating tag is present in root Pillow exif
                    if 0x4746 in exif_data:
                        info["rating"] = int(exif_data[0x4746])
                        info["is_favorite"] = (info["rating"] == 5)

                    # Check Pillow sub-IFD for dates
                    sub_ifd = exif_data.get_ifd(0x8769)
                    if sub_ifd:
                        dt_candidate = sub_ifd.get(36867) or sub_ifd.get(36868)
                        if dt_candidate:
                            info["exif_date"] = str(dt_candidate).strip()
                    if not info["exif_date"] and 306 in exif_data:
                        info["exif_date"] = str(exif_data[306]).strip()

            # Parse deeper EXIF dictionary via piexif for JPEG, PNG, TIFF
            exif_dict, _ = ExifManager._load_exif_dict(p)
            zeroth = exif_dict.get("0th", {})
            exif_sub = exif_dict.get("Exif", {})

            # 1. Date: DateTimeOriginal > DateTimeDigitized > DateTime
            dt_orig = exif_sub.get(piexif.ExifIFD.DateTimeOriginal) or exif_sub.get(piexif.ExifIFD.DateTimeDigitized)
            if not dt_orig:
                dt_orig = zeroth.get(piexif.ImageIFD.DateTime)

            if dt_orig:
                info["has_exif"] = True
                if isinstance(dt_orig, bytes):
                    info["exif_date"] = dt_orig.decode("ascii", errors="ignore").strip()
                else:
                    info["exif_date"] = str(dt_orig).strip()

            # 2. Rating tag (18246 = 0x4746)
            rating_val = zeroth.get(piexif.ImageIFD.Rating, None)
            if rating_val is not None:
                info["has_exif"] = True
                info["rating"] = int(rating_val)
                info["is_favorite"] = (info["rating"] == 5)

            # 3. Hardware / Software strings from 0th IFD
            if not info["camera_make"] and piexif.ImageIFD.Make in zeroth:
                val = zeroth[piexif.ImageIFD.Make]
                info["camera_make"] = val.decode("utf-8", errors="ignore").strip() if isinstance(val, bytes) else str(val).strip()
            if not info["camera_model"] and piexif.ImageIFD.Model in zeroth:
                val = zeroth[piexif.ImageIFD.Model]
                info["camera_model"] = val.decode("utf-8", errors="ignore").strip() if isinstance(val, bytes) else str(val).strip()
            if not info["software"] and piexif.ImageIFD.Software in zeroth:
                val = zeroth[piexif.ImageIFD.Software]
                info["software"] = val.decode("utf-8", errors="ignore").strip() if isinstance(val, bytes) else str(val).strip()
            if piexif.ImageIFD.Orientation in zeroth:
                info["orientation"] = int(zeroth[piexif.ImageIFD.Orientation])

        except Exception as e:
            info["error"] = str(e)

        return info

    @staticmethod
    def update_metadata(
        file_path: Path | str,
        new_dt: Optional[datetime] = None,
        rating: Optional[int] = None,
        clear_scanner: bool = False,
    ) -> bool:
        """
        Updates date, rating, and/or scanner hardware tags atomically in a single pass.
        Supports JPEG, PNG, and TIFF formats losslessly.
        """
        p = Path(file_path)
        exif_dict, fmt = ExifManager._load_exif_dict(p)
        if "0th" not in exif_dict:
            exif_dict["0th"] = {}
        if "Exif" not in exif_dict:
            exif_dict["Exif"] = {}

        # 1. Update Date if specified
        if new_dt is not None:
            date_bytes = new_dt.strftime(EXIF_DATE_FORMAT).encode("ascii")
            exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = date_bytes
            exif_dict["Exif"][piexif.ExifIFD.DateTimeDigitized] = date_bytes
            exif_dict["0th"][piexif.ImageIFD.DateTime] = date_bytes

        # 2. Update Rating if specified (0 clears rating)
        if rating is not None:
            if rating <= 0:
                exif_dict["0th"].pop(piexif.ImageIFD.Rating, None)
            else:
                exif_dict["0th"][piexif.ImageIFD.Rating] = rating

        # 3. Clear Scanner Hardware tags if requested
        if clear_scanner:
            for tag in [piexif.ImageIFD.Make, piexif.ImageIFD.Model, piexif.ImageIFD.Software]:
                exif_dict["0th"].pop(tag, None)

        return ExifManager._save_exif_dict(p, exif_dict, fmt)

    @staticmethod
    def set_exif_date(file_path: Path | str, new_dt: datetime) -> bool:
        """Sets DateTimeOriginal, DateTimeDigitized, and DateTime to new_dt."""
        return ExifManager.update_metadata(file_path, new_dt=new_dt)

    @staticmethod
    def set_rating(file_path: Path | str, rating: int = 5) -> bool:
        """Sets 0th IFD Rating (0 to 5 stars). 5 = Favorite."""
        return ExifManager.update_metadata(file_path, rating=rating)

    @staticmethod
    def clear_scanner_tags(file_path: Path | str) -> bool:
        """Clears hardware scanner metadata strings from Make, Model, and Software."""
        return ExifManager.update_metadata(file_path, clear_scanner=True)

    @staticmethod
    def calculate_shifted_date(
        current_str: Optional[str],
        years: int = 0,
        months: int = 0,
        days: int = 0,
        hours: int = 0,
    ) -> Optional[datetime]:
        """Calculates a new shifted datetime from an EXIF date string."""
        if not current_str:
            return None
        try:
            dt = datetime.strptime(current_str, EXIF_DATE_FORMAT)
        except ValueError:
            return None

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
            dt = dt.replace(year=new_year, month=new_month, day=28)

        dt += timedelta(days=days, hours=hours)
        return dt

    @staticmethod
    def shift_exif_date(file_path: Path | str, years: int = 0, months: int = 0, days: int = 0, hours: int = 0) -> bool:
        """Shifts existing EXIF date by delta values."""
        info = ExifManager.get_image_info(file_path)
        new_dt = ExifManager.calculate_shifted_date(info.get("exif_date"), years=years, months=months, days=days, hours=hours)
        if not new_dt:
            return False
        return ExifManager.set_exif_date(file_path, new_dt)

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
    def _human_size(size_bytes: int) -> str:
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} PB"
