from __future__ import annotations

import logging

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


from app.services.dashboard_service import (
    DashboardService,
    RecentSale,
    TopCard,
)

from app.ui.dialogs.receipt_preview_dialog import ReceiptPreviewDialog
from app.services.receipt_service import ReceiptService
from app.ui.theme import Theme
from app.ui.widgets.icons import make_icon

logger = logging.getLogger(__name__)

# Dashboard icon paths (stroke-based SVG)
_DASH_ICONS: dict[str, str] = {
    "revenue": "M1 1h4l2.68 13.39a1 1 0 001 .81h9.72a1 1 0 001-.76L23 6H6M9 22a1 1 0 100-2 1 1 0 000 2zM20 22a1 1 0 100-2 1 1 0 000 2z",
    "profit": "M12 1v22M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6",
    "bills": "M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z M14 2v6h6 M16 13H8 M16 17H8 M10 9H8",
    "lowstock": "M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z M12 9v4 M12 17h.01",
    "expiring": "M12 22a10 10 0 100-20 10 10 0 000 20z M12 6v6l4 2",
}



class ClickableCard(QFrame):
    """A dashboard stat card that emits a signal when clicked."""

    clicked = Signal()

    def __init__(self, nav_target: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.nav_target = nav_target
        self.setFrameShape(QFrame.Shape.NoFrame)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self.nav_target:
            self.clicked.emit()
        super().mousePressEvent(event)


class DashboardPage(QWidget):
    """Streamlined dashboard: 3 KPI cards, 2 alert cards, 1 recent-sales table."""

    # Emitted when a clickable card is clicked — value is the page label
    card_clicked = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ContentArea")
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
        title = QLabel("Dashboard")
        title.setObjectName("PageTitle")
        hdr.addWidget(title)
        hdr.addStretch()
        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.setObjectName("ToolbarButton")
        self._refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._refresh_btn.clicked.connect(self.refresh)
        hdr.addWidget(self._refresh_btn)
        self._main_layout.addLayout(hdr)

        # ── Top row: 3 KPI cards ───────────────────────────────
        self._cards_grid = QGridLayout()
        self._cards_grid.setSpacing(12)
        self._main_layout.addLayout(self._cards_grid)

        # ── Alert row: Low Stock + Expiry summary cards ────────
        self._alert_layout = QHBoxLayout()
        self._alert_layout.setSpacing(12)
        self._main_layout.addLayout(self._alert_layout)

        # ── Recent Sales table ─────────────────────────────────
        recent_card = self._make_panel_card("Recent Sales")
        self._recent_table = self._create_recent_table()
        recent_card["body"].layout().addWidget(self._recent_table)
        self._main_layout.addWidget(recent_card["wrapper"])

        self._main_layout.addStretch()

        scroll.setWidget(container)
        root.addWidget(scroll)

    # ── Card / panel helpers ────────────────────────────────────

    @staticmethod
    def _make_stat_card(card: TopCard, nav_target: str = "") -> QWidget:
        wrapper = ClickableCard(nav_target=nav_target)
        wrapper.setObjectName("DashboardCard")
        wrapper.setFixedHeight(90)
        if nav_target:
            wrapper.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(2)

        icon_lbl = QLabel()
        icon_lbl.setStyleSheet("background: transparent;")
        path = _DASH_ICONS.get(card.icon)
        if path:
            icon = make_icon(card.color)(path)
            icon_lbl.setPixmap(icon.pixmap(20, 20))
        else:
            icon_lbl.setText(card.icon)
            icon_lbl.setStyleSheet(f"font-size: 18pt; color: {card.color}; background: transparent;")
        layout.addWidget(icon_lbl)

        val = QLabel(card.value)
        val.setStyleSheet(
            f"font-size: 14pt; font-weight: bold; color: {card.color}; background: transparent;"
        )
        layout.addWidget(val)

        lbl = QLabel(card.label)
        lbl.setStyleSheet(f"font-size: 9pt; color: {Theme.text2()}; background: transparent;")
        layout.addWidget(lbl)

        return wrapper

    @staticmethod
    def _make_alert_card(label: str, count: int, icon_key: str, color: str, nav_target: str) -> QWidget:
        """Create a compact clickable alert summary card."""
        wrapper = ClickableCard(nav_target=nav_target)
        wrapper.setObjectName("DashboardCard")
        wrapper.setFixedHeight(70)
        wrapper.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        layout = QHBoxLayout(wrapper)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(10)

        # Icon
        icon_lbl = QLabel()
        icon_lbl.setStyleSheet("background: transparent;")
        path = _DASH_ICONS.get(icon_key)
        if path:
            icon = make_icon(color)(path)
            icon_lbl.setPixmap(icon.pixmap(18, 18))
        layout.addWidget(icon_lbl)

        # Count
        val = QLabel(str(count))
        val.setStyleSheet(
            f"font-size: 16pt; font-weight: bold; color: {color}; background: transparent;"
        )
        layout.addWidget(val)

        # Label
        lbl = QLabel(label)
        lbl.setStyleSheet(f"font-size: 9pt; color: {Theme.text2()}; background: transparent;")
        layout.addWidget(lbl)

        layout.addStretch()
        return wrapper

    @staticmethod
    def _make_panel_card(title: str) -> dict:
        wrapper = QFrame()
        wrapper.setObjectName("DashboardCard")
        wrapper.setFrameShape(QFrame.Shape.NoFrame)
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        lbl = QLabel(title)
        lbl.setStyleSheet(
            f"font-size: 10pt; font-weight: bold; color: {Theme.text()}; background: transparent;"
        )
        layout.addWidget(lbl)

        body = QFrame()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        layout.addWidget(body, stretch=1)

        return {"wrapper": wrapper, "body": body}

    # ── Table factory ───────────────────────────────────────────

    @staticmethod
    def _create_recent_table() -> QTableWidget:
        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(
            ["Bill Number", "Time", "Total", "Payment"]
        )
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.setShowGrid(False)
        return table

    # ── Signal wiring ───────────────────────────────────────────

    def _connect_signals(self) -> None:
        self._recent_table.doubleClicked.connect(self._on_recent_double_click)

    # ── Data loading ────────────────────────────────────────────

    def refresh(self) -> None:
        """Reload every dashboard widget from the database."""
        self._load_cards()
        self._load_alerts()
        self._load_recent_sales()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        QTimer.singleShot(0, self.refresh)

    # ── KPI cards ───────────────────────────────────────────────

    def _load_cards(self) -> None:
        # Clear old cards
        while self._cards_grid.count():
            item = self._cards_grid.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        cards = DashboardService.get_top_cards()
        for i, card in enumerate(cards):
            widget = self._make_stat_card(card)
            self._cards_grid.addWidget(widget, 0, i)

    # ── Alert summary cards ─────────────────────────────────────

    def _load_alerts(self) -> None:
        # Clear old alert cards
        while self._alert_layout.count():
            item = self._alert_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        low_stock_count, expiry_count = DashboardService.get_alert_counts()

        # Low Stock card
        low_card = self._make_alert_card(
            label="Low Stock",
            count=low_stock_count,
            icon_key="lowstock",
            color=Theme.warning(),
            nav_target="Low Stock",
        )
        low_card.clicked.connect(lambda: self.card_clicked.emit("Low Stock"))
        self._alert_layout.addWidget(low_card)

        # Expiry card (expired + expiring combined)
        expiry_color = Theme.danger() if expiry_count > 0 else Theme.warning()
        expiry_card = self._make_alert_card(
            label="Expired / Expiring",
            count=expiry_count,
            icon_key="expiring",
            color=expiry_color,
            nav_target="Expiry",
        )
        expiry_card.clicked.connect(lambda: self.card_clicked.emit("Expiry"))
        self._alert_layout.addWidget(expiry_card)

    # ── Recent sales ────────────────────────────────────────────

    def _load_recent_sales(self) -> None:
        sales = DashboardService.recent_sales(10)
        self._populate_recent_table(sales)

    def _populate_recent_table(self, sales: list[RecentSale]) -> None:
        self._recent_table.setRowCount(len(sales))
        for i, s in enumerate(sales):
            self._recent_table.setItem(i, 0, QTableWidgetItem(s.bill_number))
            self._recent_table.setItem(i, 1, QTableWidgetItem(s.sale_time))
            self._recent_table.setItem(i, 2, _right_aligned(f"Rs. {s.total:,.2f}"))
            self._recent_table.setItem(i, 3, QTableWidgetItem(s.payment_method))
            self._recent_table.item(i, 0).setData(Qt.ItemDataRole.UserRole, s.sale_id)

    def _on_recent_double_click(self) -> None:
        rows = self._recent_table.selectionModel().selectedRows()
        if not rows:
            return
        row = rows[0].row()
        item = self._recent_table.item(row, 0)
        if item is None:
            return
        sale_id = item.data(Qt.ItemDataRole.UserRole)
        if sale_id is None:
            return
        data = ReceiptService.load_sale_data(sale_id=sale_id)
        if data is None:
            return
        dlg = ReceiptPreviewDialog(data, parent=self)
        dlg.exec()


# ── Helpers ─────────────────────────────────────────────────────


def _right_aligned(text: str) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    item.setTextAlignment(
        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
    )
    return item
