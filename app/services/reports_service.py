from __future__ import annotations

import csv
import io
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

from sqlalchemy import func

from app.database.engine import new_session
from app.models.batch import Batch
from app.models.medicine import Medicine
from app.models.purchase import Purchase
from app.models.purchase_item import PurchaseItem
from app.models.sale import Sale
from app.models.sale_item import SaleItem
from app.models.supplier import Supplier

logger = logging.getLogger(__name__)


# ── Data containers ─────────────────────────────────────────────


@dataclass
class ReportSummary:
    """Aggregated summary for any report."""

    total_sales: float = 0.0
    total_profit: float = 0.0
    total_bills: int = 0
    total_medicines_sold: int = 0
    avg_bill_value: float = 0.0


@dataclass
class ReportRow:
    """A single row in a report table — keys vary by report type."""

    cells: list[str] = field(default_factory=list)


@dataclass
class ReportResult:
    """Full result returned to the UI for any report type."""

    headers: list[str]
    rows: list[ReportRow]
    summary: ReportSummary
    chart_labels: list[str] = field(default_factory=list)
    chart_values: list[float] = field(default_factory=list)
    chart_values2: list[float] = field(default_factory=list)
    chart_title2: str = ""


@dataclass
class FilterParams:
    """Optional filters applied to every report query."""

    date_from: date | None = None
    date_to: date | None = None
    medicine_id: int | None = None
    supplier_id: int | None = None
    category: str | None = None
    payment_method: str | None = None


# ── Service ─────────────────────────────────────────────────────


class ReportsService:
    """All report queries, filtering, export, and chart data."""

    # ── Helpers ─────────────────────────────────────────────────

    @staticmethod
    def _date_range(params: FilterParams):
        """Return (start_datetime, end_datetime) from filter params."""
        today = date.today()
        d_from = params.date_from or today.replace(day=1)
        d_to = params.date_to or today
        start = datetime.combine(d_from, datetime.min.time())
        end = datetime.combine(d_to + timedelta(days=1), datetime.min.time())
        return start, end

    @staticmethod
    def _apply_sale_filters(query, params: FilterParams):
        """Apply date, medicine, category, payment filters to a Sale query."""
        start, end = ReportsService._date_range(params)
        query = query.filter(Sale.sale_date >= start, Sale.sale_date < end)

        if params.payment_method:
            query = query.filter(Sale.payment_method == params.payment_method)

        if params.medicine_id or params.category:
            query = (
                query.join(SaleItem, SaleItem.sale_id == Sale.id)
                .join(Batch, Batch.id == SaleItem.batch_id)
                .join(Medicine, Medicine.id == Batch.medicine_id)
            )
            if params.medicine_id:
                query = query.filter(Medicine.id == params.medicine_id)
            if params.category:
                query = query.filter(Medicine.category == params.category)

        return query

    @staticmethod
    def _calc_profit(session, sale_ids: list[int]) -> float:
        """Calculate profit for a set of sale IDs."""
        if not sale_ids:
            return 0.0
        result = (
            session.query(
                func.coalesce(
                    func.sum(
                        (SaleItem.selling_price - Batch.purchase_price)
                        * SaleItem.quantity
                    ),
                    0.0,
                )
            )
            .join(Batch, Batch.id == SaleItem.batch_id)
            .filter(SaleItem.sale_id.in_(sale_ids))
            .scalar()
        )
        return float(result)

    @staticmethod
    def _build_summary(
        session, sale_ids: list[int], total_sales: float
    ) -> ReportSummary:
        """Build a ReportSummary from sale IDs."""
        profit = ReportsService._calc_profit(session, sale_ids)
        bills = len(sale_ids)
        qty = 0
        if sale_ids:
            qty = (
                session.query(func.coalesce(func.sum(SaleItem.quantity), 0))
                .filter(SaleItem.sale_id.in_(sale_ids))
                .scalar()
            )
        avg = total_sales / bills if bills else 0.0
        return ReportSummary(
            total_sales=total_sales,
            total_profit=profit,
            total_bills=bills,
            total_medicines_sold=int(qty),
            avg_bill_value=avg,
        )

    @staticmethod
    def _list_filter_values(table, name_col, params: FilterParams = None):
        """Return distinct values for a combo box filter."""
        session = new_session()
        try:
            rows = session.query(name_col).distinct().order_by(name_col).all()
            return [r[0] for r in rows if r[0]]
        finally:
            session.close()

    # ── Filter option loaders ───────────────────────────────────

    @staticmethod
    def get_medicine_options() -> list[tuple[int, str]]:
        session = new_session()
        try:
            rows = (
                session.query(Medicine.id, Medicine.medicine_name)
                .order_by(Medicine.medicine_name)
                .all()
            )
            return [(r[0], r[1]) for r in rows]
        finally:
            session.close()

    @staticmethod
    def get_supplier_options() -> list[tuple[int, str]]:
        session = new_session()
        try:
            rows = (
                session.query(Supplier.id, Supplier.supplier_name)
                .order_by(Supplier.supplier_name)
                .all()
            )
            return [(r[0], r[1]) for r in rows]
        finally:
            session.close()

    @staticmethod
    def get_category_options() -> list[str]:
        return ReportsService._list_filter_values(Medicine, Medicine.category)

    @staticmethod
    def get_payment_methods() -> list[str]:
        return ReportsService._list_filter_values(Sale, Sale.payment_method)

    # ── Report: Daily Sales ─────────────────────────────────────

    @staticmethod
    def daily_sales(params: FilterParams) -> ReportResult:
        session = new_session()
        try:
            start, end = ReportsService._date_range(params)
            base = ReportsService._apply_sale_filters(
                session.query(Sale), params
            )
            sales = base.order_by(Sale.sale_date.asc()).all()

            headers = ["Bill No", "Date", "Time", "Items", "Total", "Payment"]
            rows: list[ReportRow] = []
            sale_ids: list[int] = []
            total = 0.0
            chart_labels: list[str] = []
            chart_values: list[float] = []

            day_map: dict[str, float] = {}
            for s in sales:
                dt = s.sale_date or datetime.now()
                item_count = (
                    session.query(func.count(SaleItem.id))
                    .filter(SaleItem.sale_id == s.id)
                    .scalar()
                )
                rows.append(
                    ReportRow(
                        cells=[
                            s.bill_number,
                            dt.strftime("%Y-%m-%d"),
                            dt.strftime("%H:%M"),
                            str(item_count or 0),
                            f"Rs. {s.total_amount:,.2f}",
                            s.payment_method,
                        ]
                    )
                )
                sale_ids.append(s.id)
                total += s.total_amount
                day_key = dt.strftime("%Y-%m-%d")
                day_map[day_key] = day_map.get(day_key, 0.0) + s.total_amount

            for k in sorted(day_map):
                chart_labels.append(k)
                chart_values.append(day_map[k])

            summary = ReportsService._build_summary(session, sale_ids, total)
            return ReportResult(
                headers=headers,
                rows=rows,
                summary=summary,
                chart_labels=chart_labels,
                chart_values=chart_values,
            )
        finally:
            session.close()

    # ── Report: Weekly Sales ────────────────────────────────────

    @staticmethod
    def weekly_sales(params: FilterParams) -> ReportResult:
        session = new_session()
        try:
            base = ReportsService._apply_sale_filters(
                session.query(Sale), params
            )
            sales = base.order_by(Sale.sale_date.asc()).all()

            headers = ["Week", "Bills", "Total Sales", "Profit"]
            week_map: dict[str, dict] = {}
            sale_ids_all: list[int] = []

            for s in sales:
                dt = s.sale_date or datetime.now()
                iso = dt.isocalendar()
                week_key = f"{iso[0]}-W{iso[1]:02d}"
                if week_key not in week_map:
                    week_map[week_key] = {"bills": 0, "total": 0.0, "ids": []}
                week_map[week_key]["bills"] += 1
                week_map[week_key]["total"] += s.total_amount
                week_map[week_key]["ids"].append(s.id)
                sale_ids_all.append(s.id)

            rows: list[ReportRow] = []
            chart_labels: list[str] = []
            chart_values: list[float] = []
            chart_profit: list[float] = []

            for wk in sorted(week_map):
                d = week_map[wk]
                profit = ReportsService._calc_profit(session, d["ids"])
                rows.append(
                    ReportRow(
                        cells=[
                            wk,
                            str(d["bills"]),
                            f"Rs. {d['total']:,.2f}",
                            f"Rs. {profit:,.2f}",
                        ]
                    )
                )
                chart_labels.append(wk)
                chart_values.append(d["total"])
                chart_profit.append(profit)

            total_sales = sum(d["total"] for d in week_map.values())
            summary = ReportsService._build_summary(
                session, sale_ids_all, total_sales
            )
            return ReportResult(
                headers=headers,
                rows=rows,
                summary=summary,
                chart_labels=chart_labels,
                chart_values=chart_values,
                chart_values2=chart_profit,
                chart_title2="Profit",
            )
        finally:
            session.close()

    # ── Report: Monthly Sales ───────────────────────────────────

    @staticmethod
    def monthly_sales(params: FilterParams) -> ReportResult:
        session = new_session()
        try:
            base = ReportsService._apply_sale_filters(
                session.query(Sale), params
            )
            sales = base.order_by(Sale.sale_date.asc()).all()

            headers = ["Month", "Bills", "Total Sales", "Profit"]
            month_map: dict[str, dict] = {}
            sale_ids_all: list[int] = []

            for s in sales:
                dt = s.sale_date or datetime.now()
                mk = dt.strftime("%Y-%m")
                if mk not in month_map:
                    month_map[mk] = {"bills": 0, "total": 0.0, "ids": []}
                month_map[mk]["bills"] += 1
                month_map[mk]["total"] += s.total_amount
                month_map[mk]["ids"].append(s.id)
                sale_ids_all.append(s.id)

            rows: list[ReportRow] = []
            chart_labels: list[str] = []
            chart_values: list[float] = []
            chart_profit: list[float] = []

            for mk in sorted(month_map):
                d = month_map[mk]
                profit = ReportsService._calc_profit(session, d["ids"])
                rows.append(
                    ReportRow(
                        cells=[
                            mk,
                            str(d["bills"]),
                            f"Rs. {d['total']:,.2f}",
                            f"Rs. {profit:,.2f}",
                        ]
                    )
                )
                chart_labels.append(mk)
                chart_values.append(d["total"])
                chart_profit.append(profit)

            total_sales = sum(d["total"] for d in month_map.values())
            summary = ReportsService._build_summary(
                session, sale_ids_all, total_sales
            )
            return ReportResult(
                headers=headers,
                rows=rows,
                summary=summary,
                chart_labels=chart_labels,
                chart_values=chart_values,
                chart_values2=chart_profit,
                chart_title2="Profit",
            )
        finally:
            session.close()

    # ── Report: Yearly Sales ────────────────────────────────────

    @staticmethod
    def yearly_sales(params: FilterParams) -> ReportResult:
        session = new_session()
        try:
            base = ReportsService._apply_sale_filters(
                session.query(Sale), params
            )
            sales = base.order_by(Sale.sale_date.asc()).all()

            headers = ["Year", "Bills", "Total Sales", "Profit"]
            year_map: dict[str, dict] = {}
            sale_ids_all: list[int] = []

            for s in sales:
                dt = s.sale_date or datetime.now()
                yk = dt.strftime("%Y")
                if yk not in year_map:
                    year_map[yk] = {"bills": 0, "total": 0.0, "ids": []}
                year_map[yk]["bills"] += 1
                year_map[yk]["total"] += s.total_amount
                year_map[yk]["ids"].append(s.id)
                sale_ids_all.append(s.id)

            rows: list[ReportRow] = []
            chart_labels: list[str] = []
            chart_values: list[float] = []

            for yk in sorted(year_map):
                d = year_map[yk]
                rows.append(
                    ReportRow(
                        cells=[
                            yk,
                            str(d["bills"]),
                            f"Rs. {d['total']:,.2f}",
                            f"Rs. {ReportsService._calc_profit(session, d['ids']):,.2f}",
                        ]
                    )
                )
                chart_labels.append(yk)
                chart_values.append(d["total"])

            total_sales = sum(d["total"] for d in year_map.values())
            summary = ReportsService._build_summary(
                session, sale_ids_all, total_sales
            )
            return ReportResult(
                headers=headers,
                rows=rows,
                summary=summary,
                chart_labels=chart_labels,
                chart_values=chart_values,
            )
        finally:
            session.close()

    # ── Report: Profit Report ───────────────────────────────────

    @staticmethod
    def profit_report(params: FilterParams) -> ReportResult:
        session = new_session()
        try:
            base = ReportsService._apply_sale_filters(
                session.query(Sale), params
            )
            sales = base.order_by(Sale.sale_date.asc()).all()

            headers = ["Bill No", "Date", "Sales", "Cost", "Profit", "Margin %"]
            rows: list[ReportRow] = []
            sale_ids: list[int] = []
            total_sales = 0.0
            total_profit = 0.0
            chart_labels: list[str] = []
            chart_values: list[float] = []

            for s in sales:
                dt = s.sale_date or datetime.now()
                cost = (
                    session.query(
                        func.coalesce(
                            func.sum(Batch.purchase_price * SaleItem.quantity), 0.0
                        )
                    )
                    .join(Batch, Batch.id == SaleItem.batch_id)
                    .filter(SaleItem.sale_id == s.id)
                    .scalar()
                )
                profit = s.total_amount - float(cost)
                margin = (profit / s.total_amount * 100) if s.total_amount else 0.0

                rows.append(
                    ReportRow(
                        cells=[
                            s.bill_number,
                            dt.strftime("%Y-%m-%d"),
                            f"Rs. {s.total_amount:,.2f}",
                            f"Rs. {cost:,.2f}",
                            f"Rs. {profit:,.2f}",
                            f"{margin:.1f}%",
                        ]
                    )
                )
                sale_ids.append(s.id)
                total_sales += s.total_amount
                total_profit += profit
                chart_labels.append(dt.strftime("%m-%d"))
                chart_values.append(profit)

            summary = ReportsService._build_summary(session, sale_ids, total_sales)
            summary.total_profit = total_profit
            return ReportResult(
                headers=headers,
                rows=rows,
                summary=summary,
                chart_labels=chart_labels,
                chart_values=chart_values,
            )
        finally:
            session.close()

    # ── Report: Inventory Report ────────────────────────────────

    @staticmethod
    def inventory_report(params: FilterParams) -> ReportResult:
        session = new_session()
        try:
            q = session.query(Batch).join(Medicine, Medicine.id == Batch.medicine_id)
            if params.medicine_id:
                q = q.filter(Medicine.id == params.medicine_id)
            if params.category:
                q = q.filter(Medicine.category == params.category)
            batches = q.order_by(Medicine.medicine_name.asc()).all()

            headers = [
                "Medicine", "Batch No", "Expiry", "Qty",
                "Purchase Price", "Selling Price", "Stock Value",
            ]
            rows: list[ReportRow] = []
            total_value = 0.0
            chart_labels: list[str] = []
            chart_values: list[float] = []

            med_map: dict[str, float] = {}
            for b in batches:
                val = b.purchase_price * b.quantity
                total_value += val
                med_name = b.medicine.medicine_name
                med_map[med_name] = med_map.get(med_name, 0.0) + val
                rows.append(
                    ReportRow(
                        cells=[
                            med_name,
                            b.batch_number,
                            b.expiry_date.strftime("%Y-%m-%d"),
                            str(b.quantity),
                            f"Rs. {b.purchase_price:,.2f}",
                            f"Rs. {b.selling_price:,.2f}",
                            f"Rs. {val:,.2f}",
                        ]
                    )
                )

            for mk in sorted(med_map, key=med_map.get, reverse=True)[:10]:
                chart_labels.append(mk[:20])
                chart_values.append(med_map[mk])

            summary = ReportSummary(
                total_sales=total_value,
                total_bills=len(batches),
            )
            return ReportResult(
                headers=headers,
                rows=rows,
                summary=summary,
                chart_labels=chart_labels,
                chart_values=chart_values,
            )
        finally:
            session.close()

    # ── Report: Low Stock Report ────────────────────────────────

    @staticmethod
    def low_stock_report(params: FilterParams) -> ReportResult:
        session = new_session()
        try:
            q = (
                session.query(
                    Medicine.medicine_name,
                    Medicine.category,
                    func.coalesce(func.sum(Batch.quantity), 0).label("stock"),
                    Medicine.minimum_stock,
                )
                .outerjoin(Batch, Batch.medicine_id == Medicine.id)
                .group_by(
                    Medicine.id, Medicine.medicine_name,
                    Medicine.category, Medicine.minimum_stock,
                )
                .having(
                    func.coalesce(func.sum(Batch.quantity), 0)
                    <= Medicine.minimum_stock
                )
            )
            if params.category:
                q = q.filter(Medicine.category == params.category)

            rows_data = q.order_by(
                func.coalesce(func.sum(Batch.quantity), 0).asc()
            ).all()

            headers = ["Medicine", "Category", "Current Stock", "Min Stock", "Deficit"]
            rows: list[ReportRow] = []
            chart_labels: list[str] = []
            chart_values: list[float] = []

            for r in rows_data:
                deficit = max(0, int(r[2]) - int(r[3]))
                rows.append(
                    ReportRow(
                        cells=[
                            r[0],
                            r[1] or "N/A",
                            str(r[2]),
                            str(r[3]),
                            str(deficit),
                        ]
                    )
                )
                chart_labels.append(r[0][:20])
                chart_values.append(float(r[2]))

            summary = ReportSummary(total_bills=len(rows))
            return ReportResult(
                headers=headers,
                rows=rows,
                summary=summary,
                chart_labels=chart_labels,
                chart_values=chart_values,
            )
        finally:
            session.close()

    # ── Report: Expiry Report ───────────────────────────────────

    @staticmethod
    def expiry_report(params: FilterParams) -> ReportResult:
        session = new_session()
        try:
            today = date.today()
            q = (
                session.query(Batch)
                .join(Medicine, Medicine.id == Batch.medicine_id)
                .filter(Batch.quantity > 0)
            )
            if params.medicine_id:
                q = q.filter(Medicine.id == params.medicine_id)
            if params.category:
                q = q.filter(Medicine.category == params.category)
            if params.date_to:
                q = q.filter(Batch.expiry_date <= params.date_to)
            else:
                q = q.filter(Batch.expiry_date <= today + timedelta(days=90))

            batches = q.order_by(Batch.expiry_date.asc()).all()

            headers = ["Medicine", "Batch No", "Expiry Date", "Days Left", "Qty", "Status"]
            rows: list[ReportRow] = []
            chart_labels: list[str] = []
            chart_values: list[float] = [0.0, 0.0, 0.0, 0.0]
            chart_legend = ["Expired", "30 Days", "60 Days", "90 Days"]

            for b in batches:
                days = (b.expiry_date - today).days
                if days < 0:
                    status = "Expired"
                    chart_values[0] += 1
                elif days <= 30:
                    status = "Urgent"
                    chart_values[1] += 1
                elif days <= 60:
                    status = "Warning"
                    chart_values[2] += 1
                else:
                    status = "Soon"
                    chart_values[3] += 1

                rows.append(
                    ReportRow(
                        cells=[
                            b.medicine.medicine_name,
                            b.batch_number,
                            b.expiry_date.strftime("%Y-%m-%d"),
                            str(days),
                            str(b.quantity),
                            status,
                        ]
                    )
                )

            summary = ReportSummary(total_bills=len(rows))
            return ReportResult(
                headers=headers,
                rows=rows,
                summary=summary,
                chart_labels=chart_legend,
                chart_values=chart_values,
            )
        finally:
            session.close()

    # ── Report: Purchase Report ─────────────────────────────────

    @staticmethod
    def purchase_report(params: FilterParams) -> ReportResult:
        session = new_session()
        try:
            q = session.query(Purchase).join(Supplier, Supplier.id == Purchase.supplier_id)
            start, end = ReportsService._date_range(params)
            q = q.filter(
                Purchase.purchase_date >= start.date(),
                Purchase.purchase_date < end.date(),
            )
            if params.supplier_id:
                q = q.filter(Purchase.supplier_id == params.supplier_id)

            purchases = q.order_by(Purchase.purchase_date.asc()).all()

            headers = ["Invoice", "Supplier", "Date", "Items", "Total"]
            rows: list[ReportRow] = []
            total = 0.0
            chart_labels: list[str] = []
            chart_values: list[float] = []

            sup_map: dict[str, float] = {}
            for p in purchases:
                item_count = (
                    session.query(func.count(PurchaseItem.id))
                    .filter(PurchaseItem.purchase_id == p.id)
                    .scalar()
                )
                rows.append(
                    ReportRow(
                        cells=[
                            p.invoice_number,
                            p.supplier.supplier_name,
                            p.purchase_date.strftime("%Y-%m-%d"),
                            str(item_count or 0),
                            f"Rs. {p.total_amount:,.2f}",
                        ]
                    )
                )
                total += p.total_amount
                sn = p.supplier.supplier_name
                sup_map[sn] = sup_map.get(sn, 0.0) + p.total_amount

            for k in sorted(sup_map, key=sup_map.get, reverse=True)[:10]:
                chart_labels.append(k[:20])
                chart_values.append(sup_map[k])

            summary = ReportSummary(total_sales=total, total_bills=len(purchases))
            return ReportResult(
                headers=headers,
                rows=rows,
                summary=summary,
                chart_labels=chart_labels,
                chart_values=chart_values,
            )
        finally:
            session.close()

    # ── Report: Top Selling Medicines ───────────────────────────

    @staticmethod
    def top_selling_report(params: FilterParams) -> ReportResult:
        session = new_session()
        try:
            base = (
                session.query(
                    Medicine.medicine_name,
                    Medicine.category,
                    func.coalesce(func.sum(SaleItem.quantity), 0).label("qty"),
                    func.coalesce(
                        func.sum(SaleItem.selling_price * SaleItem.quantity), 0.0
                    ).label("revenue"),
                )
                .join(Batch, Batch.medicine_id == Medicine.id)
                .join(SaleItem, SaleItem.batch_id == Batch.id)
                .join(Sale, Sale.id == SaleItem.sale_id)
            )
            start, end = ReportsService._date_range(params)
            base = base.filter(Sale.sale_date >= start, Sale.sale_date < end)
            if params.payment_method:
                base = base.filter(Sale.payment_method == params.payment_method)
            if params.medicine_id:
                base = base.filter(Medicine.id == params.medicine_id)
            if params.category:
                base = base.filter(Medicine.category == params.category)

            rows_data = (
                base.group_by(Medicine.medicine_name, Medicine.category)
                .order_by(func.sum(SaleItem.quantity).desc())
                .limit(20)
                .all()
            )

            headers = ["Rank", "Medicine", "Category", "Qty Sold", "Revenue"]
            rows: list[ReportRow] = []
            chart_labels: list[str] = []
            chart_values: list[float] = []

            for idx, r in enumerate(rows_data, 1):
                rows.append(
                    ReportRow(
                        cells=[
                            str(idx),
                            r[0],
                            r[1] or "N/A",
                            str(r[2]),
                            f"Rs. {r[3]:,.2f}",
                        ]
                    )
                )
                chart_labels.append(r[0][:20])
                chart_values.append(float(r[2]))

            summary = ReportSummary(
                total_medicines_sold=sum(float(r[2]) for r in rows_data),
                total_bills=len(rows_data),
            )
            return ReportResult(
                headers=headers,
                rows=rows,
                summary=summary,
                chart_labels=chart_labels,
                chart_values=chart_values,
            )
        finally:
            session.close()

    # ── Export helpers ──────────────────────────────────────────

    @staticmethod
    def export_csv(result: ReportResult, path: str | Path) -> Path:
        """Write report data to a CSV file."""
        p = Path(path)
        with open(p, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(result.headers)
            for row in result.rows:
                writer.writerow(row.cells)
            writer.writerow([])
            writer.writerow(["Summary"])
            writer.writerow(["Total Sales", f"Rs. {result.summary.total_sales:,.2f}"])
            writer.writerow(["Total Profit", f"Rs. {result.summary.total_profit:,.2f}"])
            writer.writerow(["Total Bills", result.summary.total_bills])
            writer.writerow(["Medicines Sold", result.summary.total_medicines_sold])
            writer.writerow(["Avg Bill Value", f"Rs. {result.summary.avg_bill_value:,.2f}"])
        return p

    @staticmethod
    def export_excel(result: ReportResult, path: str | Path) -> Path:
        """Write report data to an Excel-compatible XML spreadsheet."""
        p = Path(path)
        lines: list[str] = []
        lines.append('<?xml version="1.0" encoding="UTF-8"?>')
        lines.append(
            '<?mso-application progid="Excel.Sheet"?>'
        )
        lines.append(
            '<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"'
            ' xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">'
        )
        lines.append('<Styles><Style ss:ID="header"><Font ss:Bold="1"/></Style></Styles>')
        lines.append('<Worksheet ss:Name="Report"><Table>')

        # Header row
        lines.append('<Row ss:StyleID="header">')
        for h in result.headers:
            lines.append(f"<Cell><Data ss:Type=\"String\">{h}</Data></Cell>")
        lines.append("</Row>")

        # Data rows
        for row in result.rows:
            lines.append("<Row>")
            for cell in row.cells:
                # Try to detect numeric values
                clean = cell.replace("Rs.", "").replace(",", "").replace("%", "").strip()
                try:
                    val = float(clean)
                    lines.append(f'<Cell><Data ss:Type="Number">{val}</Data></Cell>')
                except ValueError:
                    lines.append(
                        f'<Cell><Data ss:Type="String">{cell}</Data></Cell>'
                    )
            lines.append("</Row>")

        # Summary
        lines.append("<Row></Row>")
        lines.append('<Row ss:StyleID="header"><Cell><Data ss:Type="String">Summary</Data></Cell></Row>')
        for label, val in [
            ("Total Sales", f"{result.summary.total_sales:,.2f}"),
            ("Total Profit", f"{result.summary.total_profit:,.2f}"),
            ("Total Bills", str(result.summary.total_bills)),
            ("Medicines Sold", str(result.summary.total_medicines_sold)),
            ("Avg Bill Value", f"{result.summary.avg_bill_value:,.2f}"),
        ]:
            lines.append(
                f'<Row><Cell><Data ss:Type="String">{label}</Data></Cell>'
                f'<Cell><Data ss:Type="String">{val}</Data></Cell></Row>'
            )

        lines.append("</Table></Worksheet></Workbook>")

        with open(p, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return p
