from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class SupplierDialog(QDialog):
    """Reusable dialog for adding or editing a supplier."""

    def __init__(
        self,
        parent: QWidget | None = None,
        title: str = "Add Supplier",
        supplier_name: str = "",
        contact_person: str = "",
        phone: str = "",
        email: str = "",
        address: str = "",
        pan_number: str = "",
        registration_number: str = "",
        status: str = "Active",
        outstanding_balance: float = 0.0,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(520)
        self.setMinimumHeight(480)
        self.setModal(True)
        self._result_data: dict | None = None
        self._build_ui(
            supplier_name, contact_person, phone, email, address,
            pan_number, registration_number, status, outstanding_balance,
        )

    def _build_ui(
        self,
        supplier_name: str,
        contact_person: str,
        phone: str,
        email: str,
        address: str,
        pan_number: str,
        registration_number: str,
        status: str,
        outstanding_balance: float,
    ) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(12)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 8, 4, 8)

        form = QFormLayout()
        form.setSpacing(10)

        self._name_edit = QLineEdit(supplier_name)
        self._name_edit.setPlaceholderText("e.g. Deurali Pharmaceutical")
        form.addRow("Supplier Name *:", self._name_edit)

        self._contact_edit = QLineEdit(contact_person)
        self._contact_edit.setPlaceholderText("e.g. Ram Shrestha")
        form.addRow("Contact Person:", self._contact_edit)

        self._phone_edit = QLineEdit(phone)
        self._phone_edit.setPlaceholderText("e.g. 9841234567")
        form.addRow("Phone:", self._phone_edit)

        self._email_edit = QLineEdit(email)
        self._email_edit.setPlaceholderText("e.g. info@deurali.com")
        form.addRow("Email:", self._email_edit)

        self._address_edit = QLineEdit(address)
        self._address_edit.setPlaceholderText("e.g. Kathmandu, Nepal")
        form.addRow("Address:", self._address_edit)

        self._pan_edit = QLineEdit(pan_number)
        self._pan_edit.setPlaceholderText("e.g. 123456789")
        form.addRow("PAN Number:", self._pan_edit)

        self._reg_edit = QLineEdit(registration_number)
        self._reg_edit.setPlaceholderText("e.g. REG-12345")
        form.addRow("Registration No:", self._reg_edit)

        self._status_combo = QComboBox()
        self._status_combo.addItems(["Active", "Inactive"])
        idx = self._status_combo.findText(status)
        if idx >= 0:
            self._status_combo.setCurrentIndex(idx)
        form.addRow("Status:", self._status_combo)

        self._balance_spin = QDoubleSpinBox()
        self._balance_spin.setRange(0.0, 999999999.99)
        self._balance_spin.setDecimals(2)
        self._balance_spin.setPrefix("Rs. ")
        self._balance_spin.setValue(outstanding_balance)
        form.addRow("Outstanding Balance:", self._balance_spin)

        layout.addLayout(form)
        scroll.setWidget(container)
        root.addWidget(scroll, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        save_btn = QPushButton("Save")
        save_btn.setObjectName("PrimaryButton")
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(save_btn)

        root.addLayout(btn_row)

    def _on_save(self) -> None:
        name = self._name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation", "Supplier Name cannot be empty.")
            return

        phone = self._phone_edit.text().strip()
        email = self._email_edit.text().strip()

        if phone:
            import re
            if not re.match(r"^[\d\+\-\(\)\s]{7,20}$", phone):
                QMessageBox.warning(
                    self, "Validation",
                    "Invalid phone number format.\nUse 7-20 digits with optional +, -, (, ).",
                )
                return

        if email:
            import re
            if not re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", email):
                QMessageBox.warning(
                    self, "Validation",
                    "Invalid email address format.",
                )
                return

        self._result_data = {
            "supplier_name": name,
            "contact_person": self._contact_edit.text().strip(),
            "phone": phone,
            "email": email,
            "address": self._address_edit.text().strip(),
            "pan_number": self._pan_edit.text().strip(),
            "registration_number": self._reg_edit.text().strip(),
            "status": self._status_combo.currentText(),
            "outstanding_balance": self._balance_spin.value(),
        }
        self.accept()

    def get_data(self) -> dict | None:
        """Return the form data if the dialog was accepted, else None."""
        return self._result_data
