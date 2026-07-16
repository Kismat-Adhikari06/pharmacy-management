from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QCursor
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.services.supplier_service import (
    DuplicateSupplierError,
    SupplierInUseError,
    SupplierNotFoundError,
    SupplierService,
    SupplierValidationError,
)
from app.ui.dialogs.supplier_detail_dialog import SupplierDetailDialog
from app.ui.dialogs.supplier_dialog import SupplierDialog
from app.ui.theme import Theme


def _make_icon_button(text: str, object_name: str) -> QPushButton:
    btn = QPushButton(text)
    btn.setObjectName(object_name)
    btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
    btn.setFixedSize(28, 24)
    return btn


class SuppliersPage(QWidget):
    """Supplier management page with full CRUD, search, filter, export."""

    COLUMNS: list[tuple[str, int]] = [
        ("Supplier Name", 220),
        ("Phone", 130),
        ("Email", 200),
        ("Status", 80),
        ("Outstanding", 120),
        ("", 70),
    ]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ContentArea")
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(250)
        self._search_timer.timeout.connect(self._do_search)
        self._current_filter = "All"
        self._build_ui()
        self.refresh_data()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        title = QLabel("Suppliers")
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        add_btn = QPushButton("Add Supplier")
        add_btn.setObjectName("PrimaryButton")
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.clicked.connect(self._on_add)
        toolbar.addWidget(add_btn)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setObjectName("ToolbarButton")
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.clicked.connect(self.refresh_data)
        toolbar.addWidget(refresh_btn)

        toolbar.addStretch()

        self._search_edit = QLineEdit()
        self._search_edit.setObjectName("SearchBox")
        self._search_edit.setPlaceholderText("Search suppliers...")
        self._search_edit.setFixedWidth(260)
        self._search_edit.textChanged.connect(self._on_search_text_changed)
        toolbar.addWidget(self._search_edit)

        layout.addLayout(toolbar)

        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)

        filter_label = QLabel("Filter:")
        filter_label.setStyleSheet(f"color: {Theme.text2()}; font-size: 10pt; background: transparent;")
        filter_row.addWidget(filter_label)

        self._filter_combo = QComboBox()
        self._filter_combo.addItems(["All", "Active", "Inactive"])
        self._filter_combo.setFixedWidth(120)
        self._filter_combo.currentTextChanged.connect(self._on_filter_changed)
        filter_row.addWidget(self._filter_combo)

        filter_row.addStretch()

        export_csv_btn = QPushButton("Export CSV")
        export_csv_btn.setObjectName("ToolbarButton")
        export_csv_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        export_csv_btn.clicked.connect(self._export_csv)
        filter_row.addWidget(export_csv_btn)

        export_excel_btn = QPushButton("Export Excel")
        export_excel_btn.setObjectName("ToolbarButton")
        export_excel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        export_excel_btn.clicked.connect(self._export_excel)
        filter_row.addWidget(export_excel_btn)

        layout.addLayout(filter_row)

        self._table = QTableWidget()
        self._table.setObjectName("InventoryTable")
        self._table.setColumnCount(len(self.COLUMNS))
        self._table.setHorizontalHeaderLabels([c[0] for c in self.COLUMNS])
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setStretchLastSection(True)
        for i, (_, width) in enumerate(self.COLUMNS):
            self._table.setColumnWidth(i, width)
        self._table.doubleClicked.connect(self._on_view_detail)
        layout.addWidget(self._table)

        self._empty_label = QLabel("No suppliers found.")
        self._empty_label.setObjectName("EmptyState")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._empty_label)

        self._count_label = QLabel()
        self._count_label.setStyleSheet(f"color: {Theme.text2()}; font-size: 9pt; background: transparent;")
        layout.addWidget(self._count_label)

    def refresh_data(self) -> None:
        term = self._search_edit.text().strip()
        rows = SupplierService.get_filtered(
            status=self._current_filter, query=term,
        )
        self._populate_table(rows)

    def _populate_table(self, rows) -> None:
        self._table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            vals = [
                r.supplier_name,
                r.phone or "",
                r.email or "",
                r.status,
                f"Rs. {r.outstanding_balance:,.2f}",
            ]
            for j, val in enumerate(vals):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter)
                if j == 0:
                    item.setData(Qt.ItemDataRole.UserRole, r.id)
                if j == 3:
                    color = Theme.success() if r.status == "Active" else Theme.danger()
                    item.setForeground(QColor(color))
                if j == 4:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                self._table.setItem(i, j, item)

            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(4, 2, 4, 2)
            actions_layout.setSpacing(4)
            actions_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

            edit_btn = _make_icon_button("\u270e", "ActionEditBtn")
            edit_btn.setToolTip("Edit supplier")
            edit_btn.clicked.connect(
                lambda _, sid=r.id: self._on_edit_by_id(sid)
            )
            actions_layout.addWidget(edit_btn)

            del_btn = _make_icon_button("\u2715", "ActionDeleteBtn")
            del_btn.setToolTip("Delete supplier")
            del_btn.clicked.connect(
                lambda _, sid=r.id, name=r.supplier_name: self._on_delete_by_id(sid, name)
            )
            actions_layout.addWidget(del_btn)

            self._table.setCellWidget(i, len(self.COLUMNS) - 1, actions_widget)

        has = len(rows) > 0
        self._table.setVisible(has)
        self._empty_label.setVisible(not has)
        self._count_label.setText(f"{len(rows)} supplier(s)")

    def _selected_id(self) -> int | None:
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            return None
        item = self._table.item(rows[0].row(), 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _on_search_text_changed(self, _text: str) -> None:
        self._search_timer.start()

    def _do_search(self) -> None:
        self.refresh_data()

    def _on_filter_changed(self, text: str) -> None:
        self._current_filter = text
        self.refresh_data()

    def _on_add(self) -> None:
        dialog = SupplierDialog(self, title="Add Supplier")
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        data = dialog.get_data()
        if data is None:
            return
        try:
            SupplierService.create(**data)
            self.refresh_data()
        except DuplicateSupplierError as exc:
            QMessageBox.warning(self, "Duplicate", str(exc))
        except SupplierValidationError as exc:
            QMessageBox.warning(self, "Validation", str(exc))
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to add supplier:\n{exc}")

    def _on_edit(self) -> None:
        sup_id = self._selected_id()
        if sup_id is not None:
            self._on_edit_by_id(sup_id)

    def _on_edit_by_id(self, sup_id: int) -> None:
        sup = SupplierService.get_by_id(sup_id)
        if sup is None:
            QMessageBox.warning(self, "Not Found", "Supplier not found.")
            return

        dialog = SupplierDialog(
            self,
            title="Edit Supplier",
            supplier_name=sup.supplier_name,
            contact_person=sup.contact_person,
            phone=sup.phone,
            email=sup.email,
            address=sup.address,
            pan_number=sup.pan_number,
            registration_number=sup.registration_number,
            status=sup.status,
            outstanding_balance=sup.outstanding_balance,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        data = dialog.get_data()
        if data is None:
            return
        try:
            SupplierService.update(sup_id, **data)
            self.refresh_data()
        except DuplicateSupplierError as exc:
            QMessageBox.warning(self, "Duplicate", str(exc))
        except SupplierNotFoundError as exc:
            QMessageBox.warning(self, "Not Found", str(exc))
        except SupplierValidationError as exc:
            QMessageBox.warning(self, "Validation", str(exc))
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to update supplier:\n{exc}")

    def _on_delete(self) -> None:
        sup_id = self._selected_id()
        if sup_id is None:
            return
        item = self._table.item(
            self._table.selectionModel().selectedRows()[0].row(), 0
        )
        name = item.text() if item else "this supplier"
        self._on_delete_by_id(sup_id, name)

    def _on_delete_by_id(self, sup_id: int, name: str) -> None:
        reply = QMessageBox.question(
            self, "Confirm Delete", f'Delete supplier "{name}"?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            SupplierService.delete(sup_id)
            self.refresh_data()
        except SupplierInUseError as exc:
            QMessageBox.warning(self, "Cannot Delete", str(exc))
        except SupplierNotFoundError as exc:
            QMessageBox.warning(self, "Not Found", str(exc))
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to delete supplier:\n{exc}")

    def _on_view_detail(self) -> None:
        sup_id = self._selected_id()
        if sup_id is None:
            return
        detail = SupplierService.get_detail(sup_id)
        if detail is None:
            QMessageBox.warning(self, "Not Found", "Supplier not found.")
            return
        dlg = SupplierDetailDialog(detail, self)
        dlg.exec()

    def _export_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Suppliers CSV", "suppliers.csv", "CSV Files (*.csv)"
        )
        if not path:
            return
        try:
            SupplierService.export_csv(path)
            QMessageBox.information(self, "Exported", f"Suppliers exported to:\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Export failed:\n{exc}")

    def _export_excel(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Suppliers Excel", "suppliers.xls", "Excel Files (*.xls)"
        )
        if not path:
            return
        try:
            SupplierService.export_excel(path)
            QMessageBox.information(self, "Exported", f"Suppliers exported to:\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Export failed:\n{exc}")
