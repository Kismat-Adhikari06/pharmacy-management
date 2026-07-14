from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app.database.engine import new_session
from app.models.batch import Batch
from app.models.medicine import Medicine
from app.models.sale_item import SaleItem

logger = logging.getLogger(__name__)

_EXPIRY_WARNING_DAYS = 90


@dataclass
class BatchResult:
    """Lightweight data transfer object for a batch row."""

    id: int
    batch_number: str
    expiry_date: str
    purchase_price: float
    selling_price: float
    quantity: int
    status: str


class DuplicateBatchError(Exception):
    """Raised when a batch with the same number already exists for this medicine."""


class BatchNotFoundError(Exception):
    """Raised when a batch with the given id does not exist."""


class BatchInUseError(Exception):
    """Raised when a batch cannot be deleted because it has been used in sales."""


class BatchService:
    """Business logic for Batch CRUD operations."""

    @staticmethod
    def expiry_status(expiry_date: date) -> str:
        """Return a human-readable expiry status label."""
        today = date.today()
        if expiry_date < today:
            return "Expired"
        if expiry_date <= today + timedelta(days=_EXPIRY_WARNING_DAYS):
            return "Expiring Soon"
        return "Good"

    @staticmethod
    def _to_result(batch: Batch) -> BatchResult:
        return BatchResult(
            id=batch.id,
            batch_number=batch.batch_number,
            expiry_date=batch.expiry_date.strftime("%Y-%m-%d"),
            purchase_price=batch.purchase_price,
            selling_price=batch.selling_price,
            quantity=batch.quantity,
            status=BatchService.expiry_status(batch.expiry_date),
        )

    @staticmethod
    def get_for_medicine(medicine_id: int) -> list[BatchResult]:
        """Return all batches for a medicine, sorted by expiry date (earliest first)."""
        session = new_session()
        try:
            batches = (
                session.query(Batch)
                .filter(Batch.medicine_id == medicine_id)
                .order_by(Batch.expiry_date.asc())
                .all()
            )
            return [BatchService._to_result(b) for b in batches]
        finally:
            session.close()

    @staticmethod
    def get_stock(medicine_id: int) -> int:
        """Return the total stock (sum of all batch quantities) for a medicine."""
        session = new_session()
        try:
            total = (
                session.query(func.coalesce(func.sum(Batch.quantity), 0))
                .filter(Batch.medicine_id == medicine_id)
                .scalar()
            )
            return int(total)
        finally:
            session.close()

    @staticmethod
    def create(
        medicine_id: int,
        batch_number: str,
        expiry_date: date,
        purchase_price: float,
        selling_price: float,
        quantity: int,
    ) -> BatchResult:
        """Create a new batch. Raises errors on duplicate number or invalid data."""
        session = new_session()
        try:
            existing = (
                session.query(Batch)
                .filter(
                    Batch.medicine_id == medicine_id,
                    func.lower(Batch.batch_number) == batch_number.lower(),
                )
                .first()
            )
            if existing is not None:
                raise DuplicateBatchError(
                    f"Batch '{batch_number}' already exists for this medicine."
                )

            batch = Batch(
                medicine_id=medicine_id,
                batch_number=batch_number,
                expiry_date=expiry_date,
                purchase_price=purchase_price,
                selling_price=selling_price,
                quantity=quantity,
            )
            session.add(batch)
            session.commit()
            session.refresh(batch)
            logger.info("Created batch %s for medicine %d", batch_number, medicine_id)
            return BatchService._to_result(batch)
        except DuplicateBatchError:
            session.rollback()
            raise
        except IntegrityError:
            session.rollback()
            raise DuplicateBatchError(
                f"Batch '{batch_number}' already exists for this medicine."
            )
        finally:
            session.close()

    @staticmethod
    def update(
        batch_id: int,
        batch_number: str,
        expiry_date: date,
        purchase_price: float,
        selling_price: float,
        quantity: int,
    ) -> BatchResult:
        """Update an existing batch."""
        session = new_session()
        try:
            batch = session.get(Batch, batch_id)
            if batch is None:
                raise BatchNotFoundError(f"Batch with id {batch_id} not found.")

            dup = (
                session.query(Batch)
                .filter(
                    Batch.medicine_id == batch.medicine_id,
                    func.lower(Batch.batch_number) == batch_number.lower(),
                    Batch.id != batch_id,
                )
                .first()
            )
            if dup is not None:
                raise DuplicateBatchError(
                    f"Another batch '{batch_number}' exists for this medicine."
                )

            batch.batch_number = batch_number
            batch.expiry_date = expiry_date
            batch.purchase_price = purchase_price
            batch.selling_price = selling_price
            batch.quantity = quantity

            session.commit()
            session.refresh(batch)
            logger.info("Updated batch id=%d: %s", batch.id, batch.batch_number)
            return BatchService._to_result(batch)
        except (BatchNotFoundError, DuplicateBatchError):
            session.rollback()
            raise
        except IntegrityError:
            session.rollback()
            raise DuplicateBatchError(
                f"Another batch '{batch_number}' exists for this medicine."
            )
        finally:
            session.close()

    @staticmethod
    def delete(batch_id: int) -> None:
        """Delete a batch. Raises BatchInUseError if used in sales."""
        session = new_session()
        try:
            batch = session.get(Batch, batch_id)
            if batch is None:
                raise BatchNotFoundError(f"Batch with id {batch_id} not found.")

            sale_count = (
                session.query(func.count(SaleItem.id))
                .filter(SaleItem.batch_id == batch_id)
                .scalar()
            )
            if sale_count and sale_count > 0:
                raise BatchInUseError(
                    f"Cannot delete batch '{batch.batch_number}' — "
                    f"it has been used in {sale_count} sale(s)."
                )

            number = batch.batch_number
            session.delete(batch)
            session.commit()
            logger.info("Deleted batch: %s", number)
        except (BatchNotFoundError, BatchInUseError):
            session.rollback()
            raise
        finally:
            session.close()
