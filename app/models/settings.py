from __future__ import annotations

from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Settings(Base):
    """Application-wide pharmacy settings (single row)."""

    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # ── Section 1: Pharmacy Information ─────────────────────────
    pharmacy_name: Mapped[str] = mapped_column(String(200), nullable=False, default="My Pharmacy")
    address: Mapped[str | None] = mapped_column(String(500), default="")
    phone: Mapped[str | None] = mapped_column(String(20), default="")
    email: Mapped[str | None] = mapped_column(String(200), default="")
    pan_number: Mapped[str | None] = mapped_column(String(20), default="")
    registration_number: Mapped[str | None] = mapped_column(String(50), default="")

    # ── Section 2: Billing ──────────────────────────────────────
    default_vat: Mapped[float] = mapped_column(Float, default=13.0)
    receipt_width: Mapped[str] = mapped_column(String(10), default="80mm")
    currency_symbol: Mapped[str] = mapped_column(String(10), default="Rs")
    receipt_footer: Mapped[str] = mapped_column(String(500), default="Thank you for your purchase!")
    auto_print: Mapped[str] = mapped_column(String(3), default="No")

    # ── Section 3: Notifications ────────────────────────────────
    enable_expiry_warnings: Mapped[str] = mapped_column(String(3), default="Yes")
    enable_low_stock_warnings: Mapped[str] = mapped_column(String(3), default="Yes")
    expiry_warning_days: Mapped[int] = mapped_column(Integer, default=30)

    # ── Section 4: Appearance ───────────────────────────────────
    default_theme: Mapped[str] = mapped_column(String(20), default="dark")
    font_size: Mapped[str] = mapped_column(String(10), default="Medium")

    # ── Section 5: Backup ───────────────────────────────────────
    backup_folder: Mapped[str] = mapped_column(String(500), default="backups")
    auto_backup_daily: Mapped[str] = mapped_column(String(3), default="No")
    auto_backup_weekly: Mapped[str] = mapped_column(String(3), default="No")
    max_backups: Mapped[int] = mapped_column(Integer, default=10)

    # ── Section 6: Barcode ───────────────────────────────────────
    barcode_prefix: Mapped[str] = mapped_column(String(10), default="PHM")
    scanner_suffix: Mapped[str] = mapped_column(String(10), default="")
    auto_add_after_scan: Mapped[str] = mapped_column(String(3), default="Yes")
    play_success_sound: Mapped[str] = mapped_column(String(3), default="No")
    play_error_sound: Mapped[str] = mapped_column(String(3), default="No")
    barcode_label_width: Mapped[str] = mapped_column(String(20), default="50x30mm")
    barcode_label_font_size: Mapped[int] = mapped_column(Integer, default=8)

    # ── Section 7: AI Settings (future) ─────────────────────────
    groq_api_key: Mapped[str] = mapped_column(String(500), default="")
    groq_model: Mapped[str] = mapped_column(String(100), default="llama3-8b-8192")
    ocr_engine: Mapped[str] = mapped_column(String(50), default="Tesseract")

    def __repr__(self) -> str:
        return f"<Settings(id={self.id}, pharmacy={self.pharmacy_name!r})>"
