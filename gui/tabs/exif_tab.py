from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import List

from PyQt6.QtCore import QDate, QDateTime, QTime, Qt
from PyQt6.QtGui import QColor, QPixmap
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateTimeEdit,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core.exif_manager import ExifManager

SUPPORTED_IMAGE_EXTS = {".jpg", ".jpeg", ".tiff", ".tif", ".png"}


class ExifTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.file_items: List[dict] = []
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)

        # 1. Directory & File Selection
        top_group = QGroupBox("Target Photos / Scans Selection")
        t_layout = QHBoxLayout(top_group)

        t_layout.addWidget(QLabel("Folder:"))
        self.edit_folder = QLineEdit("/Workspaces/Photos/Historical_Master")
        t_layout.addWidget(self.edit_folder)

        btn_browse = QPushButton("Browse Folder...")
        btn_browse.clicked.connect(self._browse_folder)
        t_layout.addWidget(btn_browse)

        btn_load = QPushButton("Load Photos")
        btn_load.setStyleSheet("font-weight: bold; background-color: #2b5c8f; color: white; padding: 4px 12px;")
        btn_load.clicked.connect(self._load_photos)
        t_layout.addWidget(btn_load)

        main_layout.addWidget(top_group)

        # 2. Splitter: Left = Table of Photos, Right = Preview & Batch Editor
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left Table
        left_widget = QWidget()
        l_layout = QVBoxLayout(left_widget)
        l_layout.setContentsMargins(0, 0, 0, 0)

        h_sel = QHBoxLayout()
        self.lbl_count = QLabel("Loaded: 0 photos")
        self.lbl_count.setStyleSheet("font-weight: bold;")
        h_sel.addWidget(self.lbl_count)
        h_sel.addStretch()

        btn_select_all = QPushButton("Select All")
        btn_select_all.clicked.connect(self._select_all)
        h_sel.addWidget(btn_select_all)

        btn_deselect_all = QPushButton("Deselect All")
        btn_deselect_all.clicked.connect(self._deselect_all)
        h_sel.addWidget(btn_deselect_all)
        l_layout.addLayout(h_sel)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Sel", "Filename", "Rating", "EXIF Date (Original)", "File Date", "Dimensions"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        l_layout.addWidget(self.table)
        splitter.addWidget(left_widget)

        # Right Panel: Preview + Batch Tools
        right_widget = QWidget()
        r_layout = QVBoxLayout(right_widget)
        r_layout.setContentsMargins(0, 0, 0, 0)

        # Preview Card
        prev_group = QGroupBox("Selected Photo Preview & EXIF Tags")
        p_layout = QVBoxLayout(prev_group)
        self.lbl_preview = QLabel("Select a photo to preview")
        self.lbl_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_preview.setMinimumSize(220, 220)
        self.lbl_preview.setStyleSheet("background-color: #1e1e24; border: 1px solid #444;")
        p_layout.addWidget(self.lbl_preview)

        self.lbl_photo_details = QLabel("No photo selected.")
        self.lbl_photo_details.setWordWrap(True)
        p_layout.addWidget(self.lbl_photo_details)
        r_layout.addWidget(prev_group)

        # Batch Date Tools
        tools_group = QGroupBox("Batch EXIF Tools (Applies to Checked Photos)")
        tool_layout = QVBoxLayout(tools_group)

        # Date Option: Don't modify date option
        self.chk_modify_date = QCheckBox("Modify Date/Time Header")
        self.chk_modify_date.setChecked(True)
        tool_layout.addWidget(self.chk_modify_date)

        # Mode A: Set Exact Date
        self.radio_exact = QRadioButton("Set Unified Date & Time:")
        self.radio_exact.setChecked(True)
        tool_layout.addWidget(self.radio_exact)

        h_dt = QHBoxLayout()
        self.dt_picker = QDateTimeEdit(QDateTime.currentDateTime())
        self.dt_picker.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.dt_picker.setCalendarPopup(True)
        h_dt.addWidget(self.dt_picker)
        tool_layout.addLayout(h_dt)

        # Mode B: Set Approximate Year / Decade
        self.radio_approx = QRadioButton("Set Approximate Historical Year (Scans):")
        tool_layout.addWidget(self.radio_approx)

        h_approx = QHBoxLayout()
        h_approx.addWidget(QLabel("Year:"))
        self.spin_year = QSpinBox()
        self.spin_year.setRange(1850, 2030)
        self.spin_year.setValue(1975)
        h_approx.addWidget(self.spin_year)

        h_approx.addWidget(QLabel("Season/Month:"))
        self.spin_month = QSpinBox()
        self.spin_month.setRange(1, 12)
        self.spin_month.setValue(6)
        h_approx.addWidget(self.spin_month)
        tool_layout.addLayout(h_approx)

        # Mode C: Extract from Filename
        self.radio_filename = QRadioButton("Extract Date from Filename (e.g. 1978-08-14, 1965_beach)")
        tool_layout.addWidget(self.radio_filename)

        # Mode D: Shift Dates
        self.radio_shift = QRadioButton("Shift Date by Years/Months/Days:")
        tool_layout.addWidget(self.radio_shift)

        h_shift = QHBoxLayout()
        h_shift.addWidget(QLabel("Years:"))
        self.spin_shift_years = QSpinBox()
        self.spin_shift_years.setRange(-100, 100)
        self.spin_shift_years.setValue(0)
        h_shift.addWidget(self.spin_shift_years)

        h_shift.addWidget(QLabel("Days:"))
        self.spin_shift_days = QSpinBox()
        self.spin_shift_days.setRange(-3650, 3650)
        self.spin_shift_days.setValue(0)
        h_shift.addWidget(self.spin_shift_days)
        tool_layout.addLayout(h_shift)

        # Star Rating / Favorite Tool
        h_rating = QHBoxLayout()
        h_rating.addWidget(QLabel("⭐ Star Rating / Favorite:"))
        self.combo_rating = QComboBox()
        self.combo_rating.addItems([
            "Keep Existing Rating",
            "⭐ Mark as 5-Star Favorite",
            "Clear Rating (Un-favorite)"
        ])
        h_rating.addWidget(self.combo_rating)
        tool_layout.addLayout(h_rating)

        # Extra options
        self.chk_clear_scanner = QCheckBox("Wipe Scanner Hardware tags (Make/Model/Software)")
        self.chk_clear_scanner.setChecked(True)
        tool_layout.addWidget(self.chk_clear_scanner)

        # Apply Button
        self.btn_apply = QPushButton("⚡ Apply Changes to Selected Photos")
        self.btn_apply.setStyleSheet("font-weight: bold; background-color: #4cae4c; color: white; padding: 8px 16px;")
        self.btn_apply.clicked.connect(self._apply_changes)
        tool_layout.addWidget(self.btn_apply)

        r_layout.addWidget(tools_group)
        splitter.addWidget(right_widget)

        splitter.setSizes([600, 400])
        main_layout.addWidget(splitter)

        # Status & Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

        self.lbl_status = QLabel("Ready.")
        self.lbl_status.setStyleSheet("color: #666; font-style: italic;")
        main_layout.addWidget(self.lbl_status)

    def _browse_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Select Photo Directory", self.edit_folder.text() or "/Workspaces/Photos")
        if d:
            self.edit_folder.setText(d)
            self._load_photos()

    def _load_photos(self):
        target_dir = Path(self.edit_folder.text().strip())
        if not target_dir.is_dir():
            QMessageBox.warning(self, "Invalid Folder", f"Folder does not exist: {target_dir}")
            return

        self.lbl_status.setText("Scanning folder for photos...")
        self.table.setRowCount(0)
        self.file_items = []

        files = []
        for root, _, fnames in os.walk(target_dir):
            for fn in fnames:
                p = Path(root) / fn
                if p.suffix.lower() in SUPPORTED_IMAGE_EXTS:
                    files.append(p)
            if len(files) > 1000:
                break

        for p in sorted(files):
            info = ExifManager.get_image_info(p)
            self.file_items.append(info)

        self.lbl_count.setText(f"Loaded: {len(self.file_items):,} photos")
        self.table.setRowCount(len(self.file_items))

        for row, info in enumerate(self.file_items):
            # 0. Checkbox
            chk_item = QTableWidgetItem()
            chk_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            chk_item.setCheckState(Qt.CheckState.Checked)
            self.table.setItem(row, 0, chk_item)

            # 1. Filename
            self.table.setItem(row, 1, QTableWidgetItem(info["filename"]))

            # 2. Rating
            rating_val = info.get("rating")
            if rating_val == 5:
                rating_item = QTableWidgetItem("⭐⭐⭐⭐⭐")
                rating_item.setForeground(QColor(240, 190, 40))
            elif rating_val:
                rating_item = QTableWidgetItem(f"{rating_val}★")
            else:
                rating_item = QTableWidgetItem("-")
            self.table.setItem(row, 2, rating_item)

            # 3. EXIF Date
            exif_str = info["exif_date"] or "Missing (Not set)"
            exif_item = QTableWidgetItem(exif_str)
            if not info["exif_date"]:
                exif_item.setForeground(Qt.GlobalColor.red)
            self.table.setItem(row, 3, exif_item)

            # 4. File Date
            self.table.setItem(row, 4, QTableWidgetItem(info["modified_time"]))

            # 5. Dimensions
            dim_str = f"{info['width']} × {info['height']}" if info['width'] > 0 else "-"
            self.table.setItem(row, 5, QTableWidgetItem(dim_str))

        self.lbl_status.setText(f"Loaded {len(self.file_items):,} photos.")

    def _select_all(self):
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 0)
            if item:
                item.setCheckState(Qt.CheckState.Checked)

    def _deselect_all(self):
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 0)
            if item:
                item.setCheckState(Qt.CheckState.Unchecked)

    def _on_selection_changed(self):
        rows = self.table.selectedIndexes()
        if not rows:
            return
        row = rows[0].row()
        if row < 0 or row >= len(self.file_items):
            return

        info = self.file_items[row]
        pix = QPixmap(info["path"])
        if not pix.isNull():
            scaled = pix.scaled(220, 220, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.lbl_preview.setPixmap(scaled)
        else:
            self.lbl_preview.setText("No Preview")

        rating_str = "⭐⭐⭐⭐⭐ (Favorite)" if info.get("is_favorite") else (f"{info.get('rating')}★" if info.get("rating") else "None")

        detail_text = f"""
        <b>File:</b> {info['filename']}<br>
        <b>Rating:</b> <span style='color:#f0be28; font-weight:bold;'>{rating_str}</span><br>
        <b>EXIF Date:</b> {info['exif_date'] or '<i>None</i>'}<br>
        <b>File Size:</b> {info['size_human']}<br>
        <b>Resolution:</b> {info['width']} × {info['height']}<br>
        <b>Camera Make:</b> {info['camera_make'] or '<i>None</i>'}<br>
        <b>Camera Model:</b> {info['camera_model'] or '<i>None</i>'}<br>
        <b>Full Path:</b> <span style='font-size:10px;'>{info['path']}</span>
        """
        self.lbl_photo_details.setText(detail_text)

    def _apply_changes(self):
        selected_indices = [
            r for r in range(self.table.rowCount())
            if self.table.item(r, 0).checkState() == Qt.CheckState.Checked
        ]

        if not selected_indices:
            QMessageBox.information(self, "No Selection", "Please check at least one photo in the list.")
            return

        reply = QMessageBox.question(
            self,
            "Confirm Batch EXIF Modification",
            f"Are you sure you want to modify EXIF headers for {len(selected_indices)} photos?\nThis writes directly to image headers losslessly.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(selected_indices))
        self.progress_bar.setValue(0)

        modified_count = 0
        rating_choice = self.combo_rating.currentIndex()

        for idx, row in enumerate(selected_indices, 1):
            info = self.file_items[row]
            file_path = info["path"]

            # 1. Date Modification (if checked)
            if self.chk_modify_date.isChecked():
                if self.radio_exact.isChecked():
                    py_dt = self.dt_picker.dateTime().toPyDateTime()
                    ExifManager.set_exif_date(file_path, py_dt)
                    modified_count += 1
                elif self.radio_approx.isChecked():
                    y = self.spin_year.value()
                    m = self.spin_month.value()
                    py_dt = datetime(y, m, 15, 12, 0, 0)
                    ExifManager.set_exif_date(file_path, py_dt)
                    modified_count += 1
                elif self.radio_filename.isChecked():
                    extracted = ExifManager.extract_date_from_filename(info["filename"])
                    if extracted:
                        ExifManager.set_exif_date(file_path, extracted)
                        modified_count += 1
                elif self.radio_shift.isChecked():
                    y = self.spin_shift_years.value()
                    d = self.spin_shift_days.value()
                    if ExifManager.shift_exif_date(file_path, years=y, days=d):
                        modified_count += 1

            # 2. Rating Modification
            if rating_choice == 1:
                ExifManager.set_rating(file_path, 5)
                modified_count += 1
            elif rating_choice == 2:
                ExifManager.set_rating(file_path, 0)
                modified_count += 1

            # 3. Scanner Cleanup
            if self.chk_clear_scanner.isChecked():
                ExifManager.clear_scanner_tags(file_path)

            self.progress_bar.setValue(idx)

        self.progress_bar.setVisible(False)
        QMessageBox.information(self, "Batch Complete", f"Successfully updated EXIF tags on {modified_count} photos!")
        self._load_photos()
