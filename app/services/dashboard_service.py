from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import func

from app.database.engine import new_session
from app.models.batch import Batch
from app.models.medicine import Medicine
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
    total: float
    payment_method: str
    sale_id: int


class DashboardService:
    """Read-only queries that power every widget on the dashboard."""

    # ── Top cards ───────────────────────────────────────────────

    @staticmethod
    def get_top_cards() -> list[TopCard]:
        """Return only the 3 daily KPI cards: Sales, Profit, Bills."""
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
                    icon="revenue",
                    color="#22c55e",
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
                    icon="profit",
                    color="#3B82F6",
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
                    icon="bills",
                    color="#f59e0b",
                )
            )
        finally:
            session.close()
        return cards

    @staticmethod
    def get_alert_counts() -> tuple[int, int]:
        """Return (low_stock_count, expiry_count) for dashboard summary cards."""
        today = date.today()
        session = new_session()
        try:
            # Low stock medicines
            low_stock_count = (
                session.query(func.count(Medicine.id))
                .join(Batch, Batch.medicine_id == Medicine.id)
                .group_by(Medicine.id)
                .having(
                    func.coalesce(func.sum(Batch.quantity), 0) <= Medicine.minimum_stock
                )
                .count()
            )

            # Expired + Expiring within 90 days
            expiry_count = (
                session.query(func.count(Batch.id))
                .filter(
                    Batch.quantity > 0,
                    Batch.expiry_date <= today + timedelta(days=90),
                )
                .scalar()
            )

            return low_stock_count, expiry_count
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
                results.append(
                    RecentSale(
                        bill_number=s.bill_number,
                        sale_time=s.sale_date.strftime("%H:%M") if s.sale_date else "",
                        total=s.total_amount,
                        payment_method=s.payment_method,
                        sale_id=s.id,
                    )
                )
            return results
        finally:
            session.close()

