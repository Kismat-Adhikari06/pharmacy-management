from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDialog,
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
)
from app.ui.dialogs.supplier_dialog import SupplierDialog


class SuppliersPage(QWidget):
    """Supplier management page."""

    COLUMNS: list[tuple[str, int]] = [
        ("Supplier Name", 220),
        ("Phone", 130),
        ("Email", 200),
        ("Address", 220),
        ("PAN", 130),
    ]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ContentArea")
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(250)
        self._search_timer.timeout.connect(self._do_search)
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

        add_btn = QPushButton("\u2795  Add Supplier")
        add_btn.setObjectName("ToolbarButton")
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.clicked.connect(self._on_add)
        toolbar.addWidget(add_btn)

        edit_btn = QPushButton("\u270f\ufe0f  Edit")
        edit_btn.setObjectName("ToolbarButton")
        edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        edit_btn.clicked.connect(self._on_edit)
        toolbar.addWidget(edit_btn)

        delete_btn = QPushButton("\U0001f5d1\ufe0f  Delete")
        delete_btn.setObjectName("ToolbarButton")
        delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        delete_btn.clicked.connect(self._on_delete)
        toolbar.addWidget(delete_btn)

        refresh_btn = QPushButton("\U0001f504  Refresh")
        refresh_btn.setObjectName("ToolbarButton")
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.clicked.connect(self.refresh_data)
        toolbar.addWidget(refresh_btn)

        toolbar.addStretch()

        self._search_edit = QLineEdit()
        self._search_edit.setObjectName("SearchBox")
        self._search_edit.setPlaceholderText("\U0001f50d  Search suppliers...")
        self._search_edit.setFixedWidth(260)
        self._search_edit.textChanged.connect(self._on_search_text_changed)
        toolbar.addWidget(self._search_edit)

        layout.addLayout(toolbar)

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
        self._table.doubleClicked.connect(self._on_edit)
        layout.addWidget(self._table)

        self._empty_label = QLabel("\U0001f69a\n\nNo suppliers found.")
        self._empty_label.setObjectName("EmptyState")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._empty_label)

        layout.addStretch()

    def refresh_data(self) -> None:
        term = self._search_edit.text().strip()
        rows = SupplierService.search(term) if term else SupplierService.get_all()
        self._populate_table(rows)

    def _populate_table(self, rows) -> None:
        self._table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            vals = [r.supplier_name, r.phone, r.email, r.address, r.pan_number]
            for j, val in enumerate(vals):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter)
                if j == 0:
                    item.setData(Qt.ItemDataRole.UserRole, r.id)
                self._table.setItem(i, j, item)
        has = len(rows) > 0
        self._table.setVisible(has)
        self._empty_label.setVisible(not has)

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
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to add supplier:\n{exc}")

    def _on_edit(self) -> None:
        sup_id = self._selected_id()
        if sup_id is None:
            QMessageBox.information(self, "No Selection", "Please select a supplier to edit.")
            return

        sup = SupplierService.get_by_id(sup_id)
        if sup is None:
            QMessageBox.warning(self, "Not Found", "Supplier not found.")
            return

        dialog = SupplierDialog(
            self,
            title="Edit Supplier",
            supplier_name=sup.supplier_name,
            phone=sup.phone,
            email=sup.email,
            address=sup.address,
            pan_number=sup.pan_number,
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
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to update supplier:\n{exc}")

    def _on_delete(self) -> None:
        sup_id = self._selected_id()
        if sup_id is None:
            QMessageBox.information(self, "No Selection", "Please select a supplier to delete.")
            return

        row = self._table.selectionModel().selectedRows()[0].row()
        name_item = self._table.item(row, 0)
        name = name_item.text() if name_item else "this supplier"

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
