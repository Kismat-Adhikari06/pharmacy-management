from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDoubleSpinBox,
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


class BatchDialog(QDialog):
    """Reusable dialog for adding or editing a batch."""

    def __init__(
        self,
        parent: QWidget | None = None,
        title: str = "Add Batch",
        batch_number: str = "",
        expiry_date: date | None = None,
        purchase_price: float = 0.0,
        selling_price: float = 0.0,
        quantity: int = 0,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(460)
        self.setModal(True)
        self._result_data: dict | None = None
        self._build_ui(
            batch_number, expiry_date, purchase_price, selling_price, quantity,
        )

    def _build_ui(
        self,
        batch_number: str,
        expiry_date: date | None,
        purchase_price: float,
        selling_price: float,
        quantity: int,
    ) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(10)

        self._batch_edit = QLineEdit(batch_number)
        self._batch_edit.setPlaceholderText("e.g. BATCH-001")
        form.addRow("Batch Number *:", self._batch_edit)

        today = date.today()
        default_expiry = expiry_date or date(today.year + 1, today.month, today.day)
        self._expiry_edit = QLineEdit(default_expiry.strftime("%Y-%m-%d"))
        self._expiry_edit.setPlaceholderText("YYYY-MM-DD")
        form.addRow("Expiry Date *:", self._expiry_edit)

        self._purchase_spin = QDoubleSpinBox()
        self._purchase_spin.setRange(0.0, 999999.99)
        self._purchase_spin.setDecimals(2)
        self._purchase_spin.setValue(purchase_price)
        self._purchase_spin.setPrefix("Rs. ")
        form.addRow("Purchase Price *:", self._purchase_spin)

        self._selling_spin = QDoubleSpinBox()
        self._selling_spin.setRange(0.0, 999999.99)
        self._selling_spin.setDecimals(2)
        self._selling_spin.setValue(selling_price)
        self._selling_spin.setPrefix("Rs. ")
        form.addRow("Selling Price *:", self._selling_spin)

        self._qty_spin = QSpinBox()
        self._qty_spin.setRange(0, 99999)
        self._qty_spin.setValue(quantity)
        form.addRow("Quantity *:", self._qty_spin)

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
        batch_number = self._batch_edit.text().strip()
        if not batch_number:
            QMessageBox.warning(self, "Validation", "Batch Number cannot be empty.")
            return

        expiry_text = self._expiry_edit.text().strip()
        if not expiry_text:
            QMessageBox.warning(self, "Validation", "Expiry Date cannot be empty.")
            return
        try:
            expiry_date = date.fromisoformat(expiry_text)
        except ValueError:
            QMessageBox.warning(
                self, "Validation", "Expiry Date must be in YYYY-MM-DD format."
            )
            return

        purchase = self._purchase_spin.value()
        selling = self._selling_spin.value()
        if selling < purchase:
            reply = QMessageBox.question(
                self,
                "Price Warning",
                "Selling price is lower than purchase price. Continue anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        qty = self._qty_spin.value()

        self._result_data = {
            "batch_number": batch_number,
            "expiry_date": expiry_date,
            "purchase_price": purchase,
            "selling_price": selling,
            "quantity": qty,
        }
        self.accept()

    def get_data(self) -> dict | None:
        """Return the form data if the dialog was accepted, else None."""
        return self._result_data
