from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QCursor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.services.backup_service import BackupEntry, BackupService
from app.services.settings_service import SettingsService

logger = logging.getLogger(__name__)

# ── Colour palette (matches dark.qss) ──────────────────────────
_TEXT = "#cdd6f4"
_SUBTEXT = "#a6adc8"
_BLUE = "#89b4fa"
_GREEN = "#a6e3a1"
_YELLOW = "#f9e2af"
_ORANGE = "#fab387"
_RED = "#f38ba8"
_BORDER = "#313244"
_CARD_BG = "#181825"


class BackupPage(QWidget):
    """Backup & Restore page with create, restore, history, and settings."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ContentArea")
        self._build_ui()
        self._connect_signals()
        self._load_history()

    # ── UI construction ─────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setObjectName("ContentArea")

        container = QWidget()
        container.setObjectName("ContentArea")
        self._main_layout = QVBoxLayout(container)
        self._main_layout.setContentsMargins(20, 16, 20, 16)
        self._main_layout.setSpacing(16)

        # ── Header ─────────────────────────────────────────────
        hdr = QHBoxLayout()
        title = QLabel("\U0001f4be Backup & Restore")
        title.setObjectName("PageTitle")
        hdr.addWidget(title)
        hdr.addStretch()
        self._refresh_btn = QPushButton("\U0001f504 Refresh")
        self._refresh_btn.setObjectName("ToolbarButton")
        self._refresh_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._refresh_btn.clicked.connect(self._load_history)
        hdr.addWidget(self._refresh_btn)
        self._main_layout.addLayout(hdr)

        # ── Top row: Create Backup | Restore Backup ────────────
        top_row = QHBoxLayout()
        top_row.setSpacing(16)

        top_row.addWidget(self._build_create_backup_card(), 1)
        top_row.addWidget(self._build_restore_backup_card(), 1)

        self._main_layout.addLayout(top_row)

        # ── Status label ───────────────────────────────────────
        self._status_label = QLabel("")
        self._status_label.setStyleSheet(f"color: {_SUBTEXT}; font-size: 9pt;")
        self._main_layout.addWidget(self._status_label)

        # ── Backup History ─────────────────────────────────────
        self._main_layout.addWidget(self._build_history_label())
        self._history_table = self._create_history_table()
        self._main_layout.addWidget(self._history_table, stretch=1)

        # ── Bottom row: Backup Settings ────────────────────────
        self._main_layout.addWidget(self._build_settings_label())
        self._main_layout.addWidget(self._build_settings_card())

        self._main_layout.addStretch()
        scroll.setWidget(container)
        root.addWidget(scroll)

    # ── Card builders ───────────────────────────────────────────

    def _build_create_backup_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("DashboardCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        hdr = QLabel("\U0001f4e6 Create Backup")
        hdr.setStyleSheet(f"font-size: 12pt; font-weight: bold; color: {_TEXT};")
        layout.addWidget(hdr)

        desc = QLabel("Create a ZIP backup of your pharmacy database.\nBackups include the database file and optionally logs.")
        desc.setStyleSheet(f"color: {_SUBTEXT}; font-size: 9pt;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Include logs checkbox
        self._include_logs = QCheckBox("Include logs")
        self._include_logs.setStyleSheet(f"color: {_SUBTEXT}; font-size: 9pt;")
        layout.addWidget(self._include_logs)

        # Destination folder row
        folder_row = QHBoxLayout()
        folder_row.setSpacing(8)
        folder_lbl = QLabel("Destination:")
        folder_lbl.setStyleSheet(f"color: {_SUBTEXT}; font-size: 9pt;")
        folder_row.addWidget(folder_lbl)
        self._dest_folder = QLineEdit()
        self._dest_folder.setPlaceholderText("Default: backups/")
        self._dest_folder.setStyleSheet(
            f"background-color: #313244; color: {_TEXT}; border: 1px solid #45475a; "
            f"border-radius: 6px; padding: 6px 10px; font-size: 9pt;"
        )
        folder_row.addWidget(self._dest_folder, 1)
        self._browse_dest_btn = QPushButton("Browse")
        self._browse_dest_btn.setObjectName("ToolbarButton")
        self._browse_dest_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._browse_dest_btn.clicked.connect(self._browse_dest_folder)
        folder_row.addWidget(self._browse_dest_btn)
        layout.addLayout(folder_row)

        # Backup button
        self._backup_btn = QPushButton("\U0001f4be Create Backup Now")
        self._backup_btn.setObjectName("PrimaryButton")
        self._backup_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._backup_btn.clicked.connect(self._create_backup)
        layout.addWidget(self._backup_btn)

        return card

    def _build_restore_backup_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("DashboardCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        hdr = QLabel("\U0001f504 Restore Backup")
        hdr.setStyleSheet(f"font-size: 12pt; font-weight: bold; color: {_TEXT};")
        layout.addWidget(hdr)

        desc = QLabel("Restore pharmacy data from a backup ZIP file.\n⚠️ This will replace your current database. A safety backup is created automatically.")
        desc.setStyleSheet(f"color: {_SUBTEXT}; font-size: 9pt;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Selected file display
        self._restore_file_label = QLabel("No file selected")
        self._restore_file_label.setStyleSheet(
            f"color: {_SUBTEXT}; font-size: 9pt; "
            f"background-color: #313244; border: 1px solid #45475a; "
            f"border-radius: 6px; padding: 6px 10px;"
        )
        layout.addWidget(self._restore_file_label)

        # Buttons row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self._select_backup_btn = QPushButton("\U0001f4c2 Select Backup File")
        self._select_backup_btn.setObjectName("ToolbarButton")
        self._select_backup_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._select_backup_btn.clicked.connect(self._select_backup_file)
        btn_row.addWidget(self._select_backup_btn)

        self._restore_btn = QPushButton("\U0001f504 Restore Now")
        self._restore_btn.setObjectName("PrimaryButton")
        self._restore_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._restore_btn.setEnabled(False)
        self._restore_btn.clicked.connect(self._restore_backup)
        btn_row.addWidget(self._restore_btn)
        layout.addLayout(btn_row)

        self._selected_backup_path: str = ""

        return card

    @staticmethod
    def _build_history_label() -> QLabel:
        lbl = QLabel("\U0001f4cb Backup History")
        lbl.setStyleSheet(f"font-size: 12pt; font-weight: bold; color: {_TEXT};")
        return lbl

    @staticmethod
    def _build_settings_label() -> QLabel:
        lbl = QLabel("\u2699\ufe0f Backup Settings")
        lbl.setStyleSheet(f"font-size: 12pt; font-weight: bold; color: {_TEXT};")
        return lbl

    def _build_settings_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("DashboardCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        # Row 1: backup folder
        row1 = QHBoxLayout()
        row1.setSpacing(10)
        lbl1 = QLabel("Backup Folder:")
        lbl1.setFixedWidth(120)
        lbl1.setStyleSheet(f"color: {_SUBTEXT}; font-size: 10pt;")
        row1.addWidget(lbl1)
        self._settings_folder = QLineEdit()
        self._settings_folder.setStyleSheet(
            f"background-color: #313244; color: {_TEXT}; border: 1px solid #45475a; "
            f"border-radius: 6px; padding: 6px 10px; font-size: 10pt;"
        )
        row1.addWidget(self._settings_folder, 1)
        self._browse_settings_btn = QPushButton("Browse")
        self._browse_settings_btn.setObjectName("ToolbarButton")
        self._browse_settings_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._browse_settings_btn.clicked.connect(self._browse_settings_folder)
        row1.addWidget(self._browse_settings_btn)
        layout.addLayout(row1)

        # Row 2: auto-backup + max backups
        row2 = QHBoxLayout()
        row2.setSpacing(16)
        self._auto_daily = QCheckBox("Automatic Daily Backup")
        self._auto_daily.setStyleSheet(f"color: {_SUBTEXT}; font-size: 10pt;")
        row2.addWidget(self._auto_daily)
        self._auto_weekly = QCheckBox("Automatic Weekly Backup")
        self._auto_weekly.setStyleSheet(f"color: {_SUBTEXT}; font-size: 10pt;")
        row2.addWidget(self._auto_weekly)
        row2.addSpacing(16)
        max_lbl = QLabel("Max Backups:")
        max_lbl.setStyleSheet(f"color: {_SUBTEXT}; font-size: 10pt;")
        row2.addWidget(max_lbl)
        self._max_backups = QSpinBox()
        self._max_backups.setRange(1, 100)
        self._max_backups.setFixedWidth(80)
        row2.addWidget(self._max_backups)
        row2.addStretch()
        layout.addLayout(row2)

        # Load current settings into the form
        self._load_settings_form()

        # Save button
        save_row = QHBoxLayout()
        save_row.addStretch()
        self._save_settings_btn = QPushButton("Save Settings")
        self._save_settings_btn.setObjectName("PrimaryButton")
        self._save_settings_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._save_settings_btn.clicked.connect(self._save_settings)
        save_row.addWidget(self._save_settings_btn)
        layout.addLayout(save_row)

        return card

    # ── Table factory ───────────────────────────────────────────

    def _create_history_table(self) -> QTableWidget:
        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["Filename", "Date Created", "Size", "Location", "Actions"])
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in [1, 2, 3, 4]:
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.setShowGrid(False)
        table.setMinimumHeight(200)
        return table

    # ── Signal wiring ───────────────────────────────────────────

    def _connect_signals(self) -> None:
        pass

    # ── Actions ─────────────────────────────────────────────────

    def _browse_dest_folder(self) -> None:
        from PySide6.QtWidgets import QFileDialog

        folder = QFileDialog.getExistingDirectory(self, "Select Backup Destination")
        if folder:
            self._dest_folder.setText(folder)

    def _browse_settings_folder(self) -> None:
        from PySide6.QtWidgets import QFileDialog

        folder = QFileDialog.getExistingDirectory(self, "Select Backup Folder")
        if folder:
            self._settings_folder.setText(folder)

    def _create_backup(self) -> None:
        dest = self._dest_folder.text().strip() or None
        include_logs = self._include_logs.isChecked()

        self._status_label.setText("Creating backup...")
        self._status_label.setStyleSheet(f"color: {_BLUE}; font-size: 9pt;")
        self._backup_btn.setEnabled(False)

        try:
            path = BackupService.create_backup(dest_folder=dest, include_logs=include_logs)
            self._status_label.setText(f"\u2705 Backup created: {path.name}")
            self._status_label.setStyleSheet(f"color: {_GREEN}; font-size: 9pt;")
            self._load_history()
        except Exception as e:
            logger.exception("Backup creation failed")
            self._status_label.setText(f"\u274c Backup failed: {e}")
            self._status_label.setStyleSheet(f"color: {_RED}; font-size: 9pt;")
        finally:
            self._backup_btn.setEnabled(True)

    def _select_backup_file(self) -> None:
        from PySide6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getOpenFileName(
            self, "Select Backup File", "", "ZIP Files (*.zip);;All Files (*)"
        )
        if path:
            self._selected_backup_path = path
            name = Path(path).name
            self._restore_file_label.setText(f"\U0001f4c2 {name}")
            self._restore_file_label.setStyleSheet(
                f"color: {_TEXT}; font-size: 9pt; "
                f"background-color: #313244; border: 1px solid #45475a; "
                f"border-radius: 6px; padding: 6px 10px;"
            )
            # Validate
            valid, msg = BackupService.validate_backup(path)
            if valid:
                self._restore_btn.setEnabled(True)
                self._status_label.setText(f"\u2705 {msg}")
                self._status_label.setStyleSheet(f"color: {_GREEN}; font-size: 9pt;")
            else:
                self._restore_btn.setEnabled(False)
                self._status_label.setText(f"\u26a0\ufe0f {msg}")
                self._status_label.setStyleSheet(f"color: {_YELLOW}; font-size: 9pt;")

    def _restore_backup(self) -> None:
        if not self._selected_backup_path:
            return

        from PySide6.QtWidgets import QMessageBox

        reply = QMessageBox.warning(
            self,
            "Restore Backup",
            "⚠️ WARNING: This will replace your current database with the backup.\n\n"
            "A safety backup of the current database will be created automatically.\n\n"
            "The application will need to restart after restore.\n\n"
            "Do you want to continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        self._status_label.setText("Restoring backup...")
        self._status_label.setStyleSheet(f"color: {_BLUE}; font-size: 9pt;")
        self._restore_btn.setEnabled(False)

        try:
            BackupService.restore_backup(self._selected_backup_path)
            self._status_label.setText("\u2705 Backup restored successfully! Restarting...")
            self._status_label.setStyleSheet(f"color: {_GREEN}; font-size: 9pt;")

            # Prompt restart
            reply2 = QMessageBox.information(
                self,
                "Restart Required",
                "Backup restored successfully.\n\nThe application needs to restart to apply changes.\nRestart now?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if reply2 == QMessageBox.StandardButton.Yes:
                self._restart_app()
        except Exception as e:
            logger.exception("Restore failed")
            self._status_label.setText(f"\u274c Restore failed: {e}")
            self._status_label.setStyleSheet(f"color: {_RED}; font-size: 9pt;")
            self._restore_btn.setEnabled(True)

    def _restart_app(self) -> None:
        """Restart the application by launching a new process and closing the current one."""
        import subprocess
        python = sys.executable
        subprocess.Popen([python] + sys.argv)
        from PySide6.QtWidgets import QApplication
        QApplication.quit()

    def _open_folder(self, folder_path: str) -> None:
        """Open the backup folder in the system file explorer."""
        path = Path(folder_path)
        if not path.exists():
            return
        if sys.platform == "win32":
            os.startfile(str(path))
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])

    def _restore_from_history(self, filepath: str) -> None:
        """Restore from a specific backup file in the history table."""
        self._selected_backup_path = filepath
        self._restore_file_label.setText(f"\U0001f4c2 {Path(filepath).name}")
        self._restore_file_label.setStyleSheet(
            f"color: {_TEXT}; font-size: 9pt; "
            f"background-color: #313244; border: 1px solid #45475a; "
            f"border-radius: 6px; padding: 6px 10px;"
        )
        self._restore_btn.setEnabled(True)
        self._restore_backup()

    def _delete_from_history(self, filepath: str) -> None:
        """Delete a specific backup after confirmation."""
        from PySide6.QtWidgets import QMessageBox

        reply = QMessageBox.question(
            self,
            "Delete Backup",
            f"Delete backup {Path(filepath).name}?\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            if BackupService.delete_backup(filepath):
                self._status_label.setText("\u2705 Backup deleted.")
                self._status_label.setStyleSheet(f"color: {_GREEN}; font-size: 9pt;")
                self._load_history()
            else:
                self._status_label.setText("\u274c Failed to delete backup.")
                self._status_label.setStyleSheet(f"color: {_RED}; font-size: 9pt;")

    # ── Data loading ────────────────────────────────────────────

    def _load_history(self) -> None:
        entries = BackupService.get_backup_history()
        self._populate_history(entries)

    def _populate_history(self, entries: list[BackupEntry]) -> None:
        self._history_table.setRowCount(len(entries))
        for i, entry in enumerate(entries):
            self._history_table.setItem(i, 0, QTableWidgetItem(entry.filename))
            self._history_table.setItem(i, 1, QTableWidgetItem(entry.created_at))
            self._history_table.setItem(i, 2, QTableWidgetItem(entry.size_display))

            loc_item = QTableWidgetItem(str(Path(entry.filepath).parent))
            self._history_table.setItem(i, 3, loc_item)

            # Actions widget
            actions = QWidget()
            actions_layout = QHBoxLayout(actions)
            actions_layout.setContentsMargins(4, 2, 4, 2)
            actions_layout.setSpacing(4)

            open_btn = QPushButton("\U0001f4c2")
            open_btn.setFixedSize(28, 28)
            open_btn.setToolTip("Open folder")
            open_btn.setObjectName("ToolbarButton")
            open_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            open_btn.clicked.connect(
                lambda checked, p=str(Path(entry.filepath).parent): self._open_folder(p)
            )
            actions_layout.addWidget(open_btn)

            restore_btn = QPushButton("\U0001f504")
            restore_btn.setFixedSize(28, 28)
            restore_btn.setToolTip("Restore this backup")
            restore_btn.setObjectName("ToolbarButton")
            restore_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            restore_btn.clicked.connect(
                lambda checked, p=entry.filepath: self._restore_from_history(p)
            )
            actions_layout.addWidget(restore_btn)

            del_btn = QPushButton("\U0001f5d1")
            del_btn.setFixedSize(28, 28)
            del_btn.setToolTip("Delete backup")
            del_btn.setObjectName("ToolbarButton")
            del_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            del_btn.clicked.connect(
                lambda checked, p=entry.filepath: self._delete_from_history(p)
            )
            actions_layout.addWidget(del_btn)

            self._history_table.setCellWidget(i, 4, actions)

        if not entries:
            self._history_table.setRowCount(1)
            empty_item = QTableWidgetItem("No backups found")
            empty_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_item.setForeground(QColor(_SUBTEXT))
            self._history_table.setItem(0, 0, empty_item)
            self._history_table.setSpan(0, 0, 1, 5)

    def _load_settings_form(self) -> None:
        settings = SettingsService.get()
        self._settings_folder.setText(settings.backup_folder)
        self._auto_daily.setChecked(settings.auto_backup_daily == "Yes")
        self._auto_weekly.setChecked(settings.auto_backup_weekly == "Yes")
        self._max_backups.setValue(settings.max_backups)

    def _save_settings(self) -> None:
        settings = SettingsService.get()
        settings.backup_folder = self._settings_folder.text().strip() or "backups"
        settings.auto_backup_daily = "Yes" if self._auto_daily.isChecked() else "No"
        settings.auto_backup_weekly = "Yes" if self._auto_weekly.isChecked() else "No"
        settings.max_backups = self._max_backups.value()

        try:
            SettingsService.save(settings)
            self._status_label.setText("\u2705 Backup settings saved.")
            self._status_label.setStyleSheet(f"color: {_GREEN}; font-size: 9pt;")
        except Exception as e:
            logger.exception("Failed to save backup settings")
            self._status_label.setText(f"\u274c Failed to save: {e}")
            self._status_label.setStyleSheet(f"color: {_RED}; font-size: 9pt;")

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        QTimer.singleShot(0, self._load_history)
