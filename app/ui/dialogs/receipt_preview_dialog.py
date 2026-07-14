from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.services.receipt_service import ReceiptData, ReceiptService

logger = logging.getLogger(__name__)


class ReceiptPreviewDialog(QDialog):
    """Dialog that shows a receipt preview and offers print/save options."""

    def __init__(
        self,
        data: ReceiptData,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Receipt Preview")
        self.setMinimumSize(620, 700)
        self.setModal(True)
        self._data = data
        self._pdf_path: Path | None = None
        self._build_ui()
        self._generate_preview("80mm")

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        self._paper_combo = QComboBox()
        self._paper_combo.addItems(["58mm", "80mm", "A4"])
        self._paper_combo.setCurrentText("80mm")
        self._paper_combo.currentTextChanged.connect(self._on_paper_changed)
        top_row.addWidget(QLabel("Paper Size:"))
        top_row.addWidget(self._paper_combo)
        top_row.addStretch()

        close_btn = QPushButton("Close")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.accept)
        top_row.addWidget(close_btn)

        layout.addLayout(top_row)

        self._preview_label = QLabel("Generating preview…")
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setMinimumHeight(400)
        self._preview_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._preview_label.setStyleSheet(
            "background-color: #181825; border: 1px solid #313244; border-radius: 6px;"
        )
        layout.addWidget(self._preview_label, stretch=1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        save_btn = QPushButton("Save PDF")
        save_btn.setObjectName("ToolbarButton")
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.clicked.connect(self._save_pdf)
        btn_row.addWidget(save_btn)

        btn_row.addStretch()

        print_btn = QPushButton("Print Receipt")
        print_btn.setObjectName("PrimaryButton")
        print_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        print_btn.clicked.connect(self._print)
        btn_row.addWidget(print_btn)

        layout.addLayout(btn_row)

    def _on_paper_changed(self, paper: str) -> None:
        self._generate_preview(paper)

    def _generate_preview(self, paper: str) -> None:
        if self._pdf_path is None:
            temp_dir = ReceiptService.get_temp_dir()
            self._pdf_path = temp_dir / f"preview_{self._data.bill_number}.pdf"

        try:
            ReceiptService.generate_pdf(
                self._data, self._pdf_path, paper=paper
            )
            self._preview_label.setText(
                f"Receipt generated:\n{self._pdf_path}\n\n"
                "Open the PDF to view the full receipt."
            )
        except Exception as exc:
            logger.exception("Receipt generation failed")
            self._preview_label.setText(f"Failed to generate receipt:\n{exc}")

    def _save_pdf(self) -> None:
        if self._pdf_path is None or not self._pdf_path.exists():
            QMessageBox.warning(self, "Error", "No receipt to save.")
            return

        default_name = f"{self._data.bill_number}.pdf"
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Receipt PDF", default_name, "PDF Files (*.pdf)"
        )
        if not path:
            return

        try:
            import shutil
            shutil.copy2(self._pdf_path, path)
            QMessageBox.information(
                self, "Saved", f"Receipt saved to:\n{path}"
            )
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to save:\n{exc}")

    def _print(self) -> None:
        if self._pdf_path is None or not self._pdf_path.exists():
            QMessageBox.warning(self, "Error", "No receipt to print.")
            return

        try:
            if sys.platform == "win32":
                os_path = str(self._pdf_path.resolve())
                import os
                os.startfile(os_path, "print")
                QMessageBox.information(
                    self, "Print", "Print job sent to default printer."
                )
            else:
                subprocess.run(
                    ["lpr", str(self._pdf_path)],
                    check=True,
                    timeout=30,
                )
                QMessageBox.information(
                    self, "Print", "Print job sent to default printer."
                )
        except Exception as exc:
            logger.exception("Print failed")
            QMessageBox.critical(self, "Print Error", f"Failed to print:\n{exc}")

    def get_pdf_path(self) -> Path | None:
        return self._pdf_path
