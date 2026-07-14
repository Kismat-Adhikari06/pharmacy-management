from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import func

from app.database.engine import new_session
from app.models.batch import Batch
from app.models.medicine import Medicine
from app.models.purchase import Purchase
from app.models.purchase_item import PurchaseItem

logger = logging.getLogger(__name__)


@dataclass
class PurchaseItemData:
    """Data for a single purchase line item before saving."""

    medicine_id: int
    medicine_name: str
    batch_number: str
    expiry_date: date
    quantity: int
    purchase_price: float
    selling_price: float


@dataclass
class PurchaseResult:
    """Lightweight data transfer object for a purchase history row."""

    id: int
    invoice_number: str
    supplier_name: str
    purchase_date: str
    total_amount: float
    item_count: int


@dataclass
class PurchaseDetail:
    """Full purchase detail with items."""

    id: int
    invoice_number: str
    supplier_name: str
    supplier_id: int
    purchase_date: str
    total_amount: float
    notes: str
    items: list[PurchaseItemData] = field(default_factory=list)


class DuplicateInvoiceError(Exception):
    """Raised when an invoice number already exists for this supplier."""


class PurchaseValidationError(Exception):
    """Raised when purchase data fails validation."""


class PurchaseService:
    """Business logic for Purchase CRUD operations."""

    @staticmethod
    def _to_result(p: Purchase) -> PurchaseResult:
        return PurchaseResult(
            id=p.id,
            invoice_number=p.invoice_number,
            supplier_name=p.supplier.supplier_name if p.supplier else "",
            purchase_date=p.purchase_date.strftime("%Y-%m-%d"),
            total_amount=p.total_amount,
            item_count=len(p.items),
        )

    @staticmethod
    def get_all() -> list[PurchaseResult]:
        """Return every purchase, newest first."""
        session = new_session()
        try:
            purchases = (
                session.query(Purchase)
                .join(Purchase.supplier)
                .order_by(Purchase.purchase_date.desc(), Purchase.id.desc())
                .all()
            )
            return [PurchaseService._to_result(p) for p in purchases]
        finally:
            session.close()

    @staticmethod
    def search(query: str) -> list[PurchaseResult]:
        """Search purchases by invoice number."""
        session = new_session()
        try:
            term = f"%{query}%"
            purchases = (
                session.query(Purchase)
                .join(Purchase.supplier)
                .filter(Purchase.invoice_number.ilike(term))
                .order_by(Purchase.purchase_date.desc(), Purchase.id.desc())
                .all()
            )
            return [PurchaseService._to_result(p) for p in purchases]
        finally:
            session.close()

    @staticmethod
    def create_purchase(
        supplier_id: int,
        invoice_number: str,
        purchase_date: date,
        items: list[PurchaseItemData],
        notes: str = "",
    ) -> int:
        """Create a purchase with items and batches in a single transaction.

        Returns the purchase id on success.
        Raises on any validation error (rolls back everything).
        """
        if not items:
            raise PurchaseValidationError("At least one purchase item is required.")

        session = new_session()
        try:
            existing = (
                session.query(Purchase)
                .filter(
                    Purchase.supplier_id == supplier_id,
                    func.lower(Purchase.invoice_number) == invoice_number.lower(),
                )
                .first()
            )
            if existing is not None:
                raise DuplicateInvoiceError(
                    f"Invoice '{invoice_number}' already exists for this supplier."
                )

            total = sum(i.quantity * i.purchase_price for i in items)

            purchase = Purchase(
                supplier_id=supplier_id,
                invoice_number=invoice_number,
                purchase_date=purchase_date,
                total_amount=total,
                notes=notes or None,
            )
            session.add(purchase)
            session.flush()

            for item_data in items:
                batch = Batch(
                    medicine_id=item_data.medicine_id,
                    batch_number=item_data.batch_number,
                    expiry_date=item_data.expiry_date,
                    purchase_price=item_data.purchase_price,
                    selling_price=item_data.selling_price,
                    quantity=item_data.quantity,
                )
                session.add(batch)
                session.flush()

                pi = PurchaseItem(
                    purchase_id=purchase.id,
                    batch_id=batch.id,
                    quantity=item_data.quantity,
                    purchase_price=item_data.purchase_price,
                )
                session.add(pi)

            session.commit()
            logger.info(
                "Created purchase id=%d, invoice=%s, items=%d, total=%.2f",
                purchase.id, purchase.invoice_number, len(items), total,
            )
            return purchase.id
        except (DuplicateInvoiceError, PurchaseValidationError):
            session.rollback()
            raise
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    @staticmethod
    def get_detail(purchase_id: int) -> PurchaseDetail | None:
        """Return full purchase detail with items."""
        session = new_session()
        try:
            p = session.get(Purchase, purchase_id)
            if p is None:
                return None
            items = []
            for pi in p.items:
                batch = session.get(Batch, pi.batch_id)
                med_name = ""
                if batch:
                    med = session.get(Medicine, batch.medicine_id)
                    if med:
                        med_name = med.medicine_name
                items.append(
                    PurchaseItemData(
                        medicine_id=batch.medicine_id if batch else 0,
                        medicine_name=med_name,
                        batch_number=batch.batch_number if batch else "",
                        expiry_date=batch.expiry_date if batch else date.today(),
                        quantity=pi.quantity,
                        purchase_price=pi.purchase_price,
                        selling_price=batch.selling_price if batch else 0.0,
                    )
                )
            return PurchaseDetail(
                id=p.id,
                invoice_number=p.invoice_number,
                supplier_name=p.supplier.supplier_name if p.supplier else "",
                supplier_id=p.supplier_id,
                purchase_date=p.purchase_date.strftime("%Y-%m-%d"),
                total_amount=p.total_amount,
                notes=p.notes or "",
                items=items,
            )
        finally:
            session.close()
