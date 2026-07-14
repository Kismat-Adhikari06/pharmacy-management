from __future__ import annotations

import logging
from datetime import datetime

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.services.receipt_service import ReceiptService
from app.services.sales_history_service import SalesHistoryService
from app.ui.dialogs.receipt_preview_dialog import ReceiptPreviewDialog
from app.ui.pages.base_page import BasePage

logger = logging.getLogger(__name__)


class SalesHistoryPage(BasePage):
    """Sales history page with search, table, and double-click receipt preview."""

    def __init__(self, parent: QWidget | None = None) -> None:
        self._debounce = QTimer()
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(250)
        self._debounce.timeout.connect(self._execute_search)
        super().__init__(
            title="Sales History",
            description="View past sales and reprint receipts.",
            icon="📜",
            parent=parent,
        )

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # ── Toolbar ──────────────────────────────────────────
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setObjectName("ToolbarButton")
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.clicked.connect(self._load_data)
        toolbar.addWidget(refresh_btn)

        toolbar.addStretch()

        search_label = QLabel("Search Bill:")
        search_label.setStyleSheet("color: #a6adc8; font-size: 10pt;")
        toolbar.addWidget(search_label)

        self._search_input = QLineEdit()
        self._search_input.setObjectName("SearchBox")
        self._search_input.setPlaceholderText("Enter bill number…")
        self._search_input.setClearButtonEnabled(True)
        self._search_input.setFixedHeight(32)
        self._search_input.textChanged.connect(self._on_search_changed)
        toolbar.addWidget(self._search_input, stretch=0)

        self._receipt_btn = QPushButton("Preview Receipt")
        self._receipt_btn.setObjectName("ToolbarButton")
        self._receipt_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._receipt_btn.setEnabled(False)
        self._receipt_btn.clicked.connect(self._preview_selected)
        toolbar.addWidget(self._receipt_btn)

        self._reprint_btn = QPushButton("Reprint  (Ctrl+Shift+P)")
        self._reprint_btn.setObjectName("ToolbarButton")
        self._reprint_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._reprint_btn.setEnabled(False)
        self._reprint_btn.clicked.connect(self._reprint_selected)
        self._reprint_btn.setShortcut("Ctrl+Shift+P")
        toolbar.addWidget(self._reprint_btn)

        layout.addLayout(toolbar)

        # ── Table ─────────────────────────────────────────────
        self._table = QTableWidget()
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels(
            ["Bill Number", "Date", "Items", "Total", "Payment", "ID"]
        )
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Hidden)
        self._table.setColumnWidth(0, 170)
        self._table.setColumnWidth(1, 140)
        self._table.setColumnWidth(2, 60)
        self._table.setColumnWidth(3, 100)
        self._table.setColumnWidth(4, 100)
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self._table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        self._table.doubleClicked.connect(self._preview_selected)
        self._table.selectionModel().selectionChanged.connect(
            self._on_selection_changed
        )
        layout.addWidget(self._table, stretch=1)

        # ── Empty state ───────────────────────────────────────
        self._empty_label = QLabel("No sales recorded yet.")
        self._empty_label.setObjectName("EmptyState")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setVisible(False)
        layout.addWidget(self._empty_label)

        # ── Status ────────────────────────────────────────────
        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: #a6adc8; font-size: 9pt;")
        layout.addWidget(self._status_label)

        self._debounce.timeout.connect(self._execute_search)
        self._load_data()

    def _load_data(self) -> None:
        try:
            records = SalesHistoryService.get_all()
        except Exception as exc:
            logger.exception("Failed to load sales history")
            QMessageBox.warning(self, "Error", str(exc))
            return
        self._populate_table(records)

    def _populate_table(self, records) -> None:
        self._table.setRowCount(len(records))
        self._empty_label.setVisible(len(records) == 0)
        self._table.setVisible(len(records) > 0)

        for i, rec in enumerate(records):
            self._table.setItem(i, 0, QTableWidgetItem(rec.bill_number))
            self._table.setItem(i, 1, QTableWidgetItem(rec.sale_date))
            self._table.setItem(i, 2, self._centered(str(rec.item_count)))
            self._table.setItem(
                i, 3, self._right_aligned(f"Rs. {rec.total_amount:.2f}")
            )
            self._table.setItem(i, 4, QTableWidgetItem(rec.payment_method))
            self._table.setItem(i, 5, self._centered(str(rec.sale_id)))

        self._status_label.setText(f"{len(records)} sale{'s' if len(records) != 1 else ''} found")

    def _on_search_changed(self) -> None:
        self._debounce.start()

    def _execute_search(self) -> None:
        query = self._search_input.text().strip()
        if not query:
            self._load_data()
            return

        try:
            records = SalesHistoryService.search(query)
        except Exception as exc:
            logger.exception("Search failed")
            QMessageBox.warning(self, "Error", str(exc))
            return

        self._populate_table(records)

    def _on_selection_changed(self) -> None:
        has = len(self._table.selectionModel().selectedRows()) > 0
        self._receipt_btn.setEnabled(has)
        self._reprint_btn.setEnabled(has)

    def _get_selected_bill(self) -> tuple[int | None, str | None]:
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            return None, None
        row = rows[0].row()
        bill_item = self._table.item(row, 0)
        id_item = self._table.item(row, 5)
        if bill_item is None or id_item is None:
            return None, None
        try:
            sale_id = int(id_item.text())
        except ValueError:
            sale_id = None
        return sale_id, bill_item.text()

    def _preview_selected(self) -> None:
        sale_id, bill_number = self._get_selected_bill()
        if sale_id is None:
            QMessageBox.information(self, "No Selection", "Select a sale to preview.")
            return

        data = ReceiptService.load_sale_data(sale_id=sale_id)
        if data is None:
            QMessageBox.warning(self, "Not Found", "Could not load sale data.")
            return

        dlg = ReceiptPreviewDialog(data, parent=self)
        dlg.exec()

    def _reprint_selected(self) -> None:
        sale_id, bill_number = self._get_selected_bill()
        if sale_id is None:
            QMessageBox.information(self, "No Selection", "Select a sale to reprint.")
            return

        data = ReceiptService.load_sale_data(sale_id=sale_id)
        if data is None:
            QMessageBox.warning(self, "Not Found", "Could not load sale data.")
            return

        temp_dir = ReceiptService.get_temp_dir()
        pdf_path = temp_dir / f"{data.bill_number}_reprint.pdf"
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
