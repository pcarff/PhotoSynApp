from __future__ import annotations

import io
import logging
from datetime import datetime
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from .takeout_group import DriveFile

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


class DriveClient:
    def __init__(self, token_path: Path):
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            token_path.write_text(creds.to_json())
        self._service = build("drive", "v3", credentials=creds)

    def find_folder_id(self, folder_name: str) -> str:
        query = (
            f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' "
            "and trashed = false"
        )
        results = self._service.files().list(q=query, fields="files(id, name)").execute()
        files = results.get("files", [])
        if not files:
            raise RuntimeError(f"No Drive folder named '{folder_name}' found")
        return files[0]["id"]

    def list_takeout_files(self, folder_id: str) -> list[DriveFile]:
        files: list[DriveFile] = []
        page_token = None
        query = f"'{folder_id}' in parents and trashed = false"
        while True:
            resp = (
                self._service.files()
                .list(
                    q=query,
                    fields="nextPageToken, files(id, name, modifiedTime)",
                    pageToken=page_token,
                )
                .execute()
            )
            for f in resp.get("files", []):
                modified = datetime.fromisoformat(f["modifiedTime"].replace("Z", "+00:00"))
                files.append(DriveFile(file_id=f["id"], name=f["name"], modified_time=modified))
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        return files

    def download_file(self, file_id: str, dest_path: Path) -> None:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        request = self._service.files().get_media(fileId=file_id)
        with io.FileIO(dest_path, "wb") as fh:
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
                if status:
                    logger.info(
                        "Downloading %s: %d%%", dest_path.name, int(status.progress() * 100)
                    )
