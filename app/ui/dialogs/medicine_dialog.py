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
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.services.inventory_service import (
    DuplicateMedicineError,
    MedicineNotFoundError,
)


class MedicineDialog(QDialog):
    """Reusable dialog for adding or editing a medicine."""

    def __init__(
        self,
        parent: QWidget | None = None,
        title: str = "Add Medicine",
        medicine_name: str = "",
        generic_name: str = "",
        company: str = "",
        category: str = "",
        barcode: str = "",
        rack_location: str = "",
        minimum_stock: int = 0,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(480)
        self.setModal(True)
        self._result_data: dict | None = None
        self._build_ui(
            medicine_name, generic_name, company, category,
            barcode, rack_location, minimum_stock,
        )

    def _build_ui(
        self,
        medicine_name: str,
        generic_name: str,
        company: str,
        category: str,
        barcode: str,
        rack_location: str,
        minimum_stock: int,
    ) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(10)

        self._name_edit = QLineEdit(medicine_name)
        self._name_edit.setPlaceholderText("e.g. Paracetamol 500mg")
        form.addRow("Medicine Name *:", self._name_edit)

        self._generic_edit = QLineEdit(generic_name)
        self._generic_edit.setPlaceholderText("e.g. Acetaminophen")
        form.addRow("Generic Name:", self._generic_edit)

        self._company_edit = QLineEdit(company)
        self._company_edit.setPlaceholderText("e.g. Deurali Pharmaceutical")
        form.addRow("Company:", self._company_edit)

        self._category_edit = QLineEdit(category)
        self._category_edit.setPlaceholderText("e.g. Analgesic")
        form.addRow("Category:", self._category_edit)

        self._barcode_edit = QLineEdit(barcode)
        self._barcode_edit.setPlaceholderText("e.g. 9781234567890")
        form.addRow("Barcode:", self._barcode_edit)

        self._rack_edit = QLineEdit(rack_location)
        self._rack_edit.setPlaceholderText("e.g. A-12")
        form.addRow("Rack Location:", self._rack_edit)

        self._stock_spin = QSpinBox()
        self._stock_spin.setRange(0, 99999)
        self._stock_spin.setValue(minimum_stock)
        form.addRow("Minimum Stock:", self._stock_spin)

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
            QMessageBox.warning(self, "Validation", "Medicine Name cannot be empty.")
            return

        if self._stock_spin.value() < 0:
            QMessageBox.warning(self, "Validation", "Minimum Stock cannot be negative.")
            return

        self._result_data = {
            "medicine_name": name,
            "generic_name": self._generic_edit.text().strip(),
            "company": self._company_edit.text().strip(),
            "category": self._category_edit.text().strip(),
            "barcode": self._barcode_edit.text().strip(),
            "rack_location": self._rack_edit.text().strip(),
            "minimum_stock": self._stock_spin.value(),
        }
        self.accept()

    def get_data(self) -> dict | None:
        """Return the form data if the dialog was accepted, else None."""
        return self._result_data
