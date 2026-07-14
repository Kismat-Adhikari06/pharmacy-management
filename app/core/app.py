from __future__ import annotations

import logging
import sys

from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QMessageBox

from config import config
from app.database.manager import DatabaseManager
from app.ui.windows.main_window import MainWindow

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# Font size map
_FONT_SIZES = {"Small": 9, "Medium": 10, "Large": 12}


class Application:
    """Top-level application bootstrapper."""

    def __init__(self) -> None:
        self._app = QApplication(list())
        self._app.setApplicationName(config.APP_NAME)
        self._app.setApplicationVersion(config.APP_VERSION)
        self._app.setOrganizationName(config.APP_AUTHOR)

        self._init_database()
        self._load_settings()
        self._setup_font()
        self._load_stylesheet()
        self._window: MainWindow | None = None

    @staticmethod
    def _init_database() -> None:
        """Create the SQLite database and tables, then seed defaults."""
        try:
            DatabaseManager.init_db()
            logger.info("Database initialised at %s", config.db_path)
        except Exception:
            logger.exception("Failed to initialise the database")
            raise

    def _load_settings(self) -> None:
        """Load persisted settings from the database."""
        try:
            from app.services.settings_service import SettingsService
            self._settings = SettingsService.load()
            logger.info("Settings loaded: theme=%s, font=%s", self._settings.default_theme, self._settings.font_size)
        except Exception:
            logger.exception("Failed to load settings, using defaults")
            from app.services.settings_service import AppSettings
            self._settings = AppSettings()

    def _setup_font(self) -> None:
        size = _FONT_SIZES.get(self._settings.font_size, 10)
        font = QFont("Segoe UI", size)
        font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
        self._app.setFont(font)

    def _load_stylesheet(self) -> None:
        theme = self._settings.default_theme
        if theme == "light":
            qss_name = "light.qss"
        else:
            qss_name = "dark.qss"

        qss_path = config.styles_dir / qss_name
        if qss_path.exists():
            qss = qss_path.read_text(encoding="utf-8")
            self._app.setStyleSheet(qss)
        else:
            # Fallback to dark if light theme file doesn't exist yet
            qss_path = config.styles_dir / "dark.qss"
            if qss_path.exists():
                qss = qss_path.read_text(encoding="utf-8")
                self._app.setStyleSheet(qss)

    def run(self) -> int:
        """Show the main window and enter the event loop."""
        self._window = MainWindow()
        self._window.show()
        QTimer.singleShot(100, self._run_auto_backup)
        QTimer.singleShot(300, self._show_startup_warnings)
        return self._app.exec()

    def _run_auto_backup(self) -> None:
        """Run automatic backup if enabled in settings."""
        try:
            from app.services.backup_service import BackupService

            path = BackupService.run_auto_backup()
            if path:
                logger.info("Auto-backup created: %s", path)
        except Exception:
            logger.exception("Auto-backup failed during startup")

    def _show_startup_warnings(self) -> None:
        """Scan DB on launch and show warning dialogs for critical items."""
        # Respect notification settings
        if self._settings.enable_expiry_warnings != "Yes" and self._settings.enable_low_stock_warnings != "Yes":
            return

        try:
            from app.services.expiry_service import ExpiryService

            warnings = ExpiryService.get_startup_warnings()
        except Exception:
            logger.exception("Failed to check startup warnings")
            return

        has_any = any(len(v) > 0 for v in warnings.values())
        if not has_any:
            return

        parts: list[str] = []

        if warnings["expired"] and self._settings.enable_expiry_warnings == "Yes":
            count = len(warnings["expired"])
            items = "\n".join(warnings["expired"][:10])
            more = f"\n... and {count - 10} more" if count > 10 else ""
            parts.append(f"🔴 EXPIRED ({count} items):\n{items}{more}")

        if warnings["expiring_30"] and self._settings.enable_expiry_warnings == "Yes":
            count = len(warnings["expiring_30"])
            items = "\n".join(warnings["expiring_30"][:10])
            more = f"\n... and {count - 10} more" if count > 10 else ""
            parts.append(f"🟠 EXPIRING WITHIN {self._settings.expiry_warning_days} DAYS ({count} items):\n{items}{more}")

        if warnings["low_stock"] and self._settings.enable_low_stock_warnings == "Yes":
            count = len(warnings["low_stock"])
            items = "\n".join(warnings["low_stock"][:10])
            more = f"\n... and {count - 10} more" if count > 10 else ""
            parts.append(f"📉 LOW STOCK ({count} items):\n{items}{more}")

        if not parts:
            return

        message = "\n\n".join(parts)

        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle("Startup Alerts")
        msg.setText("The following items require your attention:")
        msg.setDetailedText(message)
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()
