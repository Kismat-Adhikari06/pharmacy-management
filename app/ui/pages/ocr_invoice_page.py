from __future__ import annotations

import base64
import difflib
import logging
import tempfile
from pathlib import Path

from PySide6.QtCore import QMimeData, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QCursor, QDragEnterEvent, QDropEvent, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.services.ocr_service import (
    EmptyDocumentError,
    OCRResult,
    OCRService,
    OCREngineError,
    UnreadableFileError,
    UnsupportedFileError,
)
from app.services.groq_service import (
    GroqConfigError,
    GroqAPIError,
    GroqParseError,
    GroqService,
    InvoiceData,
)

from app.ui.theme import Theme

logger = logging.getLogger(__name__)


# ── Background workers ──────────────────────────────────────────


class _OCRWorker(QThread):
    """Background thread for OCR processing."""

    finished = Signal(object)  # OCRResult
    error = Signal(str)

    def __init__(self, file_path: str, parent=None) -> None:
        super().__init__(parent)
        self._file_path = file_path

    def run(self) -> None:
        try:
            result = OCRService.extract_text(self._file_path)
            self.finished.emit(result)
        except Exception as exc:
            self.error.emit(str(exc))


class _ClipboardOCRWorker(QThread):
    """Background thread for OCR on clipboard image bytes."""

    finished = Signal(object)
    error = Signal(str)

    def __init__(self, image_bytes: bytes, parent=None) -> None:
        super().__init__(parent)
        self._image_bytes = image_bytes

    def run(self) -> None:
        try:
            result = OCRService.extract_text_from_images(
                [self._image_bytes], file_name="Clipboard Image",
            )
            self.finished.emit(result)
        except Exception as exc:
            self.error.emit(str(exc))


class _AIWorker(QThread):
    """Background thread for Groq AI invoice parsing from OCR text."""

    finished = Signal(object)  # InvoiceData
    error = Signal(str)

    def __init__(self, ocr_text: str, parent=None) -> None:
        super().__init__(parent)
        self._ocr_text = ocr_text

    def run(self) -> None:
        try:
            result = GroqService.parse_invoice(self._ocr_text)
            self.finished.emit(result)
        except Exception as exc:
            self.error.emit(str(exc))


class _VisionWorker(QThread):
    """Background thread for Groq vision-based invoice extraction."""

    finished = Signal(object)  # InvoiceData
    error = Signal(str)

    def __init__(self, image_path: str, parent=None) -> None:
        super().__init__(parent)
        self._image_path = image_path

    def run(self) -> None:
        try:
            result = GroqService.parse_invoice_from_image(self._image_path)
            self.finished.emit(result)
        except Exception as exc:
            self.error.emit(str(exc))


class _EngineDetector(QThread):
    """Background thread for OCR engine detection."""

    finished = Signal(str)

    def run(self) -> None:
        try:
            engine = OCRService.get_active_engine()
            self.finished.emit(engine)
        except Exception:
            self.finished.emit("None")


class _FuzzyMatcher(QThread):
    """Background thread for fuzzy-matching extracted medicines against DB."""

    finished = Signal(object)  # list[InvoiceItem]
    error = Signal(str)

    def run(self) -> None:
        try:
            from app.services.inventory_service import InventoryService

            all_meds = InventoryService.get_all()
            med_names = [(m.id, m.medicine_name) for m in all_meds]
            self.finished.emit(med_names)
        except Exception as exc:
            self.error.emit(str(exc))


class _SaveWorker(QThread):
    """Background thread for saving imported invoice items to inventory."""

    finished = Signal(str)
    error = Signal(str)

    def __init__(
        self,
        items: list[dict],
        supplier_name: str = "",
        invoice_number: str = "",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._items = items
        self._supplier_name = supplier_name
        self._invoice_number = invoice_number

    def run(self) -> None:
        try:
            from app.services.purchase_service import PurchaseService

            result = PurchaseService.create_from_invoice(
                items=self._items,
                supplier_name=self._supplier_name,
                invoice_number=self._invoice_number,
            )
            self.finished.emit(result)
        except Exception as exc:
            self.error.emit(str(exc))


# ── Main page ───────────────────────────────────────────────────


class OCRInvoicePage(QWidget):
    """AI Invoice Import page — upload, preview, OCR/vision, and AI parsing."""

    _TABLE_HEADERS = [
        "Medicine",
        "Generic",
        "Company",
        "Batch",
        "Expiry",
        "Qty",
        "Purchase Price",
        "Selling Price",
        "Status",
    ]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ContentArea")
        self.setAcceptDrops(True)
        self._current_result: OCRResult | None = None
        self._current_invoice: InvoiceData | None = None
        self._worker = None
        self._db_meds: list[tuple[int, str]] = []
        self._extracted_text = ""
        self._build_ui()

    # ── UI Construction ─────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        hdr = QHBoxLayout()
        hdr.setContentsMargins(20, 16, 20, 8)
        title = QLabel("AI Invoice Import")
        title.setObjectName("PageTitle")
        hdr.addWidget(title)
        hdr.addStretch()

        self._engine_label = QLabel("")
        self._engine_label.setStyleSheet(
            f"color: {Theme.text2()}; font-size: 9pt; background: transparent;"
        )
        hdr.addWidget(self._engine_label)
        root.addLayout(hdr)

        # Subtitle
        sub = QHBoxLayout()
        sub.setContentsMargins(20, 0, 20, 8)
        sub_text = QLabel(
            "Upload supplier invoices — AI reads the image directly for "
            "accurate extraction, or use OCR as a fallback."
        )
        sub_text.setObjectName("PageDescription")
        sub.addWidget(sub_text)
        sub.addStretch()
        root.addLayout(sub)

        # Main splitter: Left (upload + preview) | Right (text + AI)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        # ── Left panel ──────────────────────────────────────
        left = QFrame()
        left.setObjectName("ContentArea")
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(16, 12, 8, 12)
        left_layout.setSpacing(10)

        # Upload buttons row
        upload_row = QHBoxLayout()
        upload_row.setSpacing(8)

        self._upload_img_btn = QPushButton("Upload Image")
        self._upload_img_btn.setObjectName("ToolbarButton")
        self._upload_img_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._upload_img_btn.clicked.connect(self._on_upload_image)
        upload_row.addWidget(self._upload_img_btn)

        self._upload_pdf_btn = QPushButton("Upload PDF")
        self._upload_pdf_btn.setObjectName("ToolbarButton")
        self._upload_pdf_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._upload_pdf_btn.clicked.connect(self._on_upload_pdf)
        upload_row.addWidget(self._upload_pdf_btn)

        self._paste_btn = QPushButton("Paste Image")
        self._paste_btn.setObjectName("ToolbarButton")
        self._paste_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._paste_btn.clicked.connect(self._on_paste_clipboard)
        upload_row.addWidget(self._paste_btn)

        upload_row.addStretch()
        left_layout.addLayout(upload_row)

        # Drag & drop zone
        self._drop_zone = QFrame()
        self._drop_zone.setObjectName("OCDDropZone")
        self._drop_zone.setMinimumHeight(120)
        self._drop_zone.setAcceptDrops(True)
        drop_layout = QVBoxLayout(self._drop_zone)
        drop_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        drop_icon = QLabel("+")
        drop_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_icon.setStyleSheet("font-size: 28pt; background: transparent;")
        drop_layout.addWidget(drop_icon)

        drop_text = QLabel("Drag & drop invoice images or PDFs here")
        drop_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_text.setStyleSheet(
            f"color: {Theme.text2()}; font-size: 10pt; background: transparent;"
        )
        drop_layout.addWidget(drop_text)

        drop_formats = QLabel("Supports: JPG, JPEG, PNG, PDF")
        drop_formats.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_formats.setStyleSheet(
            f"color: {Theme.text3()}; font-size: 8pt; background: transparent;"
        )
        drop_layout.addWidget(drop_formats)

        left_layout.addWidget(self._drop_zone)

        # Preview area
        preview_label = QLabel("Original Document")
        preview_label.setObjectName("SectionTitle")
        left_layout.addWidget(preview_label)

        self._preview_scroll = QScrollArea()
        self._preview_scroll.setWidgetResizable(True)
        self._preview_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._preview_scroll.setMinimumHeight(200)

        self._preview_label = QLabel("No document loaded")
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setStyleSheet(
            f"color: {Theme.text3()}; font-size: 10pt; padding: 20px; background: transparent;"
        )
        self._preview_label.setMinimumHeight(200)
        self._preview_scroll.setWidget(self._preview_label)
        left_layout.addWidget(self._preview_scroll, 1)

        splitter.addWidget(left)

        # ── Right panel: fixed top (buttons) + scrollable bottom (results) ──
        right_panel = QWidget()
        right_panel.setObjectName("ContentArea")
        right_vbox = QVBoxLayout(right_panel)
        right_vbox.setContentsMargins(8, 12, 16, 0)
        right_vbox.setSpacing(8)

        # ── Action buttons row (FIXED — never scrolls) ──────
        action_row = QHBoxLayout()
        action_row.setSpacing(8)

        self._ai_btn = QPushButton("Analyze with AI")
        self._ai_btn.setObjectName("AIAnalyzeButton")
        self._ai_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._ai_btn.clicked.connect(self._on_analyze_ai)
        self._ai_btn.setEnabled(False)
        self._ai_btn.setVisible(False)
        action_row.addWidget(self._ai_btn)

        self._process_btn = QPushButton("OCR Fallback")
        self._process_btn.setObjectName("ToolbarButton")
        self._process_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._process_btn.clicked.connect(self._on_process)
        self._process_btn.setVisible(False)
        action_row.addWidget(self._process_btn)

        action_row.addStretch()
        right_vbox.addLayout(action_row)

        # Status
        self._status_label = QLabel("")
        self._status_label.setStyleSheet(
            f"color: {Theme.text2()}; font-size: 9pt; background: transparent;"
        )
        right_vbox.addWidget(self._status_label)

        # ── Scrollable area below buttons for AI results ─────
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QFrame.Shape.NoFrame)
        right_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        right_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

        right_content = QWidget()
        right_content_layout = QVBoxLayout(right_content)
        right_content_layout.setContentsMargins(0, 0, 0, 0)
        right_content_layout.setSpacing(0)

        # ── AI Results section ──────────────────────────────
        self._ai_frame = QFrame()
        self._ai_frame.setObjectName("AIResultsFrame")
        ai_layout = QVBoxLayout(self._ai_frame)
        ai_layout.setContentsMargins(12, 10, 12, 10)
        ai_layout.setSpacing(10)

        # Header row
        ai_header = QHBoxLayout()
        ai_title = QLabel("Parsed Invoice Data")
        ai_title.setObjectName("SectionTitle")
        ai_header.addWidget(ai_title)
        ai_header.addStretch()

        self._ai_model_label = QLabel("")
        self._ai_model_label.setStyleSheet(
            f"color: {Theme.text2()}; font-size: 8pt; background: transparent;"
        )
        ai_header.addWidget(self._ai_model_label)
        ai_layout.addLayout(ai_header)

        # Invoice metadata — form-style 2-column grid (label | value)
        meta_grid = QGridLayout()
        meta_grid.setContentsMargins(0, 0, 0, 0)
        meta_grid.setSpacing(6)
        meta_grid.setColumnStretch(0, 0)
        meta_grid.setColumnStretch(1, 1)

        self._meta_supplier = self._make_meta(meta_grid, "Supplier", 0)
        self._meta_inv_no = self._make_meta(meta_grid, "Invoice #", 1)
        self._meta_date = self._make_meta(meta_grid, "Invoice Date", 2)
        self._meta_total = self._make_meta(meta_grid, "Grand Total", 3)
        self._meta_items = self._make_meta(meta_grid, "Items Found", 4)
        self._meta_qty = self._make_meta(meta_grid, "Total Quantity", 5)
        self._meta_computed = self._make_meta(meta_grid, "Computed Total", 6)

        ai_layout.addLayout(meta_grid)

        # Match summary
        self._match_summary = QLabel("")
        self._match_summary.setStyleSheet(
            f"color: {Theme.text2()}; font-size: 9pt; background: transparent;"
        )
        self._match_summary.setWordWrap(True)
        ai_layout.addWidget(self._match_summary)

        # Items table
        self._items_table = QTableWidget()
        self._items_table.setObjectName("AIItemsTable")
        self._items_table.setColumnCount(len(self._TABLE_HEADERS))
        self._items_table.setHorizontalHeaderLabels(self._TABLE_HEADERS)
        self._items_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self._items_table.setEditTriggers(
            QTableWidget.EditTrigger.DoubleClicked
            | QTableWidget.EditTrigger.SelectedClicked
        )
        self._items_table.setAlternatingRowColors(True)
        self._items_table.verticalHeader().setVisible(False)
        self._items_table.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self._items_table.horizontalHeader().setStretchLastSection(False)
        self._items_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self._items_table.setMinimumHeight(150)

        ai_layout.addWidget(self._items_table, 1)

        # Save to Inventory button
        save_row = QHBoxLayout()
        save_row.addStretch()
        self._save_btn = QPushButton("Send to Inventory")
        self._save_btn.setObjectName("PrimaryButton")
        self._save_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._save_btn.clicked.connect(self._on_save_to_inventory)
        self._save_btn.setVisible(False)
        save_row.addWidget(self._save_btn)
        ai_layout.addLayout(save_row)

        self._ai_frame.setVisible(False)
        right_content_layout.addWidget(self._ai_frame)

        right_scroll.setWidget(right_content)
        right_vbox.addWidget(right_scroll, 1)

        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)

        root.addWidget(splitter, 1)

        # Defer engine + DB detection to avoid blocking UI
        self._engine_label.setText("OCR Engine: Detecting...")
        self._engine_detector = _EngineDetector(parent=self)
        self._engine_detector.finished.connect(self._on_engine_detected)
        QTimer.singleShot(100, self._engine_detector.start)

        # Load medicine DB for fuzzy matching in background
        self._fuzzy_loader = _FuzzyMatcher(parent=self)
        self._fuzzy_loader.finished.connect(self._on_db_loaded)
        self._fuzzy_loader.error.connect(self._on_db_load_error)
        QTimer.singleShot(200, self._fuzzy_loader.start)

    def _make_meta(
        self, layout: QGridLayout, label: str, row: int,
    ) -> QLabel:
        lbl = QLabel(label)
        lbl.setStyleSheet(
            f"color: {Theme.text2()}; font-size: 8pt; background: transparent;"
        )
        layout.addWidget(lbl, row, 0)
        val = QLabel("—")
        val.setStyleSheet(
            f"color: {Theme.text()}; font-size: 10pt; font-weight: bold; background: transparent;"
        )
        val.setWordWrap(True)
        layout.addWidget(val, row, 1)
        return val

    def _on_engine_detected(self, engine: str) -> None:
        if engine != "None":
            self._engine_label.setText(f"OCR Engine: {engine}")
        else:
            self._engine_label.setText(
                "OCR Engine: Not available — install PaddleOCR or EasyOCR"
            )
            self._engine_label.setStyleSheet(
                f"color: {Theme.danger()}; font-size: 9pt; background: transparent;"
            )
            self._upload_img_btn.setEnabled(False)
            self._upload_pdf_btn.setEnabled(False)
            self._paste_btn.setEnabled(False)

    def _on_db_loaded(self, meds: list) -> None:
        self._db_meds = meds
        logger.info("Loaded %d medicines for fuzzy matching", len(meds))

    def _on_db_load_error(self, error_msg: str) -> None:
        logger.warning("Failed to load medicine DB: %s", error_msg)

    # ── Upload handlers ─────────────────────────────────────────

    def _on_upload_image(self) -> None:
        exts = " ".join(
            f"*{e}"
            for e in sorted(
                e for e in OCRService.get_supported_extensions() if e != ".pdf"
            )
        )
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Invoice Image", "", f"Images ({exts});;All Files (*)",
        )
        if path:
            self._load_file(path)

    def _on_upload_pdf(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Invoice PDF", "", "PDF Files (*.pdf);;All Files (*)",
        )
        if path:
            self._load_file(path)

    def _on_paste_clipboard(self) -> None:
        clipboard = QApplication.clipboard()
        if clipboard is None:
            QMessageBox.information(self, "No Clipboard", "Clipboard is empty.")
            return

        mime = clipboard.mimeData()
        if mime is None or not mime.hasImage():
            QMessageBox.information(
                self,
                "No Image",
                "No image found in clipboard.\n"
                "Copy an image first, then paste here.",
            )
            return

        image = clipboard.image()
        if image.isNull():
            QMessageBox.warning(
                self, "Error", "Could not read image from clipboard."
            )
            return

        tmp = Path(tempfile.gettempdir()) / "ocr_clipboard_paste.png"
        image.save(str(tmp), "PNG")
        self._load_file(str(tmp), display_name="Clipboard Image")

    def _load_file(self, path: str, display_name: str | None = None) -> None:
        p = Path(path)
        if not OCRService.is_supported(p):
            QMessageBox.warning(
                self,
                "Unsupported File",
                f"File type not supported: {p.suffix}\n"
                f"Supported: {', '.join(sorted(OCRService.get_supported_extensions()))}",
            )
            return

        self._current_file = path
        self._current_display_name = display_name or p.name

        ext = p.suffix.lower()
        if ext == ".pdf":
            self._show_pdf_preview(p)
        else:
            self._show_image_preview(p)

        self._ai_btn.setVisible(True)
        self._ai_btn.setEnabled(GroqService.is_configured())
        self._process_btn.setVisible(True)
        self._status_label.setText(f"Loaded: {self._current_display_name}")
        self._status_label.setStyleSheet(
            f"color: {Theme.accent()}; font-size: 9pt; background: transparent;"
        )

        if GroqService.is_configured():
            self._ai_btn.setToolTip("Extract directly from image using AI vision")
        else:
            self._ai_btn.setToolTip(
                "Groq API key not configured.\nCreate a .env file with GROQ_API_KEY."
            )

        self._extracted_text = ""
        self._ai_frame.setVisible(False)
        self._save_btn.setVisible(False)
        self._current_invoice = None

    def _show_image_preview(self, path: Path) -> None:
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            self._preview_label.setText("Could not load image preview.")
            return
        scaled = pixmap.scaled(
            self._preview_scroll.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._preview_label.setPixmap(scaled)
        self._preview_label.setStyleSheet("")

    def _show_pdf_preview(self, path: Path) -> None:
        try:
            import fitz

            doc = fitz.open(str(path))
            if len(doc) == 0:
                self._preview_label.setText("PDF has no pages.")
                return
            page = doc.load_page(0)
            mat = fitz.Matrix(1.5, 1.5)
            pix = page.get_pixmap(matrix=mat)
            img_data = pix.tobytes("png")
            doc.close()

            pixmap = QPixmap()
            pixmap.loadFromData(img_data)
            if pixmap.isNull():
                self._preview_label.setText("Could not render PDF preview.")
                return
            scaled = pixmap.scaled(
                self._preview_scroll.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._preview_label.setPixmap(scaled)
            self._preview_label.setStyleSheet("")
        except ImportError:
            self._preview_label.setText(
                "PDF preview requires PyMuPDF.\nInstall with: pip install PyMuPDF"
            )
        except Exception as exc:
            self._preview_label.setText(f"PDF preview failed:\n{exc}")

    # ── Drag & Drop ─────────────────────────────────────────────

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        mime = event.mimeData()
        if mime is None:
            return
        if mime.hasUrls():
            for url in mime.urls():
                if url.isLocalFile():
                    ext = Path(url.toLocalFile()).suffix.lower()
                    if ext in OCRService.get_supported_extensions():
                        event.acceptProposedAction()
                        self._drop_zone.setStyleSheet(
                            f"#OCDDropZone {{ border: 2px dashed {Theme.accent()}; "
                            f"border-radius: 8px; background-color: {Theme.bg()}; }}"
                        )
                        return
        if mime.hasImage():
            event.acceptProposedAction()

    def dragLeaveEvent(self, event) -> None:  # noqa: N802
        self._drop_zone.setStyleSheet("")

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        self._drop_zone.setStyleSheet("")
        mime = event.mimeData()
        if mime is None:
            return

        if mime.hasImage():
            image = mime.imageData()
            if image is not None and not image.isNull():
                tmp = Path(tempfile.gettempdir()) / "ocr_drop_image.png"
                image.save(str(tmp), "PNG")
                self._load_file(str(tmp), display_name="Dropped Image")
                return

        if mime.hasUrls():
            for url in mime.urls():
                if url.isLocalFile():
                    path = url.toLocalFile()
                    if OCRService.is_supported(path):
                        self._load_file(path)
                        return

    # ── AI Analysis (primary: vision, fallback: text) ───────────

    def _on_analyze_ai(self) -> None:
        if not hasattr(self, "_current_file") or not self._current_file:
            QMessageBox.information(
                self, "No File", "Please upload a file first."
            )
            return

        if not GroqService.is_configured():
            QMessageBox.critical(
                self,
                "API Key Not Configured",
                "Groq API key is not set.\n\n"
                "Create a .env file in the project root:\n\n"
                "GROQ_API_KEY=your_api_key_here\n\n"
                "Get your key at: https://console.groq.com",
            )
            return

        p = Path(self._current_file)
        is_image = p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".bmp"}

        self._set_processing(True, ai=True)
        self._ai_btn.setEnabled(False)

        if is_image:
            # Vision: send image directly to vision model
            self._status_label.setText(
                f"Reading invoice with AI vision ({GroqService.get_vision_model()})…"
            )
            self._status_label.setStyleSheet(
                f"color: {Theme.warning()}; font-size: 9pt; background: transparent;"
            )
            self._worker = _VisionWorker(self._current_file, parent=self)
            self._worker.finished.connect(self._on_ai_finished)
            self._worker.error.connect(self._on_vision_error)
            self._worker.start()
        else:
            # PDF: try OCR first, then text-based AI
            text = self._extracted_text.strip()
            if not text:
                self._status_label.setText(
                    "Running OCR first (PDF cannot use vision)…"
                )
                self._status_label.setStyleSheet(
                    f"color: {Theme.warning()}; font-size: 9pt; background: transparent;"
                )
                self._worker = _OCRWorker(self._current_file, parent=self)
                self._worker.finished.connect(self._on_ocr_for_ai_finished)
                self._worker.error.connect(self._on_ocr_for_ai_error)
                self._worker.start()
            else:
                self._run_text_ai(text)

    def _on_ocr_for_ai_finished(self, result: OCRResult) -> None:
        self._current_result = result
        self._extracted_text = result.extracted_text
        self._run_text_ai(result.extracted_text)

    def _on_ocr_for_ai_error(self, error_msg: str) -> None:
        self._set_processing(False)
        self._ai_btn.setEnabled(True)
        QMessageBox.warning(
            self,
            "OCR Failed",
            f"Could not extract text from PDF:\n{error_msg}\n\n"
            "The AI analysis requires OCR text for PDFs.",
        )
        self._status_label.setText("OCR failed.")
        self._status_label.setStyleSheet(
            f"color: {Theme.danger()}; font-size: 9pt; background: transparent;"
        )

    def _run_text_ai(self, text: str) -> None:
        self._status_label.setText(
            f"Analyzing with {GroqService.get_model()}…"
        )
        self._status_label.setStyleSheet(
            f"color: {Theme.warning()}; font-size: 9pt; background: transparent;"
        )
        self._worker = _AIWorker(text, parent=self)
        self._worker.finished.connect(self._on_ai_finished)
        self._worker.error.connect(self._on_ai_error)
        self._worker.start()

    def _on_ai_finished(self, data: InvoiceData) -> None:
        self._current_invoice = data
        self._set_processing(False)

        self._meta_supplier.setText(data.supplier_name or "—")
        self._meta_inv_no.setText(data.invoice_number or "—")
        self._meta_date.setText(data.invoice_date or "—")
        self._meta_total.setText(
            f"Rs. {data.grand_total:,.2f}" if data.grand_total else "—"
        )
        self._meta_items.setText(str(data.item_count))
        self._meta_qty.setText(str(data.total_quantity))
        self._meta_computed.setText(
            f"Rs. {data.computed_total:,.2f}" if data.computed_total else "—"
        )

        method = data.extraction_method or GroqService.get_model()
        self._ai_model_label.setText(f"Method: {method}")

        self._run_fuzzy_match(data)
        self._ai_frame.setVisible(True)
        self._ai_btn.setEnabled(True)
        self._ai_btn.setVisible(True)
        self._save_btn.setVisible(True)

        self._status_label.setText(
            f"AI extraction complete — {data.item_count} items found"
        )
        self._status_label.setStyleSheet(
            f"color: {Theme.success()}; font-size: 9pt; background: transparent;"
        )

    def _on_vision_error(self, error_msg: str) -> None:
        self._set_processing(False)
        self._ai_btn.setEnabled(True)

        if "model" in error_msg.lower() and (
            "not found" in error_msg.lower() or "does not support" in error_msg.lower()
        ):
            # Vision model not available, fall back to OCR + text
            self._status_label.setText(
                "Vision not available, falling back to OCR…"
            )
            self._status_label.setStyleSheet(
                f"color: {Theme.warning()}; font-size: 9pt; background: transparent;"
            )
            if hasattr(self, "_current_file") and self._current_file:
                self._worker = _OCRWorker(self._current_file, parent=self)
                self._worker.finished.connect(self._on_ocr_for_ai_finished)
                self._worker.error.connect(self._on_ocr_for_ai_error)
                self._worker.start()
            return

        self._on_ai_error(error_msg)

    def _on_ai_error(self, error_msg: str) -> None:
        self._set_processing(False)
        self._ai_btn.setEnabled(True)

        if "API key" in error_msg or "not configured" in error_msg.lower():
            QMessageBox.critical(self, "Configuration Error", error_msg)
        elif "rate" in error_msg.lower() or "limit" in error_msg.lower():
            QMessageBox.warning(self, "Rate Limited", error_msg)
        elif "network" in error_msg.lower() or "connection" in error_msg.lower():
            QMessageBox.warning(self, "Network Error", error_msg)
        elif "invalid JSON" in error_msg or "parse" in error_msg.lower():
            QMessageBox.warning(
                self,
                "Parse Error",
                "The AI returned data that could not be parsed.\n\n"
                "Try again or use OCR fallback.",
            )
            logger.warning("AI parse error: %s", error_msg)
        elif "unavailable" in error_msg.lower():
            QMessageBox.warning(self, "Service Unavailable", error_msg)
        else:
            QMessageBox.critical(self, "AI Error", f"Analysis failed:\n{error_msg}")

        self._status_label.setText("AI analysis failed.")
        self._status_label.setStyleSheet(
            f"color: {Theme.danger()}; font-size: 9pt; background: transparent;"
        )
        logger.error("AI error: %s", error_msg)

    # ── Fuzzy matching ──────────────────────────────────────────

    def _run_fuzzy_match(self, data: InvoiceData) -> None:
        if not self._db_meds:
            try:
                from app.services.inventory_service import InventoryService
                all_meds = InventoryService.get_all()
                self._db_meds = [(m.id, m.medicine_name) for m in all_meds]
                logger.info(
                    "Loaded %d medicines for fuzzy matching (fallback sync load)",
                    len(self._db_meds),
                )
            except Exception as exc:
                logger.warning("Failed to load medicine DB: %s", exc)

        if not self._db_meds:
            self._populate_items_table(data.items)
            self._match_summary.setText(
                "No medicines in inventory yet — items extracted but not matched. "
                "Add medicines to inventory first, then re-run AI analysis."
            )
            return

        db_names = [name for _, name in self._db_meds]
        matched = 0
        fuzzy = 0
        unmatched = 0

        for item in data.items:
            name = item.medicine_name.strip()
            if not name:
                item.match_status = "no_name"
                unmatched += 1
                continue

            # Exact match (case-insensitive)
            exact = [
                (mid, mn) for mid, mn in self._db_meds
                if mn.lower() == name.lower()
            ]
            if exact:
                item.match_status = "exact"
                item.matched_medicine_id = exact[0][0]
                item.matched_medicine_name = exact[0][1]
                item.name_confidence = 1.0
                matched += 1
                continue

            # Fuzzy match
            matches = difflib.get_close_matches(
                name, db_names, n=1, cutoff=0.5
            )
            if matches:
                score = difflib.SequenceMatcher(
                    None, name.lower(), matches[0].lower()
                ).ratio()
                item.name_confidence = round(score, 2)
                if score >= 0.7:
                    item.match_status = "fuzzy"
                    item.matched_medicine_name = matches[0]
                    match_id = [
                        mid for mid, mn in self._db_meds if mn == matches[0]
                    ]
                    item.matched_medicine_id = match_id[0] if match_id else None
                    fuzzy += 1
                else:
                    item.match_status = "low_confidence"
                    item.matched_medicine_name = matches[0]
                    unmatched += 1
            else:
                item.match_status = "unmatched"
                item.name_confidence = 0.0
                unmatched += 1

        total = len(data.items)
        parts = []
        if matched:
            parts.append(f"{matched} matched")
        if fuzzy:
            parts.append(f"{fuzzy} fuzzy match")
        if unmatched:
            parts.append(f"{unmatched} needs review")
        summary = f"Matching: {', '.join(parts)} out of {total} items"
        self._match_summary.setText(summary)

        if unmatched > 0:
            self._match_summary.setStyleSheet(
                f"color: {Theme.warning()}; font-size: 9pt; font-weight: bold; background: transparent;"
            )
        else:
            self._match_summary.setStyleSheet(
                f"color: {Theme.success()}; font-size: 9pt; font-weight: bold; background: transparent;"
            )

        self._populate_items_table(data.items)

    # ── OCR Processing (fallback) ───────────────────────────────

    def _on_process(self) -> None:
        if not hasattr(self, "_current_file") or not self._current_file:
            QMessageBox.information(self, "No File", "Please upload a file first.")
            return

        self._set_processing(True, ocr=True)
        self._status_label.setText("Running OCR… please wait.")
        self._status_label.setStyleSheet(
            f"color: {Theme.warning()}; font-size: 9pt; background: transparent;"
        )

        self._worker = _OCRWorker(self._current_file, parent=self)
        self._worker.finished.connect(self._on_ocr_finished)
        self._worker.error.connect(self._on_ocr_error)
        self._worker.start()

    def _on_ocr_finished(self, result: OCRResult) -> None:
        self._current_result = result
        self._set_processing(False)

        self._extracted_text = result.extracted_text

        has_text = bool(result.extracted_text.strip())
        groq_ok = GroqService.is_configured()
        self._ai_btn.setVisible(has_text)
        self._ai_btn.setEnabled(has_text and groq_ok)
        if has_text and not groq_ok:
            self._ai_btn.setToolTip(
                "Groq API key not configured.\n"
                "Create a .env file with GROQ_API_KEY=your_key"
            )

        self._status_label.setText(
            f"OCR complete — {result.word_count} words, "
            f"{result.processing_time_seconds:.1f}s"
        )
        self._status_label.setStyleSheet(
            f"color: {Theme.success()}; font-size: 9pt; background: transparent;"
        )

    def _on_ocr_error(self, error_msg: str) -> None:
        self._set_processing(False)

        if "Unsupported file type" in error_msg:
            QMessageBox.warning(self, "Unsupported File", error_msg)
        elif "No OCR engine" in error_msg or "No OCR engine available" in error_msg:
            QMessageBox.critical(
                self,
                "OCR Engine Not Available",
                "No OCR engine is installed.\n\n"
                "Please install one of the following:\n"
                "  pip install paddleocr paddlepaddle\n"
                "  pip install easyocr",
            )
        elif "No readable text" in error_msg or "empty" in error_msg.lower():
            QMessageBox.information(self, "No Text Found", error_msg)
        elif "cannot open" in error_msg.lower() or "not found" in error_msg.lower():
            QMessageBox.warning(self, "File Error", error_msg)
        else:
            QMessageBox.critical(self, "OCR Error", f"Extraction failed:\n{error_msg}")

        self._status_label.setText("OCR failed.")
        self._status_label.setStyleSheet(
            f"color: {Theme.danger()}; font-size: 9pt; background: transparent;"
        )
        logger.error("OCR error: %s", error_msg)

    # ── Table population with match status ──────────────────────

    def _populate_items_table(self, items: list) -> None:
        self._items_table.setSortingEnabled(False)
        self._items_table.setRowCount(len(items))

        for i, item in enumerate(items):
            values = [
                item.medicine_name,
                item.generic_name,
                item.company,
                item.batch_number,
                item.expiry_date,
                str(item.quantity),
                f"{item.purchase_price:.2f}" if item.purchase_price else "",
                f"{item.selling_price:.2f}" if item.selling_price else "",
            ]

            # Status text and color
            status = getattr(item, "match_status", "")
            status_text, status_color = self._status_display(item)

            for j, val in enumerate(values):
                cell = QTableWidgetItem(val)
                cell.setTextAlignment(Qt.AlignmentFlag.AlignVCenter)
                if j in (5, 6, 7):
                    cell.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                self._items_table.setItem(i, j, cell)

            # Status column
            status_cell = QTableWidgetItem(status_text)
            status_cell.setTextAlignment(
                Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
            )
            status_cell.setForeground(
                __import__("PySide6.QtGui", fromlist=["QColor"]).QColor(status_color)
            )
            status_cell.setFlags(
                status_cell.flags() & ~Qt.ItemFlag.ItemIsEditable
            )
            self._items_table.setItem(i, len(self._TABLE_HEADERS) - 1, status_cell)

            # Color-code the medicine name cell
            name_cell = self._items_table.item(i, 0)
            if name_cell:
                if status in ("unmatched", "low_confidence", "no_name"):
                    name_cell.setForeground(
                        __import__("PySide6.QtGui", fromlist=["QColor"]).QColor(Theme.danger())
                    )
                elif status == "fuzzy":
                    name_cell.setForeground(
                        __import__("PySide6.QtGui", fromlist=["QColor"]).QColor(Theme.warning())
                    )
                else:
                    name_cell.setForeground(
                        __import__("PySide6.QtGui", fromlist=["QColor"]).QColor(Theme.success())
                    )

        self._items_table.setSortingEnabled(True)

    @staticmethod
    def _status_display(item) -> tuple[str, str]:
        """Return (status_text, color) for an invoice item."""
        status = getattr(item, "match_status", "")
        conf = getattr(item, "name_confidence", 0.0)
        matched_name = getattr(item, "matched_medicine_name", "")

        if status == "exact":
            return "Matched", Theme.success()
        elif status == "fuzzy":
            return f"~{conf:.0%} → {matched_name}", Theme.warning()
        elif status == "low_confidence":
            return f"~{conf:.0%} Review", Theme.warning()
        elif status == "unmatched":
            return "Not in DB", Theme.danger()
        elif status == "no_name":
            return "No name", Theme.danger()
        else:
            return "—", Theme.text2()

    # ── Utilities ───────────────────────────────────────────────

    def _set_processing(
        self, processing: bool, ocr: bool = False, ai: bool = False
    ) -> None:
        self._upload_img_btn.setEnabled(not processing)
        self._upload_pdf_btn.setEnabled(not processing)
        self._paste_btn.setEnabled(not processing)

        if ocr:
            self._process_btn.setVisible(
                not processing and hasattr(self, "_current_file")
            )
        if ai:
            self._ai_btn.setEnabled(not processing and GroqService.is_configured())

        if processing:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        else:
            QApplication.restoreOverrideCursor()

    def _on_clear(self) -> None:
        self._extracted_text = ""
        self._preview_label.clear()
        self._preview_label.setText("No document loaded")
        self._preview_label.setStyleSheet(
            f"color: {Theme.text3()}; font-size: 10pt; padding: 20px; background: transparent;"
        )
        self._process_btn.setVisible(False)
        self._ai_btn.setVisible(False)
        self._ai_btn.setEnabled(False)
        self._ai_frame.setVisible(False)
        self._save_btn.setVisible(False)
        self._match_summary.setText("")
        self._current_result = None
        self._current_invoice = None
        self._current_file = None
        self._status_label.setText("")
        self._items_table.setRowCount(0)
        if hasattr(self, "_drop_zone"):
            self._drop_zone.setStyleSheet("")

    # ── Save to Inventory ─────────────────────────────────────

    def _on_save_to_inventory(self) -> None:
        """Show confirmation dialog, then save all extracted items to inventory."""
        if not self._current_invoice or not self._current_invoice.items:
            QMessageBox.information(
                self, "No Data", "No invoice data to save."
            )
            return

        # Build confirmation dialog
        dlg = QDialog(self)
        dlg.setWindowTitle("Confirm Import to Inventory")
        dlg.setMinimumSize(700, 500)
        dlg.setModal(True)

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        info = QLabel(
            f"Review {len(self._current_invoice.items)} items below before importing.\n"
            "You can edit cells directly in the table. "
            "Medicines not in the database will be created automatically."
        )
        info.setWordWrap(True)
        info.setStyleSheet(
            f"color: {Theme.text()}; font-size: 10pt; background: transparent; padding: 4px;"
        )
        layout.addWidget(info)

        # Editable table
        items = self._current_invoice.items
        headers = [
            "Medicine Name", "Generic", "Company", "Batch",
            "Expiry", "Qty", "Purchase Price", "Selling Price",
        ]
        table = QTableWidget()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setRowCount(len(items))
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(False)
        table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        table.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

        for i, item in enumerate(items):
            vals = [
                item.medicine_name,
                item.generic_name,
                item.company,
                item.batch_number,
                item.expiry_date,
                str(item.quantity),
                f"{item.purchase_price:.2f}",
                f"{item.selling_price:.2f}",
            ]
            for j, val in enumerate(vals):
                cell = QTableWidgetItem(val)
                cell.setTextAlignment(
                    Qt.AlignmentFlag.AlignVCenter
                    | (
                        Qt.AlignmentFlag.AlignRight
                        if j in (5, 6, 7)
                        else Qt.AlignmentFlag.AlignLeft
                    )
                )
                table.setItem(i, j, cell)

        layout.addWidget(table, 1)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Import to Inventory")
        buttons.button(QDialogButtonBox.StandardButton.Ok).setObjectName(
            "PrimaryButton"
        )
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        layout.addWidget(buttons)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        # Read edited values from the table
        edited_items = []
        for i in range(table.rowCount()):
            qty_text = table.item(i, 5).text().strip() if table.item(i, 5) else "0"
            pp_text = table.item(i, 6).text().strip() if table.item(i, 6) else "0"
            sp_text = table.item(i, 7).text().strip() if table.item(i, 7) else "0"
            edited_items.append({
                "medicine_name": table.item(i, 0).text().strip() if table.item(i, 0) else "",
                "generic_name": table.item(i, 1).text().strip() if table.item(i, 1) else "",
                "company": table.item(i, 2).text().strip() if table.item(i, 2) else "",
                "batch_number": table.item(i, 3).text().strip() if table.item(i, 3) else "",
                "expiry_date": table.item(i, 4).text().strip() if table.item(i, 4) else "",
                "quantity": int(qty_text) if qty_text.isdigit() else 0,
                "purchase_price": float(pp_text) if pp_text else 0.0,
                "selling_price": float(sp_text) if sp_text else 0.0,
            })

        # Filter out empty rows
        edited_items = [item for item in edited_items if item["medicine_name"]]

        if not edited_items:
            QMessageBox.information(
                self, "No Items", "No valid items to import."
            )
            return

        # Do the save in a background thread
        self._set_processing(True)
        self._status_label.setText(
            f"Importing {len(edited_items)} items to inventory…"
        )
        self._status_label.setStyleSheet(
            f"color: {Theme.warning()}; font-size: 9pt; background: transparent;"
        )

        self._worker = _SaveWorker(
            edited_items,
            supplier_name=self._current_invoice.supplier_name or "",
            invoice_number=self._current_invoice.invoice_number or "",
            parent=self,
        )
        self._worker.finished.connect(self._on_save_finished)
        self._worker.error.connect(self._on_save_error)
        self._worker.start()

    def _on_save_finished(self, result: str) -> None:
        self._set_processing(False)
        self._save_btn.setVisible(False)
        self._status_label.setText(result)
        self._status_label.setStyleSheet(
            f"color: {Theme.success()}; font-size: 9pt; background: transparent;"
        )
        QMessageBox.information(self, "Import Complete", result)
        self._on_clear()

    def _on_save_error(self, error_msg: str) -> None:
        self._set_processing(False)
        self._status_label.setText("Import failed.")
        self._status_label.setStyleSheet(
            f"color: {Theme.danger()}; font-size: 9pt; background: transparent;"
        )
        QMessageBox.critical(self, "Import Error", error_msg)
