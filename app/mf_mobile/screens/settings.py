"""Ustawienia: motyw kolorów, dane przykładowe, usunięcie danych, informacje o wersji."""

from __future__ import annotations

from pathlib import Path
from typing import Any, List

import flet as ft

from mf_mobile import MOBILE_VERSION
from mf_mobile.theme import PALETTES
from mf_mobile.ui import bold, card, secondary_button, section, txt


def build(app: Any) -> List[ft.Control]:
    p, store = app.p, app.store
    out: List[ft.Control] = [section(p, "Motyw kolorów")]
    tiles = []
    for pal in PALETTES.values():
        selected = pal.name == store.theme
        tiles.append(ft.ListTile(
            leading=ft.Container(width=26, height=26, bgcolor=pal.accent, border_radius=ft.BorderRadius.all(13),
                                 border=ft.Border.all(2, p.text) if selected else None),
            title=txt(pal.label, 15, p.text),
            trailing=ft.Icon(ft.Icons.CHECK, color=p.accent) if selected else None, dense=True,
            on_click=lambda e, name=pal.name: app.apply_theme(name)))
    out.append(card(p, ft.Column(tiles, spacing=0), padding=4))

    out.append(section(p, "Dane"))
    data_controls: List[ft.Control] = []
    if store.is_demo:
        data_controls.append(txt("Używasz danych przykładowych.", 13, p.warning))
    data_controls.append(secondary_button(p, "Wczytaj dane przykładowe", lambda e: app.confirm(
        "Dane przykładowe", "Zastąpić dane w telefonie przykładowymi? (Dane na komputerze nie zmienią się.)",
        lambda: (store.load_demo(), app.go_tab(0)), yes="Wczytaj", danger=False), ft.Icons.SCIENCE_OUTLINED))
    data_controls.append(secondary_button(p, "Usuń wszystkie dane z telefonu", lambda e: app.confirm(
        "Usunąć dane z telefonu?", "Zmiany, których nie wysłano do OneDrive, zostaną utracone. Dane na komputerze "
        "pozostaną bez zmian.", lambda: (store.reset_all(), app.open_subpage("welcome")), yes="Usuń"),
        ft.Icons.DELETE_FOREVER_OUTLINED, color=p.negative))
    out.append(card(p, ft.Column(data_controls, spacing=10, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)))

    engine = Path(__file__).resolve().parents[2] / "src" / "ENGINE_VERSION"
    engine_text = engine.read_text(encoding="utf-8").strip() if engine.exists() else "?"
    out.append(section(p, "O aplikacji"))
    out.append(card(p, ft.Column([
        bold(f"Matrix Finance Mobile {MOBILE_VERSION}", 15, p.text),
        txt(f"Silnik budżetu: {engine_text}", 12, p.muted),
        txt("Budżet domowy z oszczędzaniem kopertowym. Dane zostają na telefonie; z komputerem łączą się przez "
            "zaszyfrowany plik w Twoim OneDrive.", 12, p.muted),
    ], spacing=6)))
    return out
