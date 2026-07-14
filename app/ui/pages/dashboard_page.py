from __future__ import annotations

import logging

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCursor
from PySide6.QtWidgets import (
    QAbstractItemView,
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

from app.services.dashboard_service import (
    DashboardService,
    ExpiryItem,
    LowStockItem,
    RecentSale,
    TopCard,
)
from app.ui.dialogs.receipt_preview_dialog import ReceiptPreviewDialog
from app.services.receipt_service import ReceiptService

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
_PURPLE = "#cba6f7"


class ClickableCard(QFrame):
    """A dashboard stat card that emits a signal when clicked."""

    clicked = Signal()

    def __init__(self, nav_target: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.nav_target = nav_target

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self.nav_target:
            self.clicked.emit()
        super().mousePressEvent(event)


class DashboardPage(QWidget):
    """Live dashboard with KPI cards, charts, recent sales, and alerts."""

    # Emitted when a clickable card is clicked — value is the page label
    card_clicked = Signal(str)
    refresh_requested = Signal()

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

        # Scrollable area so the dashboard works on small screens
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
        self._refresh_btn = QPushButton("\U0001f504 Refresh")
        self._refresh_btn.setObjectName("ToolbarButton")
        self._refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._refresh_btn.clicked.connect(self.refresh)
        hdr.addWidget(self._refresh_btn)
        self._main_layout.addLayout(hdr)

        # ── Top cards ──────────────────────────────────────────
        self._cards_grid = QGridLayout()
        self._cards_grid.setSpacing(12)
        self._main_layout.addLayout(self._cards_grid)

        # ── Charts row (2 x 2) ────────────────────────────────
        self._charts_grid = QGridLayout()
        self._charts_grid.setSpacing(12)
        self._main_layout.addLayout(self._charts_grid)

        self._chart_daily = self._make_chart_card("Daily Sales (Last 7 Days)")
        self._chart_monthly = self._make_chart_card("Monthly Sales (Last 6 Months)")
        self._chart_top = self._make_chart_card("Top Selling Medicines")
        self._chart_category = self._make_chart_card("Category Distribution")

        self._charts_grid.addWidget(self._chart_daily["wrapper"], 0, 0)
        self._charts_grid.addWidget(self._chart_monthly["wrapper"], 0, 1)
        self._charts_grid.addWidget(self._chart_top["wrapper"], 1, 0)
        self._charts_grid.addWidget(self._chart_category["wrapper"], 1, 1)

        # ── Bottom row: recent sales | low stock | expiry ──────
        bottom = QHBoxLayout()
        bottom.setSpacing(12)

        # Recent sales
        recent_card = self._make_panel_card("Recent Sales")
        self._recent_table = self._create_recent_table()
        recent_card["body"].layout().addWidget(self._recent_table)
        bottom.addWidget(recent_card["wrapper"], 4)

        # Low stock
        low_card = self._make_panel_card("Low Stock Alerts")
        self._low_table = self._create_low_stock_table()
        low_card["body"].layout().addWidget(self._low_table)
        bottom.addWidget(low_card["wrapper"], 3)

        # Expiry
        exp_card = self._make_panel_card("Expiry Alerts")
        self._expiry_table = self._create_expiry_table()
        exp_card["body"].layout().addWidget(self._expiry_table)
        bottom.addWidget(exp_card["wrapper"], 3)

        self._main_layout.addLayout(bottom)
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

        icon_lbl = QLabel(card.icon)
        icon_lbl.setStyleSheet("font-size: 18pt;")
        layout.addWidget(icon_lbl)

        val = QLabel(card.value)
        val.setStyleSheet(
            f"font-size: 14pt; font-weight: bold; color: {card.color};"
        )
        layout.addWidget(val)

        lbl = QLabel(card.label)
        lbl.setStyleSheet(f"font-size: 9pt; color: {_SUBTEXT};")
        layout.addWidget(lbl)

        return wrapper

    @staticmethod
    def _make_chart_card(title: str) -> dict:
        wrapper = QFrame()
        wrapper.setObjectName("DashboardCard")
        wrapper.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        lbl = QLabel(title)
        lbl.setStyleSheet(f"font-size: 10pt; font-weight: bold; color: {_TEXT};")
        layout.addWidget(lbl)

        placeholder = QLabel("Loading chart…")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet(f"color: {_SUBTEXT};")
        layout.addWidget(placeholder, stretch=1)

        return {"wrapper": wrapper, "layout": layout, "placeholder": placeholder}

    @staticmethod
    def _make_panel_card(title: str) -> dict:
        wrapper = QFrame()
        wrapper.setObjectName("DashboardCard")
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        lbl = QLabel(title)
        lbl.setStyleSheet(
            f"font-size: 10pt; font-weight: bold; color: {_TEXT};"
        )
        layout.addWidget(lbl)

        body = QFrame()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        layout.addWidget(body, stretch=1)

        return {"wrapper": wrapper, "body": body}

    # ── Table factories ─────────────────────────────────────────

    @staticmethod
    def _create_recent_table() -> QTableWidget:
        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(
            ["Bill Number", "Time", "Items", "Total", "Payment"]
        )
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.setShowGrid(False)
        table.setFixedHeight(280)
        return table

    @staticmethod
    def _create_low_stock_table() -> QTableWidget:
        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["Medicine", "Stock", "Min"])
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.setShowGrid(False)
        table.setFixedHeight(280)
        return table

    @staticmethod
    def _create_expiry_table() -> QTableWidget:
        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["Medicine", "Batch", "Expiry", "Qty"])
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.setShowGrid(False)
        table.setFixedHeight(280)
        return table

    # ── Signal wiring ───────────────────────────────────────────

    def _connect_signals(self) -> None:
        self._recent_table.doubleClicked.connect(self._on_recent_double_click)

    # ── Data loading ────────────────────────────────────────────

    def refresh(self) -> None:
        """Reload every dashboard widget from the database."""
        self._load_cards()
        self._load_charts()
        self._load_recent_sales()
        self._load_low_stock()
        self._load_expiry()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        # Auto-refresh each time the dashboard becomes visible
        QTimer.singleShot(0, self.refresh)

    # ── Cards ───────────────────────────────────────────────────

    # Map card labels to navigation targets (empty = not clickable)
    _CARD_NAV_MAP: dict[str, str] = {
        "Low Stock": "Low Stock",
        "Expiring (90d)": "Expiry",
        "Expired": "Expiry",
    }

    def _load_cards(self) -> None:
        # Clear existing cards
        while self._cards_grid.count():
            item = self._cards_grid.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        cards = DashboardService.get_top_cards()
        cols = 4
        for i, card in enumerate(cards):
            nav_target = self._CARD_NAV_MAP.get(card.label, "")
            widget = self._make_stat_card(card, nav_target=nav_target)
            if isinstance(widget, ClickableCard) and widget.nav_target:
                widget.clicked.connect(
                    lambda target=nav_target: self.card_clicked.emit(target)
                )
            self._cards_grid.addWidget(widget, i // cols, i % cols)

    # ── Charts ──────────────────────────────────────────────────

    def _load_charts(self) -> None:
        try:
            self._render_bar_chart(
                self._chart_daily,
                DashboardService.daily_sales_last_7_days(),
                color=_GREEN,
            )
            self._render_bar_chart(
                self._chart_monthly,
                DashboardService.monthly_sales_last_6_months(),
                color=_BLUE,
            )
            self._render_bar_chart(
                self._chart_top,
                DashboardService.top_selling_medicines(),
                color=_PURPLE,
                horizontal=True,
            )
            self._render_pie_chart(
                self._chart_category,
                DashboardService.category_distribution(),
            )
        except Exception:
            logger.exception("Failed to render charts")

    def _render_bar_chart(
        self,
        card: dict,
        data,
        color: str = _BLUE,
        horizontal: bool = False,
    ) -> None:
        """Replace the placeholder with a matplotlib bar chart."""
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
        from matplotlib.figure import Figure

        # Remove old canvas if any
        self._clear_chart(card)

        fig = Figure(figsize=(4, 2.2), dpi=100)
        fig.patch.set_facecolor(_CARD_BG)
        ax = fig.add_subplot(111)
        ax.set_facecolor(_CARD_BG)

        if not data.labels:
            ax.text(
                0.5, 0.5, "No data", ha="center", va="center",
                color=_SUBTEXT, fontsize=10, transform=ax.transAxes,
            )
        else:
            if horizontal:
                bars = ax.barh(data.labels, data.values, color=color, height=0.6)
                ax.invert_yaxis()
                ax.tick_params(axis="y", labelsize=7, colors=_SUBTEXT)
                ax.tick_params(axis="x", labelsize=7, colors=_SUBTEXT)
            else:
                bars = ax.bar(data.labels, data.values, color=color, width=0.6)
                ax.tick_params(axis="x", labelsize=7, colors=_SUBTEXT, rotation=30)
                ax.tick_params(axis="y", labelsize=7, colors=_SUBTEXT)

        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.grid(axis="y" if not horizontal else "x", alpha=0.15, color=_SUBTEXT)

        canvas = FigureCanvasQTAgg(fig)
        canvas.setStyleSheet("background-color: transparent;")
        card["layout"].addWidget(canvas, stretch=1)
        card["canvas"] = canvas
        fig.tight_layout(pad=0.5)

    def _render_pie_chart(self, card: dict, data) -> None:
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
        from matplotlib.figure import Figure

        self._clear_chart(card)

        fig = Figure(figsize=(4, 2.2), dpi=100)
        fig.patch.set_facecolor(_CARD_BG)
        ax = fig.add_subplot(111)
        ax.set_facecolor(_CARD_BG)

        if not data.labels:
            ax.text(
                0.5, 0.5, "No data", ha="center", va="center",
                color=_SUBTEXT, fontsize=10, transform=ax.transAxes,
            )
        else:
            colors = [_BLUE, _GREEN, _YELLOW, _ORANGE, _RED, _PURPLE, "#74c7ec", "#89dceb"]
            wedges, texts, autotexts = ax.pie(
                data.values,
                labels=data.labels,
                autopct="%1.0f%%",
                colors=colors[: len(data.labels)],
                textprops={"fontsize": 7, "color": _TEXT},
                pctdistance=0.75,
            )
            for t in autotexts:
                t.set_fontsize(6)
                t.set_color(_TEXT)

        canvas = FigureCanvasQTAgg(fig)
        canvas.setStyleSheet("background-color: transparent;")
        card["layout"].addWidget(canvas, stretch=1)
        card["canvas"] = canvas
        fig.tight_layout(pad=0.5)

    def _clear_chart(self, card: dict) -> None:
        old = card.get("canvas")
        if old is not None:
            card["layout"].removeWidget(old)
            old.deleteLater()
            card.pop("canvas", None)
        # Remove placeholder text
        ph = card.get("placeholder")
        if ph is not None:
            card["layout"].removeWidget(ph)
            ph.deleteLater()
            card.pop("placeholder", None)

    # ── Recent sales ────────────────────────────────────────────

    def _load_recent_sales(self) -> None:
        sales = DashboardService.recent_sales(10)
        self._populate_recent_table(sales)

    def _populate_recent_table(self, sales: list[RecentSale]) -> None:
        self._recent_table.setRowCount(len(sales))
        for i, s in enumerate(sales):
            self._recent_table.setItem(i, 0, QTableWidgetItem(s.bill_number))
            self._recent_table.setItem(i, 1, QTableWidgetItem(s.sale_time))
            self._recent_table.setItem(i, 2, _centered(str(s.item_count)))
            self._recent_table.setItem(i, 3, _right_aligned(f"Rs. {s.total:,.2f}"))
            self._recent_table.setItem(i, 4, QTableWidgetItem(s.payment_method))
            # Store sale_id in the first column's data role
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

    # ── Low stock ───────────────────────────────────────────────

    def _load_low_stock(self) -> None:
        items = DashboardService.low_stock_medicines()
        self._populate_low_stock(items)

    def _populate_low_stock(self, items: list[LowStockItem]) -> None:
        self._low_table.setRowCount(len(items))
        for i, item in enumerate(items):
            self._low_table.setItem(i, 0, QTableWidgetItem(item.medicine_name))
            stock_cell = _centered(str(item.current_stock))
            if item.current_stock == 0:
                stock_cell.setForeground(QColor(_RED))
            else:
                stock_cell.setForeground(QColor(_ORANGE))
            self._low_table.setItem(i, 1, stock_cell)
            self._low_table.setItem(i, 2, _centered(str(item.minimum_stock)))

    # ── Expiry ──────────────────────────────────────────────────

    def _load_expiry(self) -> None:
        items = DashboardService.expiring_medicines()
        self._populate_expiry(items)

    def _populate_expiry(self, items: list[ExpiryItem]) -> None:
        self._expiry_table.setRowCount(len(items))
        for i, item in enumerate(items):
            self._expiry_table.setItem(i, 0, QTableWidgetItem(item.medicine_name))
            self._expiry_table.setItem(i, 1, QTableWidgetItem(item.batch_number))
            exp_cell = QTableWidgetItem(item.expiry_date)
            # Colour code by urgency
            if item.days_until < 0:
                exp_cell.setForeground(QColor(_RED))
            elif item.days_until <= 30:
                exp_cell.setForeground(QColor(_RED))
            elif item.days_until <= 60:
                exp_cell.setForeground(QColor(_ORANGE))
            elif item.days_until <= 90:
                exp_cell.setForeground(QColor(_YELLOW))
            else:
                exp_cell.setForeground(QColor(_GREEN))
            self._expiry_table.setItem(i, 2, exp_cell)
            self._expiry_table.setItem(i, 3, _centered(str(item.quantity)))


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
