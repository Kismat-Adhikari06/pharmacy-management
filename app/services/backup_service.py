from __future__ import annotations

import logging
import os
import shutil
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from config import config

logger = logging.getLogger(__name__)

_BACKUP_PREFIX = "Pharmacy_Backup_"
_BACKUP_EXT = ".zip"
_DB_NAME = "pharmacy.db"
_LOG_DIR_NAME = "logs"


@dataclass
class BackupEntry:
    """Metadata for a single backup file."""

    filename: str
    filepath: str
    size_bytes: int
    created_at: str  # human-readable
    size_display: str  # e.g. "2.4 MB"


class BackupService:
    """Create, restore, list, and delete pharmacy database backups."""

    # ── Backup creation ─────────────────────────────────────────

    @staticmethod
    def create_backup(
        dest_folder: str | Path | None = None,
        include_logs: bool = False,
    ) -> Path:
        """Create a ZIP backup of the database (and optionally logs).

        Returns the path to the created ZIP file.
        Raises FileNotFoundError if the database doesn't exist.
        Raises OSError on write failure.
        """
        db_path = config.db_path
        if not db_path.exists():
            raise FileNotFoundError(f"Database not found: {db_path}")

        if dest_folder is None:
            from app.services.settings_service import SettingsService

            settings = SettingsService.get()
            dest_folder = Path(settings.backup_folder)
            if not dest_folder.is_absolute():
                dest_folder = config.BASE_DIR / dest_folder
        else:
            dest_folder = Path(dest_folder)

        dest_folder.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
        zip_name = f"{_BACKUP_PREFIX}{timestamp}{_BACKUP_EXT}"
        zip_path = dest_folder / zip_name

        try:
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                # Always include the database
                zf.write(db_path, _DB_NAME)
                logger.info("Added %s to backup", db_path)

                # Optionally include logs
                if include_logs:
                    log_dir = config.log_path
                    if log_dir.exists():
                        for log_file in log_dir.rglob("*.log"):
                            arcname = f"{_LOG_DIR_NAME}/{log_file.relative_to(log_dir)}"
                            zf.write(log_file, arcname)
                            logger.info("Added %s to backup", log_file)

            logger.info("Backup created: %s", zip_path)
            return zip_path

        except Exception:
            # Clean up partial file on failure
            if zip_path.exists():
                zip_path.unlink()
            raise

    # ── Backup restoration ──────────────────────────────────────

    @staticmethod
    def validate_backup(zip_path: str | Path) -> tuple[bool, str]:
        """Validate that a ZIP file is a valid pharmacy backup.

        Returns (is_valid, message).
        """
        zip_path = Path(zip_path)
        if not zip_path.exists():
            return False, "File not found."

        if not zipfile.is_zipfile(zip_path):
            return False, "Not a valid ZIP file."

        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                names = zf.namelist()
                if _DB_NAME not in names:
                    return False, "Backup does not contain a database file."

                # Check the DB file is not empty
                info = zf.getinfo(_DB_NAME)
                if info.file_size == 0:
                    return False, "Database file in backup is empty."

                return True, "Backup is valid."
        except zipfile.BadZipFile:
            return False, "Corrupted ZIP file."

    @staticmethod
    def restore_backup(zip_path: str | Path) -> None:
        """Restore the database from a backup ZIP.

        The current database is backed up first as a safety net.
        Raises ValueError if validation fails.
        Raises OSError on file system errors.
        """
        zip_path = Path(zip_path)
        valid, msg = BackupService.validate_backup(zip_path)
        if not valid:
            raise ValueError(f"Invalid backup: {msg}")

        db_path = config.db_path

        # Safety backup of current DB before restore
        safety_dir = config.backup_path / "_pre_restore"
        safety_dir.mkdir(parents=True, exist_ok=True)
        safety_name = f"pharmacy_pre_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        safety_path = safety_dir / safety_name
        if db_path.exists():
            shutil.copy2(db_path, safety_path)
            logger.info("Safety backup created: %s", safety_path)

        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                # Extract DB to a temp location first
                temp_path = db_path.with_suffix(".db.restoring")
                with zf.open(_DB_NAME) as src, open(temp_path, "wb") as dst:
                    dst.write(src.read())

                # Atomic replace: delete old, rename new
                if db_path.exists():
                    db_path.unlink()
                temp_path.rename(db_path)

            logger.info("Database restored from: %s", zip_path)

        except Exception:
            # Attempt to restore safety backup
            if safety_path.exists() and not db_path.exists():
                shutil.copy2(safety_path, db_path)
                logger.info("Restored safety backup after failed restore.")
            raise

    # ── Backup history ──────────────────────────────────────────

    @staticmethod
    def get_backup_history(folder: str | Path | None = None) -> list[BackupEntry]:
        """List all backup ZIPs in the backup folder, newest first."""
        if folder is None:
            from app.services.settings_service import SettingsService

            settings = SettingsService.get()
            folder = Path(settings.backup_folder)
            if not folder.is_absolute():
                folder = config.BASE_DIR / folder
        else:
            folder = Path(folder)

        if not folder.exists():
            return []

        entries: list[BackupEntry] = []
        for f in sorted(folder.glob(f"{_BACKUP_PREFIX}*{_BACKUP_EXT}"), reverse=True):
            stat = f.stat()
            created = datetime.fromtimestamp(stat.st_mtime)
            entries.append(
                BackupEntry(
                    filename=f.name,
                    filepath=str(f),
                    size_bytes=stat.st_size,
                    created_at=created.strftime("%Y-%m-%d %H:%M:%S"),
                    size_display=BackupService._format_size(stat.st_size),
                )
            )
        return entries

    # ── Delete backup ───────────────────────────────────────────

    @staticmethod
    def delete_backup(zip_path: str | Path) -> bool:
        """Delete a backup file. Returns True if successful."""
        zip_path = Path(zip_path)
        try:
            if zip_path.exists():
                zip_path.unlink()
                logger.info("Deleted backup: %s", zip_path)
                return True
            return False
        except OSError:
            logger.exception("Failed to delete backup: %s", zip_path)
            return False

    # ── Auto-backup ─────────────────────────────────────────────

    @staticmethod
    def run_auto_backup() -> Path | None:
        """Check settings and run backup if conditions are met.

        Returns the backup path if a backup was created, None otherwise.
        """
        from app.services.settings_service import SettingsService

        settings = SettingsService.get()
        should_backup = False

        if settings.auto_backup_daily == "Yes":
            should_backup = BackupService._should_run_daily()

        if settings.auto_backup_weekly == "Yes":
            should_backup = should_backup or BackupService._should_run_weekly()

        if not should_backup:
            return None

        try:
            path = BackupService.create_backup()
            BackupService.cleanup_old_backups()
            return path
        except Exception:
            logger.exception("Auto-backup failed")
            return None

    @staticmethod
    def _should_run_daily() -> bool:
        """Check if a daily backup should run (once per day)."""
        marker = config.data_dir / ".last_daily_backup"
        if marker.exists():
            try:
                last_run = datetime.fromtimestamp(marker.stat().st_mtime)
                if last_run.date() == datetime.now().date():
                    return False
            except OSError:
                pass
        # Touch the marker
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.touch()
        return True

    @staticmethod
    def _should_run_weekly() -> bool:
        """Check if a weekly backup should run (once per week, on Monday)."""
        marker = config.data_dir / ".last_weekly_backup"
        if marker.exists():
            try:
                last_run = datetime.fromtimestamp(marker.stat().st_mtime)
                days_since = (datetime.now() - last_run).days
                if days_since < 7:
                    return False
            except OSError:
                pass
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.touch()
        return True

    # ── Cleanup ─────────────────────────────────────────────────

    @staticmethod
    def cleanup_old_backups(folder: str | Path | None = None) -> int:
        """Delete oldest backups exceeding max_backups limit. Returns count deleted."""
        from app.services.settings_service import SettingsService

        settings = SettingsService.get()
        max_bk = settings.max_backups

        entries = BackupService.get_backup_history(folder)
        if len(entries) <= max_bk:
            return 0

        # Delete oldest entries
        to_delete = entries[max_bk:]
        deleted = 0
        for entry in to_delete:
            if BackupService.delete_backup(entry.filepath):
                deleted += 1
        return deleted

    # ── Helpers ─────────────────────────────────────────────────

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """Format bytes into human-readable string."""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
