from __future__ import annotations

import logging
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as pdf_canvas

from app.database.engine import new_session
from app.models.sale import Sale
from app.models.sale_item import SaleItem
from app.models.batch import Batch
from app.models.medicine import Medicine
from app.models.settings import Settings

logger = logging.getLogger(__name__)

# ── Paper widths ────────────────────────────────────────────────
THERMAL_58_MM = 48.0 * mm   # 58 mm receipt
THERMAL_80_MM = 72.0 * mm   # 80 mm receipt
A4_WIDTH, A4_HEIGHT = A4    # 210 x 297 mm

FONT_REGULAR = "Helvetica"
FONT_BOLD = "Helvetica-Bold"


@dataclass
class ReceiptItem:
    """Single line on a receipt."""

    medicine_name: str
    batch_number: str
    quantity: int
    unit_price: float
    line_total: float


@dataclass
class ReceiptData:
    """All data needed to render a receipt."""

    pharmacy_name: str
    pharmacy_address: str
    pharmacy_phone: str
    pharmacy_pan: str
    bill_number: str
    sale_date: str
    sale_time: str
    cashier: str
    items: list[ReceiptItem]
    subtotal: float
    discount: float
    vat_amount: float
    grand_total: float
    payment_method: str
    cash_received: float
    change_returned: float


class ReceiptService:
    """Generate receipt PDFs in 58 mm, 80 mm, and A4 formats."""

    # ── Data loading ────────────────────────────────────────────

    @staticmethod
    def load_sale_data(
        sale_id: int | None = None,
        bill_number: str | None = None,
    ) -> ReceiptData | None:
        """Load sale and items from the database."""
        session = new_session()
        try:
            if sale_id is not None:
                sale = session.get(Sale, sale_id)
            elif bill_number is not None:
                sale = (
                    session.query(Sale)
                    .filter(Sale.bill_number == bill_number)
                    .first()
                )
            else:
                return None

            if sale is None:
                return None

            settings = session.query(Settings).first()
            pharmacy_name = settings.pharmacy_name if settings else "My Pharmacy"
            pharmacy_address = settings.address if settings else ""
            pharmacy_phone = settings.phone if settings else ""
            pharmacy_pan = settings.pan_number if settings else ""

            items: list[ReceiptItem] = []
            subtotal = 0.0
            for si in sale.items:
                batch = session.get(Batch, si.batch_id)
                medicine_name = ""
                if batch:
                    med = session.get(Medicine, batch.medicine_id)
                    medicine_name = med.medicine_name if med else ""
                item_total = si.selling_price * si.quantity - si.discount
                subtotal += item_total
                items.append(
                    ReceiptItem(
                        medicine_name=medicine_name,
                        batch_number=batch.batch_number if batch else "",
                        quantity=si.quantity,
                        unit_price=si.selling_price,
                        line_total=item_total,
                    )
                )

            sale_dt = sale.sale_date or datetime.now()

            return ReceiptData(
                pharmacy_name=pharmacy_name,
                pharmacy_address=pharmacy_address,
                pharmacy_phone=pharmacy_phone,
                pharmacy_pan=pharmacy_pan,
                bill_number=sale.bill_number,
                sale_date=sale_dt.strftime("%Y-%m-%d"),
                sale_time=sale_dt.strftime("%H:%M:%S"),
                cashier="Admin",
                items=items,
                subtotal=subtotal,
                discount=sale.discount,
                vat_amount=sale.vat_amount,
                grand_total=sale.total_amount,
                payment_method=sale.payment_method,
                cash_received=0.0,
                change_returned=0.0,
            )
        finally:
            session.close()

    # ── PDF generation ──────────────────────────────────────────

    @staticmethod
    def generate_pdf(
        data: ReceiptData,
        output_path: str | Path,
        paper: str = "80mm",
    ) -> Path:
        """Generate a receipt PDF and return the file path.

        paper: '58mm', '80mm', or 'a4'
        """
        output = Path(output_path)

        if paper == "58mm":
            width = THERMAL_58_MM
            ReceiptService._render_thermal(data, output, width)
        elif paper == "a4":
            ReceiptService._render_a4(data, output)
        else:
            width = THERMAL_80_MM
            ReceiptService._render_thermal(data, output, width)

        return output

    # ── Thermal receipt (58 mm / 80 mm) ─────────────────────────

    @staticmethod
    def _render_thermal(
        data: ReceiptData, output: Path, width: float
    ) -> None:
        margin = 4 * mm
        usable = width - 2 * margin
        line_height = 4.2 * mm
        font_size = 7.5

        c = pdf_canvas.Canvas(str(output), pagesize=(width, 400 * mm))
        y = 400 * mm  # start from top

        def _text(
            txt: str,
            bold: bool = False,
            size: float | None = None,
            align: str = "center",
        ) -> None:
            nonlocal y
            fn = FONT_BOLD if bold else FONT_REGULAR
            sz = size or font_size
            c.setFont(fn, sz)
            if align == "center":
                c.drawCentredString(width / 2, y, txt)
            elif align == "right":
                c.drawRightString(width - margin, y, txt)
            else:
                c.drawString(margin, y, txt)
            y -= line_height

        def _line() -> None:
            nonlocal y
            c.setStrokeColorRGB(0.6, 0.6, 0.6)
            c.setLineWidth(0.3)
            c.line(margin, y, width - margin, y)
            y -= line_height * 0.5

        def _blank() -> None:
            nonlocal y
            y -= line_height * 0.3

        # ── Header ──────────────────────────────────────────
        _text(data.pharmacy_name, bold=True, size=10)
        if data.pharmacy_address:
            _text(data.pharmacy_address, size=7)
        if data.pharmacy_phone:
            _text(f"Phone: {data.pharmacy_phone}", size=7)
        if data.pharmacy_pan:
            _text(f"PAN: {data.pharmacy_pan}", size=7)
        _line()
        _blank()

        # ── Sale info ───────────────────────────────────────
        _text(f"Bill: {data.bill_number}", bold=True)
        _text(f"Date: {data.sale_date}  Time: {data.sale_time}")
        _text(f"Cashier: {data.cashier}")
        _line()
        _blank()

        # ── Column headers ──────────────────────────────────
        col_name_w = usable * 0.35
        col_batch_w = usable * 0.18
        col_qty_w = usable * 0.10
        col_rate_w = usable * 0.17
        col_amt_w = usable * 0.20

        c.setFont(FONT_BOLD, font_size)
        c.drawString(margin, y, "Medicine")
        c.drawString(margin + col_name_w, y, "Batch")
        c.drawRightString(margin + col_name_w + col_batch_w + col_qty_w, y, "Qty")
        c.drawRightString(
            margin + col_name_w + col_batch_w + col_qty_w + col_rate_w, y, "Rate"
        )
        c.drawRightString(width - margin, y, "Amount")
        y -= line_height
        _line()

        # ── Items ───────────────────────────────────────────
        c.setFont(FONT_REGULAR, font_size)
        for item in data.items:
            name = item.medicine_name[:20]
            c.drawString(margin, y, name)
            c.drawString(margin + col_name_w, y, item.batch_number[:8])
            c.drawRightString(
                margin + col_name_w + col_batch_w + col_qty_w, y,
                str(item.quantity),
            )
            c.drawRightString(
                margin + col_name_w + col_batch_w + col_qty_w + col_rate_w,
                y,
                f"{item.unit_price:.2f}",
            )
            c.drawRightString(width - margin, y, f"{item.line_total:.2f}")
            y -= line_height

        _line()
        _blank()

        # ── Summary ─────────────────────────────────────────
        label_x = margin
        value_x = width - margin

        def _summary_line(label: str, value: str, bold: bool = False) -> None:
            nonlocal y
            c.setFont(FONT_BOLD if bold else FONT_REGULAR, font_size)
            c.drawString(label_x, y, label)
            c.drawRightString(value_x, y, value)
            y -= line_height

        _summary_line("Subtotal", f"Rs. {data.subtotal:.2f}")
        if data.discount > 0:
            _summary_line("Discount", f"- Rs. {data.discount:.2f}")
        _summary_line("VAT", f"Rs. {data.vat_amount:.2f}")
        _line()
        _summary_line("Grand Total", f"Rs. {data.grand_total:.2f}", bold=True)
        _line()
        _blank()

        _summary_line("Payment", data.payment_method)
        if data.payment_method == "Cash":
            _summary_line("Cash Received", f"Rs. {data.cash_received:.2f}")
            _summary_line("Change", f"Rs. {data.change_returned:.2f}")
        _line()
        _blank()

        # ── Footer ──────────────────────────────────────────
        _text("Thank You!", bold=True, size=8)
        _text("Visit Again", size=7)

        c.showPage()
        c.save()

    # ── A4 invoice ──────────────────────────────────────────────

    @staticmethod
    def _render_a4(data: ReceiptData, output: Path) -> None:
        margin = 20 * mm
        usable = A4_WIDTH - 2 * margin
        y_start = A4_HEIGHT - margin
        y = y_start
        line_height = 6 * mm

        c = pdf_canvas.Canvas(str(output), pagesize=A4)

        def _text(
            txt: str,
            bold: bool = False,
            size: float = 10,
            align: str = "left",
        ) -> None:
            nonlocal y
            fn = FONT_BOLD if bold else FONT_REGULAR
            c.setFont(fn, size)
            if align == "center":
                c.drawCentredString(A4_WIDTH / 2, y, txt)
            elif align == "right":
                c.drawRightString(A4_WIDTH - margin, y, txt)
            else:
                c.drawString(margin, y, txt)
            y -= line_height

        def _line() -> None:
            nonlocal y
            c.setStrokeColorRGB(0.5, 0.5, 0.5)
            c.setLineWidth(0.5)
            c.line(margin, y, A4_WIDTH - margin, y)
            y -= line_height * 0.4

        # ── Header ──────────────────────────────────────────
        _text(data.pharmacy_name, bold=True, size=16, align="center")
        if data.pharmacy_address:
            _text(data.pharmacy_address, size=10, align="center")
        if data.pharmacy_phone:
            _text(f"Phone: {data.pharmacy_phone}", size=9, align="center")
        if data.pharmacy_pan:
            _text(f"PAN: {data.pharmacy_pan}", size=9, align="center")
        _line()
        _line()

        # ── Invoice title ───────────────────────────────────
        _text("SALES INVOICE", bold=True, size=14, align="center")
        _line()

        # ── Sale info ───────────────────────────────────────
        info_y = y
        c.setFont(FONT_REGULAR, 10)
        c.drawString(margin, info_y, f"Bill No: {data.bill_number}")
        c.drawRightString(A4_WIDTH - margin, info_y, f"Date: {data.sale_date}")
        info_y -= line_height
        c.drawString(margin, info_y, f"Time: {data.sale_time}")
        c.drawRightString(A4_WIDTH - margin, info_y, f"Cashier: {data.cashier}")
        y = info_y - line_height
        _line()

        # ── Table header ────────────────────────────────────
        col_w = [0.05, 0.30, 0.13, 0.08, 0.17, 0.17, 0.10]
        col_headers = ["#", "Medicine", "Batch", "Qty", "Rate", "Amount", "Disc."]

        c.setFillColorRGB(0.18, 0.18, 0.27)
        c.rect(margin, y - line_height * 0.2, usable, line_height * 1.4, fill=1, stroke=0)
        c.setFillColorRGB(0.8, 0.8, 0.85)

        x = margin
        for i, header in enumerate(col_headers):
            c.setFont(FONT_BOLD, 9)
            if i >= 3:
                c.drawRightString(x + usable * col_w[i], y, header)
            else:
                c.drawString(x + 2 * mm, y, header)
            x += usable * col_w[i]
        y -= line_height * 1.5

        # ── Table rows ──────────────────────────────────────
        c.setFillColorRGB(0.8, 0.83, 0.95)
        for idx, item in enumerate(data.items):
            x = margin
            row_data = [
                str(idx + 1),
                item.medicine_name[:25],
                item.batch_number[:10],
                str(item.quantity),
                f"{item.unit_price:.2f}",
                f"{item.line_total:.2f}",
                f"{item.discount:.2f}" if item.discount > 0 else "-",
            ]
            c.setFont(FONT_REGULAR, 9)
            for i, val in enumerate(row_data):
                if i >= 3:
                    c.drawRightString(x + usable * col_w[i], y, val)
                else:
                    c.drawString(x + 2 * mm, y, val)
                x += usable * col_w[i]
            y -= line_height
            if idx % 2 == 1:
                c.setFillColorRGB(0.12, 0.12, 0.18)
                c.rect(
                    margin,
                    y + line_height * 0.2,
                    usable,
                    line_height,
                    fill=1,
                    stroke=0,
                )
                c.setFillColorRGB(0.8, 0.83, 0.95)

        _line()

        # ── Summary ─────────────────────────────────────────
        sum_label_x = A4_WIDTH - margin - 70 * mm
        sum_val_x = A4_WIDTH - margin

        def _a4_summary(label: str, value: str, bold: bool = False) -> None:
            nonlocal y
            c.setFont(FONT_BOLD if bold else FONT_REGULAR, 10)
            c.drawString(sum_label_x, y, label)
            c.drawRightString(sum_val_x, y, value)
            y -= line_height

        _a4_summary("Subtotal:", f"Rs. {data.subtotal:.2f}")
        if data.discount > 0:
            _a4_summary("Discount:", f"- Rs. {data.discount:.2f}")
        _a4_summary("VAT (13%):", f"Rs. {data.vat_amount:.2f}")
        _line()
        _a4_summary("Grand Total:", f"Rs. {data.grand_total:.2f}", bold=True)
        _line()

        _a4_summary("Payment Method:", data.payment_method)
        if data.payment_method == "Cash":
            _a4_summary("Cash Received:", f"Rs. {data.cash_received:.2f}")
            _a4_summary("Change:", f"Rs. {data.change_returned:.2f}")
        _line()

        # ── Footer ──────────────────────────────────────────
        y -= line_height
        _text("Thank You for your purchase!", bold=True, size=12, align="center")
        _text("Visit Again", size=10, align="center")

        c.showPage()
        c.save()

    # ── Print to printer ────────────────────────────────────────

    @staticmethod
    def print_pdf(pdf_path: str | Path) -> bool:
        """Send a PDF file to the system default printer.

        Returns True if the print job was sent successfully.
        """
        pdf_path = str(Path(pdf_path).resolve())
        try:
            import subprocess
            import sys

            if sys.platform == "win32":
                # Use Windows shell print
                os.startfile(pdf_path, "print")
                return True
            elif sys.platform == "darwin":
                subprocess.run(["lpr", pdf_path], check=True, timeout=30)
                return True
            else:
                subprocess.run(["lpr", pdf_path], check=True, timeout=30)
                return True
        except Exception as exc:
            logger.exception("Print failed")
            return False

    @staticmethod
    def get_temp_dir() -> Path:
        """Get (and create) the temp directory for receipt PDFs."""
        d = Path(tempfile.gettempdir()) / "pms_receipts"
        d.mkdir(parents=True, exist_ok=True)
        return d
