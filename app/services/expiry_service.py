from __future__ import annotations

import csv
import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import func

from app.database.engine import new_session
from app.models.batch import Batch
from app.models.medicine import Medicine
from app.models.purchase import Purchase
from app.models.purchase_item import PurchaseItem
from app.models.supplier import Supplier

logger = logging.getLogger(__name__)


# ── Data containers ─────────────────────────────────────────────


@dataclass
class ExpiryBatch:
    """A single batch row for the expiry page."""

    medicine_name: str
    generic_name: str
    company: str
    category: str
    batch_number: str
    expiry_date: str
    quantity: int
    selling_price: float
    days_until: int
    status: str  # "Expired", "Critical", "Warning", "Caution"


@dataclass
class LowStockItem:
    """A single medicine row for the low stock page."""

    medicine_name: str
    generic_name: str
    company: str
    category: str
    current_stock: int
    minimum_stock: int
    difference: int
    latest_supplier: str


@dataclass
class ExpirySummary:
    """Summary counts for expiry page header cards."""

    expired_count: int = 0
    expired_qty: int = 0
    critical_count: int = 0  # <= 30 days
    warning_count: int = 0  # <= 60 days
    caution_count: int = 0  # <= 90 days
    total_items: int = 0


@dataclass
class LowStockSummary:
    """Summary counts for low stock page header cards."""

    out_of_stock: int = 0
    low_stock: int = 0
    total_items: int = 0


# ── Service ─────────────────────────────────────────────────────


class ExpiryService:
    """Queries for expired, expiring, and low-stock medicines with filtering."""

    # ── Expiry queries ──────────────────────────────────────────

    @staticmethod
    def get_expiring_batches(
        category: str | None = None,
        company: str | None = None,
    ) -> list[ExpiryBatch]:
        """Return all non-expired batches expiring within 90 days + expired batches still in stock."""
        session = new_session()
        try:
            today = date.today()
            cutoff = today + timedelta(days=90)

            query = (
                session.query(Batch, Medicine)
                .join(Medicine, Medicine.id == Batch.medicine_id)
                .filter(Batch.quantity > 0, Batch.expiry_date <= cutoff)
            )

            if category:
                query = query.filter(Medicine.category == category)
            if company:
                query = query.filter(Medicine.company == company)

            rows = query.order_by(Batch.expiry_date.asc()).all()

            results: list[ExpiryBatch] = []
            for batch, med in rows:
                days = (batch.expiry_date - today).days
                if days < 0:
                    status = "Expired"
                elif days <= 30:
                    status = "Critical"
                elif days <= 60:
                    status = "Warning"
                else:
                    status = "Caution"
                results.append(
                    ExpiryBatch(
                        medicine_name=med.medicine_name,
                        generic_name=med.generic_name or "",
                        company=med.company or "",
                        category=med.category or "",
                        batch_number=batch.batch_number,
                        expiry_date=batch.expiry_date.strftime("%Y-%m-%d"),
                        quantity=batch.quantity,
                        selling_price=batch.selling_price,
                        days_until=days,
                        status=status,
                    )
                )
            return results
        finally:
            session.close()

    @staticmethod
    def get_expired_batches(
        category: str | None = None,
        company: str | None = None,
    ) -> list[ExpiryBatch]:
        """Return only already-expired batches still in stock."""
        session = new_session()
        try:
            today = date.today()
            query = (
                session.query(Batch, Medicine)
                .join(Medicine, Medicine.id == Batch.medicine_id)
                .filter(Batch.quantity > 0, Batch.expiry_date < today)
            )
            if category:
                query = query.filter(Medicine.category == category)
            if company:
                query = query.filter(Medicine.company == company)

            rows = query.order_by(Batch.expiry_date.asc()).all()
            return [
                ExpiryBatch(
                    medicine_name=med.medicine_name,
                    generic_name=med.generic_name or "",
                    company=med.company or "",
                    category=med.category or "",
                    batch_number=batch.batch_number,
                    expiry_date=batch.expiry_date.strftime("%Y-%m-%d"),
                    quantity=batch.quantity,
                    selling_price=batch.selling_price,
                    days_until=(batch.expiry_date - today).days,
                    status="Expired",
                )
                for batch, med in rows
            ]
        finally:
            session.close()

    @staticmethod
    def get_expiry_summary() -> ExpirySummary:
        """Aggregate counts for expiry header cards."""
        session = new_session()
        try:
            today = date.today()
            d30 = today + timedelta(days=30)
            d60 = today + timedelta(days=60)
            d90 = today + timedelta(days=90)

            base = (
                session.query(func.coalesce(func.sum(Batch.quantity), 0))
                .join(Medicine, Medicine.id == Batch.medicine_id)
                .filter(Batch.quantity > 0)
            )

            expired_qty = int(
                base.filter(Batch.expiry_date < today).scalar()
            )
            critical_qty = int(
                base.filter(Batch.expiry_date >= today, Batch.expiry_date <= d30).scalar()
            )
            warning_qty = int(
                base.filter(Batch.expiry_date > d30, Batch.expiry_date <= d60).scalar()
            )
            caution_qty = int(
                base.filter(Batch.expiry_date > d60, Batch.expiry_date <= d90).scalar()
            )

            # Count distinct batches per status
            batch_base = (
                session.query(func.count(Batch.id))
                .join(Medicine, Medicine.id == Batch.medicine_id)
                .filter(Batch.quantity > 0)
            )
            expired_count = int(
                batch_base.filter(Batch.expiry_date < today).scalar()
            )
            critical_count = int(
                batch_base.filter(Batch.expiry_date >= today, Batch.expiry_date <= d30).scalar()
            )
            warning_count = int(
                batch_base.filter(Batch.expiry_date > d30, Batch.expiry_date <= d60).scalar()
            )
            caution_count = int(
                batch_base.filter(Batch.expiry_date > d60, Batch.expiry_date <= d90).scalar()
            )

            return ExpirySummary(
                expired_count=expired_count,
                expired_qty=expired_qty,
                critical_count=critical_count,
                warning_count=warning_count,
                caution_count=caution_count,
                total_items=expired_count + critical_count + warning_count + caution_count,
            )
        finally:
            session.close()

    # ── Low stock queries ───────────────────────────────────────

    @staticmethod
    def get_low_stock_medicines(
        category: str | None = None,
        company: str | None = None,
    ) -> list[LowStockItem]:
        """Return all medicines where current stock <= minimum_stock."""
        session = new_session()
        try:
            query = (
                session.query(
                    Medicine.id,
                    Medicine.medicine_name,
                    Medicine.generic_name,
                    Medicine.company,
                    Medicine.category,
                    Medicine.minimum_stock,
                    func.coalesce(func.sum(Batch.quantity), 0).label("stock"),
                )
                .outerjoin(Batch, Batch.medicine_id == Medicine.id)
                .group_by(
                    Medicine.id,
                    Medicine.medicine_name,
                    Medicine.generic_name,
                    Medicine.company,
                    Medicine.category,
                    Medicine.minimum_stock,
                )
                .having(func.coalesce(func.sum(Batch.quantity), 0) <= Medicine.minimum_stock)
            )

            if category:
                query = query.filter(Medicine.category == category)
            if company:
                query = query.filter(Medicine.company == company)

            rows = query.order_by(
                func.coalesce(func.sum(Batch.quantity), 0).asc()
            ).all()

            results: list[LowStockItem] = []
            for r in rows:
                stock = int(r[6])
                min_stock = int(r[5])
                # Find latest supplier via most recent purchase for this medicine
                supplier_name = ExpiryService._latest_supplier(session, r[0])
                results.append(
                    LowStockItem(
                        medicine_name=r[1],
                        generic_name=r[2] or "",
                        company=r[3] or "",
                        category=r[4] or "",
                        current_stock=stock,
                        minimum_stock=min_stock,
                        difference=stock - min_stock,
                        latest_supplier=supplier_name,
                    )
                )
            return results
        finally:
            session.close()

    @staticmethod
    def _latest_supplier(session, medicine_id: int) -> str:
        """Find the supplier name from the most recent purchase for a medicine."""
        row = (
            session.query(Supplier.supplier_name)
            .join(Purchase, Purchase.supplier_id == Supplier.id)
            .join(PurchaseItem, PurchaseItem.purchase_id == Purchase.id)
            .join(Batch, Batch.id == PurchaseItem.batch_id)
            .filter(Batch.medicine_id == medicine_id)
            .order_by(Purchase.purchase_date.desc())
            .first()
        )
        return row[0] if row else ""

    @staticmethod
    def get_low_stock_summary() -> LowStockSummary:
        """Aggregate counts for low stock header cards."""
        session = new_session()
        try:
            rows = (
                session.query(
                    func.coalesce(func.sum(Batch.quantity), 0).label("stock"),
                    Medicine.minimum_stock,
                )
                .outerjoin(Batch, Batch.medicine_id == Medicine.id)
                .group_by(Medicine.id, Medicine.minimum_stock)
                .having(func.coalesce(func.sum(Batch.quantity), 0) <= Medicine.minimum_stock)
                .all()
            )
            out_of_stock = sum(1 for r in rows if int(r[0]) == 0)
            return LowStockSummary(
                out_of_stock=out_of_stock,
                low_stock=len(rows) - out_of_stock,
                total_items=len(rows),
            )
        finally:
            session.close()

    # ── Filter option loaders ───────────────────────────────────

    @staticmethod
    def get_categories() -> list[str]:
        session = new_session()
        try:
            rows = (
                session.query(Medicine.category)
                .filter(Medicine.category.isnot(None), Medicine.category != "")
                .distinct()
                .order_by(Medicine.category)
                .all()
            )
            return [r[0] for r in rows]
        finally:
            session.close()

    @staticmethod
    def get_companies() -> list[str]:
        session = new_session()
        try:
            rows = (
                session.query(Medicine.company)
                .filter(Medicine.company.isnot(None), Medicine.company != "")
                .distinct()
                .order_by(Medicine.company)
                .all()
            )
            return [r[0] for r in rows]
        finally:
            session.close()

    # ── Startup check helpers ───────────────────────────────────

    @staticmethod
    def get_startup_warnings() -> dict[str, list[str]]:
        """Return warnings for startup: {expired: [...], expiring_30: [...], low_stock: [...]}."""
        session = new_session()
        try:
            today = date.today()
            d30 = today + timedelta(days=30)

            # Expired
            expired = (
                session.query(Medicine.medicine_name, Batch.batch_number, Batch.expiry_date, Batch.quantity)
                .join(Medicine, Medicine.id == Batch.medicine_id)
                .filter(Batch.quantity > 0, Batch.expiry_date < today)
                .order_by(Batch.expiry_date.asc())
                .all()
            )

            # Expiring within 30 days
            expiring = (
                session.query(Medicine.medicine_name, Batch.batch_number, Batch.expiry_date, Batch.quantity)
                .join(Medicine, Medicine.id == Batch.medicine_id)
                .filter(Batch.quantity > 0, Batch.expiry_date >= today, Batch.expiry_date <= d30)
                .order_by(Batch.expiry_date.asc())
                .all()
            )

            # Low stock
            low = (
                session.query(
                    Medicine.medicine_name,
                    func.coalesce(func.sum(Batch.quantity), 0).label("stock"),
                    Medicine.minimum_stock,
                )
                .outerjoin(Batch, Batch.medicine_id == Medicine.id)
                .group_by(Medicine.id, Medicine.medicine_name, Medicine.minimum_stock)
                .having(func.coalesce(func.sum(Batch.quantity), 0) <= Medicine.minimum_stock)
                .order_by(func.coalesce(func.sum(Batch.quantity), 0).asc())
                .all()
            )

            warnings: dict[str, list[str]] = {"expired": [], "expiring_30": [], "low_stock": []}
            for name, batch, exp, qty in expired:
                warnings["expired"].append(f"{name} (Batch {batch}) — expired {exp.strftime('%Y-%m-%d')}, qty: {qty}")
            for name, batch, exp, qty in expiring:
                warnings["expiring_30"].append(f"{name} (Batch {batch}) — expires {exp.strftime('%Y-%m-%d')}, qty: {qty}")
            for name, stock, min_s in low:
                warnings["low_stock"].append(f"{name} — stock: {int(stock)}/{int(min_s)}")

            return warnings
        finally:
            session.close()

    # ── Export helpers ──────────────────────────────────────────

    @staticmethod
    def export_csv(headers: list[str], rows: list[list[str]], path: str | Path) -> Path:
        """Write table data to a CSV file."""
        p = Path(path)
        with open(p, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            for row in rows:
                writer.writerow(row)
        return p

    @staticmethod
    def export_excel(headers: list[str], rows: list[list[str]], path: str | Path, sheet_name: str = "Report") -> Path:
        """Write table data to an Excel-compatible XML spreadsheet."""
        p = Path(path)
        lines: list[str] = []
        lines.append('<?xml version="1.0" encoding="UTF-8"?>')
        lines.append('<?mso-application progid="Excel.Sheet"?>')
        lines.append(
            '<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"'
            ' xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">'
        )
        lines.append('<Styles><Style ss:ID="header"><Font ss:Bold="1"/></Style></Styles>')
        lines.append(f'<Worksheet ss:Name="{sheet_name}"><Table>')

        lines.append('<Row ss:StyleID="header">')
        for h in headers:
            lines.append(f"<Cell><Data ss:Type=\"String\">{h}</Data></Cell>")
        lines.append("</Row>")

        for row in rows:
            lines.append("<Row>")
            for cell in row:
                clean = cell.replace("Rs.", "").replace(",", "").replace("%", "").strip()
                try:
                    val = float(clean)
                    lines.append(f'<Cell><Data ss:Type="Number">{val}</Data></Cell>')
                except ValueError:
                    lines.append(f'<Cell><Data ss:Type="String">{cell}</Data></Cell>')
            lines.append("</Row>")

        lines.append("</Table></Worksheet></Workbook>")
        with open(p, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return p
