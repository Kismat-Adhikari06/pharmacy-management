from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.services.inventory_service import (
    DuplicateMedicineError,
    InventoryService,
    MedicineInUseError,
    MedicineNotFoundError,
)
from app.services.batch_service import (
    BatchInUseError,
    BatchNotFoundError,
    BatchService,
    DuplicateBatchError,
)
from app.services.barcode_service import BarcodeService
from app.ui.dialogs.medicine_dialog import MedicineDialog
from app.ui.dialogs.batch_dialog import BatchDialog
from app.ui.theme import Theme


def _make_icon_button(text: str, object_name: str) -> QPushButton:
    btn = QPushButton(text)
    btn.setObjectName(object_name)
    btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
    btn.setFixedSize(28, 24)
    return btn


class InventoryPage(QWidget):
    """Full inventory page: medicine table (top) + batch table (bottom)."""

    MED_COLUMNS: list[tuple[str, int]] = [
        ("Medicine Name", 280),
        ("Company", 200),
        ("Min Stock", 100),
        ("Stock", 100),
        ("", 70),
    ]

    BATCH_COLUMNS: list[tuple[str, int]] = [
        ("Batch Number", 160),
        ("Expiry Date", 130),
        ("Selling Price", 130),
        ("Quantity", 100),
        ("Status", 130),
        ("", 70),
    ]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ContentArea")
        self._selected_medicine_id: int | None = None
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(250)
        self._search_timer.timeout.connect(self._do_search)
        self._build_ui()
        self.refresh_medicines()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(8)

        title = QLabel("Inventory")
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)

        top = QWidget()
        top_layout = QVBoxLayout(top)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(8)
        self._build_med_toolbar(top_layout)
        self._build_med_table(top_layout)
        self._build_med_empty(top_layout)
        top_layout.addStretch()
        splitter.addWidget(top)

        bottom = QWidget()
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(8)
        self._build_batch_header(bottom_layout)
        self._build_batch_toolbar(bottom_layout)
        self._build_batch_table(bottom_layout)
        self._build_batch_empty(bottom_layout)
        bottom_layout.addStretch()
        splitter.addWidget(bottom)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, 1)

    def _build_med_toolbar(self, parent: QVBoxLayout) -> None:
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        add_btn = QPushButton("+ Add Medicine")
        add_btn.setObjectName("PrimaryButton")
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.clicked.connect(self._on_add_medicine)
        toolbar.addWidget(add_btn)

        toolbar.addStretch()

        self._search_edit = QLineEdit()
        self._search_edit.setObjectName("SearchBox")
        self._search_edit.setPlaceholderText("Search medicines...")
        self._search_edit.setFixedWidth(280)
        self._search_edit.textChanged.connect(self._on_search_text_changed)
        toolbar.addWidget(self._search_edit)

        parent.addLayout(toolbar)

    def _build_med_table(self, parent: QVBoxLayout) -> None:
        self._med_table = QTableWidget()
        self._med_table.setObjectName("InventoryTable")
        self._med_table.setColumnCount(len(self.MED_COLUMNS))
        self._med_table.setHorizontalHeaderLabels([c[0] for c in self.MED_COLUMNS])
        self._med_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._med_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._med_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._med_table.setSortingEnabled(True)
        self._med_table.setAlternatingRowColors(True)
        self._med_table.verticalHeader().setVisible(False)
        self._med_table.horizontalHeader().setStretchLastSection(True)
        for i, (_, width) in enumerate(self.MED_COLUMNS):
            self._med_table.setColumnWidth(i, width)
        self._med_table.doubleClicked.connect(self._on_edit_medicine)
        self._med_table.currentCellChanged.connect(self._on_medicine_selected)
        parent.addWidget(self._med_table)

    def _build_med_empty(self, parent: QVBoxLayout) -> None:
        self._med_empty = QLabel("No medicines found.")
        self._med_empty.setObjectName("EmptyState")
        self._med_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        parent.addWidget(self._med_empty)

    def _build_batch_header(self, parent: QVBoxLayout) -> None:
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {Theme.border()};")
        parent.addWidget(sep)

        header_row = QHBoxLayout()
        self._batch_title = QLabel("Batches")
        self._batch_title.setObjectName("SectionTitle")
        header_row.addWidget(self._batch_title)
        header_row.addStretch()
        self._stock_label = QLabel("Total Stock: 0")
        self._stock_label.setObjectName("StockLabel")
        header_row.addWidget(self._stock_label)
        parent.addLayout(header_row)

    def _build_batch_toolbar(self, parent: QVBoxLayout) -> None:
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        add_btn = QPushButton("Add Batch")
        add_btn.setObjectName("ToolbarButton")
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.clicked.connect(self._on_add_batch)
        toolbar.addWidget(add_btn)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setObjectName("ToolbarButton")
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.clicked.connect(self._refresh_batches)
        toolbar.addWidget(refresh_btn)

        toolbar.addStretch()
        parent.addLayout(toolbar)

    def _build_batch_table(self, parent: QVBoxLayout) -> None:
        self._batch_table = QTableWidget()
        self._batch_table.setObjectName("BatchTable")
        self._batch_table.setColumnCount(len(self.BATCH_COLUMNS))
        self._batch_table.setHorizontalHeaderLabels([c[0] for c in self.BATCH_COLUMNS])
        self._batch_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._batch_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._batch_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._batch_table.setAlternatingRowColors(True)
        self._batch_table.verticalHeader().setVisible(False)
        self._batch_table.horizontalHeader().setStretchLastSection(True)
        for i, (_, width) in enumerate(self.BATCH_COLUMNS):
            self._batch_table.setColumnWidth(i, width)
        parent.addWidget(self._batch_table)

    def _build_batch_empty(self, parent: QVBoxLayout) -> None:
        self._batch_empty = QLabel("Select a medicine to view its batches.")
        self._batch_empty.setObjectName("EmptyState")
        self._batch_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        parent.addWidget(self._batch_empty)

    # ------------------------------------------------------------------
    # Medicine Data
    # ------------------------------------------------------------------

    def refresh_medicines(self) -> None:
        search_term = self._search_edit.text().strip()
        if search_term:
            rows = InventoryService.search(search_term)
        else:
            rows = InventoryService.get_all()
        self._populate_medicine_table(rows)

    def _populate_medicine_table(self, rows) -> None:
        self._med_table.setSortingEnabled(False)
        self._med_table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            values = [
                row.medicine_name,
                row.company or "",
                str(row.minimum_stock),
                str(row.total_stock),
            ]
            for j, val in enumerate(values):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter)
                if j == 0:
                    item.setData(Qt.ItemDataRole.UserRole, row.id)
                if j == 3 and row.total_stock <= row.minimum_stock:
                    color = Theme.warning() if row.total_stock > 0 else Theme.danger()
                    item.setForeground(Qt.QColor(color))
                self._med_table.setItem(i, j, item)

            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(4, 2, 4, 2)
            actions_layout.setSpacing(4)
            actions_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

            edit_btn = _make_icon_button("\u270e", "ActionEditBtn")
            edit_btn.setToolTip("Edit medicine")
            edit_btn.clicked.connect(
                lambda _, mid=row.id: self._on_edit_medicine_by_id(mid)
            )
            actions_layout.addWidget(edit_btn)

            del_btn = _make_icon_button("\u2715", "ActionDeleteBtn")
            del_btn.setToolTip("Delete medicine")
            del_btn.clicked.connect(
                lambda _, mid=row.id, name=row.medicine_name: self._on_delete_medicine_by_id(mid, name)
            )
            actions_layout.addWidget(del_btn)

            self._med_table.setCellWidget(i, len(self.MED_COLUMNS) - 1, actions_widget)

        self._med_table.setSortingEnabled(True)

        has_rows = len(rows) > 0
        self._med_table.setVisible(has_rows)
        self._med_empty.setVisible(not has_rows)

    # ------------------------------------------------------------------
    # Batch Data
    # ------------------------------------------------------------------

    def _refresh_batches(self) -> None:
        if self._selected_medicine_id is None:
            return
        batches = BatchService.get_for_medicine(self._selected_medicine_id)
        stock = BatchService.get_stock(self._selected_medicine_id)
        self._stock_label.setText(f"Total Stock: {stock}")
        self._populate_batch_table(batches)

    def _populate_batch_table(self, batches) -> None:
        self._batch_table.setRowCount(len(batches))
        for i, b in enumerate(batches):
            values = [
                b.batch_number,
                b.expiry_date,
                f"Rs. {b.selling_price:.2f}",
                str(b.quantity),
                b.status,
            ]
            for j, val in enumerate(values):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter)
                if j == 0:
                    item.setData(Qt.ItemDataRole.UserRole, b.id)
                if j == 4:
                    if b.status == "Expired":
                        item.setForeground(Qt.QColor(Theme.danger()))
                    elif b.status == "Expiring Soon":
                        item.setForeground(Qt.QColor(Theme.warning()))
                    else:
                        item.setForeground(Qt.QColor(Theme.success()))
                self._batch_table.setItem(i, j, item)

            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(4, 2, 4, 2)
            actions_layout.setSpacing(4)
            actions_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

            edit_btn = _make_icon_button("\u270e", "ActionEditBtn")
            edit_btn.setToolTip("Edit batch")
            edit_btn.clicked.connect(
                lambda _, bid=b.id: self._on_edit_batch_by_id(bid)
            )
            actions_layout.addWidget(edit_btn)

            del_btn = _make_icon_button("\u2715", "ActionDeleteBtn")
            del_btn.setToolTip("Delete batch")
            del_btn.clicked.connect(
                lambda _, bid=b.id, bnum=b.batch_number: self._on_delete_batch_by_id(bid, bnum)
            )
            actions_layout.addWidget(del_btn)

            self._batch_table.setCellWidget(i, len(self.BATCH_COLUMNS) - 1, actions_widget)

        has_rows = len(batches) > 0
        self._batch_table.setVisible(has_rows)
        self._batch_empty.setVisible(not has_rows)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def _on_search_text_changed(self, _text: str) -> None:
        self._search_timer.start()

    def _do_search(self) -> None:
        self.refresh_medicines()

    # ------------------------------------------------------------------
    # Medicine Selection
    # ------------------------------------------------------------------

    def _on_medicine_selected(self, row: int, _col: int, _prev: int, _prev_col: int) -> None:
        med_id = self._med_table.item(row, 0)
        if med_id is None:
            return
        self._selected_medicine_id = med_id.data(Qt.ItemDataRole.UserRole)
        med_name = med_id.text()
        self._batch_title.setText(f"Batches - {med_name}")
        self._refresh_batches()

    # ------------------------------------------------------------------
    # Medicine CRUD
    # ------------------------------------------------------------------

    def _on_add_medicine(self) -> None:
        dialog = MedicineDialog(self, title="Add Medicine")
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        data = dialog.get_data()
        if data is None:
            return
        try:
            InventoryService.create(**data)
            self.refresh_medicines()
        except DuplicateMedicineError as exc:
            QMessageBox.warning(self, "Duplicate", str(exc))
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to add medicine:\n{exc}")

    def _on_edit_medicine(self) -> None:
        rows = self._med_table.selectionModel().selectedRows()
        if not rows:
            return
        row = rows[0].row()
        item = self._med_table.item(row, 0)
        if item is None:
            return
        med_id = item.data(Qt.ItemDataRole.UserRole)
        if med_id is not None:
            self._on_edit_medicine_by_id(med_id)

    def _on_edit_medicine_by_id(self, med_id: int) -> None:
        session = None
        try:
            from app.database.engine import new_session
            from app.models.medicine import Medicine

            session = new_session()
            med = session.get(Medicine, med_id)
            if med is None:
                QMessageBox.warning(self, "Not Found", "Medicine not found.")
                return

            dialog = MedicineDialog(
                self,
                title="Edit Medicine",
                medicine_name=med.medicine_name,
                generic_name=med.generic_name or "",
                company=med.company or "",
                category=med.category or "",
                barcode=med.barcode or "",
                rack_location=med.rack_location or "",
                minimum_stock=med.minimum_stock,
                medicine_id=med_id,
            )
        finally:
            if session is not None:
                session.close()

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        data = dialog.get_data()
        if data is None:
            return
        try:
            InventoryService.update(med_id, **data)
            self.refresh_medicines()
            self._refresh_batches()
        except DuplicateMedicineError as exc:
            QMessageBox.warning(self, "Duplicate", str(exc))
        except MedicineNotFoundError as exc:
            QMessageBox.warning(self, "Not Found", str(exc))
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to update medicine:\n{exc}")

    def _on_delete_medicine(self) -> None:
        rows = self._med_table.selectionModel().selectedRows()
        if not rows:
            return
        row = rows[0].row()
        item = self._med_table.item(row, 0)
        if item is None:
            return
        med_id = item.data(Qt.ItemDataRole.UserRole)
        med_name = item.text()
        if med_id is not None:
            self._on_delete_medicine_by_id(med_id, med_name)

    def _on_delete_medicine_by_id(self, med_id: int, med_name: str) -> None:
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f'Delete "{med_name}"?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            InventoryService.delete(med_id)
            self._selected_medicine_id = None
            self._batch_title.setText("Batches")
            self._stock_label.setText("Total Stock: 0")
            self._batch_table.setRowCount(0)
            self._batch_table.setVisible(False)
            self._batch_empty.setVisible(True)
            self._batch_empty.setText("Select a medicine to view its batches.")
            self.refresh_medicines()
        except MedicineInUseError as exc:
            QMessageBox.warning(self, "Cannot Delete", str(exc))
        except MedicineNotFoundError as exc:
            QMessageBox.warning(self, "Not Found", str(exc))
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to delete medicine:\n{exc}")

    # ------------------------------------------------------------------
    # Batch CRUD
    # ------------------------------------------------------------------

    def _on_add_batch(self) -> None:
        if self._selected_medicine_id is None:
            QMessageBox.information(self, "No Selection", "Please select a medicine first.")
            return

        dialog = BatchDialog(self, title="Add Batch")
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        data = dialog.get_data()
        if data is None:
            return
        try:
            BatchService.create(medicine_id=self._selected_medicine_id, **data)
            self._refresh_batches()
            self.refresh_medicines()
        except DuplicateBatchError as exc:
            QMessageBox.warning(self, "Duplicate", str(exc))
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to add batch:\n{exc}")

    def _on_edit_batch(self) -> None:
        rows = self._batch_table.selectionModel().selectedRows()
        if not rows:
            return
        row = rows[0].row()
        item = self._batch_table.item(row, 0)
        if item is None:
            return
        batch_id = item.data(Qt.ItemDataRole.UserRole)
        if batch_id is not None:
            self._on_edit_batch_by_id(batch_id)

    def _on_edit_batch_by_id(self, batch_id: int) -> None:
        session = None
        try:
            from app.database.engine import new_session
            from app.models.batch import Batch

            session = new_session()
            batch = session.get(Batch, batch_id)
            if batch is None:
                QMessageBox.warning(self, "Not Found", "Batch not found.")
                return

            dialog = BatchDialog(
                self,
                title="Edit Batch",
                batch_number=batch.batch_number,
                expiry_date=batch.expiry_date,
                purchase_price=batch.purchase_price,
                selling_price=batch.selling_price,
                quantity=batch.quantity,
            )
        finally:
            if session is not None:
                session.close()

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        data = dialog.get_data()
        if data is None:
            return
        try:
            BatchService.update(batch_id, **data)
            self._refresh_batches()
            self.refresh_medicines()
        except DuplicateBatchError as exc:
            QMessageBox.warning(self, "Duplicate", str(exc))
        except BatchNotFoundError as exc:
            QMessageBox.warning(self, "Not Found", str(exc))
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to update batch:\n{exc}")

    def _on_delete_batch(self) -> None:
        rows = self._batch_table.selectionModel().selectedRows()
        if not rows:
            return
        row = rows[0].row()
        item = self._batch_table.item(row, 0)
        if item is None:
            return
        batch_id = item.data(Qt.ItemDataRole.UserRole)
        batch_name = item.text()
        if batch_id is not None:
            self._on_delete_batch_by_id(batch_id, batch_name)

    def _on_delete_batch_by_id(self, batch_id: int, batch_name: str) -> None:
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f'Delete batch "{batch_name}"?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            BatchService.delete(batch_id)
            self._refresh_batches()
            self.refresh_medicines()
        except BatchInUseError as exc:
            QMessageBox.warning(self, "Cannot Delete", str(exc))
        except BatchNotFoundError as exc:
            QMessageBox.warning(self, "Not Found", str(exc))
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to delete batch:\n{exc}")

    # ------------------------------------------------------------------
    # Barcode Actions
    # ------------------------------------------------------------------

    def _on_generate_barcode(self) -> None:
        med_id = self._selected_medicine_id
        if med_id is None:
            QMessageBox.information(self, "No Selection", "Please select a medicine.")
            return

        from app.services.settings_service import SettingsService
        from app.database.engine import new_session
        from app.models.medicine import Medicine

        session = None
        try:
            session = new_session()
            med = session.get(Medicine, med_id)
            if med is None:
                QMessageBox.warning(self, "Not Found", "Medicine not found.")
                return

            if med.barcode:
                reply = QMessageBox.question(
                    self, "Existing Barcode",
                    f"This medicine already has barcode: {med.barcode}\n"
                    "Generate a new one?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return

            settings = SettingsService.get()
            new_barcode = BarcodeService.generate_unique(prefix=settings.barcode_prefix)
            med.barcode = new_barcode
            session.commit()
            session.refresh(med)

            QMessageBox.information(
                self, "Barcode Generated",
                f"Barcode assigned:\n{new_barcode}",
            )
            self.refresh_medicines()
        except Exception as exc:
            if session:
                session.rollback()
            QMessageBox.critical(self, "Error", f"Failed to generate barcode:\n{exc}")
        finally:
            if session:
                session.close()

    def _on_print_label(self) -> None:
        med_id = self._selected_medicine_id
        if med_id is None:
            QMessageBox.information(self, "No Selection", "Please select a medicine.")
            return

        from app.ui.dialogs.barcode_label_dialog import BarcodeLabelDialog

        label_data = BarcodeService.get_label_data(med_id)
        if label_data is None:
            QMessageBox.warning(self, "Not Found", "Medicine not found.")
            return

        if not label_data.barcode:
            QMessageBox.information(
                self, "No Barcode",
                "This medicine does not have a barcode.\n"
                "Generate one first using the 'Generate Barcode' button.",
            )
            return

        dlg = BarcodeLabelDialog(label_data, parent=self)
        dlg.exec()
