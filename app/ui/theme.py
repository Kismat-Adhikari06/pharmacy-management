"""Centralized theme-aware color provider.

All UI components should import colors from here instead of hardcoding hex values.
Call Theme.refresh() after switching themes so every widget picks up the new palette.
"""

from __future__ import annotations


class Theme:
    """Singleton theme color provider. Reads current theme once per refresh()."""

    _theme: str = "dark"

    _DARK = {
        "bg": "#111827",
        "surface": "#1f2937",
        "elevated": "#374151",
        "border": "#374151",
        "muted": "#1f2937",
        "accent": "#3b82f6",
        "accent_hover": "#60a5fa",
        "accent_pressed": "#2563eb",
        "text": "#f9fafb",
        "text2": "#9ca3af",
        "text3": "#6b7280",
        "success": "#22c55e",
        "warning": "#f59e0b",
        "danger": "#ef4444",
        "row_alt": "#1a2332",
        "row_hover": "#253040",
        "selection": "#1e3a5f",
        "header_bg": "#1a2332",
        "header_border": "#2d3a4d",
        "grid": "#2d3a4d",
        "scrollbar": "#374151",
        "scrollbar_hover": "#4b5563",
        "input_bg": "#1f2937",
        "input_border": "#374151",
        "card": "#1a2332",
        "action_btn": "#3b82f6",
        "action_hover": "#60a5fa",
        "action_pressed": "#2563eb",
        "action_danger": "#ef4444",
        "action_danger_hover": "#f87171",
        "action_danger_pressed": "#dc2626",
    }

    _LIGHT = {
        "bg": "#f1f5f9",
        "surface": "#ffffff",
        "elevated": "#ffffff",
        "border": "#e2e8f0",
        "muted": "#f1f5f9",
        "accent": "#2563eb",
        "accent_hover": "#3b82f6",
        "accent_pressed": "#1d4ed8",
        "text": "#0f172a",
        "text2": "#475569",
        "text3": "#94a3b8",
        "success": "#16a34a",
        "warning": "#d97706",
        "danger": "#dc2626",
        "row_alt": "#f8fafc",
        "row_hover": "#f1f5f9",
        "selection": "#dbeafe",
        "header_bg": "#f8fafc",
        "header_border": "#e2e8f0",
        "grid": "#e2e8f0",
        "scrollbar": "#cbd5e1",
        "scrollbar_hover": "#94a3b8",
        "input_bg": "#ffffff",
        "input_border": "#d1d5db",
        "card": "#ffffff",
        "action_btn": "#2563eb",
        "action_hover": "#3b82f6",
        "action_pressed": "#1d4ed8",
        "action_danger": "#dc2626",
        "action_danger_hover": "#ef4444",
        "action_danger_pressed": "#b91c1c",
    }

    @classmethod
    def refresh(cls) -> None:
        try:
            from app.services.settings_service import SettingsService
            settings = SettingsService.load()
            cls._theme = settings.default_theme
        except Exception:
            cls._theme = "dark"

    @classmethod
    def _pal(cls) -> dict[str, str]:
        return cls._DARK if cls._theme == "dark" else cls._LIGHT

    @classmethod
    def bg(cls) -> str:
        return cls._pal()["bg"]

    @classmethod
    def surface(cls) -> str:
        return cls._pal()["surface"]

    @classmethod
    def elevated(cls) -> str:
        return cls._pal()["elevated"]

    @classmethod
    def border(cls) -> str:
        return cls._pal()["border"]

    @classmethod
    def muted(cls) -> str:
        return cls._pal()["muted"]

    @classmethod
    def accent(cls) -> str:
        return cls._pal()["accent"]

    @classmethod
    def accent_hover(cls) -> str:
        return cls._pal()["accent_hover"]

    @classmethod
    def accent_pressed(cls) -> str:
        return cls._pal()["accent_pressed"]

    @classmethod
    def text(cls) -> str:
        return cls._pal()["text"]

    @classmethod
    def text2(cls) -> str:
        return cls._pal()["text2"]

    @classmethod
    def text3(cls) -> str:
        return cls._pal()["text3"]

    @classmethod
    def success(cls) -> str:
        return cls._pal()["success"]

    @classmethod
    def warning(cls) -> str:
        return cls._pal()["warning"]

    @classmethod
    def danger(cls) -> str:
        return cls._pal()["danger"]

    @classmethod
    def row_alt(cls) -> str:
        return cls._pal()["row_alt"]

    @classmethod
    def row_hover(cls) -> str:
        return cls._pal()["row_hover"]

    @classmethod
    def selection(cls) -> str:
        return cls._pal()["selection"]

    @classmethod
    def header_bg(cls) -> str:
        return cls._pal()["header_bg"]

    @classmethod
    def header_border(cls) -> str:
        return cls._pal()["header_border"]

    @classmethod
    def grid(cls) -> str:
        return cls._pal()["grid"]

    @classmethod
    def scrollbar(cls) -> str:
        return cls._pal()["scrollbar"]

    @classmethod
    def scrollbar_hover(cls) -> str:
        return cls._pal()["scrollbar_hover"]

    @classmethod
    def input_bg(cls) -> str:
        return cls._pal()["input_bg"]

    @classmethod
    def input_border(cls) -> str:
        return cls._pal()["input_border"]

    @classmethod
    def card(cls) -> str:
        return cls._pal()["card"]

    @classmethod
    def action_btn(cls) -> str:
        return cls._pal()["action_btn"]

    @classmethod
    def action_hover(cls) -> str:
        return cls._pal()["action_hover"]

    @classmethod
    def action_pressed(cls) -> str:
        return cls._pal()["action_pressed"]

    @classmethod
    def action_danger(cls) -> str:
        return cls._pal()["action_danger"]

    @classmethod
    def action_danger_hover(cls) -> str:
        return cls._pal()["action_danger_hover"]

    @classmethod
    def action_danger_pressed(cls) -> str:
        return cls._pal()["action_danger_pressed"]

    @classmethod
    def is_dark(cls) -> bool:
        return cls._theme == "dark"

    @classmethod
    def is_light(cls) -> bool:
        return cls._theme == "light"
