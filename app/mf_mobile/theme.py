"""Motywy kolorów — te same co w wersji na komputer (Matrix, Bursztyn, Cyber, Fiolet, Karmazyn, Mono)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

import flet as ft


@dataclass(frozen=True)
class Palette:
    name: str
    label: str
    accent: str
    accent_dim: str
    accent_deep: str
    positive: str = "#3DDC84"
    negative: str = "#FF5A5A"
    warning: str = "#FFC94A"
    bg: str = "#000000"
    panel: str = "#0B110C"
    panel_hi: str = "#111A13"
    border: str = "#1C2A1F"
    track: str = "#16211A"
    text: str = "#E8ECE9"
    muted: str = "#8A948D"
    on_accent: str = "#000000"


PALETTES: Dict[str, Palette] = {
    p.name: p for p in (
        Palette("matrix", "Matrix (zielony)", "#00FF41", "#00A82B", "#002A0B", positive="#00FF41"),
        Palette("amber", "Bursztyn (pomarańczowy)", "#FF9F1C", "#B86E00", "#2E1A00", panel="#110D07",
                panel_hi="#1A140B", border="#2E2414", track="#221A0F"),
        Palette("cyber", "Cyber (cyjan)", "#00E5FF", "#008FA0", "#002A30", panel="#071012", panel_hi="#0C181B",
                border="#163036", track="#10242A"),
        Palette("violet", "Fiolet", "#C77DFF", "#7B2CBF", "#1E0B33", panel="#0D0912", panel_hi="#150F1D",
                border="#2A1D3A", track="#1F162B"),
        Palette("crimson", "Karmazyn (czerwony)", "#FF5C5C", "#A12626", "#2A0909", negative="#FF8A3D",
                panel="#110808", panel_hi="#1A0D0D", border="#341818", track="#271212"),
        Palette("mono", "Monochromatyczny", "#F0F0F0", "#8C8C8C", "#222222", positive="#BDEBC8",
                negative="#FFB3B3", panel="#0C0C0C", panel_hi="#141414", border="#262626", track="#1E1E1E"),
    )
}


def palette(name: str) -> Palette:
    return PALETTES.get(name, PALETTES["matrix"])


def flet_theme(p: Palette) -> ft.Theme:
    return ft.Theme(
        color_scheme_seed=p.accent,
        color_scheme=ft.ColorScheme(primary=p.accent, on_primary=p.on_accent, secondary=p.accent_dim,
                                    surface=p.panel, on_surface=p.text, error=p.negative),
    )
