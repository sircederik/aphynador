from __future__ import annotations

from typing import Any, Callable
import flet as ft


def border_all(width: float, color: str) -> Any:
    border_cls = getattr(ft, "Border", None) or getattr(ft, "border", None)
    return border_cls.all(width, color)


def make_button(label: str, on_click: Callable[..., Any]) -> ft.Control:
    btn_cls = getattr(ft, "Button", None) or getattr(ft, "ElevatedButton")
    return btn_cls(label, on_click=on_click)


def set_button_label(btn: ft.Control, label: str) -> None:
    if hasattr(btn, "content") and isinstance(getattr(btn, "content"), (str, type(None))):
        btn.content = label
    elif hasattr(btn, "text"):
        btn.text = label
    else:
        btn.content = ft.Text(label)


def make_dropdown(
    label: str,
    value: str,
    options: list[ft.dropdown.Option],
    width: float,
    on_change: Callable[..., Any],
) -> ft.Dropdown:
    try:
        return ft.Dropdown(
            label=label,
            value=value,
            options=options,
            width=width,
            on_select=on_change,
        )
    except TypeError:
        return ft.Dropdown(
            label=label,
            value=value,
            options=options,
            width=width,
            on_change=on_change,
        )
