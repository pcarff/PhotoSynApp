from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Dict, List, Optional

from PyQt6.QtCore import QThread, pyqtSignal


def compute_sha256(path: Path, block_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(block_size):
            h.update(chunk)
    return h.hexdigest()


class ComparatorWorker(QThread):
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, dir_a: str, dir_b: str, check_hash: bool = False, parent=None):
        super().__init__(parent)
        self.dir_a = Path(dir_a)
        self.dir_b = Path(dir_b)
        self.check_hash = check_hash
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            if not self.dir_a.is_dir():
                self.error.emit(f"Directory A does not exist: {self.dir_a}")
                return
            if not self.dir_b.is_dir():
                self.error.emit(f"Directory B does not exist: {self.dir_b}")
                return

            self.progress.emit(0, 0, "Indexing Directory A...")
            files_a: Dict[str, Path] = {}
            for root, _, files in os.walk(self.dir_a):
                if self._is_cancelled:
                    return
                for f in files:
                    full_p = Path(root) / f
                    rel_p = str(full_p.relative_to(self.dir_a))
                    files_a[rel_p] = full_p

            self.progress.emit(0, len(files_a), "Indexing Directory B...")
            files_b: Dict[str, Path] = {}
            for root, _, files in os.walk(self.dir_b):
                if self._is_cancelled:
                    return
                for f in files:
                    full_p = Path(root) / f
                    rel_p = str(full_p.relative_to(self.dir_b))
                    files_b[rel_p] = full_p

            all_rel_paths = sorted(set(files_a.keys()) | set(files_b.keys()))
            total_items = len(all_rel_paths)

            results: List[dict] = []
            summary = {
                "total_a": len(files_a),
                "total_b": len(files_b),
                "only_a": 0,
                "only_b": 0,
                "identical": 0,
                "modified": 0,
            }

            for idx, rel_path in enumerate(all_rel_paths, start=1):
                if self._is_cancelled:
                    return

                if idx % 100 == 0 or idx == total_items:
                    self.progress.emit(idx, total_items, f"Comparing {idx}/{total_items}: {rel_path[:40]}")

                in_a = rel_path in files_a
                in_b = rel_path in files_b

                if in_a and not in_b:
                    p_a = files_a[rel_path]
                    stat_a = p_a.stat()
                    results.append({
                        "rel_path": rel_path,
                        "status": "Only in A",
                        "size_a": stat_a.st_size,
                        "size_b": None,
                        "path_a": str(p_a),
                        "path_b": None,
                    })
                    summary["only_a"] += 1
                elif in_b and not in_a:
                    p_b = files_b[rel_path]
                    stat_b = p_b.stat()
                    results.append({
                        "rel_path": rel_path,
                        "status": "Only in B",
                        "size_a": None,
                        "size_b": stat_b.st_size,
                        "path_a": None,
                        "path_b": str(p_b),
                    })
                    summary["only_b"] += 1
                else:
                    p_a = files_a[rel_path]
                    p_b = files_b[rel_path]
                    stat_a = p_a.stat()
                    stat_b = p_b.stat()

                    if stat_a.st_size != stat_b.st_size:
                        status = "Modified (Size)"
                        summary["modified"] += 1
                    elif self.check_hash:
                        hash_a = compute_sha256(p_a)
                        hash_b = compute_sha256(p_b)
                        if hash_a == hash_b:
                            status = "Identical"
                            summary["identical"] += 1
                        else:
                            status = "Modified (Content)"
                            summary["modified"] += 1
                    else:
                        status = "Identical"
                        summary["identical"] += 1

                    results.append({
                        "rel_path": rel_path,
                        "status": status,
                        "size_a": stat_a.st_size,
                        "size_b": stat_b.st_size,
                        "path_a": str(p_a),
                        "path_b": str(p_b),
                    })

            self.finished.emit({"items": results, "summary": summary})
        except Exception as e:
            self.error.emit(str(e))
