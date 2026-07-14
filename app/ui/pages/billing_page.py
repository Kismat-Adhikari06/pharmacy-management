from __future__ import annotations

import logging
from datetime import date

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.services.billing_service import (
    BillItem,
    BillingService,
    ExpiredMedicineError,
    InsufficientStockError,
    MedicineSearchResult,
    NoStockError,
    SaleValidationError,
)
from app.services.receipt_service import ReceiptData, ReceiptService
from app.ui.dialogs.payment_dialog import PaymentDialog
from app.ui.dialogs.receipt_preview_dialog import ReceiptPreviewDialog
from app.ui.pages.base_page import BasePage

logger = logging.getLogger(__name__)


class BillingPage(BasePage):
    """Point-of-sale / billing page — keyboard-first POS layout."""

    # Emitted when a sale is completed; carries bill_number and total
    sale_completed = Signal(str, float)

    # Left-panel result card
    # ───────────────────────────────────────────────────────────────
    class _MedicineCard(QFrame):
        """Clickable card for a single medicine in the search results."""

        clicked = Signal(int)  # medicine_id

        def __init__(
            self,
            med: MedicineSearchResult,
            parent: QWidget | None = None,
        ) -> None:
            super().__init__(parent)
            self._med = med
            self.setObjectName("MedicineCard")
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.setFixedHeight(60)
            self._build_ui()

        def _build_ui(self) -> None:
            row = QHBoxLayout(self)
            row.setContentsMargins(12, 6, 12, 6)
            row.setSpacing(12)

            left = QVBoxLayout()
            left.setSpacing(2)

            name = QLabel(self._med.medicine_name)
            name.setStyleSheet("font-weight: bold; font-size: 10pt;")
            left.addWidget(name)

            detail = QLabel(
                f"{self._med.generic_name}  |  {self._med.company}"
            )
            detail.setStyleSheet("color: #a6adc8; font-size: 9pt;")
            left.addWidget(detail)
            row.addLayout(left, stretch=1)

            right = QVBoxLayout()
            right.setSpacing(2)
            right.setAlignment(Qt.AlignmentFlag.AlignRight)

            price = QLabel(f"Rs. {self._med.selling_price:.2f}")
            price.setStyleSheet(
                "color: #a6e3a1; font-weight: bold; font-size: 10pt;"
            )
            price.setAlignment(Qt.AlignmentFlag.AlignRight)
            right.addWidget(price)

            stock = QLabel(f"Stock: {self._med.total_stock}")
            stock.setStyleSheet("color: #a6adc8; font-size: 9pt;")
            stock.setAlignment(Qt.AlignmentFlag.AlignRight)
            right.addWidget(stock)
            row.addLayout(right)

        def mousePressEvent(self, event) -> None:  # noqa: N802
            if event.button() == Qt.MouseButton.LeftButton:
                self.clicked.emit(self._med.medicine_id)
            super().mousePressEvent(event)

    # ───────────────────────────────────────────────────────────────
    # BillingPage
    # ───────────────────────────────────────────────────────────────

    def __init__(self, parent: QWidget | None = None) -> None:
        self._bill_items: list[BillItem] = []
        self._vat_rate: float = 13.0  # Nepal VAT default
        self._last_sale_bill: str | None = None
        self._debounce = QTimer()
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(250)
        self._debounce.timeout.connect(self._execute_search)
        super().__init__(
            title="Billing (POS)",
            description="",
            icon="",
            parent=parent,
        )

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        # ── Left: search + results ───────────────────────────
        left = QFrame()
        left.setObjectName("ContentArea")
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(12, 12, 8, 12)
        left_layout.setSpacing(8)

        search_row = QHBoxLayout()
        search_row.setSpacing(8)

        self._search_input = QLineEdit()
        self._search_input.setObjectName("SearchBox")
        self._search_input.setPlaceholderText(
            "Search medicine name, generic, company, or scan barcode…"
        )
        self._search_input.setClearButtonEnabled(True)
        self._search_input.textChanged.connect(self._on_search_changed)
        self._search_input.setFixedHeight(36)
        search_row.addWidget(self._search_input, stretch=1)

        self._search_btn = QPushButton("Search")
        self._search_btn.setObjectName("ToolbarButton")
        self._search_btn.setFixedSize(70, 36)
        self._search_btn.clicked.connect(self._on_search_changed)
        search_row.addWidget(self._search_btn)

        left_layout.addLayout(search_row)

        self._results_label = QLabel("Type to search medicines…")
        self._results_label.setObjectName("StockLabel")
        left_layout.addWidget(self._results_label)

        self._results_scroll = QFrame()
        self._results_layout = QVBoxLayout(self._results_scroll)
        self._results_layout.setContentsMargins(0, 0, 0, 0)
        self._results_layout.setSpacing(4)
        self._results_layout.addStretch()
        left_layout.addWidget(self._results_scroll, stretch=1)

        # ── Right: bill table + summary ──────────────────────
        right = QFrame()
        right.setObjectName("ContentArea")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(8, 12, 12, 12)
        right_layout.setSpacing(8)

        title_row = QHBoxLayout()
        title = QLabel("Current Bill")
        title.setObjectName("SectionTitle")
        title_row.addWidget(title)
        title_row.addStretch()

        self._bill_label = QLabel("")
        self._bill_label.setStyleSheet("color: #a6adc8; font-size: 9pt;")
        title_row.addWidget(self._bill_label)

        right_layout.addLayout(title_row)

        self._bill_table = QTableWidget()
        self._bill_table.setColumnCount(6)
        self._bill_table.setHorizontalHeaderLabels(
            ["#", "Medicine", "Batch", "Qty", "Unit Price", "Total"]
        )
        header = self._bill_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self._bill_table.setColumnWidth(0, 30)
        self._bill_table.setColumnWidth(2, 100)
        self._bill_table.setColumnWidth(3, 60)
        self._bill_table.setColumnWidth(4, 90)
        self._bill_table.setColumnWidth(5, 90)
        self._bill_table.verticalHeader().setVisible(False)
        self._bill_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._bill_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self._bill_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self._bill_table.setAlternatingRowColors(True)
        self._bill_table.setShowGrid(False)
        right_layout.addWidget(self._bill_table, stretch=1)

        # ── Summary ──────────────────────────────────────────
        summary_frame = QFrame()
        summary_frame.setObjectName("MedicineCard")
        summary_frame.setFixedHeight(130)
        sf_layout = QVBoxLayout(summary_frame)
        sf_layout.setContentsMargins(12, 8, 12, 8)
        sf_layout.setSpacing(4)

        self._subtotal_label = self._summary_row(sf_layout, "Subtotal")
        self._discount_label = self._summary_row(sf_layout, "Discount", color="#f38ba8")
        self._vat_label = self._summary_row(sf_layout, "VAT (13%)")
        self._total_label = self._summary_row(
            sf_layout, "Grand Total", bold=True, color="#a6e3a1"
        )
        right_layout.addWidget(summary_frame)

        # ── Action buttons ───────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        clear_btn = QPushButton("Clear Bill  (Ctrl+D)")
        clear_btn.setObjectName("ToolbarButton")
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.clicked.connect(self._clear_bill)
        btn_row.addWidget(clear_btn)

        btn_row.addStretch()

        self._preview_btn = QPushButton("Preview  (Ctrl+P)")
        self._preview_btn.setObjectName("ToolbarButton")
        self._preview_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._preview_btn.setEnabled(False)
        self._preview_btn.clicked.connect(self._preview_receipt)
        btn_row.addWidget(self._preview_btn)

        self._save_pdf_btn = QPushButton("Save PDF")
        self._save_pdf_btn.setObjectName("ToolbarButton")
        self._save_pdf_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._save_pdf_btn.setEnabled(False)
        self._save_pdf_btn.clicked.connect(self._save_receipt_pdf)
        btn_row.addWidget(self._save_pdf_btn)

        self._print_btn = QPushButton("Print  (F10)")
        self._print_btn.setObjectName("ToolbarButton")
        self._print_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._print_btn.setEnabled(False)
        self._print_btn.clicked.connect(self._print_receipt)
        btn_row.addWidget(self._print_btn)

        pay_btn = QPushButton("Pay  (F8)")
        pay_btn.setObjectName("PrimaryButton")
        pay_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        pay_btn.setFixedHeight(36)
        pay_btn.clicked.connect(self._open_payment)
        btn_row.addWidget(pay_btn)

        right_layout.addLayout(btn_row)

        # ── Keyboard shortcuts ───────────────────────────────
        self._search_input.setShortcut("F4")
        pay_btn.setShortcut("F8")
        self._print_btn.setShortcut("F10")
        self._preview_btn.setShortcut("Ctrl+P")

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([400, 500])
        root.addWidget(splitter)

        self._debounce.timeout.connect(self._execute_search)

    # ── Summary row helper ──────────────────────────────────────
    def _summary_row(
        self,
        parent_layout: QVBoxLayout,
        label_text: str,
        bold: bool = False,
        color: str = "#cdd6f4",
    ) -> QLabel:
        row = QHBoxLayout()
        lbl = QLabel(label_text)
        lbl.setStyleSheet(f"color: #a6adc8; font-size: 10pt;")
        row.addWidget(lbl)
        row.addStretch()
        val = QLabel("Rs. 0.00")
        weight = "bold" if bold else "normal"
        val.setStyleSheet(
            f"color: {color}; font-size: 11pt; font-weight: {weight};"
        )
        row.addWidget(val)
        parent_layout.addLayout(row)
        return val

    # ── Search ──────────────────────────────────────────────────
    def _on_search_changed(self) -> None:
        self._debounce.start()

    def _execute_search(self) -> None:
        query = self._search_input.text().strip()
        if not query:
            self._results_label.setText("Type to search medicines…")
            self._clear_cards()
            return

        try:
            results = BillingService.search_medicines(query)
        except Exception as exc:
            logger.exception("POS search failed")
            QMessageBox.warning(self, "Search Error", str(exc))
            return

        self._clear_cards()
        self._results_label.setText(
            f"{len(results)} medicine{'s' if len(results) != 1 else ''} found"
        )

        for med in results:
            card = self._MedicineCard(med)
            card.clicked.connect(self._add_medicine)
            self._results_layout.insertWidget(self._results_layout.count() - 1, card)

    def _clear_cards(self) -> None:
        while self._results_layout.count():
            item = self._results_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    # ── Add medicine to bill ────────────────────────────────────
    def _add_medicine(self, medicine_id: int) -> None:
        try:
            batches = BillingService.get_fefo_batches(medicine_id)
        except Exception as exc:
            logger.exception("Failed to fetch batches")
            QMessageBox.warning(self, "Error", str(exc))
            return

        if not batches:
            QMessageBox.information(
                self, "No Stock", "No available batches for this medicine."
            )
            return

        # If only one batch with stock, add directly with qty 1
        if len(batches) == 1:
            bid, bnum, exp, price, max_qty = batches[0]
            existing = self._find_item(bid)
            if existing:
                if existing.quantity < max_qty:
                    existing.quantity += 1
                else:
                    QMessageBox.information(
                        self,
                        "Max Stock",
                        f"Only {max_qty} units available in this batch.",
                    )
                    return
            else:
                self._bill_items.append(
                    BillItem(
                        medicine_id=medicine_id,
                        medicine_name=self._get_medicine_name(medicine_id),
                        batch_id=bid,
                        batch_number=bnum,
                        expiry_date=exp.strftime("%Y-%m-%d"),
                        quantity=1,
                        unit_price=price,
                    )
                )
            self._refresh_table()
            return

        # Multiple batches — show quantity picker for earliest-expiry batch
        batch = batches[0]
        bid, bnum, exp, price, max_qty = batch

        from PySide6.QtWidgets import QDialog, QSpinBox

        dlg = QDialog(self)
        dlg.setWindowTitle("Select Quantity")
        dlg.setMinimumWidth(280)
        dlg_layout = QVBoxLayout(dlg)

        med_name = self._get_medicine_name(medicine_id)
        info = QLabel(f"{med_name}\nBatch: {bnum}\nExpires: {exp.strftime('%Y-%m-%d')}")
        info.setObjectName("SectionTitle")
        info.setWordWrap(True)
        dlg_layout.addWidget(info)

        stock_info = QLabel(f"Available: {max_qty} units")
        stock_info.setStyleSheet("color: #a6adc8;")
        dlg_layout.addWidget(stock_info)

        qty_row = QHBoxLayout()
        qty_row.addWidget(QLabel("Quantity:"))
        qty_spin = QSpinBox()
        qty_spin.setRange(1, max_qty)
        qty_spin.setValue(1)
        qty_spin.setFixedWidth(80)
        qty_row.addWidget(qty_spin)
        dlg_layout.addLayout(qty_row)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(dlg.reject)
        btn_row.addWidget(cancel)
        add = QPushButton("Add")
        add.setObjectName("PrimaryButton")
        add.clicked.connect(dlg.accept)
        btn_row.addWidget(add)
        dlg_layout.addLayout(btn_row)

        if dlg.exec() == QDialog.DialogCode.Accepted:
            qty = qty_spin.value()
            existing = self._find_item(bid)
            if existing:
                new_qty = existing.quantity + qty
                if new_qty > max_qty:
                    QMessageBox.information(
                        self,
                        "Max Stock",
                        f"Cannot exceed {max_qty} units for batch {bnum}.",
                    )
                    return
                existing.quantity = new_qty
            else:
                self._bill_items.append(
                    BillItem(
                        medicine_id=medicine_id,
                        medicine_name=med_name,
                        batch_id=bid,
                        batch_number=bnum,
                        expiry_date=exp.strftime("%Y-%m-%d"),
                        quantity=qty,
                        unit_price=price,
                    )
                )
            self._refresh_table()

    def _find_item(self, batch_id: int) -> BillItem | None:
        for item in self._bill_items:
            if item.batch_id == batch_id:
                return item
        return None

    def _get_medicine_name(self, medicine_id: int) -> str:
        try:
            results = BillingService.search_medicines(str(medicine_id))
            for r in results:
                if r.medicine_id == medicine_id:
                    return r.medicine_name
        except Exception:
            pass
        return f"Medicine #{medicine_id}"

    # ── Table ───────────────────────────────────────────────────
    def _refresh_table(self) -> None:
        self._bill_table.setRowCount(len(self._bill_items))
        subtotal = 0.0

        for i, item in enumerate(self._bill_items):
            row_total = item.line_total
            subtotal += row_total

            self._bill_table.setItem(i, 0, self._centered(str(i + 1)))
            self._bill_table.setItem(i, 1, QTableWidgetItem(item.medicine_name))
            self._bill_table.setItem(
                i, 2, self._centered(item.batch_number)
            )

            qty_spin = QSpinBox()
            qty_spin.setRange(1, 9999)
            qty_spin.setValue(item.quantity)
            qty_spin.setFixedWidth(58)
            qty_spin.valueChanged.connect(
                lambda val, idx=i: self._on_qty_changed(idx, val)
            )
            self._bill_table.setCellWidget(i, 3, qty_spin)

            self._bill_table.setItem(
                i, 4, self._right_aligned(f"{item.unit_price:.2f}")
            )
            self._bill_table.setItem(
                i, 5, self._right_aligned(f"{row_total:.2f}")
            )

        self._update_summary(subtotal)

    def _on_qty_changed(self, row_idx: int, new_qty: int) -> None:
        if 0 <= row_idx < len(self._bill_items):
            self._bill_items[row_idx].quantity = new_qty
            self._refresh_table()

    def _centered(self, text: str) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        return item

    def _right_aligned(self, text: str) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setTextAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        return item

    def _update_summary(self, subtotal: float) -> None:
        vat = subtotal * self._vat_rate / 100.0
        grand = subtotal + vat
        self._subtotal_label.setText(f"Rs. {subtotal:.2f}")
        self._discount_label.setText("Rs. 0.00")
        self._vat_label.setText(f"Rs. {vat:.2f}")
        self._total_label.setText(f"Rs. {grand:.2f}")
        self._bill_label.setText(
            f"{len(self._bill_items)} item{'s' if len(self._bill_items) != 1 else ''}"
        )

    # ── Remove / Clear ──────────────────────────────────────────
    def _remove_selected(self) -> None:
        row = self._bill_table.currentRow()
        if 0 <= row < len(self._bill_items):
            self._bill_items.pop(row)
            self._refresh_table()

    def _clear_bill(self) -> None:
        if not self._bill_items:
            return
        reply = QMessageBox.question(
            self,
            "Clear Bill",
            "Remove all items from the current bill?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._bill_items.clear()
            self._refresh_table()

    # ── Payment ─────────────────────────────────────────────────
    def _open_payment(self) -> None:
        if not self._bill_items:
            QMessageBox.information(
                self, "Empty Bill", "Add medicines to the bill before payment."
            )
            return

        subtotal = sum(item.line_total for item in self._bill_items)
        vat = subtotal * self._vat_rate / 100.0
        grand_total = subtotal + vat

        dlg = PaymentDialog(
            parent=self,
            grand_total=grand_total,
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            if data is None:
                return
            self._complete_sale(
                payment_method=data["payment_method"],
                discount=data["discount"],
                subtotal=subtotal,
                vat=vat,
                cash_received=data.get("cash_received", 0.0),
            )

    def _complete_sale(
        self,
        payment_method: str,
        discount: float,
        subtotal: float,
        vat: float,
        cash_received: float = 0.0,
    ) -> None:
        try:
            result = BillingService.create_sale(
                bill_items=self._bill_items,
                payment_method=payment_method,
                discount=discount,
                vat_rate=self._vat_rate,
            )
        except (
            InsufficientStockError,
            ExpiredMedicineError,
            SaleValidationError,
            NoStockError,
        ) as exc:
            QMessageBox.warning(self, "Sale Error", str(exc))
            return
        except Exception as exc:
            logger.exception("Unexpected sale error")
            QMessageBox.critical(self, "Error", f"Failed to save sale: {exc}")
            return

        self._last_sale_bill = result.bill_number
        self._preview_btn.setEnabled(True)
        self._save_pdf_btn.setEnabled(True)
        self._print_btn.setEnabled(True)

        grand = subtotal + vat
        change = cash_received - (grand - discount) if payment_method == "Cash" else 0.0

        msg = (
            f"Bill: {result.bill_number}\n"
            f"Total: Rs. {result.total_amount:.2f}\n"
            f"Payment: {payment_method}"
        )
        if payment_method == "Cash":
            msg += f"\nCash: Rs. {cash_received:.2f}\nChange: Rs. {change:.2f}"

        QMessageBox.information(self, "Sale Complete", msg)

        self._bill_items.clear()
        self._refresh_table()
        self._search_input.clear()
        self._clear_cards()
        self.sale_completed.emit(result.bill_number, result.total_amount)

    # ── Receipt actions ─────────────────────────────────────────
    def _build_receipt_data(self) -> ReceiptData | None:
        if self._last_sale_bill is None:
            return None
        data = ReceiptService.load_sale_data(bill_number=self._last_sale_bill)
        if data and self._last_sale_bill:
            data.change_returned = max(
                0.0, data.cash_received - (data.grand_total - data.discount)
            )
        return data

    def _preview_receipt(self) -> None:
        data = self._build_receipt_data()
        if data is None:
            QMessageBox.information(self, "No Sale", "No recent sale to preview.")
            return
        dlg = ReceiptPreviewDialog(data, parent=self)
        dlg.exec()

    def _save_receipt_pdf(self) -> None:
        data = self._build_receipt_data()
        if data is None:
            QMessageBox.information(self, "No Sale", "No recent sale to save.")
            return
        dlg = ReceiptPreviewDialog(data, parent=self)
        dlg._save_pdf()

    def _print_receipt(self) -> None:
        data = self._build_receipt_data()
        if data is None:
            QMessageBox.information(self, "No Sale", "No recent sale to print.")
            return
        temp_dir = ReceiptService.get_temp_dir()
        pdf_path = temp_dir / f"{data.bill_number}_receipt.pdf"
        try:
            ReceiptService.generate_pdf(data, pdf_path, paper="80mm")
            if ReceiptService.print_pdf(pdf_path):
                QMessageBox.information(
                    self, "Print", "Print job sent to default printer."
                )
            else:
                QMessageBox.warning(
                    self, "Print", "Failed to send print job."
                )
        except Exception as exc:
            QMessageBox.critical(self, "Print Error", str(exc))

    # ── Keyboard ────────────────────────────────────────────────
    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Delete:
            self._remove_selected()
        else:
            super().keyPressEvent(event)
