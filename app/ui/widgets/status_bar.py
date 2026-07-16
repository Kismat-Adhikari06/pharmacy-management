from __future__ import annotations

from PySide6.QtWidgets import QLabel, QStatusBar

from config import config
from app.ui.theme import Theme


class AppStatusBar(QStatusBar):
    """Bottom status bar showing ready state, DB status, and version."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("AppStatusBar")
        self.setFixedHeight(28)
        self._build_ui()

    def _build_ui(self) -> None:
        Theme.refresh()
        self.showMessage("Ready")

        connected = self._check_db()
        if connected:
            db_text = "Database: Connected"
            db_color = "#22c55e"
        else:
            db_text = "Database: Not Connected"
            db_color = "#ef4444"

        self._db_label = QLabel(db_text)
        self._db_label.setStyleSheet(f"color: {db_color}; padding-right: 4px;")
        self.addPermanentWidget(self._db_label)

        version_label = QLabel(f"Version {config.APP_VERSION}")
        version_label.setStyleSheet(f"color: {Theme.text2()}; padding-right: 4px;")
        self.addPermanentWidget(version_label)

    @staticmethod
    def _check_db() -> bool:
        try:
            from app.database.engine import get_engine
            engine = get_engine()
            with engine.connect() as conn:
                conn.execute(
                    __import__("sqlalchemy").text("SELECT 1")
                )
            return True
        except Exception:
            return False
