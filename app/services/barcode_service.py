from __future__ import annotations

import logging
import random
import re
import string
from dataclasses import dataclass
from typing import NamedTuple

from sqlalchemy import func

from app.database.engine import new_session
from app.models.medicine import Medicine

logger = logging.getLogger(__name__)


class BarcodeScanResult(NamedTuple):
    """Result of parsing a raw scanner input."""
    is_barcode: bool
    raw: str
    cleaned: str


@dataclass
class LabelData:
    """Data needed to print a single barcode label."""
    medicine_name: str
    generic_name: str
    company: str
    barcode: str
    selling_price: float
    batch_number: str
    expiry_date: str
    mrp: float


class DuplicateBarcodeError(Exception):
    """Raised when a barcode is already assigned to another medicine."""


class InvalidBarcodeError(Exception):
    """Raised when a barcode value fails validation."""


class BarcodeNotFoundError(Exception):
    """Raised when a barcode lookup finds no medicine."""


class BarcodeService:
    """Barcode generation, validation, detection, and label data."""

    # ── Generation ──────────────────────────────────────────────

    @staticmethod
    def generate(prefix: str = "") -> str:
        """Generate a unique barcode string.

        Uses a prefix (from settings) + 12 random digits for a 13-char
        barcode that is EAN-13-like in length. If prefix is empty, uses
        a pharmacy-specific 3-char prefix 'PHM'.
        """
        pfx = prefix.strip() or "PHM"
        digits_needed = max(1, 13 - len(pfx))
        body = "".join(random.choices(string.digits, k=digits_needed))
        barcode = pfx + body
        return barcode

    @staticmethod
    def generate_unique(prefix: str = "") -> str:
        """Generate a barcode that is guaranteed unique in the database."""
        session = new_session()
        try:
            for _ in range(50):
                candidate = BarcodeService.generate(prefix)
                exists = (
                    session.query(Medicine)
                    .filter(Medicine.barcode == candidate)
                    .first()
                )
                if exists is None:
                    return candidate
            raise DuplicateBarcodeError(
                "Could not generate a unique barcode after 50 attempts."
            )
        finally:
            session.close()

    # ── Validation ──────────────────────────────────────────────

    @staticmethod
    def validate(barcode: str) -> bool:
        """Check that a barcode string is well-formed (alphanumeric, 4-50 chars)."""
        if not barcode or not barcode.strip():
            return False
        cleaned = barcode.strip()
        if len(cleaned) < 4 or len(cleaned) > 50:
            return False
        return bool(re.fullmatch(r"[A-Za-z0-9\-]+", cleaned))

    @staticmethod
    def is_unique(barcode: str, exclude_medicine_id: int | None = None) -> bool:
        """Check that the barcode is not already used by another medicine."""
        if not barcode or not barcode.strip():
            return True
        session = new_session()
        try:
            q = session.query(Medicine).filter(Medicine.barcode == barcode.strip())
            if exclude_medicine_id is not None:
                q = q.filter(Medicine.id != exclude_medicine_id)
            return q.first() is None
        finally:
            session.close()

    @staticmethod
    def check_duplicate(barcode: str, exclude_medicine_id: int | None = None) -> str | None:
        """Return the name of the medicine that owns this barcode, or None if unique."""
        if not barcode or not barcode.strip():
            return None
        session = new_session()
        try:
            q = session.query(Medicine).filter(Medicine.barcode == barcode.strip())
            if exclude_medicine_id is not None:
                q = q.filter(Medicine.id != exclude_medicine_id)
            med = q.first()
            return med.medicine_name if med else None
        finally:
            session.close()

    # ── Scanner input detection ─────────────────────────────────

    @staticmethod
    def detect_scan(raw_input: str, prefix: str = "", suffix: str = "") -> BarcodeScanResult:
        """Determine if a text input is from a barcode scanner.

        Heuristics:
        1. If prefix/suffix are configured, strip them and treat as barcode.
        2. If the input is purely numeric and >= 8 chars, treat as barcode.
        3. Otherwise treat as a text search query.
        """
        if not raw_input or not raw_input.strip():
            return BarcodeScanResult(is_barcode=False, raw=raw_input, cleaned="")

        cleaned = raw_input.strip()

        # Strip configured prefix/suffix
        if prefix and cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):]
        if suffix and cleaned.endswith(suffix):
            cleaned = cleaned[:-len(suffix)]
        cleaned = cleaned.strip()

        # Pure numeric and long enough → barcode
        if cleaned.isdigit() and len(cleaned) >= 8:
            return BarcodeScanResult(is_barcode=True, raw=raw_input, cleaned=cleaned)

        # Contains non-digits and is short → text search
        if not cleaned.isdigit():
            return BarcodeScanResult(is_barcode=False, raw=raw_input, cleaned=cleaned)

        return BarcodeScanResult(is_barcode=False, raw=raw_input, cleaned=cleaned)

    # ── Lookup ──────────────────────────────────────────────────

    @staticmethod
    def find_by_barcode(barcode: str) -> Medicine | None:
        """Look up a medicine by exact barcode match. Returns ORM object or None."""
        if not barcode or not barcode.strip():
            return None
        session = new_session()
        try:
            return (
                session.query(Medicine)
                .filter(Medicine.barcode == barcode.strip())
                .first()
            )
        finally:
            session.close()

    # ── Label data ──────────────────────────────────────────────

    @staticmethod
    def get_label_data(medicine_id: int) -> LabelData | None:
        """Fetch label data for a given medicine (uses earliest-expiry batch)."""
        from app.models.batch import Batch

        session = new_session()
        try:
            from datetime import date

            med = session.get(Medicine, medicine_id)
            if med is None:
                return None

            today = date.today()
            batches = (
                session.query(Batch)
                .filter(
                    Batch.medicine_id == medicine_id,
                    Batch.quantity > 0,
                    Batch.expiry_date >= today,
                )
                .order_by(Batch.expiry_date.asc())
                .all()
            )

            if batches:
                batch = batches[0]
                return LabelData(
                    medicine_name=med.medicine_name,
                    generic_name=med.generic_name or "",
                    company=med.company or "",
                    barcode=med.barcode or "",
                    selling_price=batch.selling_price,
                    batch_number=batch.batch_number,
                    expiry_date=batch.expiry_date.strftime("%Y-%m-%d"),
                    mrp=batch.selling_price,
                )

            return LabelData(
                medicine_name=med.medicine_name,
                generic_name=med.generic_name or "",
                company=med.company or "",
                barcode=med.barcode or "",
                selling_price=0.0,
                batch_number="",
                expiry_date="",
                mrp=0.0,
            )
        finally:
            session.close()

    @staticmethod
    def get_label_data_batch(batch_id: int) -> LabelData | None:
        """Fetch label data for a specific batch."""
        from app.models.batch import Batch

        session = new_session()
        try:
            batch = session.get(Batch, batch_id)
            if batch is None:
                return None

            med = session.get(Medicine, batch.medicine_id)
            if med is None:
                return None

            return LabelData(
                medicine_name=med.medicine_name,
                generic_name=med.generic_name or "",
                company=med.company or "",
                barcode=med.barcode or "",
                selling_price=batch.selling_price,
                batch_number=batch.batch_number,
                expiry_date=batch.expiry_date.strftime("%Y-%m-%d"),
                mrp=batch.selling_price,
            )
        finally:
            session.close()
