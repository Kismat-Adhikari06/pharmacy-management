from __future__ import annotations

import csv
import logging
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app.database.engine import new_session
from app.models.purchase import Purchase
from app.models.purchase_item import PurchaseItem
from app.models.supplier import Supplier

logger = logging.getLogger(__name__)

_PHONE_RE = re.compile(r"^[\d\+\-\(\)\s]{7,20}$")
_EMAIL_RE = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


@dataclass
class SupplierResult:
    """Lightweight data transfer object for a supplier row."""

    id: int
    supplier_name: str
    contact_person: str
    phone: str
    email: str
    address: str
    pan_number: str
    registration_number: str
    status: str
    outstanding_balance: float
    last_purchase_date: str
    total_purchases: float


@dataclass
class SupplierPurchaseRow:
    """Single purchase row in supplier detail view."""

    id: int
    invoice_number: str
    purchase_date: str
    total_amount: float
    item_count: int


@dataclass
class SupplierDetail:
    """Full supplier detail with purchase history and aggregated stats."""

    id: int
    supplier_name: str
    contact_person: str
    phone: str
    email: str
    address: str
    pan_number: str
    registration_number: str
    status: str
    outstanding_balance: float
    total_purchases: float
    total_orders: int
    average_purchase_value: float
    last_invoice: str
    purchases: list[SupplierPurchaseRow] = field(default_factory=list)


class DuplicateSupplierError(Exception):
    """Raised when a supplier with the same name or PAN already exists."""


class SupplierNotFoundError(Exception):
    """Raised when a supplier with the given id does not exist."""


class SupplierInUseError(Exception):
    """Raised when a supplier cannot be deleted because it has purchases."""


class SupplierValidationError(Exception):
    """Raised when supplier data fails validation."""


class SupplierService:
    """Business logic for Supplier CRUD operations."""

    # ── Helpers ────────────────────────────────────────────────

    @staticmethod
    def _to_result(s: Supplier) -> SupplierResult:
        return SupplierResult(
            id=s.id,
            supplier_name=s.supplier_name,
            contact_person=s.contact_person or "",
            phone=s.phone or "",
            email=s.email or "",
            address=s.address or "",
            pan_number=s.pan_number or "",
            registration_number=s.registration_number or "",
            status=s.status or "Active",
            outstanding_balance=s.outstanding_balance or 0.0,
            last_purchase_date=(
                s.last_purchase_date.strftime("%Y-%m-%d")
                if s.last_purchase_date
                else ""
            ),
            total_purchases=s.total_purchases or 0.0,
        )

    @staticmethod
    def validate_phone(phone: str) -> None:
        """Raise if phone format is invalid."""
        if phone and not _PHONE_RE.match(phone):
            raise SupplierValidationError(
                "Invalid phone number format. Use 7-20 digits with optional +, -, (, )."
            )

    @staticmethod
    def validate_email(email: str) -> None:
        """Raise if email format is invalid."""
        if email and not _EMAIL_RE.match(email):
            raise SupplierValidationError(
                "Invalid email address format."
            )

    @staticmethod
    def validate(data: dict) -> None:
        """Run all validations on supplier data dict."""
        SupplierService.validate_phone(data.get("phone", ""))
        SupplierService.validate_email(data.get("email", ""))

    # ── Queries ────────────────────────────────────────────────

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
        """Search suppliers across name, contact person, phone, email, PAN, registration."""
        session = new_session()
        try:
            term = f"%{query}%"
            suppliers = (
                session.query(Supplier)
                .filter(
                    func.lower(Supplier.supplier_name).like(func.lower(term))
                    | func.lower(Supplier.contact_person).like(func.lower(term))
                    | Supplier.phone.like(term)
                    | func.lower(Supplier.email).like(func.lower(term))
                    | Supplier.pan_number.like(term)
                    | Supplier.registration_number.like(term)
                )
                .order_by(Supplier.supplier_name.asc())
                .all()
            )
            return [SupplierService._to_result(s) for s in suppliers]
        finally:
            session.close()

    @staticmethod
    def get_filtered(
        status: str = "All",
        query: str = "",
    ) -> list[SupplierResult]:
        """Get suppliers filtered by status and optional search query."""
        session = new_session()
        try:
            q = session.query(Supplier)
            if status and status != "All":
                q = q.filter(Supplier.status == status)
            if query:
                term = f"%{query}%"
                q = q.filter(
                    func.lower(Supplier.supplier_name).like(func.lower(term))
                    | func.lower(Supplier.contact_person).like(func.lower(term))
                    | Supplier.phone.like(term)
                    | func.lower(Supplier.email).like(func.lower(term))
                    | Supplier.pan_number.like(term)
                    | Supplier.registration_number.like(term)
                )
            suppliers = q.order_by(Supplier.supplier_name.asc()).all()
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
    def get_detail(supplier_id: int) -> SupplierDetail | None:
        """Return full supplier detail with purchase history and aggregated stats."""
        session = new_session()
        try:
            s = session.get(Supplier, supplier_id)
            if s is None:
                return None

            purchases = (
                session.query(Purchase)
                .filter(Purchase.supplier_id == supplier_id)
                .order_by(Purchase.purchase_date.desc(), Purchase.id.desc())
                .all()
            )

            total_orders = len(purchases)
            total_amount = sum(p.total_amount for p in purchases)
            avg_value = total_amount / total_orders if total_orders > 0 else 0.0

            last_invoice = ""
            if purchases:
                last_invoice = purchases[0].invoice_number

            purchase_rows = []
            for p in purchases:
                item_count = (
                    session.query(func.count(PurchaseItem.id))
                    .filter(PurchaseItem.purchase_id == p.id)
                    .scalar()
                    or 0
                )
                purchase_rows.append(
                    SupplierPurchaseRow(
                        id=p.id,
                        invoice_number=p.invoice_number,
                        purchase_date=p.purchase_date.strftime("%Y-%m-%d"),
                        total_amount=p.total_amount,
                        item_count=item_count,
                    )
                )

            return SupplierDetail(
                id=s.id,
                supplier_name=s.supplier_name,
                contact_person=s.contact_person or "",
                phone=s.phone or "",
                email=s.email or "",
                address=s.address or "",
                pan_number=s.pan_number or "",
                registration_number=s.registration_number or "",
                status=s.status or "Active",
                outstanding_balance=s.outstanding_balance or 0.0,
                total_purchases=s.total_purchases or 0.0,
                total_orders=total_orders,
                average_purchase_value=avg_value,
                last_invoice=last_invoice,
                purchases=purchase_rows,
            )
        finally:
            session.close()

    # ── CRUD ───────────────────────────────────────────────────

    @staticmethod
    def create(
        supplier_name: str,
        contact_person: str = "",
        phone: str = "",
        email: str = "",
        address: str = "",
        pan_number: str = "",
        registration_number: str = "",
        status: str = "Active",
        outstanding_balance: float = 0.0,
    ) -> SupplierResult:
        """Create a new supplier."""
        data = {
            "supplier_name": supplier_name,
            "contact_person": contact_person,
            "phone": phone,
            "email": email,
            "address": address,
            "pan_number": pan_number,
            "registration_number": registration_number,
            "status": status,
            "outstanding_balance": outstanding_balance,
        }
        SupplierService.validate(data)

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

            if pan_number:
                pan_dup = (
                    session.query(Supplier)
                    .filter(Supplier.pan_number == pan_number)
                    .first()
                )
                if pan_dup is not None:
                    raise DuplicateSupplierError(
                        f"A supplier with PAN '{pan_number}' already exists."
                    )

            sup = Supplier(
                supplier_name=supplier_name,
                contact_person=contact_person or None,
                phone=phone or None,
                email=email or None,
                address=address or None,
                pan_number=pan_number or None,
                registration_number=registration_number or None,
                status=status,
                outstanding_balance=outstanding_balance,
            )
            session.add(sup)
            session.commit()
            session.refresh(sup)
            logger.info("Created supplier: %s", sup.supplier_name)
            return SupplierService._to_result(sup)
        except (DuplicateSupplierError, SupplierValidationError):
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
        contact_person: str = "",
        phone: str = "",
        email: str = "",
        address: str = "",
        pan_number: str = "",
        registration_number: str = "",
        status: str = "Active",
        outstanding_balance: float = 0.0,
    ) -> SupplierResult:
        """Update an existing supplier."""
        data = {
            "supplier_name": supplier_name,
            "contact_person": contact_person,
            "phone": phone,
            "email": email,
            "address": address,
            "pan_number": pan_number,
            "registration_number": registration_number,
            "status": status,
            "outstanding_balance": outstanding_balance,
        }
        SupplierService.validate(data)

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

            if pan_number:
                pan_dup = (
                    session.query(Supplier)
                    .filter(
                        Supplier.pan_number == pan_number,
                        Supplier.id != supplier_id,
                    )
                    .first()
                )
                if pan_dup is not None:
                    raise DuplicateSupplierError(
                        f"Another supplier with PAN '{pan_number}' already exists."
                    )

            sup.supplier_name = supplier_name
            sup.contact_person = contact_person or None
            sup.phone = phone or None
            sup.email = email or None
            sup.address = address or None
            sup.pan_number = pan_number or None
            sup.registration_number = registration_number or None
            sup.status = status
            sup.outstanding_balance = outstanding_balance

            session.commit()
            session.refresh(sup)
            logger.info("Updated supplier id=%d: %s", sup.id, sup.supplier_name)
            return SupplierService._to_result(sup)
        except (DuplicateSupplierError, SupplierNotFoundError, SupplierValidationError):
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

            purchase_count = (
                session.query(func.count(Purchase.id))
                .filter(Purchase.supplier_id == supplier_id)
                .scalar()
            )
            if purchase_count and purchase_count > 0:
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

    # ── Export ──────────────────────────────────────────────────

    @staticmethod
    def export_csv(path: str | Path) -> Path:
        """Export all suppliers to CSV."""
        rows = SupplierService.get_all()
        headers = [
            "Supplier Name", "Contact Person", "Phone", "Email",
            "Address", "PAN Number", "Registration Number", "Status",
            "Outstanding Balance", "Last Purchase Date", "Total Purchases",
        ]
        p = Path(path)
        with open(p, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            for r in rows:
                writer.writerow([
                    r.supplier_name, r.contact_person, r.phone, r.email,
                    r.address, r.pan_number, r.registration_number, r.status,
                    f"{r.outstanding_balance:.2f}", r.last_purchase_date,
                    f"{r.total_purchases:.2f}",
                ])
        return p

    @staticmethod
    def export_excel(path: str | Path) -> Path:
        """Export all suppliers to Excel-compatible XML spreadsheet."""
        rows = SupplierService.get_all()
        headers = [
            "Supplier Name", "Contact Person", "Phone", "Email",
            "Address", "PAN Number", "Registration Number", "Status",
            "Outstanding Balance", "Last Purchase Date", "Total Purchases",
        ]
        p = Path(path)
        lines: list[str] = []
        lines.append('<?xml version="1.0" encoding="UTF-8"?>')
        lines.append('<?mso-application progid="Excel.Sheet"?>')
        lines.append(
            '<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"'
            ' xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">'
        )
        lines.append(
            '<Styles><Style ss:ID="header"><Font ss:Bold="1"/></Style></Styles>'
        )
        lines.append(
            '<Worksheet ss:Name="Suppliers"><Table>'
        )

        lines.append('<Row ss:StyleID="header">')
        for h in headers:
            lines.append(f"<Cell><Data ss:Type=\"String\">{h}</Data></Cell>")
        lines.append("</Row>")

        for r in rows:
            vals = [
                r.supplier_name, r.contact_person, r.phone, r.email,
                r.address, r.pan_number, r.registration_number, r.status,
                f"{r.outstanding_balance:.2f}", r.last_purchase_date,
                f"{r.total_purchases:.2f}",
            ]
            lines.append("<Row>")
            for v in vals:
                lines.append(f"<Cell><Data ss:Type=\"String\">{v}</Data></Cell>")
            lines.append("</Row>")

        lines.append("</Table></Worksheet></Workbook>")

        p.write_text("\n".join(lines), encoding="utf-8")
        return p
