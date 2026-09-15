from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import List

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QProgressDialog,
    QPushButton,
    QRadioButton,
    QSlider,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ..core.deduplicator import DeduplicatorWorker
from ..core.exif_manager import ExifManager


class DedupeTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker: DeduplicatorWorker | None = None
        self.duplicate_groups: List[List[dict]] = []
        self.current_group_idx = -1
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)

        # 1. Scan Configuration Group
        cfg_group = QGroupBox("Duplicate Scan Configuration")
        c_layout = QVBoxLayout(cfg_group)

        # Path Selection
        h_path = QHBoxLayout()
        h_path.addWidget(QLabel("Target Directory:"))
        self.edit_dir = QLineEdit("/Workspaces/Photos")
        h_path.addWidget(self.edit_dir)
        btn_browse = QPushButton("Browse...")
        btn_browse.clicked.connect(self._browse_dir)
        h_path.addWidget(btn_browse)
        c_layout.addLayout(h_path)

        # Mode Selection
        h_mode = QHBoxLayout()
        h_mode.addWidget(QLabel("Detection Mode:"))
        self.radio_binary = QRadioButton("Exact Binary Match (SHA-256)")
        self.radio_phash = QRadioButton("Perceptual Visual Match (pHash - Finds Same Photo with Different EXIF/Resolution)")
        self.radio_phash.setChecked(True)
        self.radio_phash.toggled.connect(self._toggle_phash_opts)

        self.btn_group_mode = QButtonGroup(self)
        self.btn_group_mode.addButton(self.radio_binary)
        self.btn_group_mode.addButton(self.radio_phash)
        h_mode.addWidget(self.radio_binary)
        h_mode.addWidget(self.radio_phash)
        h_mode.addStretch()
        c_layout.addLayout(h_mode)

        # Sensitivity & Multi-core Settings
        self.h_phash_opts = QHBoxLayout()
        self.lbl_thresh = QLabel("pHash Sensitivity (Max Difference: 4):")
        self.slider_thresh = QSlider(Qt.Orientation.Horizontal)
        self.slider_thresh.setRange(0, 10)
        self.slider_thresh.setValue(4)
        self.slider_thresh.valueChanged.connect(
            lambda v: self.lbl_thresh.setText(f"pHash Sensitivity (Max Difference: {v}):")
        )
        self.h_phash_opts.addWidget(self.lbl_thresh)
        self.h_phash_opts.addWidget(self.slider_thresh)

        self.h_phash_opts.addWidget(QLabel("Parallel Threads (Cores):"))
        self.slider_threads = QSlider(Qt.Orientation.Horizontal)
        self.slider_threads.setRange(2, 64)
        self.slider_threads.setValue(16)
        self.lbl_threads = QLabel("16")
        self.slider_threads.valueChanged.connect(lambda v: self.lbl_threads.setText(str(v)))
        self.h_phash_opts.addWidget(self.slider_threads)
        self.h_phash_opts.addWidget(self.lbl_threads)
        c_layout.addLayout(self.h_phash_opts)

        # Buttons
        h_btns = QHBoxLayout()
        self.btn_scan = QPushButton("Start Duplicate Scan")
        self.btn_scan.setStyleSheet("font-weight: bold; background-color: #2b5c8f; color: white; padding: 6px 16px;")
        self.btn_scan.clicked.connect(self._start_scan)
        h_btns.addWidget(self.btn_scan)

        self.btn_cancel = QPushButton("Cancel Scan")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self._cancel_scan)
        h_btns.addWidget(self.btn_cancel)
        h_btns.addStretch()
        c_layout.addLayout(h_btns)

        main_layout.addWidget(cfg_group)

        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

        self.lbl_status = QLabel("Ready to scan.")
        self.lbl_status.setStyleSheet("color: #666; font-style: italic;")
        main_layout.addWidget(self.lbl_status)

        # 2. Main Work Area: Left = Duplicate Sets, Right = Side-by-Side Review
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: Duplicate Groups List
        left_widget = QWidget()
        l_layout = QVBoxLayout(left_widget)
        l_layout.setContentsMargins(0, 0, 0, 0)
        self.lbl_groups_count = QLabel("Duplicate Groups (0 found)")
        self.lbl_groups_count.setStyleSheet("font-weight: bold;")
        l_layout.addWidget(self.lbl_groups_count)

        self.list_groups = QListWidget()
        self.list_groups.currentRowChanged.connect(self._on_group_selected)
        l_layout.addWidget(self.list_groups)
        splitter.addWidget(left_widget)

        # Right: Side-by-Side Comparison
        right_widget = QWidget()
        r_layout = QVBoxLayout(right_widget)
        r_layout.setContentsMargins(0, 0, 0, 0)

        # Top Action Bar
        h_actions = QHBoxLayout()
        self.btn_keep_left = QPushButton("Keep Left (Trash Right)")
        self.btn_keep_left.clicked.connect(self._keep_left)
        h_actions.addWidget(self.btn_keep_left)

        self.btn_keep_right = QPushButton("Keep Right (Trash Left)")
        self.btn_keep_right.clicked.connect(self._keep_right)
        h_actions.addWidget(self.btn_keep_right)

        self.btn_keep_higher_res = QPushButton("⚡ Smart Pick: Keep Highest Resolution")
        self.btn_keep_higher_res.setStyleSheet("font-weight: bold; color: #2e6da4;")
        self.btn_keep_higher_res.clicked.connect(self._keep_higher_res)
        h_actions.addWidget(self.btn_keep_higher_res)

        self.btn_auto_resolve_all = QPushButton("⚡ Keep Highest Res on ALL Duplicates")
        self.btn_auto_resolve_all.setStyleSheet("font-weight: bold; background-color: #2b7a4b; color: white; padding: 4px 12px;")
        self.btn_auto_resolve_all.setToolTip("Automatically keep the highest resolution / highest quality photo in every duplicate group and move all other duplicates to trash.")
        self.btn_auto_resolve_all.clicked.connect(self._auto_resolve_all_highest_res)
        h_actions.addWidget(self.btn_auto_resolve_all)
        r_layout.addLayout(h_actions)

        # Image Cards Splitter
        img_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left Image Card
        self.left_card = QGroupBox("Photo A (Left)")
        lc_layout = QVBoxLayout(self.left_card)
        self.lbl_preview_left = QLabel("Select a duplicate group to compare")
        self.lbl_preview_left.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_preview_left.setMinimumSize(250, 250)
        self.lbl_preview_left.setStyleSheet("background-color: #1e1e1e; border: 1px solid #444;")
        lc_layout.addWidget(self.lbl_preview_left)

        self.lbl_info_left = QLabel("-")
        self.lbl_info_left.setWordWrap(True)
        lc_layout.addWidget(self.lbl_info_left)
        img_splitter.addWidget(self.left_card)

        # Right Image Card
        self.right_card = QGroupBox("Photo B (Right)")
        rc_layout = QVBoxLayout(self.right_card)
        self.lbl_preview_right = QLabel("Select a duplicate group to compare")
        self.lbl_preview_right.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_preview_right.setMinimumSize(250, 250)
        self.lbl_preview_right.setStyleSheet("background-color: #1e1e1e; border: 1px solid #444;")
        rc_layout.addWidget(self.lbl_preview_right)

        self.lbl_info_right = QLabel("-")
        self.lbl_info_right.setWordWrap(True)
        rc_layout.addWidget(self.lbl_info_right)
        img_splitter.addWidget(self.right_card)

        r_layout.addWidget(img_splitter)
        splitter.addWidget(right_widget)

        splitter.setSizes([300, 700])
        main_layout.addWidget(splitter)
        self._update_action_buttons_state()

    def _toggle_phash_opts(self):
        enabled = self.radio_phash.isChecked()
        self.slider_thresh.setEnabled(enabled)

    def _browse_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Select Directory to Scan", self.edit_dir.text() or "/Workspaces/Photos")
        if d:
            self.edit_dir.setText(d)

    def _start_scan(self):
        target_dir = self.edit_dir.text().strip()
        if not target_dir or not Path(target_dir).is_dir():
            QMessageBox.warning(self, "Invalid Directory", f"Directory does not exist: {target_dir}")
            return

        mode = "phash" if self.radio_phash.isChecked() else "binary"
        thresh = self.slider_thresh.value()
        workers = self.slider_threads.value()

        self.btn_scan.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.lbl_status.setText("Initializing scanner...")
        self.list_groups.clear()
        self.duplicate_groups = []
        self.current_group_idx = -1
        self._update_action_buttons_state()

        self.worker = DeduplicatorWorker(
            directories=[target_dir],
            mode=mode,
            phash_threshold=thresh,
            max_workers=workers,
            parent=self,
        )
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _cancel_scan(self):
        if self.worker:
            self.worker.cancel()
            self.lbl_status.setText("Scan cancelled by user.")
            self.btn_scan.setEnabled(True)
            self.btn_cancel.setEnabled(False)
            self.progress_bar.setVisible(False)
            self._update_action_buttons_state()

    def _on_progress(self, current: int, total: int, msg: str):
        if total > 0:
            self.progress_bar.setMaximum(total)
            self.progress_bar.setValue(current)
        self.lbl_status.setText(msg)

    def _on_finished(self, groups: List[List[dict]]):
        self.btn_scan.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.progress_bar.setVisible(False)
        self.duplicate_groups = groups
        self.lbl_groups_count.setText(f"Duplicate Groups ({len(groups):,} found)")
        self.lbl_status.setText(f"Scan complete. Found {len(groups):,} duplicate sets.")

        self.list_groups.clear()
        for idx, grp in enumerate(groups, 1):
            names = ", ".join(item["filename"] for item in grp[:2])
            item = QListWidgetItem(f"Set #{idx} ({len(grp)} files): {names}")
            self.list_groups.addItem(item)

        if groups:
            self.list_groups.setCurrentRow(0)
            self._on_group_selected(0)
        else:
            self._clear_cards()
        self._update_action_buttons_state()

    def _on_error(self, err_msg: str):
        self.btn_scan.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.progress_bar.setVisible(False)
        self.lbl_status.setText(f"Error: {err_msg}")
        self._update_action_buttons_state()
        QMessageBox.critical(self, "Scan Error", err_msg)

    def _clear_cards(self):
        """Reset card previews and information when no duplicate group is selected."""
        self.lbl_preview_left.clear()
        self.lbl_preview_left.setText("No duplicates to compare")
        self.lbl_info_left.setText("-")
        self.left_card.setTitle("Photo A (Left)")

        self.lbl_preview_right.clear()
        self.lbl_preview_right.setText("No duplicates to compare")
        self.lbl_info_right.setText("-")
        self.right_card.setTitle("Photo B (Right)")
        self._update_action_buttons_state()

    def _on_group_selected(self, row: int):
        if row < 0 or row >= len(self.duplicate_groups):
            self._clear_cards()
            return
        self.current_group_idx = row
        self._update_action_buttons_state()
        grp = self.duplicate_groups[row]
        if len(grp) < 2:
            self._clear_cards()
            return

        item_a = grp[0]
        item_b = grp[1]

        self._render_card(item_a, self.lbl_preview_left, self.lbl_info_left, is_left=True, other_item=item_b)
        self._render_card(item_b, self.lbl_preview_right, self.lbl_info_right, is_left=False, other_item=item_a)

    def _render_card(self, item: dict, preview_lbl: QLabel, info_lbl: QLabel, is_left: bool, other_item: dict):
        pixmap = QPixmap(item["path"])
        if not pixmap.isNull():
            scaled = pixmap.scaled(320, 320, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            preview_lbl.setPixmap(scaled)
        else:
            preview_lbl.setText("Failed to load preview")

        res_a = item["width"] * item["height"]
        res_b = other_item["width"] * other_item["height"]

        res_color = "#28a745" if res_a > res_b else ("#dc3545" if res_a < res_b else "#bbb")
        size_color = "#28a745" if item["size"] > other_item["size"] else ("#dc3545" if item["size"] < other_item["size"] else "#bbb")

        card = self.left_card if is_left else self.right_card
        card.setTitle(f"Photo {'A (Left)' if is_left else 'B (Right)'}: {item['filename']}")

        info_text = f"""
        <b>Filename:</b> {item['filename']}<br>
        <b>Resolution:</b> <span style='color:{res_color}; font-weight:bold;'>{item['width']} × {item['height']}</span><br>
        <b>File Size:</b> <span style='color:{size_color}; font-weight:bold;'>{ExifManager._human_size(item['size'])}</span><br>
        <b>Path:</b> <span style='font-size:10px;'>{item['path']}</span>
        """
        info_lbl.setText(info_text)

    def _keep_left(self):
        if self.current_group_idx < 0 or self.current_group_idx >= len(self.duplicate_groups):
            return
        self._resolve_duplicate(keep_idx=0, trash_idx=1)

    def _keep_right(self):
        if self.current_group_idx < 0 or self.current_group_idx >= len(self.duplicate_groups):
            return
        self._resolve_duplicate(keep_idx=1, trash_idx=0)

    def _keep_higher_res(self):
        if self.current_group_idx < 0 or self.current_group_idx >= len(self.duplicate_groups):
            return
        grp = self.duplicate_groups[self.current_group_idx]
        if len(grp) < 2:
            return

        res_0 = grp[0]["width"] * grp[0]["height"]
        res_1 = grp[1]["width"] * grp[1]["height"]

        if res_0 > res_1:
            self._resolve_duplicate(keep_idx=0, trash_idx=1)
        elif res_1 > res_0:
            self._resolve_duplicate(keep_idx=1, trash_idx=0)
        else:
            # Identical resolution: prefer larger file size (less compression/higher fidelity)
            if grp[0].get("size", 0) >= grp[1].get("size", 0):
                self._resolve_duplicate(keep_idx=0, trash_idx=1)
            else:
                self._resolve_duplicate(keep_idx=1, trash_idx=0)

    def _resolve_duplicate(self, keep_idx: int, trash_idx: int):
        if self.current_group_idx < 0 or self.current_group_idx >= len(self.duplicate_groups):
            return
        grp = self.duplicate_groups[self.current_group_idx]
        if len(grp) < 2 or trash_idx >= len(grp):
            return

        trash_item = grp[trash_idx]
        trash_dir = Path("/Workspaces/Photos/_Duplicates_Trash")
        trash_dir.mkdir(parents=True, exist_ok=True)

        target_name = trash_item["filename"]
        dest = trash_dir / target_name
        if dest.exists():
            stem = Path(target_name).stem
            suffix = Path(target_name).suffix
            counter = 1
            while (trash_dir / f"{stem}_{counter}{suffix}").exists():
                counter += 1
            dest = trash_dir / f"{stem}_{counter}{suffix}"

        try:
            src = Path(trash_item["path"])
            if src.exists():
                shutil.move(str(src), str(dest))
                self.lbl_status.setText(f"Moved duplicate to trash folder: {dest.name}")
            else:
                self.lbl_status.setText(f"Source file was already missing: {src.name}")

            # Remove trashed item from the duplicate group
            grp.pop(trash_idx)

            # If the group still has 2 or more files, keep it active to compare remaining duplicates
            if len(grp) >= 2:
                names = ", ".join(item["filename"] for item in grp[:2])
                item_widget = self.list_groups.item(self.current_group_idx)
                if item_widget:
                    item_widget.setText(f"Set #{self.current_group_idx + 1} ({len(grp)} files): {names}")
                # Re-render the current group with remaining photos
                self._on_group_selected(self.current_group_idx)
            else:
                # Group is fully resolved! Remove from list and duplicate_groups
                # Temporarily block signals so intermediate takeItem events don't desynchronize UI
                self.list_groups.blockSignals(True)
                try:
                    self.duplicate_groups.pop(self.current_group_idx)
                    taken = self.list_groups.takeItem(self.current_group_idx)
                    del taken
                finally:
                    self.list_groups.blockSignals(False)

                total_remaining = len(self.duplicate_groups)
                self.lbl_groups_count.setText(f"Duplicate Groups ({total_remaining:,} found)")

                if total_remaining > 0:
                    # Advance to next group, clamping if we just removed the last item
                    next_idx = min(self.current_group_idx, total_remaining - 1)
                    self.current_group_idx = next_idx
                    self.list_groups.setCurrentRow(next_idx)
                    self._on_group_selected(next_idx)
                else:
                    self.current_group_idx = -1
                    self.list_groups.setCurrentRow(-1)
                    self._clear_cards()
                    self.lbl_status.setText("All duplicate groups have been resolved!")

                self._update_action_buttons_state()

        except Exception as e:
            QMessageBox.critical(self, "Error Moving Duplicate", str(e))

    def _update_action_buttons_state(self):
        """Enable or disable comparison and batch resolution buttons based on current state."""
        has_active_selection = (
            bool(self.duplicate_groups)
            and 0 <= self.current_group_idx < len(self.duplicate_groups)
        )
        self.btn_keep_left.setEnabled(has_active_selection)
        self.btn_keep_right.setEnabled(has_active_selection)
        self.btn_keep_higher_res.setEnabled(has_active_selection)
        self.btn_auto_resolve_all.setEnabled(bool(self.duplicate_groups))

    def _auto_resolve_all_highest_res(self):
        """Automatically keep the highest resolution / highest quality image in all duplicate groups, moving lower resolution duplicates to trash."""
        if not self.duplicate_groups:
            QMessageBox.information(
                self,
                "No Duplicates",
                "There are no duplicate groups to resolve. Please run a duplicate scan first.",
            )
            return

        total_groups = len(self.duplicate_groups)
        total_files = sum(len(grp) for grp in self.duplicate_groups)
        excess_files = total_files - total_groups

        reply = QMessageBox.question(
            self,
            "Confirm Keep Highest Resolution on ALL Duplicates",
            f"<h3>Auto-Resolve All Duplicates?</h3>"
            f"<p>This will analyze all <b>{total_groups:,}</b> duplicate sets ({total_files:,} total files).</p>"
            f"<p>In every set, the image with the <b>highest resolution</b> (and largest file size as tie-breaker) will be kept.<br>"
            f"The other <b>{excess_files:,}</b> lower-resolution / redundant duplicate files will be safely moved to:</p>"
            f"<pre>/Workspaces/Photos/_Duplicates_Trash</pre>"
            f"<p>Are you sure you want to proceed?</p>",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        trash_dir = Path("/Workspaces/Photos/_Duplicates_Trash")
        trash_dir.mkdir(parents=True, exist_ok=True)

        progress = QProgressDialog(
            "Resolving duplicates by highest resolution...",
            "Cancel",
            0,
            total_groups,
            self,
        )
        progress.setWindowTitle("Auto-Resolving Duplicates")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)

        resolved_groups = 0
        total_trashed = 0
        errors = []
        remaining_groups = []

        for idx, grp in enumerate(self.duplicate_groups):
            if progress.wasCanceled():
                remaining_groups.extend(self.duplicate_groups[idx:])
                break

            progress.setValue(idx)
            if grp:
                progress.setLabelText(f"Resolving set {idx + 1} of {total_groups}: {grp[0].get('filename', '')}...")
            QApplication.processEvents()

            if len(grp) < 2:
                continue

            # Rank files: highest resolution (w * h) first, then largest file size
            ranked = sorted(
                grp,
                key=lambda x: (x.get("width", 0) * x.get("height", 0), x.get("size", 0)),
                reverse=True,
            )

            trash_items = ranked[1:]
            for item in trash_items:
                target_name = item["filename"]
                dest = trash_dir / target_name
                if dest.exists():
                    stem = Path(target_name).stem
                    suffix = Path(target_name).suffix
                    counter = 1
                    while (trash_dir / f"{stem}_{counter}{suffix}").exists():
                        counter += 1
                    dest = trash_dir / f"{stem}_{counter}{suffix}"

                try:
                    src = Path(item["path"])
                    if src.exists():
                        shutil.move(str(src), str(dest))
                        total_trashed += 1
                except Exception as e:
                    errors.append(f"{item['filename']}: {e}")

            resolved_groups += 1

        progress.setValue(total_groups)

        # Update list widget with blocked signals
        self.list_groups.blockSignals(True)
        try:
            if not remaining_groups:
                self.duplicate_groups = []
                self.list_groups.clear()
                self.current_group_idx = -1
                self._clear_cards()
                self.lbl_groups_count.setText("Duplicate Groups (0 found)")
                self.lbl_status.setText(
                    f"Auto-resolved {resolved_groups:,} sets. Moved {total_trashed:,} duplicate files to trash."
                )

                msg = (
                    f"<b>Successfully resolved all {resolved_groups:,} duplicate sets!</b><br><br>"
                    f"<b>{total_trashed:,}</b> duplicate files were moved to:<br>"
                    f"<code>/Workspaces/Photos/_Duplicates_Trash</code>"
                )
                if errors:
                    msg += f"<br><br><span style='color:red;'>Encountered {len(errors)} file move errors:</span><br>" + "<br>".join(errors[:5])
                QMessageBox.information(self, "Auto-Resolve Complete", msg)
            else:
                # Canceled before finishing all sets
                self.duplicate_groups = remaining_groups
                self.list_groups.clear()
                for i, grp in enumerate(self.duplicate_groups, 1):
                    names = ", ".join(item["filename"] for item in grp[:2])
                    item_widget = QListWidgetItem(f"Set #{i} ({len(grp)} files): {names}")
                    self.list_groups.addItem(item_widget)

                self.lbl_groups_count.setText(f"Duplicate Groups ({len(self.duplicate_groups):,} found)")
                if self.duplicate_groups:
                    self.list_groups.setCurrentRow(0)
                    self._on_group_selected(0)
                else:
                    self._clear_cards()
                self.lbl_status.setText(
                    f"Auto-resolve canceled. Resolved {resolved_groups:,} sets, moved {total_trashed:,} files."
                )
        finally:
            self.list_groups.blockSignals(False)

        self._update_action_buttons_state()
