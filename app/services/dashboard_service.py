from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import func

from app.database.engine import new_session
from app.models.batch import Batch
from app.models.medicine import Medicine
from app.models.purchase import Purchase
from app.models.purchase_item import PurchaseItem
from app.models.sale import Sale
from app.models.sale_item import SaleItem

logger = logging.getLogger(__name__)


@dataclass
class TopCard:
    """A single KPI card on the dashboard."""

    label: str
    value: str
    icon: str
    color: str  # hex colour for the accent


@dataclass
class RecentSale:
    """Lightweight sale record for the recent-sales table."""

    bill_number: str
    sale_time: str
    item_count: int
    total: float
    payment_method: str
    sale_id: int


@dataclass
class LowStockItem:
    """Medicine whose stock is at or below its minimum threshold."""

    medicine_name: str
    current_stock: int
    minimum_stock: int


@dataclass
class ExpiryItem:
    """Medicine batch expiring within a given window."""

    medicine_name: str
    batch_number: str
    expiry_date: str
    quantity: int
    days_until: int  # negative = already expired


@dataclass
class ChartData:
    """Generic container returned to the UI for chart rendering."""

    labels: list[str]
    values: list[float]


class DashboardService:
    """Read-only queries that power every widget on the dashboard."""

    # ── Top cards ───────────────────────────────────────────────

    @staticmethod
    def get_top_cards() -> list[TopCard]:
        today = date.today()
        cards: list[TopCard] = []
        session = new_session()
        try:
            # 1. Today's Sales (Rs)
            today_sales = (
                session.query(func.coalesce(func.sum(Sale.total_amount), 0.0))
                .filter(func.date(Sale.sale_date) == today)
                .scalar()
            )
            cards.append(
                TopCard(
                    label="Today's Sales",
                    value=f"Rs. {today_sales:,.2f}",
                    icon="\U0001f4b0",
                    color="#a6e3a1",
                )
            )

            # 2. Today's Profit (estimated: selling_price - purchase_price for sold items)
            profit_subq = (
                session.query(
                    func.coalesce(
                        func.sum(
                            (SaleItem.selling_price - Batch.purchase_price)
                            * SaleItem.quantity
                        ),
                        0.0,
                    )
                )
                .join(Sale, Sale.id == SaleItem.sale_id)
                .join(Batch, Batch.id == SaleItem.batch_id)
                .filter(func.date(Sale.sale_date) == today)
                .scalar()
            )
            cards.append(
                TopCard(
                    label="Today's Profit",
                    value=f"Rs. {profit_subq:,.2f}",
                    icon="\U0001f4c8",
                    color="#89b4fa",
                )
            )

            # 3. Bills Today
            bills_today = (
                session.query(func.count(Sale.id))
                .filter(func.date(Sale.sale_date) == today)
                .scalar()
            )
            cards.append(
                TopCard(
                    label="Bills Today",
                    value=str(bills_today),
                    icon="\U0001f4cb",
                    color="#f9e2af",
                )
            )

            # 4. Total Medicines
            total_meds = session.query(func.count(Medicine.id)).scalar()
            cards.append(
                TopCard(
                    label="Total Medicines",
                    value=str(total_meds),
                    icon="\U0001f48a",
                    color="#cba6f7",
                )
            )

            # 5. Total Inventory Value (sum of batch purchase_price * quantity)
            inv_value = (
                session.query(
                    func.coalesce(
                        func.sum(Batch.purchase_price * Batch.quantity), 0.0
                    )
                )
                .scalar()
            )
            cards.append(
                TopCard(
                    label="Inventory Value",
                    value=f"Rs. {inv_value:,.2f}",
                    icon="\U0001f3e6",
                    color="#f38ba8",
                )
            )

            # 6. Low Stock Medicines
            low_stock_count = (
                session.query(func.count(Medicine.id))
                .join(Batch, Batch.medicine_id == Medicine.id)
                .group_by(Medicine.id)
                .having(
                    func.coalesce(func.sum(Batch.quantity), 0) <= Medicine.minimum_stock
                )
                .count()
            )
            cards.append(
                TopCard(
                    label="Low Stock",
                    value=str(low_stock_count),
                    icon="\u26a0\ufe0f",
                    color="#fab387",
                )
            )

            # 7. Expiring Within 90 Days
            exp_90 = (
                session.query(func.count(Batch.id))
                .filter(
                    Batch.quantity > 0,
                    Batch.expiry_date >= today,
                    Batch.expiry_date <= today + timedelta(days=90),
                )
                .scalar()
            )
            cards.append(
                TopCard(
                    label="Expiring (90d)",
                    value=str(exp_90),
                    icon="\u23f0",
                    color="#f9e2af",
                )
            )

            # 8. Expired Medicines
            expired = (
                session.query(func.count(Batch.id))
                .filter(Batch.expiry_date < today, Batch.quantity > 0)
                .scalar()
            )
            cards.append(
                TopCard(
                    label="Expired",
                    value=str(expired),
                    icon="\U0001f6ab",
                    color="#f38ba8",
                )
            )
        finally:
            session.close()
        return cards

    # ── Charts ──────────────────────────────────────────────────

    @staticmethod
    def daily_sales_last_7_days() -> ChartData:
        session = new_session()
        try:
            today = date.today()
            labels: list[str] = []
            values: list[float] = []
            for i in range(6, -1, -1):
                d = today - timedelta(days=i)
                labels.append(d.strftime("%b %d"))
                total = (
                    session.query(func.coalesce(func.sum(Sale.total_amount), 0.0))
                    .filter(func.date(Sale.sale_date) == d)
                    .scalar()
                )
                values.append(float(total))
            return ChartData(labels=labels, values=values)
        finally:
            session.close()

    @staticmethod
    def monthly_sales_last_6_months() -> ChartData:
        session = new_session()
        try:
            today = date.today()
            labels: list[str] = []
            values: list[float] = []
            for i in range(5, -1, -1):
                # Calculate month offset
                month = today.month - i
                year = today.year
                while month <= 0:
                    month += 12
                    year -= 1
                labels.append(date(year, month, 1).strftime("%b %Y"))
                start = date(year, month, 1)
                if month == 12:
                    end = date(year + 1, 1, 1)
                else:
                    end = date(year, month + 1, 1)
                total = (
                    session.query(func.coalesce(func.sum(Sale.total_amount), 0.0))
                    .filter(
                        Sale.sale_date >= datetime.combine(start, datetime.min.time()),
                        Sale.sale_date < datetime.combine(end, datetime.min.time()),
                    )
                    .scalar()
                )
                values.append(float(total))
            return ChartData(labels=labels, values=values)
        finally:
            session.close()

    @staticmethod
    def top_selling_medicines(limit: int = 5) -> ChartData:
        session = new_session()
        try:
            rows = (
                session.query(
                    Medicine.medicine_name,
                    func.coalesce(func.sum(SaleItem.quantity), 0).label("total_qty"),
                )
                .join(Batch, Batch.medicine_id == Medicine.id)
                .join(SaleItem, SaleItem.batch_id == Batch.id)
                .group_by(Medicine.medicine_name)
                .order_by(func.sum(SaleItem.quantity).desc())
                .limit(limit)
                .all()
            )
            labels = [r[0][:20] for r in rows] if rows else []
            values = [float(r[1]) for r in rows] if rows else []
            return ChartData(labels=labels, values=values)
        finally:
            session.close()

    @staticmethod
    def category_distribution() -> ChartData:
        session = new_session()
        try:
            rows = (
                session.query(
                    func.coalesce(Medicine.category, "Uncategorized"),
                    func.count(Medicine.id),
                )
                .group_by(func.coalesce(Medicine.category, "Uncategorized"))
                .order_by(func.count(Medicine.id).desc())
                .all()
            )
            labels = [r[0] for r in rows] if rows else []
            values = [float(r[1]) for r in rows] if rows else []
            return ChartData(labels=labels, values=values)
        finally:
            session.close()

    # ── Recent sales ────────────────────────────────────────────

    @staticmethod
    def recent_sales(limit: int = 10) -> list[RecentSale]:
        session = new_session()
        try:
            sales = (
                session.query(Sale)
                .order_by(Sale.sale_date.desc())
                .limit(limit)
                .all()
            )
            results: list[RecentSale] = []
            for s in sales:
                item_count = (
                    session.query(func.count(SaleItem.id))
                    .filter(SaleItem.sale_id == s.id)
                    .scalar()
                )
                results.append(
                    RecentSale(
                        bill_number=s.bill_number,
                        sale_time=s.sale_date.strftime("%H:%M") if s.sale_date else "",
                        item_count=item_count or 0,
                        total=s.total_amount,
                        payment_method=s.payment_method,
                        sale_id=s.id,
                    )
                )
            return results
        finally:
            session.close()

    # ── Low stock ───────────────────────────────────────────────

    @staticmethod
    def low_stock_medicines() -> list[LowStockItem]:
        session = new_session()
        try:
            rows = (
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
            return [
                LowStockItem(
                    medicine_name=r[0],
                    current_stock=int(r[1]),
                    minimum_stock=int(r[2]),
                )
                for r in rows
            ]
        finally:
            session.close()

    # ── Expiry panels ───────────────────────────────────────────

    @staticmethod
    def expiring_medicines() -> list[ExpiryItem]:
        """Return all non-expired batches expiring within 90 days + already expired."""
        session = new_session()
        try:
            today = date.today()
            cutoff = today + timedelta(days=90)
            batches = (
                session.query(Batch)
                .join(Medicine, Medicine.id == Batch.medicine_id)
                .filter(Batch.quantity > 0, Batch.expiry_date <= cutoff)
                .order_by(Batch.expiry_date.asc())
                .all()
            )
            results: list[ExpiryItem] = []
            for b in batches:
                days = (b.expiry_date - today).days
                results.append(
                    ExpiryItem(
                        medicine_name=b.medicine.medicine_name,
                        batch_number=b.batch_number,
                        expiry_date=b.expiry_date.strftime("%Y-%m-%d"),
                        quantity=b.quantity,
                        days_until=days,
                    )
                )
            return results
        finally:
            session.close()
