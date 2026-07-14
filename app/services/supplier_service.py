from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app.database.engine import new_session
from app.models.supplier import Supplier

logger = logging.getLogger(__name__)


@dataclass
class SupplierResult:
    """Lightweight data transfer object for a supplier row."""

    id: int
    supplier_name: str
    phone: str
    email: str
    address: str
    pan_number: str


class DuplicateSupplierError(Exception):
    """Raised when a supplier with the same name or PAN already exists."""


class SupplierNotFoundError(Exception):
    """Raised when a supplier with the given id does not exist."""


class SupplierService:
    """Business logic for Supplier CRUD operations."""

    @staticmethod
    def _to_result(s: Supplier) -> SupplierResult:
        return SupplierResult(
            id=s.id,
            supplier_name=s.supplier_name,
            phone=s.phone or "",
            email=s.email or "",
            address=s.address or "",
            pan_number=s.pan_number or "",
        )

    @staticmethod
    def get_all() -> list[SupplierResult]:
        """Return every supplier, ordered by name."""
        session = new_session()
        try:
            suppliers = (
                session.query(Supplier)
                .order_by(Supplier.supplier_name.asc())
                .all()
            )
            return [SupplierService._to_result(s) for s in suppliers]
        finally:
            session.close()

    @staticmethod
    def search(query: str) -> list[SupplierResult]:
        """Search suppliers across name, phone, email, PAN."""
        session = new_session()
        try:
            term = f"%{query}%"
            suppliers = (
                session.query(Supplier)
                .filter(
                    func.lower(Supplier.supplier_name).like(func.lower(term))
                    | Supplier.phone.like(term)
                    | func.lower(Supplier.email).like(func.lower(term))
                    | Supplier.pan_number.like(term)
                )
                .order_by(Supplier.supplier_name.asc())
                .all()
            )
            return [SupplierService._to_result(s) for s in suppliers]
        finally:
            session.close()

    @staticmethod
    def get_by_id(supplier_id: int) -> SupplierResult | None:
        """Return a single supplier by id."""
        session = new_session()
        try:
            s = session.get(Supplier, supplier_id)
            if s is None:
                return None
            return SupplierService._to_result(s)
        finally:
            session.close()

    @staticmethod
    def create(
        supplier_name: str,
        phone: str = "",
        email: str = "",
        address: str = "",
        pan_number: str = "",
    ) -> SupplierResult:
        """Create a new supplier."""
        session = new_session()
        try:
            existing = (
                session.query(Supplier)
                .filter(func.lower(Supplier.supplier_name) == supplier_name.lower())
                .first()
            )
            if existing is not None:
                raise DuplicateSupplierError(
                    f"A supplier named '{supplier_name}' already exists."
                )

            sup = Supplier(
                supplier_name=supplier_name,
                phone=phone or None,
                email=email or None,
                address=address or None,
                pan_number=pan_number or None,
            )
            session.add(sup)
            session.commit()
            session.refresh(sup)
            logger.info("Created supplier: %s", sup.supplier_name)
            return SupplierService._to_result(sup)
        except DuplicateSupplierError:
            session.rollback()
            raise
        except IntegrityError:
            session.rollback()
            raise DuplicateSupplierError(
                f"A supplier named '{supplier_name}' already exists."
            )
        finally:
            session.close()

    @staticmethod
    def update(
        supplier_id: int,
        supplier_name: str,
        phone: str = "",
        email: str = "",
        address: str = "",
        pan_number: str = "",
    ) -> SupplierResult:
        """Update an existing supplier."""
        session = new_session()
        try:
            sup = session.get(Supplier, supplier_id)
            if sup is None:
                raise SupplierNotFoundError(
                    f"Supplier with id {supplier_id} not found."
                )

            dup = (
                session.query(Supplier)
                .filter(
                    func.lower(Supplier.supplier_name) == supplier_name.lower(),
                    Supplier.id != supplier_id,
                )
                .first()
            )
            if dup is not None:
                raise DuplicateSupplierError(
                    f"Another supplier named '{supplier_name}' already exists."
                )

            sup.supplier_name = supplier_name
            sup.phone = phone or None
            sup.email = email or None
            sup.address = address or None
            sup.pan_number = pan_number or None

            session.commit()
            session.refresh(sup)
            logger.info("Updated supplier id=%d: %s", sup.id, sup.supplier_name)
            return SupplierService._to_result(sup)
        except (DuplicateSupplierError, SupplierNotFoundError):
            session.rollback()
            raise
        except IntegrityError:
            session.rollback()
            raise DuplicateSupplierError(
                f"A supplier named '{supplier_name}' already exists."
            )
        finally:
            session.close()

    @staticmethod
    def delete(supplier_id: int) -> None:
        """Delete a supplier. Raises if supplier has purchases."""
        session = new_session()
        try:
            sup = session.get(Supplier, supplier_id)
            if sup is None:
                raise SupplierNotFoundError(
                    f"Supplier with id {supplier_id} not found."
                )

            from app.models.purchase import Purchase

            purchase_count = (
                session.query(func.count(Purchase.id))
                .filter(Purchase.supplier_id == supplier_id)
                .scalar()
            )
            if purchase_count and purchase_count > 0:
                from app.services.supplier_service import SupplierInUseError

                raise SupplierInUseError(
                    f"Cannot delete '{sup.supplier_name}' — "
                    f"it has {purchase_count} purchase(s). "
                    "Remove all purchases first."
                )

            name = sup.supplier_name
            session.delete(sup)
            session.commit()
            logger.info("Deleted supplier: %s", name)
        except SupplierNotFoundError:
            session.rollback()
            raise
        finally:
            session.close()


class SupplierInUseError(Exception):
    """Raised when a supplier cannot be deleted because it has purchases."""
