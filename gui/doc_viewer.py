from __future__ import annotations

from pathlib import Path
from PyQt6.QtCore import QUrl, Qt
from PyQt6.QtGui import QDesktopServices, QTextDocument
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)

DOC_PATH = Path("/workspaces_nvme/PhotoSynApp/docs/PHOTO_SYNC_AND_SCANNING_GUIDE.md")


class DocViewerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PhotoVault Studio - Operations Guide & System Documentation")
        self.resize(1000, 750)
        self._setup_ui()
        self._load_documentation()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Top Toolbar
        top_bar = QHBoxLayout()

        lbl_title = QLabel("📖 <b>PhotoSynApp System Documentation & Runbook</b>")
        lbl_title.setStyleSheet("font-size: 14px; color: #79a6d2;")
        top_bar.addWidget(lbl_title)
        top_bar.addStretch()

        # Search / Find in text
        top_bar.addWidget(QLabel("Find in Docs:"))
        self.edit_find = QLineEdit()
        self.edit_find.setPlaceholderText("Search keyword...")
        self.edit_find.returnPressed.connect(self._find_next)
        top_bar.addWidget(self.edit_find)

        btn_find = QPushButton("Next")
        btn_find.clicked.connect(self._find_next)
        top_bar.addWidget(btn_find)

        # Open in External Editor
        btn_external = QPushButton("Open in External Editor / Browser")
        btn_external.setStyleSheet("background-color: #2b5c8f; color: white;")
        btn_external.clicked.connect(self._open_external)
        top_bar.addWidget(btn_external)

        # Refresh
        btn_reload = QPushButton("Reload")
        btn_reload.clicked.connect(self._load_documentation)
        top_bar.addWidget(btn_reload)

        layout.addLayout(top_bar)

        # Markdown Browser View
        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(True)
        self.browser.setStyleSheet("""
            QTextBrowser {
                background-color: #1a1a22;
                color: #e2e2e8;
                border: 1px solid #3d3d4a;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                font-size: 13px;
                padding: 16px;
                line-height: 1.5;
            }
        """)
        layout.addWidget(self.browser)

        # Bottom Bar
        bottom_bar = QHBoxLayout()
        self.lbl_path = QLabel(f"Document: {DOC_PATH}")
        self.lbl_path.setStyleSheet("color: #777; font-size: 11px;")
        bottom_bar.addWidget(self.lbl_path)
        bottom_bar.addStretch()

        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.close)
        bottom_bar.addWidget(btn_close)
        layout.addLayout(bottom_bar)

    def _load_documentation(self):
        if not DOC_PATH.exists():
            self.browser.setHtml(f"<h3 style='color:red;'>Documentation file not found at:</h3><p>{DOC_PATH}</p>")
            return

        try:
            content = DOC_PATH.read_text(encoding="utf-8")
            self.browser.setMarkdown(content)
        except Exception as e:
            self.browser.setHtml(f"<h3 style='color:red;'>Error loading documentation:</h3><p>{e}</p>")

    def _find_next(self):
        query = self.edit_find.text().strip()
        if query:
            found = self.browser.find(query)
            if not found:
                # Wrap around to start
                cursor = self.browser.textCursor()
                cursor.movePosition(cursor.MoveOperation.Start)
                self.browser.setTextCursor(cursor)
                self.browser.find(query)

    def _open_external(self):
        if DOC_PATH.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(DOC_PATH)))
        else:
            QMessageBox.warning(self, "Not Found", f"File not found: {DOC_PATH}")
