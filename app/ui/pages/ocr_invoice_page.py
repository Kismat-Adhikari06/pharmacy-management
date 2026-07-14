from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from PySide6.QtCore import QMimeData, Qt, QThread, Signal
from PySide6.QtGui import QCursor, QDragEnterEvent, QDropEvent, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QPlainTextEdit,
    QTextEdit,
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

logger = logging.getLogger(__name__)

_TEXT = "#cdd6f4"
_SUBTEXT = "#a6adc8"
_BLUE = "#89b4fa"
_GREEN = "#a6e3a1"
_YELLOW = "#f9e2af"
_RED = "#f38ba8"
_BORDER = "#313244"
_CARD_BG = "#181825"


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


class OCRInvoicePage(QWidget):
    """AI Invoice Import page — upload, preview, and extract text from invoices."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ContentArea")
        self.setAcceptDrops(True)
        self._current_result: OCRResult | None = None
        self._worker: _OCRWorker | _ClipboardOCRWorker | None = None
        self._build_ui()

    # ── UI Construction ─────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        hdr = QHBoxLayout()
        hdr.setContentsMargins(20, 16, 20, 8)
        title = QLabel("\U0001f4e1 AI Invoice Import")
        title.setObjectName("PageTitle")
        hdr.addWidget(title)
        hdr.addStretch()

        self._engine_label = QLabel("")
        self._engine_label.setStyleSheet(f"color: {_SUBTEXT}; font-size: 9pt;")
        hdr.addWidget(self._engine_label)
        root.addLayout(hdr)

        # Subtitle
        sub = QHBoxLayout()
        sub.setContentsMargins(20, 0, 20, 8)
        sub_text = QLabel("Upload supplier invoices to extract text using offline OCR.")
        sub_text.setObjectName("PageDescription")
        sub.addWidget(sub_text)
        sub.addStretch()
        root.addLayout(sub)

        # Splitter: Left (upload + preview) | Right (extracted text)
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

        self._upload_img_btn = QPushButton("\U0001f5bc\ufe0f  Upload Image")
        self._upload_img_btn.setObjectName("ToolbarButton")
        self._upload_img_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._upload_img_btn.clicked.connect(self._on_upload_image)
        upload_row.addWidget(self._upload_img_btn)

        self._upload_pdf_btn = QPushButton("\U0001f4c4  Upload PDF")
        self._upload_pdf_btn.setObjectName("ToolbarButton")
        self._upload_pdf_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._upload_pdf_btn.clicked.connect(self._on_upload_pdf)
        upload_row.addWidget(self._upload_pdf_btn)

        self._paste_btn = QPushButton("\U0001f4cb  Paste Image")
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

        drop_icon = QLabel("\U0001f4c1")
        drop_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_icon.setStyleSheet("font-size: 28pt;")
        drop_layout.addWidget(drop_icon)

        drop_text = QLabel("Drag & drop invoice images or PDFs here")
        drop_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_text.setStyleSheet(f"color: {_SUBTEXT}; font-size: 10pt;")
        drop_layout.addWidget(drop_text)

        drop_formats = QLabel("Supports: JPG, JPEG, PNG, PDF")
        drop_formats.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_formats.setStyleSheet(f"color: #585b70; font-size: 8pt;")
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
        self._preview_label.setStyleSheet(f"color: #585b70; font-size: 10pt; padding: 20px;")
        self._preview_label.setMinimumHeight(200)
        self._preview_scroll.setWidget(self._preview_label)
        left_layout.addWidget(self._preview_scroll, 1)

        splitter.addWidget(left)

        # ── Right panel ─────────────────────────────────────
        right = QFrame()
        right.setObjectName("ContentArea")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(8, 12, 16, 12)
        right_layout.setSpacing(10)

        text_header = QHBoxLayout()
        text_title = QLabel("Extracted Text")
        text_title.setObjectName("SectionTitle")
        text_header.addWidget(text_title)
        text_header.addStretch()

        self._copy_btn = QPushButton("\U0001f4cb  Copy All")
        self._copy_btn.setObjectName("ToolbarButton")
        self._copy_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._copy_btn.clicked.connect(self._on_copy_text)
        self._copy_btn.setEnabled(False)
        text_header.addWidget(self._copy_btn)

        self._clear_btn = QPushButton("\U0001f5d1\ufe0f  Clear")
        self._clear_btn.setObjectName("ToolbarButton")
        self._clear_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._clear_btn.clicked.connect(self._on_clear)
        text_header.addWidget(self._clear_btn)

        right_layout.addLayout(text_header)

        # Stats row
        self._stats_frame = QFrame()
        self._stats_frame.setObjectName("OCRStats")
        stats_layout = QGridLayout(self._stats_frame)
        stats_layout.setContentsMargins(12, 8, 12, 8)
        stats_layout.setSpacing(16)

        self._stat_engine = self._make_stat(stats_layout, "Engine", 0)
        self._stat_pages = self._make_stat(stats_layout, "Pages", 1)
        self._stat_time = self._make_stat(stats_layout, "Time", 2)
        self._stat_words = self._make_stat(stats_layout, "Words", 3)
        self._stat_conf = self._make_stat(stats_layout, "Confidence", 0, row=1)
        self._stat_lines = self._make_stat(stats_layout, "Lines", 1, row=1)
        self._stat_chars = self._make_stat(stats_layout, "Characters", 2, row=1)

        self._stats_frame.setVisible(False)
        right_layout.addWidget(self._stats_frame)

        # Extracted text display
        self._text_display = QPlainTextEdit()
        self._text_display.setObjectName("OCRTextDisplay")
        self._text_display.setReadOnly(True)
        self._text_display.setPlaceholderText(
            "Extracted text will appear here after processing…"
        )
        self._text_display.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        right_layout.addWidget(self._text_display, 1)

        # Process button (shown when a file is loaded but not yet processed)
        self._process_btn = QPushButton("\u25b6  Process Document")
        self._process_btn.setObjectName("PrimaryButton")
        self._process_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._process_btn.clicked.connect(self._on_process)
        self._process_btn.setVisible(False)
        right_layout.addWidget(self._process_btn)

        # Status
        self._status_label = QLabel("")
        self._status_label.setStyleSheet(f"color: {_SUBTEXT}; font-size: 9pt;")
        right_layout.addWidget(self._status_label)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)

        root.addWidget(splitter, 1)

        # Initialize engine label
        engine = OCRService.get_active_engine()
        if engine != "None":
            self._engine_label.setText(f"Engine: {engine}")
        else:
            self._engine_label.setText("Engine: Not available — install PaddleOCR or EasyOCR")
            self._engine_label.setStyleSheet(f"color: {_RED}; font-size: 9pt;")
            self._upload_img_btn.setEnabled(False)
            self._upload_pdf_btn.setEnabled(False)
            self._paste_btn.setEnabled(False)

    def _make_stat(
        self, layout: QGridLayout, label: str, col: int, row: int = 0,
    ) -> QLabel:
        """Create a stat label in the grid. Returns the value QLabel."""
        lbl = QLabel(label)
        lbl.setStyleSheet(f"color: {_SUBTEXT}; font-size: 8pt;")
        layout.addWidget(lbl, row * 2, col)
        val = QLabel("—")
        val.setStyleSheet(f"color: {_TEXT}; font-size: 11pt; font-weight: bold;")
        layout.addWidget(val, row * 2 + 1, col)
        return val

    # ── Upload handlers ─────────────────────────────────────────

    def _on_upload_image(self) -> None:
        exts = " ".join(f"*{e}" for e in sorted(
            e for e in OCRService.get_supported_extensions() if e != ".pdf"
        ))
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Invoice Image", "",
            f"Images ({exts});;All Files (*)",
        )
        if path:
            self._load_file(path)

    def _on_upload_pdf(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Invoice PDF", "",
            "PDF Files (*.pdf);;All Files (*)",
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
                self, "No Image",
                "No image found in clipboard.\n"
                "Copy an image first, then paste here.",
            )
            return

        image = clipboard.image()
        if image.isNull():
            QMessageBox.warning(self, "Error", "Could not read image from clipboard.")
            return

        # Save to temp file
        tmp = Path(tempfile.gettempdir()) / "ocr_clipboard_paste.png"
        image.save(str(tmp), "PNG")

        self._load_file(str(tmp), display_name="Clipboard Image")

    def _load_file(self, path: str, display_name: str | None = None) -> None:
        """Load a file and show preview, then enable process button."""
        p = Path(path)
        if not OCRService.is_supported(p):
            QMessageBox.warning(
                self, "Unsupported File",
                f"File type not supported: {p.suffix}\n"
                f"Supported: {', '.join(sorted(OCRService.get_supported_extensions()))}",
            )
            return

        self._current_file = path
        self._current_display_name = display_name or p.name

        # Show preview
        ext = p.suffix.lower()
        if ext == ".pdf":
            self._show_pdf_preview(p)
        else:
            self._show_image_preview(p)

        # Show process button
        self._process_btn.setVisible(True)
        self._status_label.setText(f"Loaded: {self._current_display_name}")
        self._status_label.setStyleSheet(f"color: {_BLUE}; font-size: 9pt;")

        # Reset text
        self._text_display.clear()
        self._stats_frame.setVisible(False)
        self._copy_btn.setEnabled(False)

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
        """Render first page of PDF as preview."""
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
                            "#OCDDropZone { border: 2px dashed #89b4fa; "
                            "border-radius: 8px; background-color: #1e1e2e; }"
                        )
                        return
        # Also accept image drops from clipboard
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

    # ── OCR Processing ──────────────────────────────────────────

    def _on_process(self) -> None:
        if not hasattr(self, "_current_file") or not self._current_file:
            QMessageBox.information(self, "No File", "Please upload a file first.")
            return

        self._set_processing(True)
        self._status_label.setText("Processing document… please wait.")
        self._status_label.setStyleSheet(f"color: {_YELLOW}; font-size: 9pt;")

        self._worker = _OCRWorker(self._current_file, parent=self)
        self._worker.finished.connect(self._on_ocr_finished)
        self._worker.error.connect(self._on_ocr_error)
        self._worker.start()

    def _on_ocr_finished(self, result: OCRResult) -> None:
        self._current_result = result
        self._set_processing(False)

        # Display text
        self._text_display.setPlainText(result.extracted_text)
        self._copy_btn.setEnabled(bool(result.extracted_text.strip()))

        # Update stats
        self._stat_engine.setText(result.engine_used)
        self._stat_pages.setText(f"{result.pages_processed}/{result.total_pages}")
        self._stat_time.setText(f"{result.processing_time_seconds:.1f}s")
        self._stat_words.setText(str(result.word_count))
        self._stat_conf.setText(f"{result.average_confidence:.0%}")
        self._stat_lines.setText(str(result.line_count))
        self._stat_chars.setText(str(len(result.extracted_text)))
        self._stats_frame.setVisible(True)

        self._status_label.setText(
            f"Extraction complete — {result.word_count} words, "
            f"{result.processing_time_seconds:.1f}s"
        )
        self._status_label.setStyleSheet(f"color: {_GREEN}; font-size: 9pt;")

    def _on_ocr_error(self, error_msg: str) -> None:
        self._set_processing(False)

        # Friendly error messages
        if "Unsupported file type" in error_msg:
            QMessageBox.warning(self, "Unsupported File", error_msg)
        elif "No OCR engine" in error_msg or "No OCR engine available" in error_msg:
            QMessageBox.critical(
                self, "OCR Engine Not Available",
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

        self._status_label.setText("Extraction failed.")
        self._status_label.setStyleSheet(f"color: {_RED}; font-size: 9pt;")
        logger.error("OCR error: %s", error_msg)

    def _set_processing(self, processing: bool) -> None:
        """Toggle UI state during processing."""
        self._upload_img_btn.setEnabled(not processing)
        self._upload_pdf_btn.setEnabled(not processing)
        self._paste_btn.setEnabled(not processing)
        self._process_btn.setVisible(not processing and hasattr(self, "_current_file"))
        if processing:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        else:
            QApplication.restoreOverrideCursor()

    # ── Actions ─────────────────────────────────────────────────

    def _on_copy_text(self) -> None:
        text = self._text_display.toPlainText()
        if text:
            clipboard = QApplication.clipboard()
            if clipboard:
                clipboard.setText(text)
            self._status_label.setText("Text copied to clipboard.")
            self._status_label.setStyleSheet(f"color: {_GREEN}; font-size: 9pt;")

    def _on_clear(self) -> None:
        self._text_display.clear()
        self._preview_label.clear()
        self._preview_label.setText("No document loaded")
        self._preview_label.setStyleSheet(
            f"color: #585b70; font-size: 10pt; padding: 20px;"
        )
        self._stats_frame.setVisible(False)
        self._copy_btn.setEnabled(False)
        self._process_btn.setVisible(False)
        self._current_result = None
        self._current_file = None
        self._status_label.setText("")
        if hasattr(self, "_drop_zone"):
            self._drop_zone.setStyleSheet("")
