from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, Optional, Set

import piexif
from PIL import Image

logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".tiff", ".tif", ".png", ".webp"}


class MetadataTagger:
    @staticmethod
    def parse_takeout_metadata(extracted_dir: Path) -> Tuple[Set[str], Dict[str, str]]:
        """Scans extracted Takeout directory for companion JSON sidecars.
        Returns a set of favorited base filenames, and a dict of image descriptions.
        """
        favorited_names: Set[str] = set()
        descriptions: Dict[str, str] = {}

        for json_path in extracted_dir.rglob("*.json"):
            if not json_path.is_file():
                continue
            if json_path.name in {"archive_browser.html", "metadata.json"}:
                continue

            try:
                with json_path.open("r", encoding="utf-8", errors="ignore") as f:
                    data = json.load(f)
            except Exception:
                continue

            if not isinstance(data, dict):
                continue

            # Determine the target photo filename
            title = data.get("title")
            if not title:
                # Derive from JSON filename (e.g. photo.jpg.json -> photo.jpg)
                fn = json_path.name
                if fn.endswith(".supplemental-metadata.json"):
                    title = fn[:-len(".supplemental-metadata.json")]
                elif fn.endswith(".json"):
                    title = fn[:-len(".json")]

            if not title:
                continue

            # Check favorited status
            is_fav = data.get("favorited", False) or data.get("favorite", False)
            if is_fav:
                favorited_names.add(title.lower())
                favorited_names.add(Path(title).stem.lower())

            # Check description / caption
            desc = data.get("description", "").strip()
            if desc:
                descriptions[title.lower()] = desc
                descriptions[Path(title).stem.lower()] = desc

        return favorited_names, descriptions

    @staticmethod
    def tag_media_file(file_path: Path, is_favorite: bool = False, description: Optional[str] = None) -> bool:
        """Injects Rating=5 and/or ImageDescription into the photo's EXIF header losslessly."""
        if not file_path.is_file() or file_path.is_symlink():
            return False

        ext = file_path.suffix.lower()
        if ext not in IMAGE_EXTENSIONS:
            return False

        try:
            if ext in {".jpg", ".jpeg"}:
                try:
                    exif_dict = piexif.load(str(file_path))
                except Exception:
                    exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}}

                if "0th" not in exif_dict:
                    exif_dict["0th"] = {}

                changed = False
                if is_favorite:
                    # Tag 5-Star Rating (0x4746 = 18246)
                    exif_dict["0th"][piexif.ImageIFD.Rating] = 5
                    changed = True

                if description:
                    exif_dict["0th"][piexif.ImageIFD.ImageDescription] = description.encode("utf-8", errors="ignore")
                    changed = True

                if changed:
                    exif_bytes = piexif.dump(exif_dict)
                    piexif.insert(exif_bytes, str(file_path))
                    return True

            elif ext in {".tiff", ".tif", ".png"}:
                # Pillow fallback for non-JPEG
                with Image.open(file_path) as img:
                    exif = img.getexif()
                    if is_favorite:
                        exif[18246] = 5
                    if description:
                        exif[270] = description
                    img.save(file_path, exif=exif)
                return True

        except Exception as e:
            logger.debug("Failed to tag EXIF on %s: %s", file_path.name, e)

        return False

    @classmethod
    def tag_favorites_in_directory(cls, target_dir: Path, favorited_names: Set[str], descriptions: Dict[str, str]) -> int:
        """Applies ratings and descriptions to all matching media files in target_dir."""
        tagged_count = 0
        for p in target_dir.rglob("*"):
            if not p.is_file() or p.is_symlink():
                continue

            name_lower = p.name.lower()
            stem_lower = p.stem.lower()

            is_fav = (name_lower in favorited_names) or (stem_lower in favorited_names)
            desc = descriptions.get(name_lower) or descriptions.get(stem_lower)

            if is_fav or desc:
                if cls.tag_media_file(p, is_favorite=is_fav, description=desc):
                    tagged_count += 1

        return tagged_count
