from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import flet as ft


class ThemeChoice(str, Enum):
    SYSTEM = "system"
    LIGHT = "light"
    DARK = "dark"


@dataclass(frozen=True)
class AppPalette:
    bg_primary: str
    bg_card: str
    border_subtle: str
    text_primary: str
    text_secondary: str
    dial_face: str
    dial_border: str
    tick_major: str
    tick_minor: str
    needle_color: str
    in_tune_color: str
    near_tune_color: str
    out_tune_color: str
    accent: str


LIGHT_PALETTE = AppPalette(
    bg_primary="#F4F1EA",
    bg_card="#FFFFFF",
    border_subtle="#D6CFC2",
    text_primary="#1E1D1A",
    text_secondary="#5C584F",
    dial_face="#FAF8F2",
    dial_border="#8E8677",
    tick_major="#2B2925",
    tick_minor="#7A7468",
    needle_color="#D9381E",
    in_tune_color="#1B8A4B",
    near_tune_color="#D9821E",
    out_tune_color="#C92A2A",
    accent="#2B5B84",
)

DARK_PALETTE = AppPalette(
    bg_primary="#141619",
    bg_card="#1E2227",
    border_subtle="#313740",
    text_primary="#F0F2F5",
    text_secondary="#9AA3B0",
    dial_face="#1A1D22",
    dial_border="#4B5360",
    tick_major="#E5E9F0",
    tick_minor="#7D8694",
    needle_color="#FF5238",
    in_tune_color="#2ECC71",
    near_tune_color="#F39C12",
    out_tune_color="#E74C3C",
    accent="#5DADE2",
)


def resolve_palette(choice: ThemeChoice, platform_brightness: ft.Brightness | None) -> AppPalette:
    if choice == ThemeChoice.LIGHT:
        return LIGHT_PALETTE
    if choice == ThemeChoice.DARK:
        return DARK_PALETTE
    if platform_brightness == ft.Brightness.LIGHT:
        return LIGHT_PALETTE
    return DARK_PALETTE


def to_flet_theme_mode(choice: ThemeChoice) -> ft.ThemeMode:
    if choice == ThemeChoice.LIGHT:
        return ft.ThemeMode.LIGHT
    if choice == ThemeChoice.DARK:
        return ft.ThemeMode.DARK
    return ft.ThemeMode.SYSTEM
