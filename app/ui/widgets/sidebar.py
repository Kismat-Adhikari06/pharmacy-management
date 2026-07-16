from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.ui.widgets.icons import NavIcons
from app.ui.theme import Theme


class Sidebar(QFrame):
    """Left navigation sidebar with grouped icon-style buttons."""

    navigation_clicked = Signal(str)

    # ── Grouped navigation ──────────────────────────────────────
    # Each group is (section_label_or_None, [page_labels])
    _GROUPS: list[tuple[str | None, list[str]]] = [
        (None, ["Dashboard"]),
        ("SALES", ["Billing (POS)", "Sales History"]),
        ("INVENTORY", ["Inventory", "Purchases", "Suppliers"]),
        ("ALERTS", ["Expiry", "Low Stock"]),
        ("TOOLS", ["AI Invoice Import"]),
        (None, ["Backup", "Settings"]),
    ]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(220)
        self._buttons: dict[str, QPushButton] = {}
        self._icons: dict[str, tuple[QIcon, QIcon]] = {}
        self._section_labels: list[QLabel] = []
        self._brand_text: QLabel | None = None
        self._brand_icon: QLabel | None = None
        self._sep: QFrame | None = None
        self._version_label: QLabel | None = None
        self._active: str = "Dashboard"
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 12, 0, 12)
        layout.setSpacing(0)

        # ── Brand ─────────────────────────────────────────────
        brand_row = QHBoxLayout()
        brand_row.setContentsMargins(16, 0, 0, 0)
        brand_icon = QLabel()
        self._brand_icon = brand_icon
        brand_icon.setPixmap(
            NavIcons.save(Theme.accent()).pixmap(20, 20)
        )
        brand_row.addWidget(brand_icon)
        brand_text = QLabel("Pharmacy")
        brand_text.setStyleSheet(
            f"font-size: 15pt; font-weight: bold; color: {Theme.accent()}; "
            f"padding: 10px 0 14px 0;"
        )
        self._brand_text = brand_text
        brand_row.addWidget(brand_text)
        brand_row.addStretch()
        layout.addLayout(brand_row)

        sep = QFrame()
        self._sep = sep
        sep.setObjectName("SidebarSep")
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {Theme.border()}; margin: 0 8px;")
        layout.addWidget(sep)

        layout.addSpacing(6)

        # ── Grouped items ─────────────────────────────────────
        for section_label, items in self._GROUPS:
            if section_label is not None:
                lbl = QLabel(f"  {section_label}")
                lbl.setStyleSheet(
                    f"color: {Theme.text3()}; font-size: 8pt; font-weight: bold; "
                    f"letter-spacing: 1px; padding: 10px 16px 4px 16px;"
                )
                layout.addWidget(lbl)
                self._section_labels.append(lbl)

            for label in items:
                icons = NavIcons.get(label)
                self._icons[label] = icons

                btn = QPushButton(f"  {label}")
                btn.setIcon(icons[0])
                btn.setCheckable(True)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.clicked.connect(lambda checked, l=label: self._on_click(l))
                self._buttons[label] = btn
                layout.addWidget(btn)

        layout.addStretch()

        # ── Version ───────────────────────────────────────────
        version = QLabel("v1.0.0")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version.setStyleSheet(f"color: {Theme.text3()}; font-size: 8pt; padding-bottom: 4px;")
        self._version_label = version
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
            icons = self._icons.get(name)
            if icons:
                btn.setIcon(icons[1] if is_active else icons[0])
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self._active = label

    def theme_refresh(self) -> None:
        """Re-apply all inline styles using current Theme colors."""
        if self._brand_icon:
            self._brand_icon.setPixmap(
                NavIcons.save(Theme.accent()).pixmap(20, 20)
            )
        if self._brand_text:
            self._brand_text.setStyleSheet(
                f"font-size: 15pt; font-weight: bold; color: {Theme.accent()}; "
                f"padding: 10px 0 14px 0;"
            )
        if self._sep:
            self._sep.setStyleSheet(
                f"background-color: {Theme.border()}; margin: 0 8px;"
            )
        for lbl in self._section_labels:
            lbl.setStyleSheet(
                f"color: {Theme.text3()}; font-size: 8pt; font-weight: bold; "
                f"letter-spacing: 1px; padding: 10px 16px 4px 16px;"
            )
        if self._version_label:
            self._version_label.setStyleSheet(
                f"color: {Theme.text3()}; font-size: 8pt; padding-bottom: 4px;"
            )
        for btn in self._buttons.values():
            btn.style().unpolish(btn)
            btn.style().polish(btn)
