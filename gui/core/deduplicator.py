from __future__ import annotations

import concurrent.futures
import hashlib
import os
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

import imagehash
from PIL import Image
from PyQt6.QtCore import QThread, pyqtSignal

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".tiff", ".tif", ".bmp", ".heic"}


def _compute_sha256(path: Path) -> Tuple[Path, str]:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return path, h.hexdigest()


def _compute_phash(path: Path) -> Tuple[Path, Optional[imagehash.ImageHash], int, int]:
    try:
        with Image.open(path) as img:
            w, h = img.size
            ph = imagehash.phash(img)
            return path, ph, w, h
    except Exception:
        return path, None, 0, 0


class DeduplicatorWorker(QThread):
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(
        self,
        directories: List[str],
        mode: str = "binary",  # "binary" or "phash"
        phash_threshold: int = 4,
        max_workers: int = 16,
        parent=None,
    ):
        super().__init__(parent)
        self.directories = [Path(d) for d in directories]
        self.mode = mode
        self.phash_threshold = phash_threshold
        self.max_workers = max_workers
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            all_files: List[Path] = []
            self.progress.emit(0, 0, "Discovering files across selected directories...")

            for d in self.directories:
                if not d.is_dir():
                    continue
                for root, _, files in os.walk(d):
                    if self._is_cancelled:
                        return
                    for f in files:
                        p = Path(root) / f
                        if self.mode == "phash":
                            if p.suffix.lower() in IMAGE_EXTENSIONS:
                                all_files.append(p)
                        else:
                            all_files.append(p)

            total_files = len(all_files)
            if total_files == 0:
                self.finished.emit([])
                return

            if self.mode == "binary":
                self._run_binary_dedupe(all_files)
            else:
                self._run_phash_dedupe(all_files)

        except Exception as e:
            self.error.emit(str(e))

    def _run_binary_dedupe(self, files: List[Path]):
        # Step 1: Group by file size to avoid unnecessary hashing
        self.progress.emit(0, len(files), "Grouping files by size...")
        size_map = defaultdict(list)
        for idx, f in enumerate(files, 1):
            if self._is_cancelled:
                return
            try:
                size_map[f.stat().st_size].append(f)
            except OSError:
                continue

        candidates = [f for flist in size_map.values() if len(flist) > 1 for f in flist]
        total_candidates = len(candidates)

        if total_candidates == 0:
            self.finished.emit([])
            return

        self.progress.emit(0, total_candidates, f"Hashing {total_candidates} size-matched candidates...")
        hash_map = defaultdict(list)
        completed = 0

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(_compute_sha256, p): p for p in candidates}
            for future in concurrent.futures.as_completed(futures):
                if self._is_cancelled:
                    return
                completed += 1
                if completed % 100 == 0 or completed == total_candidates:
                    self.progress.emit(completed, total_candidates, f"Hashed {completed}/{total_candidates} files...")
                try:
                    p, h = future.result()
                    hash_map[h].append(p)
                except Exception:
                    continue

        duplicate_groups = []
        for h, plist in hash_map.items():
            if len(plist) > 1:
                group_items = []
                for p in plist:
                    stat = p.stat()
                    w, h_dim = 0, 0
                    if p.suffix.lower() in IMAGE_EXTENSIONS:
                        try:
                            with Image.open(p) as img:
                                w, h_dim = img.size
                        except Exception:
                            pass
                    group_items.append({
                        "path": str(p),
                        "filename": p.name,
                        "size": stat.st_size,
                        "width": w,
                        "height": h_dim,
                        "hash": h,
                    })
                duplicate_groups.append(group_items)

        self.finished.emit(duplicate_groups)

    def _run_phash_dedupe(self, files: List[Path]):
        total_files = len(files)
        self.progress.emit(0, total_files, f"Calculating perceptual hashes for {total_files} images...")

        file_hashes: List[Tuple[Path, imagehash.ImageHash, int, int]] = []
        completed = 0

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(_compute_phash, p): p for p in files}
            for future in concurrent.futures.as_completed(futures):
                if self._is_cancelled:
                    return
                completed += 1
                if completed % 100 == 0 or completed == total_files:
                    self.progress.emit(completed, total_files, f"Analyzed {completed}/{total_files} images...")
                try:
                    p, ph, w, h = future.result()
                    if ph is not None:
                        file_hashes.append((p, ph, w, h))
                except Exception:
                    continue

        self.progress.emit(0, len(file_hashes), "Clustering visually similar duplicates...")

        # Disjoint set / clustering by Hamming distance
        parent = {i: i for i in range(len(file_hashes))}

        def find(i):
            if parent[i] == i:
                return i
            parent[i] = find(parent[i])
            return parent[i]

        def union(i, j):
            root_i = find(i)
            root_j = find(j)
            if root_i != root_j:
                parent[root_i] = root_j

        # Fast BK-tree or pairwise clustering within hash prefixes
        # For typical batch sizes, cluster by hex prefix then compare
        prefix_buckets = defaultdict(list)
        for idx, (_, ph, _, _) in enumerate(file_hashes):
            prefix = str(ph)[:4]
            prefix_buckets[prefix].append(idx)

        # Compare items in same and nearby buckets
        n = len(file_hashes)
        for idx1 in range(n):
            if self._is_cancelled:
                return
            p1, ph1, _, _ = file_hashes[idx1]
            prefix = str(ph1)[:4]
            bucket = prefix_buckets[prefix]

            for idx2 in bucket:
                if idx2 > idx1:
                    dist = ph1 - file_hashes[idx2][1]
                    if dist <= self.phash_threshold:
                        union(idx1, idx2)

        clusters = defaultdict(list)
        for idx in range(n):
            root = find(idx)
            clusters[root].append(idx)

        duplicate_groups = []
        for root, indices in clusters.items():
            if len(indices) > 1:
                group_items = []
                for idx in indices:
                    p, ph, w, h = file_hashes[idx]
                    group_items.append({
                        "path": str(p),
                        "filename": p.name,
                        "size": p.stat().st_size,
                        "width": w,
                        "height": h,
                        "hash": str(ph),
                    })
                duplicate_groups.append(group_items)

        self.finished.emit(duplicate_groups)
