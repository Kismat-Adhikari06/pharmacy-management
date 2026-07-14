from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from app.database.engine import new_session
from app.models.batch import Batch
from app.models.medicine import Medicine

logger = logging.getLogger(__name__)


@dataclass
class MedicineResult:
    """Lightweight data transfer object for a medicine row."""

    id: int
    medicine_name: str
    generic_name: str
    company: str
    category: str
    barcode: str
    rack_location: str
    minimum_stock: int
    total_stock: int
    created_at: str
    updated_at: str


class DuplicateMedicineError(Exception):
    """Raised when a medicine with the same name already exists."""


class MedicineNotFoundError(Exception):
    """Raised when a medicine with the given id does not exist."""


class MedicineInUseError(Exception):
    """Raised when a medicine cannot be deleted because it has batches."""


class InventoryService:
    """Business logic for Medicine CRUD operations."""

    @staticmethod
    def _to_result(med: Medicine) -> MedicineResult:
        total_stock = sum(b.quantity for b in med.batches)
        return MedicineResult(
            id=med.id,
            medicine_name=med.medicine_name,
            generic_name=med.generic_name or "",
            company=med.company or "",
            category=med.category or "",
            barcode=med.barcode or "",
            rack_location=med.rack_location or "",
            minimum_stock=med.minimum_stock,
            total_stock=total_stock,
            created_at=med.created_at.strftime("%Y-%m-%d") if med.created_at else "",
            updated_at=med.updated_at.strftime("%Y-%m-%d") if med.updated_at else "",
        )

    @staticmethod
    def get_all() -> list[MedicineResult]:
        """Return every medicine, ordered by name."""
        session = new_session()
        try:
            medicines = (
                session.query(Medicine)
                .options(joinedload(Medicine.batches))
                .order_by(Medicine.medicine_name.asc())
                .all()
            )
            return [InventoryService._to_result(m) for m in medicines]
        finally:
            session.close()

    @staticmethod
    def search(query: str) -> list[MedicineResult]:
        """Search medicines across name, generic, company, category, barcode."""
        session = new_session()
        try:
            term = f"%{query}%"
            medicines = (
                session.query(Medicine)
                .options(joinedload(Medicine.batches))
                .filter(
                    or_(
                        Medicine.medicine_name.ilike(term),
                        Medicine.generic_name.ilike(term),
                        Medicine.company.ilike(term),
                        Medicine.category.ilike(term),
                        Medicine.barcode.ilike(term),
                    )
                )
                .order_by(Medicine.medicine_name.asc())
                .all()
            )
            return [InventoryService._to_result(m) for m in medicines]
        finally:
            session.close()

    @staticmethod
    def create(
        medicine_name: str,
        generic_name: str = "",
        company: str = "",
        category: str = "",
        barcode: str = "",
        rack_location: str = "",
        minimum_stock: int = 0,
    ) -> MedicineResult:
        """Create a new medicine. Raises DuplicateMedicineError on conflict."""
        session = new_session()
        try:
            existing = (
                session.query(Medicine)
                .filter(func.lower(Medicine.medicine_name) == medicine_name.lower())
                .first()
            )
            if existing is not None:
                raise DuplicateMedicineError(
                    f"A medicine named '{medicine_name}' already exists."
                )

            med = Medicine(
                medicine_name=medicine_name,
                generic_name=generic_name or None,
                company=company or None,
                category=category or None,
                barcode=barcode or None,
                rack_location=rack_location or None,
                minimum_stock=minimum_stock,
            )
            session.add(med)
            session.commit()
            session.refresh(med)
            logger.info("Created medicine: %s", med.medicine_name)
            return InventoryService._to_result(med)
        except DuplicateMedicineError:
            session.rollback()
            raise
        except IntegrityError:
            session.rollback()
            raise DuplicateMedicineError(
                f"A medicine named '{medicine_name}' already exists."
            )
        finally:
            session.close()

    @staticmethod
    def update(
        medicine_id: int,
        medicine_name: str,
        generic_name: str = "",
        company: str = "",
        category: str = "",
        barcode: str = "",
        rack_location: str = "",
        minimum_stock: int = 0,
    ) -> MedicineResult:
        """Update an existing medicine. Raises errors on not found or duplicate name."""
        session = new_session()
        try:
            med = session.get(Medicine, medicine_id)
            if med is None:
                raise MedicineNotFoundError(
                    f"Medicine with id {medicine_id} not found."
                )

            dup = (
                session.query(Medicine)
                .filter(
                    func.lower(Medicine.medicine_name) == medicine_name.lower(),
                    Medicine.id != medicine_id,
                )
                .first()
            )
            if dup is not None:
                raise DuplicateMedicineError(
                    f"Another medicine named '{medicine_name}' already exists."
                )

            med.medicine_name = medicine_name
            med.generic_name = generic_name or None
            med.company = company or None
            med.category = category or None
            med.barcode = barcode or None
            med.rack_location = rack_location or None
            med.minimum_stock = minimum_stock

            session.commit()
            session.refresh(med)
            logger.info("Updated medicine id=%d: %s", med.id, med.medicine_name)
            return InventoryService._to_result(med)
        except (DuplicateMedicineError, MedicineNotFoundError):
            session.rollback()
            raise
        except IntegrityError:
            session.rollback()
            raise DuplicateMedicineError(
                f"A medicine named '{medicine_name}' already exists."
            )
        finally:
            session.close()

    @staticmethod
    def delete(medicine_id: int) -> None:
        """Delete a medicine. Raises MedicineInUseError if it has batches."""
        session = new_session()
        try:
            med = session.get(Medicine, medicine_id)
            if med is None:
                raise MedicineNotFoundError(
                    f"Medicine with id {medicine_id} not found."
                )

            batch_count = (
                session.query(func.count(Batch.id))
                .filter(Batch.medicine_id == medicine_id)
                .scalar()
            )
            if batch_count and batch_count > 0:
                raise MedicineInUseError(
                    f"Cannot delete '{med.medicine_name}' — "
                    f"it has {batch_count} batch(es) in stock. "
                    "Remove all batches first."
                )

            name = med.medicine_name
            session.delete(med)
            session.commit()
            logger.info("Deleted medicine: %s", name)
        except (MedicineNotFoundError, MedicineInUseError):
            session.rollback()
            raise
        finally:
            session.close()
