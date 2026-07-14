from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy import select

from app.database.engine import new_session
from app.models.settings import Settings

logger = logging.getLogger(__name__)

# ── Default values ──────────────────────────────────────────────

DEFAULTS: dict[str, object] = {
    # Pharmacy Information
    "pharmacy_name": "My Pharmacy",
    "address": "",
    "phone": "",
    "email": "",
    "pan_number": "",
    "registration_number": "",
    # Billing
    "default_vat": 13.0,
    "receipt_width": "80mm",
    "currency_symbol": "Rs",
    "receipt_footer": "Thank you for your purchase!",
    "auto_print": "No",
    # Notifications
    "enable_expiry_warnings": "Yes",
    "enable_low_stock_warnings": "Yes",
    "expiry_warning_days": 30,
    # Appearance
    "default_theme": "dark",
    "font_size": "Medium",
    # Backup
    "backup_folder": "backups",
    "auto_backup_daily": "No",
    "auto_backup_weekly": "No",
    "max_backups": 10,
    # Barcode
    "barcode_prefix": "PHM",
    "scanner_suffix": "",
    "auto_add_after_scan": "Yes",
    "play_success_sound": "No",
    "play_error_sound": "No",
    "barcode_label_width": "50x30mm",
    "barcode_label_font_size": 8,
    # AI Settings (future)
    "groq_api_key": "",
    "groq_model": "llama3-8b-8192",
    "ocr_engine": "Tesseract",
}


@dataclass
class AppSettings:
    """In-memory settings cache. All fields match the Settings model columns."""

    pharmacy_name: str = "My Pharmacy"
    address: str = ""
    phone: str = ""
    email: str = ""
    pan_number: str = ""
    registration_number: str = ""

    default_vat: float = 13.0
    receipt_width: str = "80mm"
    currency_symbol: str = "Rs"
    receipt_footer: str = "Thank you for your purchase!"
    auto_print: str = "No"

    enable_expiry_warnings: str = "Yes"
    enable_low_stock_warnings: str = "Yes"
    expiry_warning_days: int = 30

    default_theme: str = "dark"
    font_size: str = "Medium"

    backup_folder: str = "backups"
    auto_backup_daily: str = "No"
    auto_backup_weekly: str = "No"
    max_backups: int = 10

    # Barcode
    barcode_prefix: str = "PHM"
    scanner_suffix: str = ""
    auto_add_after_scan: str = "Yes"
    play_success_sound: str = "No"
    play_error_sound: str = "No"
    barcode_label_width: str = "50x30mm"
    barcode_label_font_size: int = 8

    groq_api_key: str = ""
    groq_model: str = "llama3-8b-8192"
    ocr_engine: str = "Tesseract"


# ── Global cache ────────────────────────────────────────────────

_settings_cache: AppSettings | None = None


class SettingsService:
    """Load, save, and cache application settings from the database."""

    @staticmethod
    def load() -> AppSettings:
        """Load settings from DB into the global cache. Creates defaults if missing."""
        global _settings_cache
        session = new_session()
        try:
            stmt = select(Settings).limit(1)
            row = session.execute(stmt).scalar_one_or_none()
            if row is None:
                # Seed defaults
                row = Settings()
                for key, val in DEFAULTS.items():
                    setattr(row, key, val)
                session.add(row)
                session.commit()
                logger.info("Seeded default settings.")

            _settings_cache = AppSettings(
                pharmacy_name=row.pharmacy_name or "",
                address=row.address or "",
                phone=row.phone or "",
                email=row.email or "",
                pan_number=row.pan_number or "",
                registration_number=row.registration_number or "",
                default_vat=row.default_vat,
                receipt_width=row.receipt_width or "80mm",
                currency_symbol=row.currency_symbol or "Rs",
                receipt_footer=row.receipt_footer or "",
                auto_print=row.auto_print or "No",
                enable_expiry_warnings=row.enable_expiry_warnings or "Yes",
                enable_low_stock_warnings=row.enable_low_stock_warnings or "Yes",
                expiry_warning_days=row.expiry_warning_days,
                default_theme=row.default_theme or "dark",
                font_size=row.font_size or "Medium",
                backup_folder=row.backup_folder or "backups",
                auto_backup_daily=row.auto_backup_daily or "No",
                auto_backup_weekly=row.auto_backup_weekly or "No",
                max_backups=row.max_backups,
                groq_api_key=row.groq_api_key or "",
                groq_model=row.groq_model or "llama3-8b-8192",
                ocr_engine=row.ocr_engine or "Tesseract",
                barcode_prefix=row.barcode_prefix or "PHM",
                scanner_suffix=row.scanner_suffix or "",
                auto_add_after_scan=row.auto_add_after_scan or "Yes",
                play_success_sound=row.play_success_sound or "No",
                play_error_sound=row.play_error_sound or "No",
                barcode_label_width=row.barcode_label_width or "50x30mm",
                barcode_label_font_size=row.barcode_label_font_size or 8,
            )
            return _settings_cache
        finally:
            session.close()

    @staticmethod
    def get() -> AppSettings:
        """Return the cached settings, loading from DB if not yet loaded."""
        global _settings_cache
        if _settings_cache is None:
            return SettingsService.load()
        return _settings_cache

    @staticmethod
    def save(settings: AppSettings) -> None:
        """Persist the given settings to the database and update the cache."""
        global _settings_cache
        session = new_session()
        try:
            stmt = select(Settings).limit(1)
            row = session.execute(stmt).scalar_one_or_none()
            if row is None:
                row = Settings()
                session.add(row)

            row.pharmacy_name = settings.pharmacy_name
            row.address = settings.address
            row.phone = settings.phone
            row.email = settings.email
            row.pan_number = settings.pan_number
            row.registration_number = settings.registration_number
            row.default_vat = settings.default_vat
            row.receipt_width = settings.receipt_width
            row.currency_symbol = settings.currency_symbol
            row.receipt_footer = settings.receipt_footer
            row.auto_print = settings.auto_print
            row.enable_expiry_warnings = settings.enable_expiry_warnings
            row.enable_low_stock_warnings = settings.enable_low_stock_warnings
            row.expiry_warning_days = settings.expiry_warning_days
            row.default_theme = settings.default_theme
            row.font_size = settings.font_size
            row.backup_folder = settings.backup_folder
            row.auto_backup_daily = settings.auto_backup_daily
            row.auto_backup_weekly = settings.auto_backup_weekly
            row.max_backups = settings.max_backups
            row.groq_api_key = settings.groq_api_key
            row.groq_model = settings.groq_model
            row.ocr_engine = settings.ocr_engine
            row.barcode_prefix = settings.barcode_prefix
            row.scanner_suffix = settings.scanner_suffix
            row.auto_add_after_scan = settings.auto_add_after_scan
            row.play_success_sound = settings.play_success_sound
            row.play_error_sound = settings.play_error_sound
            row.barcode_label_width = settings.barcode_label_width
            row.barcode_label_font_size = settings.barcode_label_font_size

            session.commit()
            _settings_cache = settings
            logger.info("Settings saved successfully.")
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    @staticmethod
    def reset() -> AppSettings:
        """Reset all settings to defaults and save."""
        settings = AppSettings()
        SettingsService.save(settings)
        logger.info("Settings reset to defaults.")
        return settings
