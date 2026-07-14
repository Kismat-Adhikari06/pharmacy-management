from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class Sidebar(QFrame):
    """Left navigation sidebar with icon-style buttons."""

    NAV_ITEMS: list[tuple[str, str]] = [
        ("Dashboard", "📊"),
        ("Inventory", "📦"),
        ("Billing (POS)", "💳"),
        ("Sales History", "📜"),
        ("Purchases", "🛒"),
        ("Suppliers", "🚚"),
        ("Reports", "📋"),
        ("Analytics", "📈"),
        ("Expiry", "⏰"),
        ("Low Stock", "📉"),
        ("Backup", "💾"),
        ("Settings", "⚙"),
    ]

    navigation_clicked = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(220)
        self._buttons: dict[str, QPushButton] = {}
        self._active: str = "Dashboard"
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 12, 0, 12)
        layout.setSpacing(2)

        brand = QLabel("🏥 PMS")
        brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand.setStyleSheet(
            "font-size: 16pt; font-weight: bold; color: #89b4fa; "
            "padding: 10px 0 18px 0; border-bottom: 1px solid #313244;"
        )
        layout.addWidget(brand)

        for label, icon in self.NAV_ITEMS:
            btn = QPushButton(f"  {icon}  {label}")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, l=label: self._on_click(l))
            self._buttons[label] = btn
            layout.addWidget(btn)

        layout.addStretch()

        version = QLabel("v1.0.0")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version.setStyleSheet("color: #585b70; font-size: 8pt; padding-bottom: 4px;")
        layout.addWidget(version)

        self._set_active("Dashboard")

    def _on_click(self, label: str) -> None:
        self._set_active(label)
        self.navigation_clicked.emit(label)

    def _set_active(self, label: str) -> None:
        for name, btn in self._buttons.items():
            is_active = name == label
            btn.setProperty("active", is_active)
            btn.setChecked(is_active)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self._active = label
