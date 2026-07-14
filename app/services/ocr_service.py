from __future__ import annotations

import io
import logging
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

logger = logging.getLogger(__name__)

SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"}
SUPPORTED_PDF_EXTENSIONS = {".pdf"}
SUPPORTED_EXTENSIONS = SUPPORTED_IMAGE_EXTENSIONS | SUPPORTED_PDF_EXTENSIONS


class OCREngine:
    """Enum-like for available OCR engines."""

    PADDLE = "PaddleOCR"
    EASYOCR = "EasyOCR"
    NONE = "None"


class OCRError(Exception):
    """Base OCR error."""


class UnsupportedFileError(OCRError):
    """Raised for unsupported file types."""


class UnreadableFileError(OCRError):
    """Raised when the file cannot be read or decoded."""


class OCREngineError(OCRError):
    """Raised when the OCR engine fails."""


class EmptyDocumentError(OCRError):
    """Raised when OCR produces no text."""


@dataclass
class PageResult:
    """OCR result for a single page/image."""

    page_number: int
    text: str
    confidence: float = 0.0


@dataclass
class OCRResult:
    """Complete OCR result for a document."""

    file_path: str
    file_name: str
    engine_used: str
    pages_processed: int
    total_pages: int
    extracted_text: str
    average_confidence: float
    processing_time_seconds: float
    page_results: list[PageResult] = field(default_factory=list)

    @property
    def word_count(self) -> int:
        return len(self.extracted_text.split())

    @property
    def line_count(self) -> int:
        return len([l for l in self.extracted_text.splitlines() if l.strip()])


class OCRService:
    """Offline OCR service with PaddleOCR/EasyOCR fallback."""

    _paddle_instance = None
    _easy_instance = None
    _active_engine: str = OCREngine.NONE

    # ── Engine initialization ───────────────────────────────────

    @classmethod
    def _get_paddle(cls):
        """Lazy-initialize PaddleOCR. Returns instance or None."""
        if cls._paddle_instance is not None:
            return cls._paddle_instance
        try:
            from paddleocr import PaddleOCR
            cls._paddle_instance = PaddleOCR(
                use_angle_cls=True,
                lang="en",
                show_log=False,
                use_gpu=False,
            )
            cls._active_engine = OCREngine.PADDLE
            logger.info("PaddleOCR engine initialized.")
            return cls._paddle_instance
        except ImportError:
            logger.debug("PaddleOCR not installed.")
            return None
        except Exception as exc:
            logger.warning("PaddleOCR init failed: %s", exc)
            return None

    @classmethod
    def _get_easy(cls):
        """Lazy-initialize EasyOCR. Returns instance or None."""
        if cls._easy_instance is not None:
            return cls._easy_instance
        try:
            import easyocr
            cls._easy_instance = easyocr.Reader(
                ["en"],
                gpu=False,
                verbose=False,
            )
            cls._active_engine = OCREngine.EASYOCR
            logger.info("EasyOCR engine initialized.")
            return cls._easy_instance
        except ImportError:
            logger.debug("EasyOCR not installed.")
            return None
        except Exception as exc:
            logger.warning("EasyOCR init failed: %s", exc)
            return None

    @classmethod
    def get_active_engine(cls) -> str:
        """Return the name of the currently active OCR engine."""
        if cls._active_engine != OCREngine.NONE:
            return cls._active_engine
        # Try to initialize
        if cls._get_paddle() is not None:
            return OCREngine.PADDLE
        if cls._get_easy() is not None:
            return OCREngine.EASYOCR
        return OCREngine.NONE

    @classmethod
    def is_available(cls) -> bool:
        """Check if any OCR engine is available."""
        return cls.get_active_engine() != OCREngine.NONE

    # ── Public API ──────────────────────────────────────────────

    @classmethod
    def extract_text(cls, file_path: str | Path) -> OCRResult:
        """Extract text from an image or PDF file.

        Args:
            file_path: Path to image (JPG/PNG/BMP/TIFF) or PDF.

        Returns:
            OCRResult with extracted text and metadata.

        Raises:
            UnsupportedFileError: File type not supported.
            UnreadableFileError: File cannot be opened.
            OCREngineError: OCR engine failed.
            EmptyDocumentError: No text found.
        """
        path = Path(file_path)
        if not path.exists():
            raise UnreadableFileError(f"File not found: {path}")

        ext = path.suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            raise UnsupportedFileError(
                f"Unsupported file type: {ext}\n"
                f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
            )

        start_time = time.time()

        if ext in SUPPORTED_PDF_EXTENSIONS:
            result = cls._process_pdf(path)
        else:
            result = cls._process_image(path)

        result.processing_time_seconds = round(time.time() - start_time, 2)

        if not result.extracted_text.strip():
            raise EmptyDocumentError(
                "No readable text found in the document.\n"
                "The image may be too low quality or contain only graphics."
            )

        return result

    @classmethod
    def extract_text_from_images(
        cls, images: list[Path | bytes], file_name: str = "clipboard",
    ) -> OCRResult:
        """Extract text from a list of images (bytes or paths)."""
        start_time = time.time()
        page_results: list[PageResult] = []
        all_text_parts: list[str] = []
        all_confidences: list[float] = []

        for idx, img in enumerate(images, 1):
            if isinstance(img, bytes):
                tmp = Path(tempfile.gettempdir()) / f"ocr_clipboard_{idx}.png"
                tmp.write_bytes(img)
                img_path = tmp
            else:
                img_path = Path(img)

            pr = cls._ocr_single_image(img_path, idx)
            page_results.append(pr)
            all_text_parts.append(pr.text)
            all_confidences.append(pr.confidence)

        merged_text = "\n\n".join(all_text_parts)
        avg_conf = sum(all_confidences) / len(all_confidences) if all_confidences else 0.0

        return OCRResult(
            file_path="",
            file_name=file_name,
            engine_used=cls.get_active_engine(),
            pages_processed=len(images),
            total_pages=len(images),
            extracted_text=merged_text,
            average_confidence=round(avg_conf, 2),
            processing_time_seconds=round(time.time() - start_time, 2),
            page_results=page_results,
        )

    # ── PDF processing ──────────────────────────────────────────

    @classmethod
    def _process_pdf(cls, path: Path) -> OCRResult:
        """Convert PDF pages to images and OCR each."""
        try:
            import fitz  # PyMuPDF
        except ImportError:
            raise OCREngineError(
                "PyMuPDF is required for PDF processing.\n"
                "Install with: pip install PyMuPDF"
            )

        try:
            doc = fitz.open(str(path))
        except Exception as exc:
            raise UnreadableFileError(f"Cannot open PDF: {exc}")

        total_pages = len(doc)
        if total_pages == 0:
            doc.close()
            raise EmptyDocumentError("PDF has no pages.")

        page_results: list[PageResult] = []
        all_text: list[str] = []
        all_conf: list[float] = []

        for page_num in range(total_pages):
            page = doc.load_page(page_num)
            # Render page to image at 2x resolution for better OCR
            mat = fitz.Matrix(2.0, 2.0)
            pix = page.get_pixmap(matrix=mat)
            img_bytes = pix.tobytes("png")

            # Save to temp file for OCR
            tmp = Path(tempfile.gettempdir()) / f"ocr_pdf_page_{page_num + 1}.png"
            tmp.write_bytes(img_bytes)

            try:
                pr = cls._ocr_single_image(tmp, page_num + 1)
                page_results.append(pr)
                all_text.append(pr.text)
                all_conf.append(pr.confidence)
            except Exception as exc:
                logger.warning("OCR failed on page %d: %s", page_num + 1, exc)
                page_results.append(PageResult(
                    page_number=page_num + 1,
                    text=f"[OCR failed on this page: {exc}]",
                    confidence=0.0,
                ))

            # Clean up temp
            try:
                tmp.unlink()
            except OSError:
                pass

        doc.close()

        merged = "\n\n".join(all_text)
        avg_conf = sum(all_conf) / len(all_conf) if all_conf else 0.0

        return OCRResult(
            file_path=str(path),
            file_name=path.name,
            engine_used=cls.get_active_engine(),
            pages_processed=len([p for p in page_results if p.confidence > 0]),
            total_pages=total_pages,
            extracted_text=merged,
            average_confidence=round(avg_conf, 2),
            processing_time_seconds=0.0,  # filled by caller
            page_results=page_results,
        )

    # ── Image processing ────────────────────────────────────────

    @classmethod
    def _process_image(cls, path: Path) -> OCRResult:
        """OCR a single image file."""
        pr = cls._ocr_single_image(path, 1)
        return OCRResult(
            file_path=str(path),
            file_name=path.name,
            engine_used=cls.get_active_engine(),
            pages_processed=1,
            total_pages=1,
            extracted_text=pr.text,
            average_confidence=pr.confidence,
            processing_time_seconds=0.0,
            page_results=[pr],
        )

    @classmethod
    def _ocr_single_image(cls, img_path: Path, page_num: int) -> PageResult:
        """Run OCR on a single image file. Tries PaddleOCR then EasyOCR."""
        # Try PaddleOCR
        paddle = cls._get_paddle()
        if paddle is not None:
            try:
                return cls._run_paddle(paddle, img_path, page_num)
            except Exception as exc:
                logger.warning("PaddleOCR failed on page %d: %s", page_num, exc)

        # Fallback to EasyOCR
        easy = cls._get_easy()
        if easy is not None:
            try:
                return cls._run_easy(easy, img_path, page_num)
            except Exception as exc:
                logger.warning("EasyOCR failed on page %d: %s", page_num, exc)

        raise OCREngineError(
            "No OCR engine available.\n"
            "Install PaddleOCR: pip install paddleocr paddlepaddle\n"
            "Or EasyOCR: pip install easyocr"
        )

    @classmethod
    def _run_paddle(cls, engine, img_path: Path, page_num: int) -> PageResult:
        """Run PaddleOCR on an image."""
        result = engine.ocr(str(img_path), cls=True)
        if result is None or len(result) == 0 or result[0] is None:
            return PageResult(page_number=page_num, text="", confidence=0.0)

        lines: list[str] = []
        confidences: list[float] = []

        for line in result[0]:
            if line and len(line) >= 2:
                text = line[1][0] if isinstance(line[1], (list, tuple)) else str(line[1])
                conf = line[1][1] if isinstance(line[1], (list, tuple)) and len(line[1]) > 1 else 0.0
                lines.append(text)
                confidences.append(conf)

        merged = "\n".join(lines)
        avg = sum(confidences) / len(confidences) if confidences else 0.0

        return PageResult(
            page_number=page_num,
            text=merged,
            confidence=round(avg, 2),
        )

    @classmethod
    def _run_easy(cls, engine, img_path: Path, page_num: int) -> PageResult:
        """Run EasyOCR on an image."""
        results = engine.readtext(str(img_path))
        lines: list[str] = []
        confidences: list[float] = []

        for bbox, text, conf in results:
            lines.append(text)
            confidences.append(conf)

        merged = "\n".join(lines)
        avg = sum(confidences) / len(confidences) if confidences else 0.0

        return PageResult(
            page_number=page_num,
            text=merged,
            confidence=round(avg, 2),
        )

    # ── Utilities ───────────────────────────────────────────────

    @staticmethod
    def get_supported_extensions() -> set[str]:
        return SUPPORTED_EXTENSIONS.copy()

    @staticmethod
    def is_supported(file_path: str | Path) -> bool:
        return Path(file_path).suffix.lower() in SUPPORTED_EXTENSIONS
