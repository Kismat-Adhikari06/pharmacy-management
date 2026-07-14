from __future__ import annotations

import logging

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.services.expiry_service import ExpiryBatch, ExpiryService, ExpirySummary

logger = logging.getLogger(__name__)

# ── Colour palette (matches dark.qss) ──────────────────────────
_BG = "#1e1e2e"
_CARD_BG = "#181825"
_BORDER = "#313244"
_TEXT = "#cdd6f4"
_SUBTEXT = "#a6adc8"
_BLUE = "#89b4fa"
_GREEN = "#a6e3a1"
_YELLOW = "#f9e2af"
_ORANGE = "#fab387"
_RED = "#f38ba8"


class ExpiryPage(QWidget):
    """Expiry management page with grouped alerts, filters, and export."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ContentArea")
        self._all_data: list[ExpiryBatch] = []
        self._current_filter: str = "All"
        self._build_ui()
        self._connect_signals()

    # ── UI construction ─────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setObjectName("ContentArea")

        container = QWidget()
        container.setObjectName("ContentArea")
        self._main_layout = QVBoxLayout(container)
        self._main_layout.setContentsMargins(20, 16, 20, 16)
        self._main_layout.setSpacing(16)

        # ── Header row ─────────────────────────────────────────
        hdr = QHBoxLayout()
        title = QLabel("⏰ Expiry Management")
        title.setObjectName("PageTitle")
        hdr.addWidget(title)
        hdr.addStretch()
        self._refresh_btn = QPushButton("\U0001f504 Refresh")
        self._refresh_btn.setObjectName("ToolbarButton")
        self._refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._refresh_btn.clicked.connect(self.refresh)
        hdr.addWidget(self._refresh_btn)
        self._main_layout.addLayout(hdr)

        # ── Summary cards ──────────────────────────────────────
        self._cards_grid = QGridLayout()
        self._cards_grid.setSpacing(12)
        self._main_layout.addLayout(self._cards_grid)

        # ── Filter bar ─────────────────────────────────────────
        filter_row = QHBoxLayout()
        filter_row.setSpacing(10)

        filter_row.addWidget(self._make_label("Category:"))
        self._category_combo = QComboBox()
        self._category_combo.setMinimumWidth(140)
        self._category_combo.currentIndexChanged.connect(self._apply_filters)
        filter_row.addWidget(self._category_combo)

        filter_row.addWidget(self._make_label("Company:"))
        self._company_combo = QComboBox()
        self._company_combo.setMinimumWidth(140)
        self._company_combo.currentIndexChanged.connect(self._apply_filters)
        filter_row.addWidget(self._company_combo)

        filter_row.addSpacing(16)

        filter_row.addWidget(self._make_label("Status:"))
        self._status_buttons: dict[str, QPushButton] = {}
        for label in ["All", "🔴 Expired", "🟠 30d", "🟡 60d", "🟢 90d"]:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, l=label: self._set_status_filter(l))
            self._status_buttons[label] = btn
            filter_row.addWidget(btn)

        filter_row.addStretch()

        self._export_csv_btn = QPushButton("📄 Export CSV")
        self._export_csv_btn.setObjectName("ToolbarButton")
        self._export_csv_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._export_csv_btn.clicked.connect(self._export_csv)
        filter_row.addWidget(self._export_csv_btn)

        self._export_excel_btn = QPushButton("📊 Export Excel")
        self._export_excel_btn.setObjectName("ToolbarButton")
        self._export_excel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._export_excel_btn.clicked.connect(self._export_excel)
        filter_row.addWidget(self._export_excel_btn)

        self._main_layout.addLayout(filter_row)

        # ── Table ──────────────────────────────────────────────
        self._table = self._create_table()
        self._main_layout.addWidget(self._table, stretch=1)

        # ── Count label ────────────────────────────────────────
        self._count_label = QLabel("Showing 0 items")
        self._count_label.setStyleSheet(f"color: {_SUBTEXT}; font-size: 9pt;")
        self._main_layout.addWidget(self._count_label)

        self._main_layout.addStretch()
        scroll.setWidget(container)
        root.addWidget(scroll)

        self._set_status_filter("All")

    # ── Helpers ─────────────────────────────────────────────────

    @staticmethod
    def _make_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {_SUBTEXT}; font-size: 9pt;")
        return lbl

    def _create_table(self) -> QTableWidget:
        table = QTableWidget()
        table.setColumnCount(9)
        table.setHorizontalHeaderLabels([
            "Status", "Medicine", "Generic", "Company", "Category",
            "Batch", "Expiry", "Qty", "Selling Price",
        ])
        header = table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for col in [0, 2, 3, 4, 5, 6, 7, 8]:
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.setShowGrid(False)
        table.setSortingEnabled(True)
        return table

    # ── Signal wiring ───────────────────────────────────────────

    def _connect_signals(self) -> None:
        pass

    # ── Filter logic ────────────────────────────────────────────

    def _set_status_filter(self, label: str) -> None:
        self._current_filter = label
        for name, btn in self._status_buttons.items():
            btn.setChecked(name == label)
        self._apply_filters()

    def _apply_filters(self) -> None:
        category = self._category_combo.currentText() or None
        company = self._company_combo.currentText() or None

        filtered = self._all_data

        if category:
            filtered = [d for d in filtered if d.category == category]
        if company:
            filtered = [d for d in filtered if d.company == company]

        status_map = {
            "🔴 Expired": "Expired",
            "🟠 30d": "Critical",
            "🟡 60d": "Warning",
            "🟢 90d": "Caution",
        }
        if self._current_filter in status_map:
            target = status_map[self._current_filter]
            filtered = [d for d in filtered if d.status == target]

        # Sort: Expired first, then by days_until ascending
        status_order = {"Expired": 0, "Critical": 1, "Warning": 2, "Caution": 3}
        filtered.sort(key=lambda d: (status_order.get(d.status, 99), d.days_until))

        self._populate_table(filtered)
        self._count_label.setText(f"Showing {len(filtered)} of {len(self._all_data)} items")

    def _load_filter_options(self) -> None:
        categories = ExpiryService.get_categories()
        companies = ExpiryService.get_companies()

        prev_cat = self._category_combo.currentText()
        prev_co = self._company_combo.currentText()

        self._category_combo.blockSignals(True)
        self._company_combo.blockSignals(True)

        self._category_combo.clear()
        self._category_combo.addItem("")
        self._category_combo.addItems(categories)

        self._company_combo.clear()
        self._company_combo.addItem("")
        self._company_combo.addItems(companies)

        # Restore previous selection if still available
        idx = self._category_combo.findText(prev_cat)
        if idx >= 0:
            self._category_combo.setCurrentIndex(idx)
        idx = self._company_combo.findText(prev_co)
        if idx >= 0:
            self._company_combo.setCurrentIndex(idx)

        self._category_combo.blockSignals(False)
        self._company_combo.blockSignals(False)

    # ── Data loading ────────────────────────────────────────────

    def refresh(self) -> None:
        """Reload all expiry data from the database."""
        try:
            self._all_data = ExpiryService.get_expiring_batches()
            self._load_filter_options()
            self._load_summary_cards()
            self._apply_filters()
        except Exception:
            logger.exception("Failed to load expiry data")

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        QTimer.singleShot(0, self.refresh)

    def _load_summary_cards(self) -> None:
        while self._cards_grid.count():
            item = self._cards_grid.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        summary = ExpiryService.get_expiry_summary()
        cards = [
            ("🔴", "Expired", str(summary.expired_count), f"{summary.expired_qty} units", _RED),
            ("🟠", "≤ 30 Days", str(summary.critical_count), "Critical", _ORANGE),
            ("🟡", "≤ 60 Days", str(summary.warning_count), "Warning", _YELLOW),
            ("🟢", "≤ 90 Days", str(summary.caution_count), "Caution", _GREEN),
        ]
        for i, (icon, label, value, sub, color) in enumerate(cards):
            widget = self._make_stat_card(icon, label, value, sub, color)
            self._cards_grid.addWidget(widget, 0, i)

    @staticmethod
    def _make_stat_card(icon: str, label: str, value: str, sub: str, color: str) -> QWidget:
        wrapper = QFrame()
        wrapper.setObjectName("DashboardCard")
        wrapper.setFixedHeight(90)
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(2)

        icon_lbl = QLabel(icon)
        icon_lbl.setStyleSheet("font-size: 18pt;")
        layout.addWidget(icon_lbl)

        val = QLabel(value)
        val.setStyleSheet(f"font-size: 14pt; font-weight: bold; color: {color};")
        layout.addWidget(val)

        lbl = QLabel(f"{label} — {sub}")
        lbl.setStyleSheet(f"font-size: 9pt; color: {_SUBTEXT};")
        layout.addWidget(lbl)

        return wrapper

    def _populate_table(self, items: list[ExpiryBatch]) -> None:
        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(items))
        for i, item in enumerate(items):
            # Status with color
            status_item = QTableWidgetItem(item.status)
            if item.status == "Expired":
                status_item.setForeground(QColor(_RED))
            elif item.status == "Critical":
                status_item.setForeground(QColor(_ORANGE))
            elif item.status == "Warning":
                status_item.setForeground(QColor(_YELLOW))
            else:
                status_item.setForeground(QColor(_GREEN))
            self._table.setItem(i, 0, status_item)

            self._table.setItem(i, 1, QTableWidgetItem(item.medicine_name))
            self._table.setItem(i, 2, QTableWidgetItem(item.generic_name))
            self._table.setItem(i, 3, QTableWidgetItem(item.company))
            self._table.setItem(i, 4, QTableWidgetItem(item.category))
            self._table.setItem(i, 5, QTableWidgetItem(item.batch_number))

            exp_item = QTableWidgetItem(item.expiry_date)
            if item.days_until < 0:
                exp_item.setForeground(QColor(_RED))
            elif item.days_until <= 30:
                exp_item.setForeground(QColor(_ORANGE))
            elif item.days_until <= 60:
                exp_item.setForeground(QColor(_YELLOW))
            else:
                exp_item.setForeground(QColor(_GREEN))
            self._table.setItem(i, 6, exp_item)

            qty_item = _centered(str(item.quantity))
            if item.quantity == 0:
                qty_item.setForeground(QColor(_RED))
            self._table.setItem(i, 7, qty_item)

            self._table.setItem(i, 8, _right_aligned(f"Rs. {item.selling_price:,.2f}"))

        self._table.setSortingEnabled(True)

    # ── Export ──────────────────────────────────────────────────

    def _get_visible_rows(self) -> tuple[list[str], list[list[str]]]:
        headers = [
            "Status", "Medicine", "Generic", "Company", "Category",
            "Batch", "Expiry", "Qty", "Selling Price",
        ]
        rows: list[list[str]] = []
        for r in range(self._table.rowCount()):
            row_data = []
            for c in range(self._table.columnCount()):
                item = self._table.item(r, c)
                row_data.append(item.text() if item else "")
            rows.append(row_data)
        return headers, rows

    def _export_csv(self) -> None:
        from PySide6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getSaveFileName(
            self, "Export CSV", "expiry_report.csv", "CSV Files (*.csv)"
        )
        if path:
            headers, rows = self._get_visible_rows()
            ExpiryService.export_csv(headers, rows, path)

    def _export_excel(self) -> None:
        from PySide6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getSaveFileName(
            self, "Export Excel", "expiry_report.xml", "Excel Files (*.xml)"
        )
        if path:
            headers, rows = self._get_visible_rows()
            ExpiryService.export_excel(headers, rows, path, sheet_name="Expiry Report")


# ── Helpers ─────────────────────────────────────────────────────


def _centered(text: str) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
    return item


def _right_aligned(text: str) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    item.setTextAlignment(
        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
    )
    return item
