from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDateEdit,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.services.inventory_service import InventoryService
from app.services.supplier_service import SupplierService
from app.services.purchase_service import PurchaseService


class NewPurchaseDialog(QDialog):
    """Full purchase entry window with header info and item rows."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Purchase")
        self.setMinimumSize(950, 620)
        self.setModal(True)
        self._item_rows: list[dict] = []
        self._result_data: dict | None = None
        self._build_ui()
        self._load_suppliers()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        header_form = QFormLayout()
        header_form.setSpacing(8)

        self._supplier_combo = QComboBox()
        self._supplier_combo.setMinimumWidth(250)
        header_form.addRow("Supplier *:", self._supplier_combo)

        self._invoice_edit = QLineEdit()
        self._invoice_edit.setPlaceholderText("e.g. INV-2026-001")
        header_form.addRow("Invoice Number *:", self._invoice_edit)

        self._date_edit = QDateEdit()
        self._date_edit.setDate(date.today())
        self._date_edit.setCalendarPopup(True)
        header_form.addRow("Invoice Date *:", self._date_edit)

        self._notes_edit = QLineEdit()
        self._notes_edit.setPlaceholderText("Optional notes")
        header_form.addRow("Notes:", self._notes_edit)

        layout.addLayout(header_form)

        item_toolbar = QHBoxLayout()
        item_toolbar.setSpacing(8)

        add_row_btn = QPushButton("\u2795  Add Row")
        add_row_btn.setObjectName("ToolbarButton")
        add_row_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_row_btn.clicked.connect(self._add_empty_row)
        item_toolbar.addWidget(add_row_btn)

        dup_row_btn = QPushButton("\u2398  Duplicate Row")
        dup_row_btn.setObjectName("ToolbarButton")
        dup_row_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        dup_row_btn.clicked.connect(self._duplicate_row)
        item_toolbar.addWidget(dup_row_btn)

        del_row_btn = QPushButton("\U0001f5d1\ufe0f  Delete Row")
        del_row_btn.setObjectName("ToolbarButton")
        del_row_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_row_btn.clicked.connect(self._delete_row)
        item_toolbar.addWidget(del_row_btn)

        item_toolbar.addStretch()

        self._total_label = QLabel("Total: Rs. 0.00")
        self._total_label.setObjectName("SectionTitle")
        item_toolbar.addWidget(self._total_label)

        layout.addLayout(item_toolbar)

        self._item_table = QTableWidget()
        self._item_table.setColumnCount(7)
        self._item_table.setHorizontalHeaderLabels([
            "Medicine", "Batch Number", "Expiry Date",
            "Qty", "Purchase Price", "Selling Price", "Line Total",
        ])
        self._item_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._item_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._item_table.horizontalHeader().setStretchLastSection(True)
        self._item_table.verticalHeader().setVisible(False)
        self._item_table.setAlternatingRowColors(True)
        for i, w in enumerate([220, 130, 100, 70, 110, 110, 100]):
            self._item_table.setColumnWidth(i, w)
        layout.addWidget(self._item_table, 1)

        self._add_empty_row()

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        save_btn = QPushButton("Save Purchase")
        save_btn.setObjectName("PrimaryButton")
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(save_btn)

        layout.addLayout(btn_row)

    def _load_suppliers(self) -> None:
        self._supplier_combo.addItem("-- Select Supplier --", None)
        for s in SupplierService.get_all():
            self._supplier_combo.addItem(s.supplier_name, s.id)

    def _add_empty_row(self) -> None:
        row = self._item_table.rowCount()
        self._item_table.insertRow(row)
        self._item_rows.insert(row, {"medicine_id": None, "medicine_name": ""})

        med_edit = QLineEdit()
        med_edit.setPlaceholderText("Search medicine...")
        med_edit.textChanged.connect(lambda text, r=row: self._on_medicine_search(text, r))
        self._item_table.setCellWidget(row, 0, med_edit)

        batch_edit = QLineEdit()
        batch_edit.setPlaceholderText("BATCH-001")
        self._item_table.setCellWidget(row, 1, batch_edit)

        expiry_edit = QLineEdit()
        expiry_edit.setPlaceholderText("YYYY-MM-DD")
        expiry_edit.setText(date.today().replace(year=date.today().year + 1).strftime("%Y-%m-%d"))
        self._item_table.setCellWidget(row, 2, expiry_edit)

        qty_spin = QSpinBox()
        qty_spin.setRange(1, 99999)
        qty_spin.setValue(1)
        qty_spin.valueChanged.connect(lambda: self._recalc_totals())
        self._item_table.setCellWidget(row, 3, qty_spin)

        pp_spin = QDoubleSpinBox()
        pp_spin.setRange(0.0, 999999.99)
        pp_spin.setDecimals(2)
        pp_spin.setPrefix("Rs. ")
        pp_spin.valueChanged.connect(lambda: self._recalc_totals())
        self._item_table.setCellWidget(row, 4, pp_spin)

        sp_spin = QDoubleSpinBox()
        sp_spin.setRange(0.0, 999999.99)
        sp_spin.setDecimals(2)
        sp_spin.setPrefix("Rs. ")
        sp_spin.valueChanged.connect(lambda: self._recalc_totals())
        self._item_table.setCellWidget(row, 5, sp_spin)

        total_item = QTableWidgetItem("Rs. 0.00")
        total_item.setFlags(total_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self._item_table.setItem(row, 6, total_item)

    def _duplicate_row(self) -> None:
        rows = self._item_table.selectionModel().selectedRows()
        if not rows:
            return
        src = rows[0].row()
        self._add_empty_row()
        dst = self._item_table.rowCount() - 1

        med_src = self._item_table.cellWidget(src, 0)
        if isinstance(med_src, QLineEdit):
            med_dst = self._item_table.cellWidget(dst, 0)
            if isinstance(med_dst, QLineEdit):
                med_dst.setText(med_src.text())

        for col in [1, 2]:
            w_src = self._item_table.cellWidget(src, col)
            w_dst = self._item_table.cellWidget(dst, col)
            if isinstance(w_src, QLineEdit) and isinstance(w_dst, QLineEdit):
                w_dst.setText(w_src.text())

        qty_src = self._item_table.cellWidget(src, 3)
        qty_dst = self._item_table.cellWidget(dst, 3)
        if isinstance(qty_src, QSpinBox) and isinstance(qty_dst, QSpinBox):
            qty_dst.setValue(qty_src.value())

        for col in [4, 5]:
            w_src = self._item_table.cellWidget(src, col)
            w_dst = self._item_table.cellWidget(dst, col)
            if isinstance(w_src, QDoubleSpinBox) and isinstance(w_dst, QDoubleSpinBox):
                w_dst.setValue(w_src.value())

        self._item_rows[dst] = dict(self._item_rows[src])

    def _delete_row(self) -> None:
        rows = self._item_table.selectionModel().selectedRows()
        if not rows:
            return
        row = rows[0].row()
        if self._item_table.rowCount() <= 1:
            QMessageBox.information(self, "Info", "At least one item is required.")
            return
        self._item_table.removeRow(row)
        self._item_rows.pop(row)
        self._recalc_totals()

    def _on_medicine_search(self, text: str, row: int) -> None:
        if not text or len(text) < 2:
            return
        results = InventoryService.search(text)
        if results:
            med = results[0]
            self._item_rows[row]["medicine_id"] = med.id
            self._item_rows[row]["medicine_name"] = med.medicine_name

    def _recalc_totals(self) -> None:
        grand = 0.0
        for row in range(self._item_table.rowCount()):
            qty_w = self._item_table.cellWidget(row, 3)
            pp_w = self._item_table.cellWidget(row, 4)
            if isinstance(qty_w, QSpinBox) and isinstance(pp_w, QDoubleSpinBox):
                line_total = qty_w.value() * pp_w.value()
                item = QTableWidgetItem(f"Rs. {line_total:.2f}")
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self._item_table.setItem(row, 6, item)
                grand += line_total
        self._total_label.setText(f"Total: Rs. {grand:.2f}")

    def _on_save(self) -> None:
        supplier_id = self._supplier_combo.currentData()
        if supplier_id is None:
            QMessageBox.warning(self, "Validation", "Please select a supplier.")
            return

        invoice = self._invoice_edit.text().strip()
        if not invoice:
            QMessageBox.warning(self, "Validation", "Invoice Number cannot be empty.")
            return

        items = []
        for row in range(self._item_table.rowCount()):
            med_data = self._item_rows[row] if row < len(self._item_rows) else {}
            med_id = med_data.get("medicine_id")

            batch_w = self._item_table.cellWidget(row, 1)
            expiry_w = self._item_table.cellWidget(row, 2)
            qty_w = self._item_table.cellWidget(row, 3)
            pp_w = self._item_table.cellWidget(row, 4)
            sp_w = self._item_table.cellWidget(row, 5)

            if not isinstance(batch_w, QLineEdit) or not isinstance(expiry_w, QLineEdit):
                continue
            if not isinstance(qty_w, QSpinBox) or not isinstance(pp_w, QDoubleSpinBox):
                continue
            if not isinstance(sp_w, QDoubleSpinBox):
                continue

            batch_num = batch_w.text().strip()
            expiry_text = expiry_w.text().strip()
            qty = qty_w.value()
            pp = pp_w.value()
            sp = sp_w.value()

            if not batch_num:
                QMessageBox.warning(self, "Validation", f"Row {row+1}: Batch Number is required.")
                return

            if not expiry_text:
                QMessageBox.warning(self, "Validation", f"Row {row+1}: Expiry Date is required.")
                return
            try:
                expiry_date = date.fromisoformat(expiry_text)
            except ValueError:
                QMessageBox.warning(
                    self, "Validation",
                    f"Row {row+1}: Expiry Date must be YYYY-MM-DD format.",
                )
                return

            if qty < 1:
                QMessageBox.warning(self, "Validation", f"Row {row+1}: Quantity must be > 0.")
                return
            if pp < 0:
                QMessageBox.warning(self, "Validation", f"Row {row+1}: Purchase price cannot be negative.")
                return

            if med_id is None:
                med_name = med_data.get("medicine_name", "")
                if not med_name:
                    med_name = batch_w.text().strip() if batch_w.text().strip() else ""
                    med_edit = self._item_table.cellWidget(row, 0)
                    if isinstance(med_edit, QLineEdit):
                        med_name = med_edit.text().strip()
                if not med_name:
                    QMessageBox.warning(self, "Validation", f"Row {row+1}: Medicine is required.")
                    return

                from app.services.inventory_service import DuplicateMedicineError
                try:
                    created = InventoryService.create(medicine_name=med_name)
                    med_id = created.id
                except DuplicateMedicineError:
                    results = InventoryService.search(med_name)
                    if results:
                        med_id = results[0].id
                    else:
                        QMessageBox.warning(self, "Validation", f"Row {row+1}: Could not create medicine.")
                        return

            items.append({
                "medicine_id": med_id,
                "medicine_name": med_data.get("medicine_name", ""),
                "batch_number": batch_num,
                "expiry_date": expiry_date,
                "quantity": qty,
                "purchase_price": pp,
                "selling_price": sp,
            })

        if not items:
            QMessageBox.warning(self, "Validation", "At least one purchase item is required.")
            return

        from app.services.purchase_service import (
            DuplicateInvoiceError,
            PurchaseItemData,
            PurchaseValidationError,
        )

        try:
            purchase_items = [PurchaseItemData(**item) for item in items]
            purchase_id = PurchaseService.create_purchase(
                supplier_id=supplier_id,
                invoice_number=invoice,
                purchase_date=self._date_edit.date().toPython(),
                items=purchase_items,
                notes=self._notes_edit.text().strip(),
            )
            self._result_data = {"purchase_id": purchase_id}
            self.accept()
        except DuplicateInvoiceError as exc:
            QMessageBox.warning(self, "Duplicate", str(exc))
        except PurchaseValidationError as exc:
            QMessageBox.warning(self, "Validation", str(exc))
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to save purchase:\n{exc}")

    def get_data(self) -> dict | None:
        """Return the result data if the dialog was accepted, else None."""
        return self._result_data
