from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QMainWindow, QStackedWidget, QVBoxLayout, QWidget

from config import config
from app.ui.widgets.sidebar import Sidebar
from app.ui.widgets.header import Header
from app.ui.widgets.status_bar import AppStatusBar
from app.ui.pages.dashboard_page import DashboardPage
from app.ui.pages.inventory_page import InventoryPage
from app.ui.pages.billing_page import BillingPage
from app.ui.pages.sales_history_page import SalesHistoryPage
from app.ui.pages.purchases_page import PurchasesPage
from app.ui.pages.suppliers_page import SuppliersPage
from app.ui.pages.reports_page import ReportsPage
from app.ui.pages.analytics_page import AnalyticsPage
from app.ui.pages.expiry_page import ExpiryPage
from app.ui.pages.low_stock_page import LowStockPage
from app.ui.pages.backup_page import BackupPage
from app.ui.pages.settings_page import SettingsPage

PAGE_MAP: dict[str, type[QWidget]] = {
    "Dashboard": DashboardPage,
    "Inventory": InventoryPage,
    "Billing (POS)": BillingPage,
    "Sales History": SalesHistoryPage,
    "Purchases": PurchasesPage,
    "Suppliers": SuppliersPage,
    "Reports": ReportsPage,
    "Analytics": AnalyticsPage,
    "Expiry": ExpiryPage,
    "Low Stock": LowStockPage,
    "Backup": BackupPage,
    "Settings": SettingsPage,
}


class MainWindow(QMainWindow):
    """Primary application window with sidebar, header, content area, and status bar."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(config.APP_NAME)
        self.resize(config.WINDOW_DEFAULT_WIDTH, config.WINDOW_DEFAULT_HEIGHT)
        self.setMinimumSize(config.WINDOW_MIN_WIDTH, config.WINDOW_MIN_HEIGHT)
        self._pages: dict[str, QWidget] = {}
        self._center_on_screen()
        self._build_ui()

    def _center_on_screen(self) -> None:
        screen = self.screen()
        if screen is not None:
            geo = screen.availableGeometry()
            x = (geo.width() - self.width()) // 2
            y = (geo.height() - self.height()) // 2
            self.move(x, y)

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self._header = Header()
        main_layout.addWidget(self._header)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        self._sidebar = Sidebar()
        self._sidebar.navigation_clicked.connect(self._on_nav)
        body.addWidget(self._sidebar)

        self._stack = QStackedWidget()
        self._stack.setObjectName("ContentArea")
        self._create_pages()
        body.addWidget(self._stack, 1)

        main_layout.addLayout(body, 1)

        status_bar = AppStatusBar()
        self.setStatusBar(status_bar)

        # Wire dashboard card clicks to navigation
        dashboard = self._pages.get("Dashboard")
        if dashboard is not None and hasattr(dashboard, "card_clicked"):
            dashboard.card_clicked.connect(self._on_nav)

        self._on_nav("Dashboard")

    def _create_pages(self) -> None:
        """Instantiate all pages once and add them to the stacked widget."""
        for label, page_cls in PAGE_MAP.items():
            page = page_cls()
            self._pages[label] = page
            self._stack.addWidget(page)

    def _on_nav(self, label: str) -> None:
        """Switch to the selected page and update the header title."""
        page = self._pages.get(label)
        if page is not None:
            self._stack.setCurrentWidget(page)
            self._header.set_page_title(label)
