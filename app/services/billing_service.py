from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime

from sqlalchemy import func

from app.database.engine import new_session
from app.models.batch import Batch
from app.models.medicine import Medicine
from app.models.sale import Sale
from app.models.sale_item import SaleItem

logger = logging.getLogger(__name__)


@dataclass
class BillItem:
    """A single line item in the current bill (before saving)."""

    medicine_id: int
    medicine_name: str
    batch_id: int
    batch_number: str
    expiry_date: str
    quantity: int
    unit_price: float
    discount: float = 0.0

    @property
    def line_total(self) -> float:
        return self.quantity * self.unit_price - self.discount


@dataclass
class MedicineSearchResult:
    """Lightweight result for medicine search in POS."""

    medicine_id: int
    medicine_name: str
    generic_name: str
    company: str
    total_stock: int
    selling_price: float
    earliest_expiry: str


@dataclass
class SaleResult:
    """Result after saving a sale."""

    sale_id: int
    bill_number: str
    total_amount: float


class InsufficientStockError(Exception):
    """Raised when trying to sell more than available stock."""


class ExpiredMedicineError(Exception):
    """Raised when trying to sell expired medicine."""


class NoStockError(Exception):
    """No batches with available stock for this medicine."""


class SaleValidationError(Exception):
    """Raised when sale data fails validation."""


class BillingService:
    """Business logic for POS billing operations."""

    @staticmethod
    def search_medicines(query: str) -> list[MedicineSearchResult]:
        """Search medicines with available stock for POS display."""
        session = new_session()
        try:
            today = date.today()
            term = f"%{query}%"
            medicines = (
                session.query(Medicine)
                .join(Batch, Batch.medicine_id == Medicine.id)
                .filter(
                    Batch.quantity > 0,
                    Batch.expiry_date >= today,
                    (
                        Medicine.medicine_name.ilike(term)
                        | Medicine.generic_name.ilike(term)
                        | Medicine.company.ilike(term)
                        | Medicine.barcode.ilike(term)
                    ),
                )
                .distinct()
                .order_by(Medicine.medicine_name.asc())
                .all()
            )

            results = []
            for med in medicines:
                active_batches = [
                    b for b in med.batches
                    if b.quantity > 0 and b.expiry_date >= today
                ]
                if not active_batches:
                    continue
                total_stock = sum(b.quantity for b in active_batches)
                earliest = min(b.expiry_date for b in active_batches)
                prices = [b.selling_price for b in active_batches]
                avg_price = sum(prices) / len(prices) if prices else 0.0
                results.append(
                    MedicineSearchResult(
                        medicine_id=med.id,
                        medicine_name=med.medicine_name,
                        generic_name=med.generic_name or "",
                        company=med.company or "",
                        total_stock=total_stock,
                        selling_price=avg_price,
                        earliest_expiry=earliest.strftime("%Y-%m-%d"),
                    )
                )
            return results
        finally:
            session.close()

    @staticmethod
    def get_fefo_batches(medicine_id: int) -> list[tuple[int, str, date, float, int]]:
        """Return batches for a medicine in FEFO order (earliest expiry first).

        Returns list of (batch_id, batch_number, expiry_date, selling_price, quantity).
        Only non-expired batches with stock > 0.
        """
        session = new_session()
        try:
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
            return [
                (b.id, b.batch_number, b.expiry_date, b.selling_price, b.quantity)
                for b in batches
            ]
        finally:
            session.close()

    @staticmethod
    def create_sale(
        bill_items: list[BillItem],
        payment_method: str,
        discount: float = 0.0,
        vat_rate: float = 0.0,
    ) -> SaleResult:
        """Create a sale with items and reduce batch quantities in one transaction.

        Returns SaleResult with the new sale's info.
        """
        if not bill_items:
            raise SaleValidationError("Cannot save an empty bill.")

        session = new_session()
        try:
            bill_number = BillingService._next_bill_number(session)

            subtotal = sum(item.line_total for item in bill_items)
            vat_amount = subtotal * vat_rate / 100.0
            grand_total = subtotal - discount + vat_amount

            sale = Sale(
                bill_number=bill_number,
                total_amount=grand_total,
                discount=discount,
                vat_amount=vat_amount,
                payment_method=payment_method,
            )
            session.add(sale)
            session.flush()

            for item in bill_items:
                batch = session.get(Batch, item.batch_id)
                if batch is None:
                    raise InsufficientStockError(
                        f"Batch {item.batch_number} not found."
                    )
                if batch.quantity < item.quantity:
                    raise InsufficientStockError(
                        f"Insufficient stock for {item.medicine_name} "
                        f"(batch {item.batch_number}): "
                        f"need {item.quantity}, have {batch.quantity}."
                    )

                batch.quantity -= item.quantity

                sale_item = SaleItem(
                    sale_id=sale.id,
                    batch_id=batch.id,
                    quantity=item.quantity,
                    selling_price=item.unit_price,
                    discount=item.discount,
                )
                session.add(sale_item)

            session.commit()
            logger.info(
                "Sale completed: bill=%s total=%.2f payment=%s items=%d",
                bill_number, grand_total, payment_method, len(bill_items),
            )
            return SaleResult(
                sale_id=sale.id,
                bill_number=bill_number,
                total_amount=grand_total,
            )
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    @staticmethod
    def _next_bill_number(session) -> str:
        """Generate the next sequential bill number."""
        today = date.today()
        prefix = f"BILL-{today.strftime('%Y%m%d')}-"
        last = (
            session.query(Sale.bill_number)
            .filter(Sale.bill_number.like(f"{prefix}%"))
            .order_by(Sale.bill_number.desc())
            .first()
        )
        if last is None:
            return f"{prefix}0001"
        try:
            num = int(last[0].split("-")[-1]) + 1
        except (ValueError, IndexError):
            num = 1
        return f"{prefix}{num:04d}"
