from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QWidget,
)

from config import config


class Header(QFrame):
    """Top header bar showing app name, current page, date/time, and logged-in user."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Header")
        self.setFixedHeight(56)
        self._build_ui()
        self._start_clock()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 0, 20, 0)

        self._page_title = QLabel(config.APP_NAME)
        self._page_title.setObjectName("HeaderTitle")
        layout.addWidget(self._page_title)

        layout.addStretch()

        self._date_label = QLabel()
        self._date_label.setObjectName("HeaderText")
        self._date_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self._date_label)

        separator = QLabel("  |  ")
        separator.setObjectName("HeaderText")
        layout.addWidget(separator)

        self._time_label = QLabel()
        self._time_label.setObjectName("HeaderText")
        self._time_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self._time_label)

        separator2 = QLabel("  |  ")
        separator2.setObjectName("HeaderText")
        layout.addWidget(separator2)

        user_label = QLabel(f"\U0001f464  {config.CURRENT_USER}")
        user_label.setObjectName("HeaderText")
        layout.addWidget(user_label)

    def set_page_title(self, title: str) -> None:
        """Update the displayed page title."""
        self._page_title.setText(title)

    def _start_clock(self) -> None:
        self._update_clock()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_clock)
        self._timer.start(1000)

    def _update_clock(self) -> None:
        now = datetime.now()
        self._date_label.setText(now.strftime("%A, %B %d, %Y"))
        self._time_label.setText(now.strftime("%I:%M:%S %p"))
