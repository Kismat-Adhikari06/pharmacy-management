from __future__ import annotations

from PySide6.QtWidgets import QWidget

from app.ui.pages.base_page import BasePage


class AnalyticsPage(BasePage):
    """Analytics and charts page."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            title="Analytics",
            description=(
                "Visual analytics with sales trends,\n"
                "top medicines, and category breakdowns."
            ),
            icon="\U0001f4c8",
            parent=parent,
        )
