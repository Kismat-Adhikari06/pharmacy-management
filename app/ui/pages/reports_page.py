from __future__ import annotations

import logging
from datetime import date, timedelta

from PySide6.QtCore import QDate, Qt, QThread, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDateEdit,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.services.reports_service import (
    FilterParams,
    ReportResult,
    ReportsService,
)

logger = logging.getLogger(__name__)

# ── Colours ─────────────────────────────────────────────────────
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

REPORT_TYPES = [
    "Daily Sales",
    "Weekly Sales",
    "Monthly Sales",
    "Yearly Sales",
    "Profit Report",
    "Inventory Report",
    "Low Stock Report",
    "Expiry Report",
    "Purchase Report",
    "Top Selling Medicines",
]


class ReportsPage(QWidget):
    """Professional reports page with filters, summary, table, charts, and export."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ContentArea")
        self._current_result: ReportResult | None = None
        self._build_ui()
        self._load_filter_options()
        self._connect_signals()
        # Load first report
        self._on_generate()

    # ── UI ──────────────────────────────────────────────────────

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
        main = QVBoxLayout(container)
        main.setContentsMargins(20, 16, 20, 16)
        main.setSpacing(14)

        # ── Header ─────────────────────────────────────────────
        hdr = QHBoxLayout()
        title = QLabel("Reports & Analytics")
        title.setObjectName("PageTitle")
        hdr.addWidget(title)
        hdr.addStretch()
        main.addLayout(hdr)

        # ── Top area: filters sidebar + content ────────────────
        top_splitter = QSplitter(Qt.Orientation.Horizontal)
        top_splitter.setChildrenCollapsible(False)

        # Left: filters
        filter_frame = QFrame()
        filter_frame.setObjectName("ReportFilterPanel")
        filter_frame.setFixedWidth(260)
        fl = QVBoxLayout(filter_frame)
        fl.setContentsMargins(14, 14, 14, 14)
        fl.setSpacing(10)

        fl.addWidget(self._section_label("Report Type"))
        self._type_combo = QComboBox()
        self._type_combo.setObjectName("SearchBox")
        self._type_combo.addItems(REPORT_TYPES)
        fl.addWidget(self._type_combo)

        fl.addWidget(self._section_label("Date Range"))
        date_row = QHBoxLayout()
        self._date_from = QDateEdit()
        self._date_from.setCalendarPopup(True)
        self._date_from.setDate(QDate.currentDate().addMonths(-1))
        self._date_from.setObjectName("SearchBox")
        self._date_from.setFixedHeight(30)
        date_row.addWidget(self._date_from)
        date_row.addWidget(QLabel("to"))
        self._date_to = QDateEdit()
        self._date_to.setCalendarPopup(True)
        self._date_to.setDate(QDate.currentDate())
        self._date_to.setObjectName("SearchBox")
        self._date_to.setFixedHeight(30)
        date_row.addWidget(self._date_to)
        fl.addLayout(date_row)

        fl.addWidget(self._section_label("Medicine"))
        self._med_combo = QComboBox()
        self._med_combo.setObjectName("SearchBox")
        self._med_combo.addItem("All", None)
        fl.addWidget(self._med_combo)

        fl.addWidget(self._section_label("Supplier"))
        self._sup_combo = QComboBox()
        self._sup_combo.setObjectName("SearchBox")
        self._sup_combo.addItem("All", None)
        fl.addWidget(self._sup_combo)

        fl.addWidget(self._section_label("Category"))
        self._cat_combo = QComboBox()
        self._cat_combo.setObjectName("SearchBox")
        self._cat_combo.addItem("All", None)
        fl.addWidget(self._cat_combo)

        fl.addWidget(self._section_label("Payment Method"))
        self._pay_combo = QComboBox()
        self._pay_combo.setObjectName("SearchBox")
        self._pay_combo.addItem("All", None)
        fl.addWidget(self._pay_combo)

        fl.addSpacing(8)

        self._generate_btn = QPushButton("Generate Report")
        self._generate_btn.setObjectName("PrimaryButton")
        self._generate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        fl.addWidget(self._generate_btn)

        fl.addStretch()

        top_splitter.addWidget(filter_frame)

        # Right: content area
        content_frame = QFrame()
        content_frame.setObjectName("ContentArea")
        cl = QVBoxLayout(content_frame)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(12)

        # Summary cards
        self._summary_grid = QGridLayout()
        self._summary_grid.setSpacing(10)
        cl.addLayout(self._summary_grid)

        # Charts row
        self._charts_frame = QFrame()
        self._charts_frame.setObjectName("ReportFilterPanel")
        charts_l = QHBoxLayout(self._charts_frame)
        charts_l.setContentsMargins(12, 8, 12, 8)
        charts_l.setSpacing(12)
        self._chart1_container = QWidget()
        self._chart1_layout = QVBoxLayout(self._chart1_container)
        self._chart1_layout.setContentsMargins(0, 0, 0, 0)
        charts_l.addWidget(self._chart1_container, 1)
        self._chart2_container = QWidget()
        self._chart2_layout = QVBoxLayout(self._chart2_container)
        self._chart2_layout.setContentsMargins(0, 0, 0, 0)
        charts_l.addWidget(self._chart2_container, 1)
        cl.addWidget(self._charts_frame)

        # Search bar
        search_row = QHBoxLayout()
        self._search_input = QLineEdit()
        self._search_input.setObjectName("SearchBox")
        self._search_input.setPlaceholderText("Search table…")
        self._search_input.setClearButtonEnabled(True)
        self._search_input.setFixedHeight(32)
        search_row.addWidget(self._search_input, stretch=1)
        self._search_input.textChanged.connect(self._filter_table)
        cl.addLayout(search_row)

        # Table
        self._table = QTableWidget()
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        cl.addWidget(self._table, stretch=1)

        # Export row
        export_row = QHBoxLayout()
        export_row.setSpacing(8)

        self._csv_btn = QPushButton("Export CSV")
        self._csv_btn.setObjectName("ToolbarButton")
        self._csv_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        export_row.addWidget(self._csv_btn)

        self._excel_btn = QPushButton("Export Excel")
        self._excel_btn.setObjectName("ToolbarButton")
        self._excel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        export_row.addWidget(self._excel_btn)

        self._print_btn = QPushButton("Print")
        self._print_btn.setObjectName("ToolbarButton")
        self._print_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._print_btn.setEnabled(False)
        export_row.addWidget(self._print_btn)

        export_row.addStretch()

        self._record_count = QLabel("0 records")
        self._record_count.setStyleSheet(f"color: {_SUBTEXT}; font-size: 9pt;")
        export_row.addWidget(self._record_count)

        cl.addLayout(export_row)

        top_splitter.addWidget(content_frame)
        top_splitter.setSizes([260, 900])

        main.addWidget(top_splitter, 1)
        main.addStretch()

        scroll.setWidget(container)
        root.addWidget(scroll)

    # ── Helpers ─────────────────────────────────────────────────

    @staticmethod
    def _section_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {_SUBTEXT}; font-size: 9pt; font-weight: bold;")
        return lbl

    def _make_summary_card(self, label: str, value: str, color: str) -> QWidget:
        frame = QFrame()
        frame.setObjectName("DashboardCard")
        frame.setFixedHeight(72)
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(2)
        val = QLabel(value)
        val.setStyleSheet(f"font-size: 13pt; font-weight: bold; color: {color};")
        lay.addWidget(val)
        lbl = QLabel(label)
        lbl.setStyleSheet(f"font-size: 9pt; color: {_SUBTEXT};")
        lay.addWidget(lbl)
        return frame

    # ── Filter options ──────────────────────────────────────────

    def _load_filter_options(self) -> None:
        for mid, name in ReportsService.get_medicine_options():
            self._med_combo.addItem(name, mid)
        for sid, name in ReportsService.get_supplier_options():
            self._sup_combo.addItem(name, sid)
        for cat in ReportsService.get_category_options():
            self._cat_combo.addItem(cat, cat)
        for pm in ReportsService.get_payment_methods():
            self._pay_combo.addItem(pm, pm)

    def _get_filters(self) -> FilterParams:
        return FilterParams(
            date_from=self._date_from.date().toPython(),
            date_to=self._date_to.date().toPython(),
            medicine_id=self._med_combo.currentData(),
            supplier_id=self._sup_combo.currentData(),
            category=self._cat_combo.currentData(),
            payment_method=self._pay_combo.currentData(),
        )

    # ── Signals ─────────────────────────────────────────────────

    def _connect_signals(self) -> None:
        self._generate_btn.clicked.connect(self._on_generate)
        self._csv_btn.clicked.connect(self._on_export_csv)
        self._excel_btn.clicked.connect(self._on_export_excel)
        self._table.horizontalHeader().sectionClicked.connect(self._sort_table)

    # ── Generate ────────────────────────────────────────────────

    def _on_generate(self) -> None:
        report_type = self._type_combo.currentText()
        params = self._get_filters()
        try:
            fn = getattr(ReportsService, self._report_fn_name(report_type))
            result: ReportResult = fn(params)
        except Exception as exc:
            logger.exception("Report generation failed")
            QMessageBox.warning(self, "Error", str(exc))
            return
        self._current_result = result
        self._render_summary(result)
        self._render_charts(result)
        self._render_table(result)

    @staticmethod
    def _report_fn_name(report_type: str) -> str:
        mapping = {
            "Daily Sales": "daily_sales",
            "Weekly Sales": "weekly_sales",
            "Monthly Sales": "monthly_sales",
            "Yearly Sales": "yearly_sales",
            "Profit Report": "profit_report",
            "Inventory Report": "inventory_report",
            "Low Stock Report": "low_stock_report",
            "Expiry Report": "expiry_report",
            "Purchase Report": "purchase_report",
            "Top Selling Medicines": "top_selling_report",
        }
        return mapping.get(report_type, "daily_sales")

    # ── Summary ─────────────────────────────────────────────────

    def _render_summary(self, result: ReportResult) -> None:
        while self._summary_grid.count():
            item = self._summary_grid.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        cards = [
            ("Total Sales", f"Rs. {result.summary.total_sales:,.2f}", _GREEN),
            ("Total Profit", f"Rs. {result.summary.total_profit:,.2f}", _BLUE),
            ("Bills", str(result.summary.total_bills), _YELLOW),
            ("Meds Sold", str(result.summary.total_medicines_sold), _PURPLE),
            ("Avg Bill", f"Rs. {result.summary.avg_bill_value:,.2f}", _ORANGE),
        ]
        for i, (label, value, color) in enumerate(cards):
            self._summary_grid.addWidget(
                self._make_summary_card(label, value, color), 0, i
            )

    # ── Charts ──────────────────────────────────────────────────

    def _render_charts(self, result: ReportResult) -> None:
        self._clear_layout(self._chart1_layout)
        self._clear_layout(self._chart2_layout)

        if not result.chart_labels:
            lbl = QLabel("No chart data")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"color: {_SUBTEXT};")
            self._chart1_layout.addWidget(lbl)
            return

        self._draw_bar(
            self._chart1_layout,
            result.chart_labels,
            result.chart_values,
            "Sales Trend",
        )

        if result.chart_values2:
            self._draw_bar(
                self._chart2_layout,
                result.chart_labels,
                result.chart_values2,
                result.chart_title2 or "Secondary",
            )
        else:
            self._draw_bar(
                self._chart2_layout,
                result.chart_labels,
                result.chart_values,
                "Distribution",
            )

    def _draw_bar(self, layout, labels, values, title):
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
        from matplotlib.figure import Figure

        fig = Figure(figsize=(5, 2.2), dpi=100)
        fig.patch.set_facecolor(_CARD_BG)
        ax = fig.add_subplot(111)
        ax.set_facecolor(_CARD_BG)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(f"font-size: 9pt; font-weight: bold; color: {_TEXT};")
        layout.addWidget(title_lbl)

        if not labels or not any(v != 0 for v in values):
            ax.text(
                0.5, 0.5, "No data", ha="center", va="center",
                color=_SUBTEXT, fontsize=10, transform=ax.transAxes,
            )
        else:
            display_labels = [l[:15] for l in labels]
            ax.bar(display_labels, values, color=_BLUE, width=0.6)
            ax.tick_params(axis="x", labelsize=7, colors=_SUBTEXT, rotation=30)
            ax.tick_params(axis="y", labelsize=7, colors=_SUBTEXT)

        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.grid(axis="y", alpha=0.15, color=_SUBTEXT)

        canvas = FigureCanvasQTAgg(fig)
        canvas.setStyleSheet("background-color: transparent;")
        layout.addWidget(canvas, stretch=1)
        fig.tight_layout(pad=0.5)

    # ── Table ───────────────────────────────────────────────────

    def _render_table(self, result: ReportResult) -> None:
        self._table.setColumnCount(len(result.headers))
        self._table.setHorizontalHeaderLabels(result.headers)
        self._table.setRowCount(len(result.rows))

        header = self._table.horizontalHeader()
        for i in range(len(result.headers)):
            if i == 0:
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
            else:
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)

        for i, row in enumerate(result.rows):
            for j, cell in enumerate(row.cells):
                item = QTableWidgetItem(cell)
                # Right-align monetary columns
                if any(
                    kw in result.headers[j].lower()
                    for kw in ["total", "sales", "profit", "price", "value", "revenue", "avg"]
                ):
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                self._table.setItem(i, j, item)

        self._record_count.setText(f"{len(result.rows)} records")

    def _filter_table(self, text: str) -> None:
        """Hide rows that don't match the search text."""
        term = text.lower()
        for i in range(self._table.rowCount()):
            match = False
            for j in range(self._table.columnCount()):
                item = self._table.item(i, j)
                if item and term in item.text().lower():
                    match = True
                    break
            self._table.setRowHidden(i, not match)

    def _sort_table(self, logical_index: int) -> None:
        """Sort table by clicked column."""
        if self._current_result is None:
            return
        self._table.sortItems(logical_index, Qt.SortOrder.AscendingOrder)

    # ── Export ──────────────────────────────────────────────────

    def _on_export_csv(self) -> None:
        if self._current_result is None:
            QMessageBox.information(self, "No Data", "Generate a report first.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export CSV", "report.csv", "CSV Files (*.csv)"
        )
        if not path:
            return
        try:
            ReportsService.export_csv(self._current_result, path)
            QMessageBox.information(self, "Exported", f"Report saved to:\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def _on_export_excel(self) -> None:
        if self._current_result is None:
            QMessageBox.information(self, "No Data", "Generate a report first.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Excel", "report.xls", "Excel Files (*.xls *.xml)"
        )
        if not path:
            return
        try:
            ReportsService.export_excel(self._current_result, path)
            QMessageBox.information(self, "Exported", f"Report saved to:\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    # ── Utilities ───────────────────────────────────────────────

    @staticmethod
    def _clear_layout(layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
