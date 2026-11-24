"""Wspólne elementy interfejsu: karty, paski postępu (jak na komputerze), kwoty, nagłówki."""

from __future__ import annotations

from typing import Any, Callable, List, Optional

import flet as ft

from mf_mobile.store import money
from mf_mobile.theme import Palette


def txt(value: str, size: float = 14, color: Optional[str] = None, weight: Optional[ft.FontWeight] = None,
        **kwargs: Any) -> ft.Text:
    return ft.Text(value, size=size, color=color, weight=weight, **kwargs)


def bold(value: str, size: float = 14, color: Optional[str] = None, **kwargs: Any) -> ft.Text:
    return txt(value, size, color, ft.FontWeight.BOLD, **kwargs)


def amount(p: Palette, value: float, size: float = 14, signed: bool = False, neutral: bool = False) -> ft.Text:
    color = p.text if neutral or value == 0 else (p.positive if value > 0 else p.negative)
    return bold(money(value, signed=signed), size, color, no_wrap=True)


def meter_color(p: Palette, pct: Optional[float], kind: str = "budget") -> str:
    """Kolory pasków jak w wersji na komputer: budżet zielony → żółty → czerwony, cele w kolorze motywu."""
    if pct is None:
        return p.muted
    if kind == "goal":
        return p.positive if pct >= 100 else p.accent
    if pct >= 100:
        return p.negative
    if pct >= 80:
        return p.warning
    return p.positive


def meter(p: Palette, pct: Optional[float], kind: str = "budget", height: float = 8) -> ft.ProgressBar:
    value = 0.0 if pct is None else max(0.0, min(1.0, pct / 100.0))
    return ft.ProgressBar(value=value, color=meter_color(p, pct, kind), bgcolor=p.track, bar_height=height,
                          border_radius=ft.BorderRadius.all(height / 2))


def card(p: Palette, content: ft.Control, on_click: Optional[Callable] = None, padding: float = 14,
         highlight: bool = False, key: Optional[str] = None) -> ft.Container:
    return ft.Container(content=content, padding=ft.Padding.all(padding), bgcolor=p.panel_hi if highlight else p.panel,
                        border_radius=ft.BorderRadius.all(14), border=ft.Border.all(1, p.border),
                        on_click=on_click, ink=on_click is not None, key=key)


def section(p: Palette, title: str, action: Optional[str] = None, on_action: Optional[Callable] = None) -> ft.Row:
    controls: List[ft.Control] = [bold(title.upper(), 12, p.muted, expand=True)]
    if action:
        controls.append(ft.TextButton(content=action, on_click=on_action,
                                      style=ft.ButtonStyle(color=p.accent, padding=ft.Padding.all(4))))
    return ft.Row(controls, vertical_alignment=ft.CrossAxisAlignment.CENTER)


def envelope_title(p: Palette, name: str, rollover: bool, size: float = 15, weight_bold: bool = True) -> ft.Row:
    """Nazwa koperty; elastyczna (reszta przechodzi na kolejny miesiąc) z ikoną ↻."""
    label = bold(name, size, p.text) if weight_bold else txt(name, size, p.text)
    items: List[ft.Control] = [label]
    if rollover:
        items.insert(0, ft.Icon(ft.Icons.AUTORENEW, size=size + 1, color=p.accent, tooltip="koperta elastyczna"))
    return ft.Row(items, spacing=4, expand=True, tight=True)


def kpi(p: Palette, label: str, value: str, color: Optional[str] = None, hint: str = "") -> ft.Container:
    col: List[ft.Control] = [txt(label, 12, p.muted), bold(value, 18, color or p.text, no_wrap=True)]
    if hint:
        col.append(txt(hint, 11, p.muted))
    return ft.Container(content=ft.Column(col, spacing=2), padding=ft.Padding.all(12), bgcolor=p.panel,
                        border_radius=ft.BorderRadius.all(14), border=ft.Border.all(1, p.border), expand=True)


def empty(p: Palette, text: str, icon: Any = ft.Icons.INBOX_OUTLINED) -> ft.Container:
    return ft.Container(content=ft.Column([ft.Icon(icon, color=p.muted, size=40), txt(text, 14, p.muted,
                                                                                    text_align=ft.TextAlign.CENTER)],
                                          horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
                        padding=ft.Padding.symmetric(vertical=40, horizontal=20), alignment=ft.Alignment.CENTER)


def banner(p: Palette, icon: Any, text: str, color: str, action: Optional[str] = None,
           on_action: Optional[Callable] = None) -> ft.Container:
    row: List[ft.Control] = [ft.Icon(icon, color=color, size=22), txt(text, 13, p.text, expand=True)]
    if action:
        row.append(ft.FilledButton(content=action, on_click=on_action,
                                   style=ft.ButtonStyle(bgcolor=color, color=p.on_accent)))
    return ft.Container(content=ft.Row(row, spacing=10), padding=ft.Padding.all(12), bgcolor=p.panel_hi,
                        border_radius=ft.BorderRadius.all(14), border=ft.Border.all(1, color))


def primary_button(p: Palette, text: str, on_click: Callable, icon: Any = None, expand: bool = True) -> ft.FilledButton:
    return ft.FilledButton(content=text, icon=icon, on_click=on_click, expand=expand, height=48,
                           style=ft.ButtonStyle(bgcolor=p.accent, color=p.on_accent,
                                                shape=ft.RoundedRectangleBorder(radius=12)))


def secondary_button(p: Palette, text: str, on_click: Callable, icon: Any = None, expand: bool = True,
                     color: Optional[str] = None) -> ft.OutlinedButton:
    return ft.OutlinedButton(content=text, icon=icon, on_click=on_click, expand=expand, height=48,
                             style=ft.ButtonStyle(color=color or p.accent,
                                                  side=ft.BorderSide(1, color or p.accent_dim),
                                                  shape=ft.RoundedRectangleBorder(radius=12)))


def field(p: Palette, label: str, value: str = "", **kwargs: Any) -> ft.TextField:
    return ft.TextField(label=label, value=value, border_color=p.border, focused_border_color=p.accent,
                        cursor_color=p.accent, border_radius=ft.BorderRadius.all(12), **kwargs)


def dropdown(p: Palette, label: str, options: List[tuple], value: Optional[str] = None, **kwargs: Any) -> ft.Dropdown:
    return ft.Dropdown(label=label, value=value, options=[ft.DropdownOption(key=k, text=t) for t, k in options],
                       border_color=p.border, focused_border_color=p.accent, border_radius=ft.BorderRadius.all(12),
                       expand=True, **kwargs)
