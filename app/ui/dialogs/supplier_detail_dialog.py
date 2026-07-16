from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.services.supplier_service import SupplierDetail
from app.ui.theme import Theme


class SupplierDetailDialog(QDialog):
    """Dialog showing full supplier details with purchase history and stats."""

    def __init__(
        self,
        detail: SupplierDetail,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Supplier — {detail.supplier_name}")
        self.setMinimumSize(800, 560)
        self.setModal(True)
        self._detail = detail
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(16)

        d = self._detail

        title = QLabel(d.supplier_name)
        title.setObjectName("PageTitle")
        root.addWidget(title)

        info_grid = QHBoxLayout()
        info_grid.setSpacing(24)

        left_col = QVBoxLayout()
        left_col.setSpacing(6)
        left_col.addWidget(self._info_row("Contact Person", d.contact_person or "—"))
        left_col.addWidget(self._info_row("Phone", d.phone or "—"))
        left_col.addWidget(self._info_row("Email", d.email or "—"))
        left_col.addWidget(self._info_row("Address", d.address or "—"))
        info_grid.addLayout(left_col, 1)

        right_col = QVBoxLayout()
        right_col.setSpacing(6)
        right_col.addWidget(self._info_row("PAN Number", d.pan_number or "—"))
        right_col.addWidget(self._info_row("Registration No", d.registration_number or "—"))
        status_color = Theme.success() if d.status == "Active" else Theme.danger()
        right_col.addWidget(self._info_row("Status", d.status, status_color))
        right_col.addWidget(self._info_row(
            "Outstanding Balance", f"Rs. {d.outstanding_balance:,.2f}",
            Theme.warning() if d.outstanding_balance > 0 else None,
        ))
        info_grid.addLayout(right_col, 1)

        root.addLayout(info_grid)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {Theme.border()};")
        root.addWidget(sep)

        stats_grid = QHBoxLayout()
        stats_grid.setSpacing(20)
        stats_grid.addWidget(self._stat_card("Total Orders", str(d.total_orders)))
        stats_grid.addWidget(self._stat_card(
            "Total Purchased", f"Rs. {d.total_purchases:,.2f}"
        ))
        stats_grid.addWidget(self._stat_card(
            "Avg Purchase Value", f"Rs. {d.average_purchase_value:,.2f}"
        ))
        stats_grid.addWidget(self._stat_card("Last Invoice", d.last_invoice or "—"))
        root.addLayout(stats_grid)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(f"color: {Theme.border()};")
        root.addWidget(sep2)

        hist_label = QLabel("Purchase History")
        hist_label.setObjectName("SectionTitle")
        root.addWidget(hist_label)

        self._table = QTableWidget()
        self._table.setObjectName("InventoryTable")
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels([
            "Invoice #", "Date", "Items", "Total Amount"
        ])
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(0, hdr.ResizeMode.Stretch)
        hdr.setSectionResizeMode(1, hdr.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(2, hdr.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(3, hdr.ResizeMode.ResizeToContents)

        self._populate_table(d.purchases)
        root.addWidget(self._table, 1)

    def _info_row(self, label: str, value: str, color: str | None = None) -> QWidget:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        lbl = QLabel(f"{label}:")
        lbl.setStyleSheet(f"color: {Theme.text2()}; font-size: 10pt; min-width: 130px;")
        row.addWidget(lbl)

        val = QLabel(value)
        style = "font-size: 10pt; font-weight: bold;"
        if color:
            style += f" color: {color};"
        else:
            style += f" color: {Theme.text()};"
        val.setStyleSheet(style)
        row.addWidget(val)
        row.addStretch()

        container = QWidget()
        container.setLayout(row)
        return container

    def _stat_card(self, label: str, value: str) -> QFrame:
        card = QFrame()
        card.setObjectName("DashboardCard")
        card.setFixedHeight(72)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(2)

        val_lbl = QLabel(value)
        val_lbl.setStyleSheet(f"font-size: 14pt; font-weight: bold; color: {Theme.accent()};")
        layout.addWidget(val_lbl)

        name_lbl = QLabel(label)
        name_lbl.setStyleSheet(f"font-size: 9pt; color: {Theme.text2()};")
        layout.addWidget(name_lbl)

        return card

    def _populate_table(self, purchases) -> None:
        self._table.setRowCount(len(purchases))
        for i, p in enumerate(purchases):
            vals = [
                p.invoice_number,
                p.purchase_date,
                str(p.item_count),
                f"Rs. {p.total_amount:,.2f}",
            ]
            for j, val in enumerate(vals):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter)
                if j == 3:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                self._table.setItem(i, j, item)
