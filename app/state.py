from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS processed_drive_files (
    file_id TEXT PRIMARY KEY,
    export_ts TEXT NOT NULL,
    downloaded_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS library_files (
    hash TEXT PRIMARY KEY,
    path TEXT NOT NULL,
    first_seen_export_ts TEXT NOT NULL
);
"""


class StateStore:
    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def is_drive_file_processed(self, file_id: str) -> bool:
        cur = self._conn.execute(
            "SELECT 1 FROM processed_drive_files WHERE file_id = ?", (file_id,)
        )
        return cur.fetchone() is not None

    def mark_drive_file_processed(self, file_id: str, export_ts: str, downloaded_at: str) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO processed_drive_files (file_id, export_ts, downloaded_at) "
            "VALUES (?, ?, ?)",
            (file_id, export_ts, downloaded_at),
        )
        self._conn.commit()

    def has_hash(self, file_hash: str) -> bool:
        cur = self._conn.execute("SELECT 1 FROM library_files WHERE hash = ?", (file_hash,))
        return cur.fetchone() is not None

    def record_hash(self, file_hash: str, path: str, export_ts: str) -> None:
        self._conn.execute(
            "INSERT OR IGNORE INTO library_files (hash, path, first_seen_export_ts) "
            "VALUES (?, ?, ?)",
            (file_hash, path, export_ts),
        )
        self._conn.commit()
