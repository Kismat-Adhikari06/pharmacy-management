from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtWidgets import QPushButton

from app.services.barcode_service import BarcodeService, LabelData

logger = logging.getLogger(__name__)

_TEXT = "#cdd6f4"
_SUBTEXT = "#a6adc8"
_BLUE = "#89b4fa"
_GREEN = "#a6e3a1"
_RED = "#f38ba8"


class BarcodeLabelDialog(QDialog):
    """Dialog for previewing and printing barcode labels for a medicine."""

    def __init__(
        self,
        label_data: LabelData,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Barcode Label")
        self.setMinimumSize(420, 520)
        self.setModal(True)
        self._data = label_data
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # Header
        title = QLabel("Barcode Label Preview")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        # Label preview card
        preview_frame = QFrame()
        preview_frame.setObjectName("BarcodeLabelPreview")
        preview_frame.setMinimumHeight(200)
        preview_frame.setStyleSheet(
            "#BarcodeLabelPreview {"
            "  background-color: #ffffff;"
            "  border: 1px solid #45475a;"
            "  border-radius: 8px;"
            "  padding: 16px;"
            "}"
        )
        preview_layout = QVBoxLayout(preview_frame)
        preview_layout.setSpacing(6)
        preview_layout.setContentsMargins(20, 16, 20, 16)

        med_name = QLabel(self._data.medicine_name)
        med_name.setStyleSheet("color: #1e1e2e; font-size: 12pt; font-weight: bold;")
        med_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        med_name.setWordWrap(True)
        preview_layout.addWidget(med_name)

        if self._data.generic_name:
            gen = QLabel(self._data.generic_name)
            gen.setStyleSheet("color: #45475a; font-size: 9pt;")
            gen.setAlignment(Qt.AlignmentFlag.AlignCenter)
            preview_layout.addWidget(gen)

        if self._data.company:
            co = QLabel(self._data.company)
            co.setStyleSheet("color: #585b70; font-size: 8pt;")
            co.setAlignment(Qt.AlignmentFlag.AlignCenter)
            preview_layout.addWidget(co)

        preview_layout.addSpacing(4)

        # Barcode visual placeholder (text representation)
        barcode_lbl = QLabel(self._data.barcode or "NO BARCODE")
        barcode_lbl.setStyleSheet(
            "color: #1e1e2e; font-size: 14pt; font-weight: bold; "
            "font-family: 'Courier New', monospace; letter-spacing: 2px;"
        )
        barcode_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_layout.addWidget(barcode_lbl)

        # Price and batch info
        info_row = QHBoxLayout()
        if self._data.selling_price > 0:
            price_lbl = QLabel(f"Rs. {self._data.selling_price:.2f}")
            price_lbl.setStyleSheet("color: #1e1e2e; font-size: 10pt; font-weight: bold;")
            info_row.addWidget(price_lbl)

        info_row.addStretch()

        if self._data.batch_number:
            batch_lbl = QLabel(f"Batch: {self._data.batch_number}")
            batch_lbl.setStyleSheet("color: #585b70; font-size: 8pt;")
            info_row.addWidget(batch_lbl)
        preview_layout.addLayout(info_row)

        if self._data.expiry_date:
            exp_lbl = QLabel(f"Exp: {self._data.expiry_date}")
            exp_lbl.setStyleSheet("color: #585b70; font-size: 8pt;")
            preview_layout.addWidget(exp_lbl)

        layout.addWidget(preview_frame)

        # Print count
        count_row = QHBoxLayout()
        count_row.setSpacing(8)
        count_lbl = QLabel("Print Count:")
        count_lbl.setStyleSheet(f"color: {_SUBTEXT}; font-size: 10pt;")
        count_row.addWidget(count_lbl)

        self._count_spin = QSpinBox()
        self._count_spin.setRange(1, 100)
        self._count_spin.setValue(1)
        self._count_spin.setFixedWidth(80)
        count_row.addWidget(self._count_spin)
        count_row.addStretch()
        layout.addLayout(count_row)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        self._print_btn = QPushButton("\U0001f5a8\ufe0f  Print Label")
        self._print_btn.setObjectName("PrimaryButton")
        self._print_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._print_btn.clicked.connect(self._on_print)
        btn_row.addWidget(self._print_btn)

        layout.addLayout(btn_row)

    def _on_print(self) -> None:
        """Generate PDF label(s) and send to printer."""
        if not self._data.barcode:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self, "No Barcode",
                "This medicine does not have a barcode assigned.",
            )
            return

        count = self._count_spin.value()
        try:
            pdf_path = self._generate_label_pdf()
            from app.services.receipt_service import ReceiptService
            if ReceiptService.print_pdf(pdf_path):
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.information(
                    self, "Printed",
                    f"{count} label(s) sent to the default printer.",
                )
                self.accept()
            else:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(
                    self, "Print Failed",
                    "Could not send the print job. Check your printer.",
                )
        except Exception as exc:
            logger.exception("Label print failed")
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Print Error", str(exc))

    def _generate_label_pdf(self) -> Path:
        """Generate a PDF with the label, printed N times on one page."""
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas

        count = self._count_spin.value()
        tmp = Path(tempfile.gettempdir())
        pdf_path = tmp / f"barcode_label_{self._data.barcode}.pdf"

        c = canvas.Canvas(str(pdf_path), pagesize=A4)
        page_w, page_h = A4

        # Label dimensions: ~50mm x 30mm
        label_w = 50 * mm
        label_h = 30 * mm
        margin_x = 10 * mm
        margin_y = 15 * mm

        cols = max(1, int((page_w - 2 * margin_x) / label_w))
        rows = max(1, int((page_h - 2 * margin_y) / label_h))
        per_page = cols * rows

        for idx in range(count):
            page_idx = idx % per_page
            if idx > 0 and page_idx == 0:
                c.showPage()

            col = page_idx % cols
            row = page_idx // cols

            x = margin_x + col * label_w
            y = page_h - margin_y - (row + 1) * label_h

            # Draw label border
            c.setStrokeColorRGB(0.3, 0.3, 0.3)
            c.setLineWidth(0.5)
            c.roundRect(x, y, label_w, label_h, 3)

            # Medicine name (top, bold)
            c.setFillColorRGB(0.1, 0.1, 0.1)
            c.setFont("Helvetica-Bold", 8)
            name = self._data.medicine_name
            if len(name) > 25:
                name = name[:22] + "..."
            c.drawCentredString(x + label_w / 2, y + label_h - 12, name)

            # Generic name
            c.setFont("Helvetica", 6)
            c.setFillColorRGB(0.3, 0.3, 0.3)
            gen = self._data.generic_name
            if gen and len(gen) > 30:
                gen = gen[:27] + "..."
            if gen:
                c.drawCentredString(x + label_w / 2, y + label_h - 20, gen)

            # Barcode text (center)
            c.setFillColorRGB(0.1, 0.1, 0.1)
            c.setFont("Courier-Bold", 9)
            c.drawCentredString(x + label_w / 2, y + label_h - 30, self._data.barcode)

            # Price (bottom left)
            if self._data.selling_price > 0:
                c.setFont("Helvetica-Bold", 7)
                c.setFillColorRGB(0.1, 0.1, 0.1)
                c.drawString(x + 4, y + 4, f"Rs. {self._data.selling_price:.0f}")

            # Batch (bottom right)
            if self._data.batch_number:
                c.setFont("Helvetica", 5)
                c.setFillColorRGB(0.4, 0.4, 0.4)
                c.drawRightString(x + label_w - 4, y + 4, f"B:{self._data.batch_number}")

        c.save()
        return pdf_path
