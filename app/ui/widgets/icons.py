from __future__ import annotations

from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtCore import Qt


def _svg_icon(svg: str, size: int = 20) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.end()
    from PySide6.QtSvg import QSvgRenderer
    from PySide6.QtCore import QByteArray
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    renderer.render(painter := QPainter(pixmap))
    painter.end()
    return QIcon(pixmap)


def make_icon(color: str = "#8b9cc0", size: int = 20) -> callable:
    """Factory that returns a function creating a colored SVG icon from a path."""
    def _builder(path_d: str) -> QIcon:
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
            f'width="{size}" height="{size}">'
            f'<path d="{path_d}" fill="none" stroke="{color}" '
            f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
            f'</svg>'
        )
        return _svg_icon(svg, size)
    return _builder


_normal = make_icon("#8b9cc0")
_active = make_icon("#ffffff")


class NavIcons:
    DASHBOARD = (
        "M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z"
    )
    INVENTORY = (
        "M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z"
        "M3.27 6.96L12 12.01l8.73-5.05M12 22.08V12"
    )
    BILLING = (
        "M1 4h22v16H1zM1 10h22"
    )
    SALES_HISTORY = (
        "M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"
        "M14 2v6h6M16 13H8M16 17H8M10 9H8"
    )
    PURCHASES = (
        "M1 1h4l2.68 13.39a1 1 0 001 .81h9.72a1 1 0 001-.76L23 6H6"
        "M9 22a1 1 0 100-2 1 1 0 000 2zM20 22a1 1 0 100-2 1 1 0 000 2z"
    )
    SUPPLIERS = (
        "M1 3h15v13H1zM16 8h4l3 4v4h-7V8z"
        "M5 21a1 1 0 100-2 1 1 0 000 2zM19 21a1 1 0 100-2 1 1 0 000 2z"
    )
    EXPIRY = (
        "M12 22a10 10 0 100-20 10 10 0 000 20z"
        "M12 6v6l4 2"
    )
    LOW_STOCK = (
        "M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"
        "M12 9v4M12 17h.01"
    )
    OCR = (
        "M23 19a2 2 0 01-2 2H3a2 2 0 01-2-2V8a2 2 0 012-2h4l2-3h6l2 3h4a2 2 0 012 2z"
        "M12 17a5 5 0 100-10 5 5 0 000 10z"
    )
    BACKUP = (
        "M19 21H5a2 2 0 01-2-2V5a2 2 0 012-2h11l5 5v11a2 2 0 01-2 2z"
        "M17 21v-8H7v8M7 3v5h8"
    )
    SETTINGS = (
        "M12 15a3 3 0 100-6 3 3 0 000 6z"
        "M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 01-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"
    )

    _MAP: dict[str, str] = {
        "Dashboard": DASHBOARD,
        "Inventory": INVENTORY,
        "Billing (POS)": BILLING,
        "Sales History": SALES_HISTORY,
        "Purchases": PURCHASES,
        "Suppliers": SUPPLIERS,
        "Expiry": EXPIRY,
        "Low Stock": LOW_STOCK,
        "AI Invoice Import": OCR,
        "Backup": BACKUP,
        "Settings": SETTINGS,
    }

    @classmethod
    def get(cls, label: str) -> tuple[QIcon, QIcon]:
        path = cls._MAP.get(label)
        if path is None:
            return (QIcon(), QIcon())
        return (_normal(path), _active(path))

    # Single-color icons for buttons / misc
    @staticmethod
    def user(color: str = "#8b9cc0") -> QIcon:
        path = (
            "M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"
            "M12 11a4 4 0 100-8 4 4 0 000 8z"
        )
        return make_icon(color)(path)

    @staticmethod
    def refresh(color: str = "#8b9cc0") -> QIcon:
        path = (
            "M23 4v6h-6M1 20v-6h6"
            "M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15"
        )
        return make_icon(color)(path)

    @staticmethod
    def delete(color: str = "#8b9cc0") -> QIcon:
        path = (
            "M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6"
            "M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2"
            "M10 11v6M14 11v6"
        )
        return make_icon(color)(path)

    @staticmethod
    def search(color: str = "#8b9cc0") -> QIcon:
        path = (
            "M11 19a8 8 0 100-16 8 8 0 000 16z"
            "M21 21l-4.35-4.35"
        )
        return make_icon(color)(path)

    @staticmethod
    def export(color: str = "#8b9cc0") -> QIcon:
        path = (
            "M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"
            "M7 10l5 5 5-5M12 15V3"
        )
        return make_icon(color)(path)

    @staticmethod
    def barcode(color: str = "#8b9cc0") -> QIcon:
        path = (
            "M2 4h2v16H2zM6 4v16M10 4h2v16h-2zM14 4v16"
            "M18 4h2v16h-2zM22 4v16"
        )
        return make_icon(color)(path)

    @staticmethod
    def printer(color: str = "#8b9cc0") -> QIcon:
        path = (
            "M6 9V2h12v7M6 18H4a2 2 0 01-2-2v-5a2 2 0 012-2h16a2 2 0 012 2v5a2 2 0 01-2 2h-2"
            "M6 14h12v8H6z"
        )
        return make_icon(color)(path)

    @staticmethod
    def folder(color: str = "#8b9cc0") -> QIcon:
        path = (
            "M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z"
        )
        return make_icon(color)(path)

    @staticmethod
    def paste(color: str = "#8b9cc0") -> QIcon:
        path = (
            "M16 4h2a2 2 0 012 2v14a2 2 0 01-2 2H6a2 2 0 01-2-2V6a2 2 0 012-2h2"
            "M15 2H9a1 1 0 00-1 1v2a1 1 0 001 1h6a1 1 0 001-1V3a1 1 0 00-1-1z"
            "M12 11h4M12 16h4M8 11h.01M8 16h.01"
        )
        return make_icon(color)(path)

    @staticmethod
    def upload(color: str = "#8b9cc0") -> QIcon:
        path = (
            "M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"
            "M17 8l-5-5-5 5M12 3v12"
        )
        return make_icon(color)(path)

    @staticmethod
    def copy(color: str = "#8b9cc0") -> QIcon:
        path = (
            "M20 9h-7a2 2 0 00-2 2v7a2 2 0 002 2h7a2 2 0 002-2v-7a2 2 0 00-2-2z"
            "M3 15V4a2 2 0 012-2h9"
        )
        return make_icon(color)(path)

    @staticmethod
    def clear(color: str = "#8b9cc0") -> QIcon:
        path = (
            "M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6"
            "M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2"
        )
        return make_icon(color)(path)

    @staticmethod
    def ai(color: str = "#3B82F6") -> QIcon:
        path = (
            "M12 2a7 7 0 017 7c0 2.38-1.19 4.47-3 5.74V17a2 2 0 01-2 2h-4a2 2 0 01-2-2v-2.26C6.19 13.47 5 11.38 5 9a7 7 0 017-7z"
            "M10 21v1a2 2 0 004 0v-1"
        )
        return make_icon(color)(path)

    @staticmethod
    def alert(color: str = "#8b9cc0") -> QIcon:
        path = (
            "M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"
            "M12 9v4M12 17h.01"
        )
        return make_icon(color)(path)

    @staticmethod
    def save(color: str = "#8b9cc0") -> QIcon:
        path = (
            "M19 21H5a2 2 0 01-2-2V5a2 2 0 012-2h11l5 5v11a2 2 0 01-2 2z"
            "M17 21v-8H7v8M7 3v5h8"
        )
        return make_icon(color)(path)

    @staticmethod
    def file(color: str = "#8b9cc0") -> QIcon:
        path = (
            "M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"
            "M14 2v6h6"
        )
        return make_icon(color)(path)

    @staticmethod
    def open_folder(color: str = "#8b9cc0") -> QIcon:
        path = (
            "M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z"
        )
        return make_icon(color)(path)

    @staticmethod
    def edit(color: str = "#8b9cc0") -> QIcon:
        path = (
            "M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"
            "M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"
        )
        return make_icon(color)(path)
