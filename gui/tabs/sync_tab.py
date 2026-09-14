from __future__ import annotations

import shutil
from pathlib import Path

from PyQt6.QtCore import QProcess, Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class SyncTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.process: QProcess | None = None
        self._setup_ui()
        self._update_storage_stats()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)

        # 1. Storage Status Dashboard
        storage_group = QGroupBox("Local Storage Overview (Cortex)")
        s_layout = QHBoxLayout(storage_group)

        self.lbl_workspaces_storage = QLabel("Workspaces: Calculating...")
        self.lbl_nvme_storage = QLabel("NVMe: Calculating...")
        s_layout.addWidget(self.lbl_workspaces_storage)
        s_layout.addWidget(self.lbl_nvme_storage)

        btn_refresh = QPushButton("Refresh Storage")
        btn_refresh.clicked.connect(self._update_storage_stats)
        s_layout.addWidget(btn_refresh)

        main_layout.addWidget(storage_group)

        # 2. Sync Trigger Actions
        action_group = QGroupBox("NAS to Cortex Synchronization Triggers")
        a_layout = QVBoxLayout(action_group)

        h_btns = QHBoxLayout()
        self.btn_sync_laura = QPushButton("Sync Laura Only (NAS -> Cortex)")
        self.btn_sync_laura.clicked.connect(lambda: self._start_sync("laura"))
        h_btns.addWidget(self.btn_sync_laura)

        self.btn_sync_paul = QPushButton("Sync Paul Combined (NAS -> Cortex)")
        self.btn_sync_paul.clicked.connect(lambda: self._start_sync("paul"))
        h_btns.addWidget(self.btn_sync_paul)

        self.btn_sync_hist = QPushButton("Sync Historical Master (NAS -> Cortex)")
        self.btn_sync_hist.clicked.connect(lambda: self._start_sync("historical"))
        h_btns.addWidget(self.btn_sync_hist)

        self.btn_sync_all = QPushButton("Sync ALL Photos (Full Mirror)")
        self.btn_sync_all.setStyleSheet("font-weight: bold; background-color: #2b5c8f; color: white;")
        self.btn_sync_all.clicked.connect(lambda: self._start_sync("all"))
        h_btns.addWidget(self.btn_sync_all)

        a_layout.addLayout(h_btns)

        # Abort Button
        self.btn_stop = QPushButton("Stop Active Sync")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._stop_sync)
        a_layout.addWidget(self.btn_stop)

        main_layout.addWidget(action_group)

        # 3. Live Console Terminal
        main_layout.addWidget(QLabel("Real-time Synchronization Output:"))
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setFont(QFont("Monospace", 9))
        self.console.setStyleSheet("background-color: #121212; color: #00ff00; border: 1px solid #333;")
        main_layout.addWidget(self.console)

    def _update_storage_stats(self):
        try:
            total_ws, used_ws, free_ws = shutil.disk_usage("/Workspaces")
            self.lbl_workspaces_storage.setText(
                f"<b>/Workspaces:</b> {free_ws / (1024**3):.1f} GB free of {total_ws / (1024**3):.1f} GB ({used_ws / total_ws * 100:.1f}% used)"
            )
        except Exception:
            self.lbl_workspaces_storage.setText("/Workspaces: N/A")

        try:
            total_nv, used_nv, free_nv = shutil.disk_usage("/workspaces_nvme")
            self.lbl_nvme_storage.setText(
                f"<b>/workspaces_nvme:</b> {free_nv / (1024**3):.1f} GB free of {total_nv / (1024**3):.1f} GB"
            )
        except Exception:
            self.lbl_nvme_storage.setText("/workspaces_nvme: N/A")

    def _start_sync(self, target: str):
        if self.process and self.process.state() == QProcess.ProcessState.Running:
            QMessageBox.warning(self, "Process Running", "A sync job is already in progress.")
            return

        script_path = "/workspaces_nvme/PhotoSynApp/scripts/sync_from_nas.sh"
        if not Path(script_path).exists():
            QMessageBox.critical(self, "Script Missing", f"Sync script not found at: {script_path}")
            return

        self.console.clear()
        self.console.append(f"Starting synchronization for target: {target} ...\n")
        self.btn_stop.setEnabled(True)
        self._set_sync_buttons_enabled(False)

        self.process = QProcess(self)
        self.process.readyReadStandardOutput.connect(self._handle_stdout)
        self.process.readyReadStandardError.connect(self._handle_stderr)
        self.process.finished.connect(self._handle_finished)

        self.process.start("/bin/bash", [script_path, target])

    def _handle_stdout(self):
        if self.process:
            data = self.process.readAllStandardOutput().data().decode("utf-8", errors="ignore")
            self.console.insertPlainText(data)
            self.console.ensureCursorVisible()

    def _handle_stderr(self):
        if self.process:
            data = self.process.readAllStandardError().data().decode("utf-8", errors="ignore")
            self.console.insertPlainText(data)
            self.console.ensureCursorVisible()

    def _handle_finished(self, exit_code: int):
        self.btn_stop.setEnabled(False)
        self._set_sync_buttons_enabled(True)
        self.console.append(f"\n[Sync process finished with exit code {exit_code}]\n")
        self._update_storage_stats()

    def _stop_sync(self):
        if self.process and self.process.state() == QProcess.ProcessState.Running:
            self.process.terminate()
            self.console.append("\n[Termination request sent to sync process...]\n")

    def _set_sync_buttons_enabled(self, enabled: bool):
        self.btn_sync_laura.setEnabled(enabled)
        self.btn_sync_paul.setEnabled(enabled)
        self.btn_sync_hist.setEnabled(enabled)
        self.btn_sync_all.setEnabled(enabled)
