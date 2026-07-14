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
from app.services.barcode_service import BarcodeService


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
        medicine_id: int | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(480)
        self.setModal(True)
        self._result_data: dict | None = None
        self._medicine_id = medicine_id
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

        barcode_row = QHBoxLayout()
        barcode_row.setSpacing(6)
        barcode_row.addWidget(self._barcode_edit, 1)

        gen_btn = QPushButton("Generate")
        gen_btn.setObjectName("ToolbarButton")
        gen_btn.setFixedWidth(80)
        gen_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        gen_btn.clicked.connect(self._on_generate_barcode)
        barcode_row.addWidget(gen_btn)

        form.addRow("Barcode:", barcode_row)

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

    def _on_generate_barcode(self) -> None:
        """Generate a unique barcode and fill the field."""
        from app.services.settings_service import SettingsService
        settings = SettingsService.get()
        barcode = BarcodeService.generate_unique(prefix=settings.barcode_prefix)
        self._barcode_edit.setText(barcode)

    def _on_save(self) -> None:
        name = self._name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation", "Medicine Name cannot be empty.")
            return

        if self._stock_spin.value() < 0:
            QMessageBox.warning(self, "Validation", "Minimum Stock cannot be negative.")
            return

        barcode = self._barcode_edit.text().strip()

        # Validate barcode format if provided
        if barcode and not BarcodeService.validate(barcode):
            QMessageBox.warning(
                self, "Invalid Barcode",
                "Barcode must be 4-50 characters, alphanumeric or hyphens only.",
            )
            return

        # Check duplicate barcode
        if barcode:
            owner = BarcodeService.check_duplicate(barcode, exclude_medicine_id=self._medicine_id)
            if owner:
                QMessageBox.warning(
                    self, "Duplicate Barcode",
                    f"Barcode '{barcode}' is already assigned to '{owner}'.",
                )
                return

        self._result_data = {
            "medicine_name": name,
            "generic_name": self._generic_edit.text().strip(),
            "company": self._company_edit.text().strip(),
            "category": self._category_edit.text().strip(),
            "barcode": barcode,
            "rack_location": self._rack_edit.text().strip(),
            "minimum_stock": self._stock_spin.value(),
        }
        self.accept()

    def get_data(self) -> dict | None:
        """Return the form data if the dialog was accepted, else None."""
        return self._result_data
