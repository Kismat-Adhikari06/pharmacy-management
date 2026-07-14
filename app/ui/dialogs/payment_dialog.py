from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class PaymentDialog(QDialog):
    """Dialog for selecting payment method and entering payment details."""

    def __init__(
        self,
        parent: QWidget | None = None,
        grand_total: float = 0.0,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Payment")
        self.setMinimumWidth(420)
        self.setModal(True)
        self._grand_total = grand_total
        self._result_data: dict | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        total_label = QLabel(f"Grand Total:  Rs. {self._grand_total:.2f}")
        total_label.setObjectName("SectionTitle")
        total_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(total_label)

        form = QFormLayout()
        form.setSpacing(10)

        self._method_combo = _PaymentCombo()
        self._method_combo.addItems(["Cash", "Card", "QR Payment", "Credit"])
        self._method_combo.currentTextChanged.connect(self._on_method_changed)
        form.addRow("Payment Method:", self._method_combo)

        self._discount_spin = QDoubleSpinBox()
        self._discount_spin.setRange(0.0, self._grand_total)
        self._discount_spin.setDecimals(2)
        self._discount_spin.setPrefix("Rs. ")
        self._discount_spin.valueChanged.connect(self._update_summary)
        form.addRow("Discount:", self._discount_spin)

        self._cash_row_label = QLabel("Cash Received:")
        self._cash_row_label.setStyleSheet("color: #a6adc8; font-size: 10pt;")
        self._cash_spin = QDoubleSpinBox()
        self._cash_spin.setRange(0.0, 9999999.0)
        self._cash_spin.setDecimals(2)
        self._cash_spin.setPrefix("Rs. ")
        self._cash_spin.setValue(self._grand_total)
        self._cash_spin.valueChanged.connect(self._update_summary)
        form.addRow(self._cash_row_label, self._cash_spin)

        layout.addLayout(form)

        self._payable_label = QLabel()
        self._payable_label.setObjectName("SectionTitle")
        self._payable_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._payable_label)

        self._change_label = QLabel()
        self._change_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._change_label)

        self._update_summary()

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        pay_btn = QPushButton("Complete Sale")
        pay_btn.setObjectName("PrimaryButton")
        pay_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        pay_btn.clicked.connect(self._on_pay)
        btn_row.addWidget(pay_btn)

        layout.addLayout(btn_row)

        self._on_method_changed("Cash")

    def _on_method_changed(self, method: str) -> None:
        is_cash = method == "Cash"
        self._cash_row_label.setVisible(is_cash)
        self._cash_spin.setVisible(is_cash)
        self._change_label.setVisible(is_cash)
        self._update_summary()

    def _update_summary(self) -> None:
        discount = self._discount_spin.value()
        payable = self._grand_total - discount
        self._payable_label.setText(f"You Pay:  Rs. {payable:.2f}")

        method = self._method_combo.currentText()
        if method == "Cash":
            cash = self._cash_spin.value()
            change = cash - payable
            if change < 0:
                self._change_label.setText(
                    f"Remaining:  Rs. {abs(change):.2f}"
                )
                self._change_label.setStyleSheet(
                    "color: #f38ba8; font-size: 11pt; font-weight: bold;"
                )
            else:
                self._change_label.setText(
                    f"Change:  Rs. {change:.2f}"
                )
                self._change_label.setStyleSheet(
                    "color: #a6e3a1; font-size: 11pt; font-weight: bold;"
                )
        else:
            self._change_label.setText("")

    def _on_pay(self) -> None:
        discount = self._discount_spin.value()
        method = self._method_combo.currentText()
        payable = self._grand_total - discount

        if method == "Cash":
            cash = self._cash_spin.value()
            if cash < payable:
                QMessageBox.warning(
                    self,
                    "Insufficient Payment",
                    f"Cash received (Rs. {cash:.2f}) is less than "
                    f"the payable amount (Rs. {payable:.2f}).",
                )
                return

        self._result_data = {
            "payment_method": method,
            "discount": discount,
            "cash_received": self._cash_spin.value() if method == "Cash" else 0.0,
        }
        self.accept()

    def get_data(self) -> dict | None:
        """Return payment data if accepted, else None."""
        return self._result_data


class _PaymentCombo(QWidget):
    """Simple wrapper that acts like a QComboBox for the form layout."""

    def __init__(self, parent=None):
        super().__init__(parent)
        from PySide6.QtWidgets import QComboBox
        self._combo = QComboBox()
        self._combo.setObjectName("SearchBox")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._combo)
        self.currentTextChanged = self._combo.currentTextChanged

    def addItems(self, items):
        self._combo.addItems(items)

    def currentText(self):
        return self._combo.currentText()
