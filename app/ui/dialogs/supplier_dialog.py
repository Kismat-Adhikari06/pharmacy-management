from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
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
        phone: str = "",
        email: str = "",
        address: str = "",
        pan_number: str = "",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(460)
        self.setModal(True)
        self._result_data: dict | None = None
        self._build_ui(supplier_name, phone, email, address, pan_number)

    def _build_ui(
        self,
        supplier_name: str,
        phone: str,
        email: str,
        address: str,
        pan_number: str,
    ) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(10)

        self._name_edit = QLineEdit(supplier_name)
        self._name_edit.setPlaceholderText("e.g. Deurali Pharmaceutical")
        form.addRow("Supplier Name *:", self._name_edit)

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

        layout.addLayout(form)

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

        layout.addLayout(btn_row)

    def _on_save(self) -> None:
        name = self._name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation", "Supplier Name cannot be empty.")
            return

        self._result_data = {
            "supplier_name": name,
            "phone": self._phone_edit.text().strip(),
            "email": self._email_edit.text().strip(),
            "address": self._address_edit.text().strip(),
            "pan_number": self._pan_edit.text().strip(),
        }
        self.accept()

    def get_data(self) -> dict | None:
        """Return the form data if the dialog was accepted, else None."""
        return self._result_data
