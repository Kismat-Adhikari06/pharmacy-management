from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from config import config


class WelcomePage(QWidget):
    """Landing page shown when the application starts."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ContentArea")
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(16)

        layout.addStretch()

        emoji = QLabel("\U0001f3e5")
        emoji.setAlignment(Qt.AlignmentFlag.AlignCenter)
        emoji.setStyleSheet("font-size: 64pt;")
        layout.addWidget(emoji)

        title = QLabel(config.APP_NAME)
        title.setObjectName("WelcomeTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel(f"Built for Nepal \U0001f1f3\U0001f1f5")
        subtitle.setObjectName("WelcomeSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        version = QLabel(f"Version {config.APP_VERSION}")
        version.setObjectName("WelcomeBody")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version)

        layout.addSpacing(12)

        body = QLabel(
            "A complete offline-first pharmacy management system\n"
            "designed for retail pharmacies across Nepal.\n\n"
            "Start by navigating through the sidebar."
        )
        body.setObjectName("WelcomeBody")
        body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(body)

        layout.addStretch()
