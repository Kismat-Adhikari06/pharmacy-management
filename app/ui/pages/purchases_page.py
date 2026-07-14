from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.services.purchase_service import PurchaseService
from app.ui.dialogs.new_purchase_dialog import NewPurchaseDialog


class PurchasesPage(QWidget):
    """Purchase management page with history table."""

    COLUMNS: list[tuple[str, int]] = [
        ("Invoice", 160),
        ("Supplier", 200),
        ("Date", 110),
        ("Items", 70),
        ("Total", 130),
    ]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ContentArea")
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(250)
        self._search_timer.timeout.connect(self._do_search)
        self._build_ui()
        self.refresh_data()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        title = QLabel("Purchases")
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        new_btn = QPushButton("\u2795  New Purchase")
        new_btn.setObjectName("ToolbarButton")
        new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        new_btn.clicked.connect(self._on_new_purchase)
        toolbar.addWidget(new_btn)

        refresh_btn = QPushButton("\U0001f504  Refresh")
        refresh_btn.setObjectName("ToolbarButton")
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.clicked.connect(self.refresh_data)
        toolbar.addWidget(refresh_btn)

        toolbar.addStretch()

        self._search_edit = QLineEdit()
        self._search_edit.setObjectName("SearchBox")
        self._search_edit.setPlaceholderText("\U0001f50d  Search invoice...")
        self._search_edit.setFixedWidth(260)
        self._search_edit.textChanged.connect(self._on_search_text_changed)
        toolbar.addWidget(self._search_edit)

        layout.addLayout(toolbar)

        self._table = QTableWidget()
        self._table.setObjectName("InventoryTable")
        self._table.setColumnCount(len(self.COLUMNS))
        self._table.setHorizontalHeaderLabels([c[0] for c in self.COLUMNS])
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setStretchLastSection(True)
        for i, (_, width) in enumerate(self.COLUMNS):
            self._table.setColumnWidth(i, width)
        self._table.doubleClicked.connect(self._on_view_detail)
        layout.addWidget(self._table)

        self._empty_label = QLabel("\U0001f4e6\n\nNo purchases found.")
        self._empty_label.setObjectName("EmptyState")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._empty_label)

        layout.addStretch()

    def refresh_data(self) -> None:
        term = self._search_edit.text().strip()
        rows = PurchaseService.search(term) if term else PurchaseService.get_all()
        self._populate_table(rows)

    def _populate_table(self, rows) -> None:
        self._table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            vals = [
                r.invoice_number,
                r.supplier_name,
                r.purchase_date,
                str(r.item_count),
                f"Rs. {r.total_amount:.2f}",
            ]
            for j, val in enumerate(vals):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter)
                if j == 0:
                    item.setData(Qt.ItemDataRole.UserRole, r.id)
                self._table.setItem(i, j, item)
        has = len(rows) > 0
        self._table.setVisible(has)
        self._empty_label.setVisible(not has)

    def _on_search_text_changed(self, _text: str) -> None:
        self._search_timer.start()

    def _do_search(self) -> None:
        self.refresh_data()

    def _on_new_purchase(self) -> None:
        dialog = NewPurchaseDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh_data()

    def _on_view_detail(self) -> None:
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            return
        row = rows[0].row()
        item = self._table.item(row, 0)
        if item is None:
            return
        purchase_id = item.data(Qt.ItemDataRole.UserRole)
        if purchase_id is None:
            return

        detail = PurchaseService.get_detail(purchase_id)
        if detail is None:
            QMessageBox.warning(self, "Not Found", "Purchase not found.")
            return

        lines = [
            f"Invoice: {detail.invoice_number}",
            f"Supplier: {detail.supplier_name}",
            f"Date: {detail.purchase_date}",
            f"Total: Rs. {detail.total_amount:.2f}",
            f"Notes: {detail.notes}" if detail.notes else "",
            "",
            "--- Items ---",
        ]
        for it in detail.items:
            line_total = it.quantity * it.purchase_price
            lines.append(
                f"  {it.medicine_name} | Batch: {it.batch_number} | "
                f"Exp: {it.expiry_date} | Qty: {it.quantity} | "
                f"Price: Rs. {it.purchase_price:.2f} | Total: Rs. {line_total:.2f}"
            )

        QMessageBox.information(self, "Purchase Detail", "\n".join(lines))
