from __future__ import annotations

import sys
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

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
        self.resize(1300, 850)

        # Tabs Setup
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

        self.setCentralWidget(tabs)

        # Status Bar
        status = QStatusBar()
        self.setStatusBar(status)
        status.showMessage("Cortex Workstation Active | 72 Xeon Cores | /Workspaces & /workspaces_nvme Ready")


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_STYLE)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
