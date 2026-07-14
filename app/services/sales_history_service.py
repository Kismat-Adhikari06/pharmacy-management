from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from app.database.engine import new_session
from app.models.sale import Sale
from app.models.sale_item import SaleItem

logger = logging.getLogger(__name__)


@dataclass
class SaleRecord:
    """Lightweight sale record for history display."""

    sale_id: int
    bill_number: str
    sale_date: str
    total_amount: float
    payment_method: str
    item_count: int


class SalesHistoryService:
    """Read-only queries for sales history."""

    @staticmethod
    def get_all(limit: int = 500) -> list[SaleRecord]:
        session = new_session()
        try:
            sales = (
                session.query(Sale)
                .order_by(Sale.sale_date.desc())
                .limit(limit)
                .all()
            )
            results = []
            for s in sales:
                item_count = (
                    session.query(SaleItem)
                    .filter(SaleItem.sale_id == s.id)
                    .count()
                )
                dt = s.sale_date or datetime.now()
                results.append(
                    SaleRecord(
                        sale_id=s.id,
                        bill_number=s.bill_number,
                        sale_date=dt.strftime("%Y-%m-%d %H:%M"),
                        total_amount=s.total_amount,
                        payment_method=s.payment_method,
                        item_count=item_count,
                    )
                )
            return results
        finally:
            session.close()

    @staticmethod
    def search(query: str) -> list[SaleRecord]:
        session = new_session()
        try:
            term = f"%{query}%"
            sales = (
                session.query(Sale)
                .filter(Sale.bill_number.ilike(term))
                .order_by(Sale.sale_date.desc())
                .all()
            )
            results = []
            for s in sales:
                item_count = (
                    session.query(SaleItem)
                    .filter(SaleItem.sale_id == s.id)
                    .count()
                )
                dt = s.sale_date or datetime.now()
                results.append(
                    SaleRecord(
                        sale_id=s.id,
                        bill_number=s.bill_number,
                        sale_date=dt.strftime("%Y-%m-%d %H:%M"),
                        total_amount=s.total_amount,
                        payment_method=s.payment_method,
                        item_count=item_count,
                    )
                )
            return results
        finally:
            session.close()
