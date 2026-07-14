from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QStatusBar, QWidget

from config import config


class AppStatusBar(QStatusBar):
    """Bottom status bar showing ready state, DB status, and version."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("AppStatusBar")
        self.setFixedHeight(28)
        self._build_ui()

    def _build_ui(self) -> None:
        self.showMessage("Ready")

        self._db_label = QLabel("Database: Not Connected")
        self._db_label.setStyleSheet("color: #a6adc8; padding-right: 4px;")
        self.addPermanentWidget(self._db_label)

        version_label = QLabel(f"Version {config.APP_VERSION}")
        version_label.setStyleSheet("color: #a6adc8; padding-right: 4px;")
        self.addPermanentWidget(version_label)
