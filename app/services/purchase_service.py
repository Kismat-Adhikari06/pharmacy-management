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
from app.models.supplier import Supplier

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

    @staticmethod
    def create_from_invoice(
        items: list[dict],
        supplier_name: str = "",
        invoice_number: str = "",
    ) -> str:
        """Create medicines, batches, and a purchase record from AI-imported invoice items.

        Each item dict should have: medicine_name, generic_name, company,
        batch_number, expiry_date, quantity, purchase_price, selling_price.

        Returns a summary string on success.
        """
        from datetime import date as _date

        session = new_session()
        try:
            supplier_id = None
            if supplier_name:
                existing = (
                    session.query(Supplier)
                    .filter(
                        func.lower(Supplier.supplier_name) == supplier_name.lower()
                    )
                    .first()
                )
                if existing:
                    supplier_id = existing.id
                else:
                    sup = Supplier(supplier_name=supplier_name)
                    session.add(sup)
                    session.flush()
                    supplier_id = sup.id

            created_meds = 0
            created_batches = 0

            for item in items:
                med_name = item.get("medicine_name", "").strip()
                if not med_name:
                    continue

                med = (
                    session.query(Medicine)
                    .filter(func.lower(Medicine.medicine_name) == med_name.lower())
                    .first()
                )
                if not med:
                    med = Medicine(
                        medicine_name=med_name,
                        generic_name=item.get("generic_name", ""),
                        company=item.get("company", ""),
                    )
                    session.add(med)
                    session.flush()
                    created_meds += 1

                batch_number = item.get("batch_number", "").strip()
                if not batch_number:
                    continue

                existing_batch = (
                    session.query(Batch)
                    .filter(
                        Batch.medicine_id == med.id,
                        func.lower(Batch.batch_number) == batch_number.lower(),
                    )
                    .first()
                )
                if existing_batch:
                    existing_batch.quantity += item.get("quantity", 0)
                    continue

                expiry_str = item.get("expiry_date", "")
                try:
                    expiry = _date.fromisoformat(expiry_str)
                except (ValueError, TypeError):
                    expiry = _date.today()

                batch = Batch(
                    medicine_id=med.id,
                    batch_number=batch_number,
                    expiry_date=expiry,
                    purchase_price=item.get("purchase_price", 0.0),
                    selling_price=item.get("selling_price", 0.0),
                    quantity=item.get("quantity", 0),
                )
                session.add(batch)
                session.flush()
                created_batches += 1

            total = sum(
                i.get("quantity", 0) * i.get("purchase_price", 0.0) for i in items
            )

            purchase = Purchase(
                supplier_id=supplier_id,
                invoice_number=invoice_number or "AI-IMPORT",
                purchase_date=_date.today(),
                total_amount=total,
                notes="Imported via AI Invoice Import",
            )
            session.add(purchase)
            session.flush()

            for item in items:
                med_name = item.get("medicine_name", "").strip()
                batch_number = item.get("batch_number", "").strip()
                if not med_name or not batch_number:
                    continue
                med = (
                    session.query(Medicine)
                    .filter(func.lower(Medicine.medicine_name) == med_name.lower())
                    .first()
                )
                if not med:
                    continue
                batch = (
                    session.query(Batch)
                    .filter(
                        Batch.medicine_id == med.id,
                        func.lower(Batch.batch_number) == batch_number.lower(),
                    )
                    .first()
                )
                if not batch:
                    continue
                pi = PurchaseItem(
                    purchase_id=purchase.id,
                    batch_id=batch.id,
                    quantity=item.get("quantity", 0),
                    purchase_price=item.get("purchase_price", 0.0),
                )
                session.add(pi)

            session.commit()
            return (
                f"Import complete: {created_meds} new medicines, "
                f"{created_batches} new batches created."
            )
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
