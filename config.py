from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class AppConfig:
    """Immutable application configuration."""

    APP_NAME: str = "Pharmacy Management System"
    APP_VERSION: str = "1.0.0"
    APP_AUTHOR: str = "Kismat Adhikari"
    APP_COUNTRY: str = "Nepal"

    DATA_DIR: str = "data"
    DB_FILENAME: str = "pharmacy.db"
    BACKUP_DIR: str = "backups"
    LOG_DIR: str = "logs"

    WINDOW_DEFAULT_WIDTH: int = 1400
    WINDOW_DEFAULT_HEIGHT: int = 850
    WINDOW_MIN_WIDTH: int = 1200
    WINDOW_MIN_HEIGHT: int = 700

    CURRENT_USER: str = "Admin"

    BASE_DIR: Path = field(default_factory=lambda: Path(__file__).resolve().parent)

    @property
    def data_dir(self) -> Path:
        path = self.BASE_DIR / self.DATA_DIR
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def db_path(self) -> Path:
        return self.data_dir / self.DB_FILENAME

    @property
    def backup_path(self) -> Path:
        return self.BASE_DIR / self.BACKUP_DIR

    @property
    def log_path(self) -> Path:
        return self.BASE_DIR / self.LOG_DIR

    @property
    def styles_dir(self) -> Path:
        return self.BASE_DIR / "app" / "resources" / "styles"

    @property
    def icons_dir(self) -> Path:
        return self.BASE_DIR / "app" / "resources" / "icons"


config = AppConfig()
