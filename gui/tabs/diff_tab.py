from __future__ import annotations

import csv
from pathlib import Path
from typing import List

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core.comparator import ComparatorWorker
from ..core.exif_manager import ExifManager


class DiffTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker: ComparatorWorker | None = None
        self.current_items: List[dict] = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # 1. Folder Selection Group
        folder_group = QGroupBox("Directory Comparison Targets")
        f_layout = QVBoxLayout(folder_group)

        # Folder A
        h_a = QHBoxLayout()
        h_a.addWidget(QLabel("Directory A (Base):"))
        self.edit_dir_a = QLineEdit("/Workspaces/Photos/Paul_Combined")
        h_a.addWidget(self.edit_dir_a)
        btn_browse_a = QPushButton("Browse...")
        btn_browse_a.clicked.connect(lambda: self._browse_dir(self.edit_dir_a))
        h_a.addWidget(btn_browse_a)
        f_layout.addLayout(h_a)

        # Folder B
        h_b = QHBoxLayout()
        h_b.addWidget(QLabel("Directory B (Compare):"))
        self.edit_dir_b = QLineEdit("/Workspaces/Photos/Laura_Only")
        h_b.addWidget(self.edit_dir_b)
        btn_browse_b = QPushButton("Browse...")
        btn_browse_b.clicked.connect(lambda: self._browse_dir(self.edit_dir_b))
        h_b.addWidget(btn_browse_b)
        f_layout.addLayout(h_b)

        # Presets
        h_presets = QHBoxLayout()
        h_presets.addWidget(QLabel("Quick Presets:"))
        btn_p1 = QPushButton("Paul vs. Laura")
        btn_p1.clicked.connect(lambda: self._set_presets("/Workspaces/Photos/Paul_Combined", "/Workspaces/Photos/Laura_Only"))
        h_presets.addWidget(btn_p1)

        btn_p2 = QPushButton("Paul vs. Historical Master")
        btn_p2.clicked.connect(lambda: self._set_presets("/Workspaces/Photos/Paul_Combined", "/Workspaces/Photos/Historical_Master"))
        h_presets.addWidget(btn_p2)

        btn_p3 = QPushButton("Laura vs. Historical Master")
        btn_p3.clicked.connect(lambda: self._set_presets("/Workspaces/Photos/Laura_Only", "/Workspaces/Photos/Historical_Master"))
        h_presets.addWidget(btn_p3)
        h_presets.addStretch()
        f_layout.addLayout(h_presets)

        layout.addWidget(folder_group)

        # 2. Options & Actions Bar
        h_opts = QHBoxLayout()
        self.chk_hash = QCheckBox("Deep Content Check (SHA-256 for identical sizes)")
        self.chk_hash.setChecked(False)
        h_opts.addWidget(self.chk_hash)

        self.btn_run = QPushButton("Start Comparison")
        self.btn_run.setStyleSheet("font-weight: bold; background-color: #2b5c8f; color: white; padding: 6px 16px;")
        self.btn_run.clicked.connect(self._start_comparison)
        h_opts.addWidget(self.btn_run)

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self._cancel_comparison)
        h_opts.addWidget(self.btn_cancel)

        self.btn_export = QPushButton("Export CSV Report...")
        self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(self._export_csv)
        h_opts.addWidget(self.btn_export)

        layout.addLayout(h_opts)

        # 3. Progress Bar & Status
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.lbl_status = QLabel("Ready to compare.")
        self.lbl_status.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(self.lbl_status)

        # 4. Summary Dashboard
        self.summary_group = QGroupBox("Comparison Statistics")
        s_layout = QHBoxLayout(self.summary_group)
        self.lbl_total_a = QLabel("Total in A: -")
        self.lbl_total_b = QLabel("Total in B: -")
        self.lbl_only_a = QLabel("Only in A: -")
        self.lbl_only_a.setStyleSheet("color: #d9534f; font-weight: bold;")
        self.lbl_only_b = QLabel("Only in B: -")
        self.lbl_only_b.setStyleSheet("color: #337ab7; font-weight: bold;")
        self.lbl_identical = QLabel("Identical: -")
        self.lbl_identical.setStyleSheet("color: #5cb85c; font-weight: bold;")
        self.lbl_modified = QLabel("Modified: -")
        self.lbl_modified.setStyleSheet("color: #f0ad4e; font-weight: bold;")

        for lbl in [self.lbl_total_a, self.lbl_total_b, self.lbl_only_a, self.lbl_only_b, self.lbl_identical, self.lbl_modified]:
            s_layout.addWidget(lbl)
        layout.addWidget(self.summary_group)

        # 5. Filter & Search
        h_filter = QHBoxLayout()
        h_filter.addWidget(QLabel("Filter Status:"))
        self.combo_filter = QComboBox()
        self.combo_filter.addItems(["All Items", "Only in A", "Only in B", "Modified", "Identical"])
        self.combo_filter.currentTextChanged.connect(self._apply_filters)
        h_filter.addWidget(self.combo_filter)

        h_filter.addWidget(QLabel("Search Path:"))
        self.edit_search = QLineEdit()
        self.edit_search.setPlaceholderText("Filter by filename or folder...")
        self.edit_search.textChanged.connect(self._apply_filters)
        h_filter.addWidget(self.edit_search)
        layout.addLayout(h_filter)

        # 6. Results Table
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Status", "Relative Path", "Size in A", "Size in B", "Full Path"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setSortingEnabled(True)
        layout.addWidget(self.table)

    def _browse_dir(self, line_edit: QLineEdit):
        d = QFileDialog.getExistingDirectory(self, "Select Directory", line_edit.text() or "/Workspaces/Photos")
        if d:
            line_edit.setText(d)

    def _set_presets(self, path_a: str, path_b: str):
        self.edit_dir_a.setText(path_a)
        self.edit_dir_b.setText(path_b)

    def _start_comparison(self):
        dir_a = self.edit_dir_a.text().strip()
        dir_b = self.edit_dir_b.text().strip()

        if not dir_a or not Path(dir_a).is_dir():
            QMessageBox.warning(self, "Invalid Directory", f"Directory A does not exist: {dir_a}")
            return
        if not dir_b or not Path(dir_b).is_dir():
            QMessageBox.warning(self, "Invalid Directory", f"Directory B does not exist: {dir_b}")
            return

        self.btn_run.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.btn_export.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.lbl_status.setText("Starting comparison...")
        self.table.setRowCount(0)

        self.worker = ComparatorWorker(dir_a, dir_b, check_hash=self.chk_hash.isChecked(), parent=self)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _cancel_comparison(self):
        if self.worker:
            self.worker.cancel()
            self.lbl_status.setText("Comparison cancelled by user.")
            self.btn_run.setEnabled(True)
            self.btn_cancel.setEnabled(False)
            self.progress_bar.setVisible(False)

    def _on_progress(self, current: int, total: int, msg: str):
        if total > 0:
            self.progress_bar.setMaximum(total)
            self.progress_bar.setValue(current)
        self.lbl_status.setText(msg)

    def _on_finished(self, results: dict):
        self.btn_run.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.btn_export.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.lbl_status.setText("Comparison complete.")

        summary = results["summary"]
        self.lbl_total_a.setText(f"Total in A: {summary['total_a']:,}")
        self.lbl_total_b.setText(f"Total in B: {summary['total_b']:,}")
        self.lbl_only_a.setText(f"Only in A: {summary['only_a']:,}")
        self.lbl_only_b.setText(f"Only in B: {summary['only_b']:,}")
        self.lbl_identical.setText(f"Identical: {summary['identical']:,}")
        self.lbl_modified.setText(f"Modified: {summary['modified']:,}")

        self.current_items = results["items"]
        self._apply_filters()

    def _on_error(self, err_msg: str):
        self.btn_run.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.progress_bar.setVisible(False)
        self.lbl_status.setText(f"Error: {err_msg}")
        QMessageBox.critical(self, "Comparison Error", err_msg)

    def _apply_filters(self):
        filter_status = self.combo_filter.currentText()
        search_query = self.edit_search.text().lower().strip()

        filtered = []
        for item in self.current_items:
            # Status check
            if filter_status == "Only in A" and item["status"] != "Only in A":
                continue
            if filter_status == "Only in B" and item["status"] != "Only in B":
                continue
            if filter_status == "Modified" and not item["status"].startswith("Modified"):
                continue
            if filter_status == "Identical" and item["status"] != "Identical":
                continue

            # Search check
            if search_query and search_query not in item["rel_path"].lower():
                continue

            filtered.append(item)

        self.table.setRowCount(0)
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(filtered))

        for row, item in enumerate(filtered):
            # Status item with color
            status_item = QTableWidgetItem(item["status"])
            if item["status"] == "Only in A":
                status_item.setForeground(Qt.GlobalColor.red)
            elif item["status"] == "Only in B":
                status_item.setForeground(Qt.GlobalColor.blue)
            elif item["status"].startswith("Modified"):
                status_item.setForeground(Qt.GlobalColor.darkYellow)
            else:
                status_item.setForeground(Qt.GlobalColor.darkGreen)
            self.table.setItem(row, 0, status_item)

            self.table.setItem(row, 1, QTableWidgetItem(item["rel_path"]))

            size_a_str = ExifManager._human_size(item["size_a"]) if item["size_a"] is not None else "-"
            size_b_str = ExifManager._human_size(item["size_b"]) if item["size_b"] is not None else "-"
            self.table.setItem(row, 2, QTableWidgetItem(size_a_str))
            self.table.setItem(row, 3, QTableWidgetItem(size_b_str))

            full_p = item["path_a"] or item["path_b"] or ""
            self.table.setItem(row, 4, QTableWidgetItem(full_p))

        self.table.setSortingEnabled(True)

    def _export_csv(self):
        if not self.current_items:
            return
        dest, _ = QFileDialog.getSaveFileName(self, "Export Comparison Results", "photos_comparison_report.csv", "CSV Files (*.csv)")
        if not dest:
            return
        with open(dest, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Status", "Relative Path", "Size A (Bytes)", "Size B (Bytes)", "Path A", "Path B"])
            for item in self.current_items:
                writer.writerow([
                    item["status"],
                    item["rel_path"],
                    item["size_a"] or "",
                    item["size_b"] or "",
                    item["path_a"] or "",
                    item["path_b"] or "",
                ])
        QMessageBox.information(self, "Export Successful", f"Report saved successfully to:\n{dest}")
