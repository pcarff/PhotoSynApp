from __future__ import annotations

import sys
from pathlib import Path
from PyQt6.QtCore import QUrl, Qt
from PyQt6.QtGui import QAction, QDesktopServices, QIcon, QKeySequence
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .doc_viewer import DOC_PATH, DocViewerDialog
from .tabs.dedupe_tab import DedupeTab
from .tabs.diff_tab import DiffTab
from .tabs.exif_tab import ExifTab
from .tabs.sync_tab import SyncTab


DARK_STYLE = """
QMainWindow, QWidget {
    background-color: #1e1e24;
    color: #e0e0e0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    font-size: 13px;
}
QMenuBar {
    background-color: #181820;
    color: #cccccc;
    border-bottom: 1px solid #333344;
}
QMenuBar::item:selected {
    background-color: #2b2b36;
    color: #ffffff;
}
QMenu {
    background-color: #22222c;
    color: #eeeeee;
    border: 1px solid #3d3d4a;
}
QMenu::item:selected {
    background-color: #384860;
}
QGroupBox {
    border: 1px solid #3d3d4a;
    border-radius: 6px;
    margin-top: 12px;
    font-weight: bold;
    padding-top: 14px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 4px;
    color: #79a6d2;
}
QLineEdit, QSpinBox, QDateTimeEdit, QComboBox {
    background-color: #2b2b36;
    border: 1px solid #444455;
    border-radius: 4px;
    padding: 4px 8px;
    color: #ffffff;
}
QLineEdit:focus, QSpinBox:focus, QDateTimeEdit:focus, QComboBox:focus {
    border: 1px solid #4a90e2;
}
QPushButton {
    background-color: #333344;
    border: 1px solid #555566;
    border-radius: 4px;
    padding: 5px 12px;
    color: #ffffff;
}
QPushButton:hover {
    background-color: #444458;
    border-color: #66667a;
}
QPushButton:pressed {
    background-color: #222230;
}
QPushButton:disabled {
    background-color: #262630;
    color: #666677;
    border-color: #333340;
}
QTableWidget {
    background-color: #1a1a20;
    border: 1px solid #333344;
    gridline-color: #2c2c38;
    selection-background-color: #2a4d69;
    selection-color: #ffffff;
}
QHeaderView::section {
    background-color: #282834;
    padding: 4px;
    border: 1px solid #333344;
    font-weight: bold;
    color: #cccccc;
}
QListWidget {
    background-color: #1a1a20;
    border: 1px solid #333344;
}
QTabWidget::pane {
    border: 1px solid #3d3d4a;
    background-color: #1e1e24;
}
QTabBar::tab {
    background-color: #2a2a35;
    color: #aaaaaa;
    padding: 8px 18px;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    font-weight: bold;
}
QTabBar::tab:selected {
    background-color: #1e1e24;
    color: #ffffff;
    border-top: 2px solid #4a90e2;
}
QTabBar::tab:hover:!selected {
    background-color: #353545;
}
QProgressBar {
    border: 1px solid #444455;
    border-radius: 4px;
    text-align: center;
    background-color: #181820;
}
QProgressBar::chunk {
    background-color: #4a90e2;
}
"""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PhotoVault Studio (Qt6) - Photo Ingestion, Differential & Deduplication")
        self.resize(1350, 880)

        # 1. Setup Menu Bar
        self._setup_menus()

        # 2. Tabs Setup
        tabs = QTabWidget()
        tabs.setDocumentMode(True)

        self.diff_tab = DiffTab(self)
        self.dedupe_tab = DedupeTab(self)
        self.exif_tab = ExifTab(self)
        self.sync_tab = SyncTab(self)

        tabs.addTab(self.diff_tab, "🔍 Dataset Comparison (Diff)")
        tabs.addTab(self.dedupe_tab, "🖼️ Duplicate Finder & Visual Matcher")
        tabs.addTab(self.exif_tab, "🏷️ EXIF Inspector & Batch Date Editor")
        tabs.addTab(self.sync_tab, "⚡ NAS Sync & Local Vault")

        # 3. Top-Right Documentation Button
        btn_doc = QPushButton("📖 Documentation (F1)")
        btn_doc.setStyleSheet("""
            QPushButton {
                background-color: #2b5c8f;
                color: #ffffff;
                font-weight: bold;
                border: 1px solid #4178b0;
                padding: 4px 14px;
                margin: 4px 6px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #356fa8;
            }
        """)
        btn_doc.clicked.connect(self.show_documentation)
        tabs.setCornerWidget(btn_doc, Qt.Corner.TopRightCorner)

        self.setCentralWidget(tabs)

        # 4. Status Bar
        status = QStatusBar()
        self.setStatusBar(status)
        status.showMessage("Cortex Workstation Active | 72 Xeon Cores | Local Storage: /Workspaces/Photos")

    def _setup_menus(self):
        menu_bar = self.menuBar()

        # File Menu
        file_menu = menu_bar.addMenu("&File")
        act_exit = QAction("E&xit", self)
        act_exit.setShortcut("Ctrl+Q")
        act_exit.triggered.connect(self.close)
        file_menu.addAction(act_exit)

        # Tools Menu
        tools_menu = menu_bar.addMenu("&Tools")
        act_sync = QAction("Open NAS Sync Manager", self)
        act_sync.triggered.connect(lambda: self.centralWidget().setCurrentIndex(3))
        tools_menu.addAction(act_sync)

        # Help Menu
        help_menu = menu_bar.addMenu("&Help")

        act_docs = QAction("📖 View Operations Guide & Runbook", self)
        act_docs.setShortcut(QKeySequence("F1"))
        act_docs.triggered.connect(self.show_documentation)
        help_menu.addAction(act_docs)

        act_ext_docs = QAction("📂 Open Guide in External Editor", self)
        act_ext_docs.triggered.connect(self.open_external_docs)
        help_menu.addAction(act_ext_docs)

        help_menu.addSeparator()

        act_about = QAction("ℹ️ About PhotoVault Studio", self)
        act_about.triggered.connect(self.show_about)
        help_menu.addAction(act_about)

    def show_documentation(self):
        dlg = DocViewerDialog(self)
        dlg.exec()

    def open_external_docs(self):
        if DOC_PATH.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(DOC_PATH)))
        else:
            QMessageBox.warning(self, "Not Found", f"Documentation file not found: {DOC_PATH}")

    def show_about(self):
        QMessageBox.about(
            self,
            "About PhotoVault Studio",
            "<h3>PhotoVault Studio (Qt6)</h3>"
            "<p><b>Version:</b> 1.0.0<br>"
            "<b>System:</b> Cortex Workstation (72 Xeon Cores, NVMe Scratch)<br>"
            "<b>NAS Pair:</b> Synology DiskStation (10.19.5.11)</p>"
            "<p>High-performance photo ingestion, differential analysis, perceptual visual deduplication, "
            "and EXIF metadata repair engine.</p>"
        )


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_STYLE)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
