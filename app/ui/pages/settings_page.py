from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.services.settings_service import AppSettings, SettingsService

logger = logging.getLogger(__name__)

# ── Colour palette (matches dark.qss) ──────────────────────────
_TEXT = "#cdd6f4"
_SUBTEXT = "#a6adc8"
_BLUE = "#89b4fa"
_GREEN = "#a6e3a1"
_YELLOW = "#f9e2af"
_RED = "#f38ba8"
_BORDER = "#313244"
_CARD_BG = "#181825"


class SettingsPage(QWidget):
    """Complete settings page with 6 sections, save/reset/cancel."""

    settings_changed = Signal()

    SECTIONS: list[tuple[str, str]] = [
        ("Pharmacy Info", "\U0001f3e5"),
        ("Billing", "\U0001f4b3"),
        ("Notifications", "\U0001f514"),
        ("Appearance", "\U0001f3a8"),
        ("Backup", "\U0001f4be"),
        ("AI Settings", "\U0001f916"),
    ]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ContentArea")
        self._settings = SettingsService.get()
        self._build_ui()
        self._load_form()
        self._connect_signals()

    # ── UI construction ─────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header ─────────────────────────────────────────────
        hdr = QHBoxLayout()
        hdr.setContentsMargins(20, 16, 20, 8)
        title = QLabel("\u2699\ufe0f Settings")
        title.setObjectName("PageTitle")
        hdr.addWidget(title)
        hdr.addStretch()
        root.addLayout(hdr)

        # ── Body: sidebar + content ────────────────────────────
        body = QHBoxLayout()
        body.setContentsMargins(20, 8, 20, 0)
        body.setSpacing(16)

        # Left: section nav
        self._nav_layout = QVBoxLayout()
        self._nav_layout.setSpacing(4)
        self._nav_buttons: dict[str, QPushButton] = {}
        for label, icon in self.SECTIONS:
            btn = QPushButton(f"  {icon}  {label}")
            btn.setCheckable(True)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.setObjectName("SettingsNavBtn")
            btn.clicked.connect(lambda checked, l=label: self._switch_section(l))
            self._nav_buttons[label] = btn
            self._nav_layout.addWidget(btn)
        self._nav_layout.addStretch()
        body.addLayout(self._nav_layout)

        # Right: stacked content
        self._stack = QStackedWidget()
        self._stack.setObjectName("SettingsContent")

        self._page_pharmacy = self._build_pharmacy_page()
        self._page_billing = self._build_billing_page()
        self._page_notifications = self._build_notifications_page()
        self._page_appearance = self._build_appearance_page()
        self._page_backup = self._build_backup_page()
        self._page_ai = self._build_ai_page()

        self._stack.addWidget(self._page_pharmacy)
        self._stack.addWidget(self._page_billing)
        self._stack.addWidget(self._page_notifications)
        self._stack.addWidget(self._page_appearance)
        self._stack.addWidget(self._page_backup)
        self._stack.addWidget(self._page_ai)

        body.addWidget(self._stack, 1)
        root.addLayout(body, 1)

        # ── Bottom buttons ─────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(20, 12, 20, 16)
        btn_row.setSpacing(10)

        self._status_label = QLabel("")
        self._status_label.setStyleSheet(f"color: {_SUBTEXT}; font-size: 9pt;")
        btn_row.addWidget(self._status_label)
        btn_row.addStretch()

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setObjectName("ToolbarButton")
        self._cancel_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_row.addWidget(self._cancel_btn)

        self._reset_btn = QPushButton("Reset to Defaults")
        self._reset_btn.setObjectName("ToolbarButton")
        self._reset_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_row.addWidget(self._reset_btn)

        self._save_btn = QPushButton("Save")
        self._save_btn.setObjectName("PrimaryButton")
        self._save_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_row.addWidget(self._save_btn)

        root.addLayout(btn_row)

        # Activate first section
        self._switch_section("Pharmacy Info")

    # ── Section builders ────────────────────────────────────────

    def _build_form_page(self) -> tuple[QVBoxLayout, QWidget]:
        """Create a scrollable form page. Returns (outer_layout, form_widget)."""
        outer = QVBoxLayout()
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setObjectName("ContentArea")

        form_widget = QWidget()
        form_widget.setObjectName("ContentArea")
        form_layout = QVBoxLayout(form_widget)
        form_layout.setContentsMargins(16, 12, 16, 12)
        form_layout.setSpacing(12)

        scroll.setWidget(form_widget)
        outer.addWidget(scroll)
        return outer, form_widget

    def _add_section_header(self, layout: QVBoxLayout, text: str) -> None:
        lbl = QLabel(text)
        lbl.setObjectName("SettingsSectionHeader")
        layout.addWidget(lbl)

    def _add_field_row(
        self,
        layout: QVBoxLayout,
        label: str,
        widget: QWidget,
        tooltip: str = "",
    ) -> None:
        row = QHBoxLayout()
        row.setSpacing(12)
        lbl = QLabel(label)
        lbl.setFixedWidth(200)
        lbl.setStyleSheet(f"color: {_SUBTEXT}; font-size: 10pt;")
        row.addWidget(lbl)
        if tooltip:
            widget.setToolTip(tooltip)
        row.addWidget(widget, 1)
        row.addStretch()
        layout.addLayout(row)

    # ── Section 1: Pharmacy Info ────────────────────────────────

    def _build_pharmacy_page(self) -> QWidget:
        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setObjectName("ContentArea")

        form = QWidget()
        form.setObjectName("ContentArea")
        layout = QVBoxLayout(form)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        self._add_section_header(layout, "Pharmacy Information")

        self._inp_pharmacy_name = QLineEdit()
        self._add_field_row(layout, "Pharmacy Name", self._inp_pharmacy_name, "Name displayed on receipts")

        self._inp_address = QLineEdit()
        self._add_field_row(layout, "Address", self._inp_address, "Full pharmacy address")

        self._inp_phone = QLineEdit()
        self._add_field_row(layout, "Phone Number", self._inp_phone, "Contact number")

        self._inp_email = QLineEdit()
        self._add_field_row(layout, "Email", self._inp_email, "Email address")

        self._inp_pan = QLineEdit()
        self._add_field_row(layout, "PAN/VAT Number", self._inp_pan, "Tax registration number")

        self._inp_reg_no = QLineEdit()
        self._add_field_row(layout, "Registration Number", self._inp_reg_no, "Business registration number")

        layout.addStretch()
        scroll.setWidget(form)
        outer.addWidget(scroll)
        return container

    # ── Section 2: Billing ──────────────────────────────────────

    def _build_billing_page(self) -> QWidget:
        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setObjectName("ContentArea")

        form = QWidget()
        form.setObjectName("ContentArea")
        layout = QVBoxLayout(form)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        self._add_section_header(layout, "Billing Settings")

        self._inp_vat = QDoubleSpinBox()
        self._inp_vat.setRange(0.0, 100.0)
        self._inp_vat.setSuffix(" %")
        self._inp_vat.setSingleStep(0.5)
        self._add_field_row(layout, "Default VAT %", self._inp_vat, "Applied to all sales")

        self._inp_receipt_width = QComboBox()
        self._inp_receipt_width.addItems(["58mm", "80mm", "A4"])
        self._add_field_row(layout, "Receipt Width", self._inp_receipt_width, "Thermal printer paper width")

        self._inp_currency = QLineEdit()
        self._inp_currency.setFixedWidth(100)
        self._add_field_row(layout, "Currency Symbol", self._inp_currency, "Display on receipts and invoices")

        self._inp_footer = QLineEdit()
        self._add_field_row(layout, "Receipt Footer Message", self._inp_footer, "Shown at the bottom of receipts")

        self._inp_auto_print = QComboBox()
        self._inp_auto_print.addItems(["No", "Yes"])
        self._add_field_row(layout, "Auto Print After Sale", self._inp_auto_print, "Automatically print receipt after sale")

        layout.addStretch()
        scroll.setWidget(form)
        outer.addWidget(scroll)
        return container

    # ── Section 3: Notifications ────────────────────────────────

    def _build_notifications_page(self) -> QWidget:
        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setObjectName("ContentArea")

        form = QWidget()
        form.setObjectName("ContentArea")
        layout = QVBoxLayout(form)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        self._add_section_header(layout, "Notification Settings")

        self._chk_expiry = QCheckBox("Enable Expiry Warnings")
        self._add_field_row(layout, "Expiry Alerts", self._chk_expiry, "Show warnings for expiring medicines")

        self._chk_low_stock = QCheckBox("Enable Low Stock Warnings")
        self._add_field_row(layout, "Low Stock Alerts", self._chk_low_stock, "Show warnings for low stock medicines")

        self._inp_expiry_days = QSpinBox()
        self._inp_expiry_days.setRange(7, 365)
        self._inp_expiry_days.setSuffix(" days")
        self._inp_expiry_days.setSingleStep(30)
        self._add_field_row(layout, "Days Before Expiry", self._inp_expiry_days, "Warning window for expiring items")

        layout.addStretch()
        scroll.setWidget(form)
        outer.addWidget(scroll)
        return container

    # ── Section 4: Appearance ───────────────────────────────────

    def _build_appearance_page(self) -> QWidget:
        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setObjectName("ContentArea")

        form = QWidget()
        form.setObjectName("ContentArea")
        layout = QVBoxLayout(form)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        self._add_section_header(layout, "Appearance Settings")

        self._inp_theme = QComboBox()
        self._inp_theme.addItems(["dark", "light", "system"])
        self._add_field_row(layout, "Theme", self._inp_theme, "Application colour theme (light/system future-ready)")

        self._inp_font_size = QComboBox()
        self._inp_font_size.addItems(["Small", "Medium", "Large"])
        self._add_field_row(layout, "Font Size", self._inp_font_size, "Base font size for the application")

        layout.addStretch()
        scroll.setWidget(form)
        outer.addWidget(scroll)
        return container

    # ── Section 5: Backup ───────────────────────────────────────

    def _build_backup_page(self) -> QWidget:
        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setObjectName("ContentArea")

        form = QWidget()
        form.setObjectName("ContentArea")
        layout = QVBoxLayout(form)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        self._add_section_header(layout, "Backup Settings")

        # Backup folder row with browse button
        folder_row = QHBoxLayout()
        folder_row.setSpacing(12)
        folder_lbl = QLabel("Backup Folder")
        folder_lbl.setFixedWidth(200)
        folder_lbl.setStyleSheet(f"color: {_SUBTEXT}; font-size: 10pt;")
        folder_row.addWidget(folder_lbl)
        self._inp_backup_folder = QLineEdit()
        folder_row.addWidget(self._inp_backup_folder, 1)
        self._browse_btn = QPushButton("Browse")
        self._browse_btn.setObjectName("ToolbarButton")
        self._browse_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._browse_btn.clicked.connect(self._browse_backup_folder)
        folder_row.addWidget(self._browse_btn)
        folder_row.addStretch()
        layout.addLayout(folder_row)

        self._chk_daily_backup = QCheckBox("Automatic Daily Backup")
        self._add_field_row(layout, "Daily Backup", self._chk_daily_backup, "Backup database every day on startup")

        self._chk_weekly_backup = QCheckBox("Automatic Weekly Backup")
        self._add_field_row(layout, "Weekly Backup", self._chk_weekly_backup, "Backup database once per week on startup")

        self._inp_max_backups = QSpinBox()
        self._inp_max_backups.setRange(1, 100)
        self._inp_max_backups.setSuffix(" backups")
        self._add_field_row(layout, "Maximum Backups", self._inp_max_backups, "Oldest backups are deleted when limit is reached")

        layout.addStretch()
        scroll.setWidget(form)
        outer.addWidget(scroll)
        return container

    # ── Section 6: AI Settings (future) ─────────────────────────

    def _build_ai_page(self) -> QWidget:
        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setObjectName("ContentArea")

        form = QWidget()
        form.setObjectName("ContentArea")
        layout = QVBoxLayout(form)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        self._add_section_header(layout, "AI Settings (Future)")

        future_lbl = QLabel(
            "These settings are for future AI-powered features.\n"
            "Values are saved and will be used when AI integration is enabled."
        )
        future_lbl.setStyleSheet(f"color: {_SUBTEXT}; font-size: 9pt; margin-bottom: 8px;")
        future_lbl.setWordWrap(True)
        layout.addWidget(future_lbl)

        self._inp_api_key = QLineEdit()
        self._inp_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._inp_api_key.setPlaceholderText("gsk_...")
        self._add_field_row(layout, "Groq API Key", self._inp_api_key, "API key for Groq LLM services")

        self._inp_model = QComboBox()
        self._inp_model.setEditable(True)
        self._inp_model.addItems([
            "llama3-8b-8192",
            "llama3-70b-8192",
            "mixtral-8x7b-32768",
            "gemma-7b-it",
        ])
        self._add_field_row(layout, "Groq Model", self._inp_model, "LLM model for AI features")

        self._inp_ocr = QComboBox()
        self._inp_ocr.addItems(["Tesseract", "EasyOCR", "PaddleOCR"])
        self._add_field_row(layout, "OCR Engine", self._inp_ocr, "OCR engine for prescription scanning")

        layout.addStretch()
        scroll.setWidget(form)
        outer.addWidget(scroll)
        return container

    # ── Section navigation ──────────────────────────────────────

    def _switch_section(self, label: str) -> None:
        idx = next(i for i, (l, _) in enumerate(self.SECTIONS) if l == label)
        self._stack.setCurrentIndex(idx)
        for name, btn in self._nav_buttons.items():
            btn.setChecked(name == label)

    # ── Load / Save ─────────────────────────────────────────────

    def _load_form(self) -> None:
        s = self._settings

        # Pharmacy
        self._inp_pharmacy_name.setText(s.pharmacy_name)
        self._inp_address.setText(s.address)
        self._inp_phone.setText(s.phone)
        self._inp_email.setText(s.email)
        self._inp_pan.setText(s.pan_number)
        self._inp_reg_no.setText(s.registration_number)

        # Billing
        self._inp_vat.setValue(s.default_vat)
        idx = self._inp_receipt_width.findText(s.receipt_width)
        if idx >= 0:
            self._inp_receipt_width.setCurrentIndex(idx)
        self._inp_currency.setText(s.currency_symbol)
        self._inp_footer.setText(s.receipt_footer)
        idx = self._inp_auto_print.findText(s.auto_print)
        if idx >= 0:
            self._inp_auto_print.setCurrentIndex(idx)

        # Notifications
        self._chk_expiry.setChecked(s.enable_expiry_warnings == "Yes")
        self._chk_low_stock.setChecked(s.enable_low_stock_warnings == "Yes")
        self._inp_expiry_days.setValue(s.expiry_warning_days)

        # Appearance
        idx = self._inp_theme.findText(s.default_theme)
        if idx >= 0:
            self._inp_theme.setCurrentIndex(idx)
        idx = self._inp_font_size.findText(s.font_size)
        if idx >= 0:
            self._inp_font_size.setCurrentIndex(idx)

        # Backup
        self._inp_backup_folder.setText(s.backup_folder)
        self._chk_daily_backup.setChecked(s.auto_backup_daily == "Yes")
        self._chk_weekly_backup.setChecked(s.auto_backup_weekly == "Yes")
        self._inp_max_backups.setValue(s.max_backups)

        # AI
        self._inp_api_key.setText(s.groq_api_key)
        idx = self._inp_model.findText(s.groq_model)
        if idx >= 0:
            self._inp_model.setCurrentIndex(idx)
        else:
            self._inp_model.setEditText(s.groq_model)
        idx = self._inp_ocr.findText(s.ocr_engine)
        if idx >= 0:
            self._inp_ocr.setCurrentIndex(idx)

    def _collect_form(self) -> AppSettings:
        return AppSettings(
            pharmacy_name=self._inp_pharmacy_name.text().strip(),
            address=self._inp_address.text().strip(),
            phone=self._inp_phone.text().strip(),
            email=self._inp_email.text().strip(),
            pan_number=self._inp_pan.text().strip(),
            registration_number=self._inp_reg_no.text().strip(),
            default_vat=self._inp_vat.value(),
            receipt_width=self._inp_receipt_width.currentText(),
            currency_symbol=self._inp_currency.text().strip() or "Rs",
            receipt_footer=self._inp_footer.text().strip(),
            auto_print=self._inp_auto_print.currentText(),
            enable_expiry_warnings="Yes" if self._chk_expiry.isChecked() else "No",
            enable_low_stock_warnings="Yes" if self._chk_low_stock.isChecked() else "No",
            expiry_warning_days=self._inp_expiry_days.value(),
            default_theme=self._inp_theme.currentText(),
            font_size=self._inp_font_size.currentText(),
            backup_folder=self._inp_backup_folder.text().strip() or "backups",
            auto_backup_daily="Yes" if self._chk_daily_backup.isChecked() else "No",
            auto_backup_weekly="Yes" if self._chk_weekly_backup.isChecked() else "No",
            max_backups=self._inp_max_backups.value(),
            groq_api_key=self._inp_api_key.text().strip(),
            groq_model=self._inp_model.currentText(),
            ocr_engine=self._inp_ocr.currentText(),
        )

    def _save(self) -> None:
        settings = self._collect_form()

        # Validate
        if not settings.pharmacy_name:
            self._status_label.setText("\u26a0\ufe0f Pharmacy name is required.")
            self._status_label.setStyleSheet(f"color: {_RED}; font-size: 9pt;")
            self._switch_section("Pharmacy Info")
            return

        try:
            SettingsService.save(settings)
            self._settings = settings
            self._status_label.setText("\u2705 Settings saved successfully.")
            self._status_label.setStyleSheet(f"color: {_GREEN}; font-size: 9pt;")
            self.settings_changed.emit()
        except Exception as e:
            logger.exception("Failed to save settings")
            self._status_label.setText(f"\u274c Failed to save: {e}")
            self._status_label.setStyleSheet(f"color: {_RED}; font-size: 9pt;")

    def _reset(self) -> None:
        from PySide6.QtWidgets import QMessageBox

        reply = QMessageBox.question(
            self,
            "Reset Settings",
            "Are you sure you want to reset all settings to defaults?\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._settings = SettingsService.reset()
            self._load_form()
            self._status_label.setText("\u2705 Settings reset to defaults.")
            self._status_label.setStyleSheet(f"color: {_GREEN}; font-size: 9pt;")
            self.settings_changed.emit()

    def _cancel(self) -> None:
        self._settings = SettingsService.get()
        self._load_form()
        self._status_label.setText("Changes discarded.")
        self._status_label.setStyleSheet(f"color: {_SUBTEXT}; font-size: 9pt;")

    def _browse_backup_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "Select Backup Folder", self._inp_backup_folder.text()
        )
        if folder:
            self._inp_backup_folder.setText(folder)

    # ── Signals ─────────────────────────────────────────────────

    def _connect_signals(self) -> None:
        self._save_btn.clicked.connect(self._save)
        self._reset_btn.clicked.connect(self._reset)
        self._cancel_btn.clicked.connect(self._cancel)
