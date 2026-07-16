from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from config import config
from app.ui.theme import Theme
from app.ui.widgets.sidebar import Sidebar
from app.ui.widgets.header import Header
from app.ui.widgets.status_bar import AppStatusBar

_PAGE_CLASSES: dict[str, str] = {
    "Dashboard": "app.ui.pages.dashboard_page.DashboardPage",
    "Billing (POS)": "app.ui.pages.billing_page.BillingPage",
    "Sales History": "app.ui.pages.sales_history_page.SalesHistoryPage",
    "Inventory": "app.ui.pages.inventory_page.InventoryPage",
    "Purchases": "app.ui.pages.purchases_page.PurchasesPage",
    "Suppliers": "app.ui.pages.suppliers_page.SuppliersPage",
    "Expiry": "app.ui.pages.expiry_page.ExpiryPage",
    "Low Stock": "app.ui.pages.low_stock_page.LowStockPage",
    "AI Invoice Import": "app.ui.pages.ocr_invoice_page.OCRInvoicePage",
    "Backup": "app.ui.pages.backup_page.BackupPage",
    "Settings": "app.ui.pages.settings_page.SettingsPage",
}


def _import_page(dotted: str) -> type[QWidget]:
    module_path, class_name = dotted.rsplit(".", 1)
    import importlib
    mod = importlib.import_module(module_path)
    return getattr(mod, class_name)


class _Placeholder(QWidget):
    """Shown while a page is loading (should be nearly instant)."""

    def __init__(self, label: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl = QLabel(f"Loading {label}...")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(f"color: {Theme.text3()}; font-size: 14pt;")
        layout.addWidget(lbl)


class MainWindow(QMainWindow):
    """Primary application window with sidebar, header, content area, and status bar."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(config.APP_NAME)
        self.setWindowFlags(Qt.WindowType.Window)
        self.resize(config.WINDOW_DEFAULT_WIDTH, config.WINDOW_DEFAULT_HEIGHT)
        self.setMinimumSize(config.WINDOW_MIN_WIDTH, config.WINDOW_MIN_HEIGHT)
        self._pages: dict[str, QWidget] = {}
        self._center_on_screen()
        self._build_ui()
        self.showMaximized()

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

        self._page_indices: dict[str, int] = {}
        for label in _PAGE_CLASSES:
            placeholder = _Placeholder(label)
            idx = self._stack.addWidget(placeholder)
            self._page_indices[label] = idx

        body.addWidget(self._stack, 1)

        main_layout.addLayout(body, 1)

        status_bar = AppStatusBar()
        self.setStatusBar(status_bar)

        self._on_nav("Dashboard")

    def _ensure_page(self, label: str) -> QWidget:
        """Instantiate the real page on first visit."""
        if label in self._pages:
            return self._pages[label]

        dotted = _PAGE_CLASSES.get(label)
        if dotted is None:
            return QWidget()

        page_cls = _import_page(dotted)
        page = page_cls()
        self._pages[label] = page

        idx = self._page_indices[label]
        self._stack.removeWidget(self._stack.widget(idx))
        self._stack.insertWidget(idx, page)
        self._stack.setCurrentIndex(idx)

        if label == "Dashboard" and hasattr(page, "card_clicked"):
            page.card_clicked.connect(self._on_nav)

        if label == "Settings" and hasattr(page, "settings_changed"):
            page.settings_changed.connect(self._on_settings_changed)

        return page

    def _on_settings_changed(self) -> None:
        """Reload the stylesheet when settings are saved."""
        try:
            from PySide6.QtWidgets import QApplication
            from app.services.settings_service import SettingsService
            from config import config

            Theme.refresh()

            settings = SettingsService.load()
            qss_name = "light.qss" if settings.default_theme == "light" else "dark.qss"
            qss_path = config.styles_dir / qss_name
            if qss_path.exists():
                qss = qss_path.read_text(encoding="utf-8")
                app = QApplication.instance()
                if app is not None:
                    app.setStyleSheet(qss)
            self._sidebar.theme_refresh()
        except Exception:
            pass

    def _on_nav(self, label: str) -> None:
        """Switch to the selected page and update the header title."""
        page = self._ensure_page(label)
        self._stack.setCurrentWidget(page)
        self._header.set_page_title(label)
