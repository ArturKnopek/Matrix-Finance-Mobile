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

    out.append(section(p, "Tryb pracy"))
    mode_controls: List[ft.Control] = []
    if store.is_solo:
        mode_controls += [
            ft.Row([ft.Icon(ft.Icons.PHONE_IPHONE, color=p.accent), bold("Bez komputera", 15, p.text)]),
            txt("Telefon jest główną bazą: sam księguje stałe płatności, raty i lokaty. Dane chroni kopia zapasowa.",
                12, p.muted),
            secondary_button(p, "Stałe płatności", lambda e: app.open_subpage("recurring"), ft.Icons.EVENT_REPEAT),
            secondary_button(p, "Kopia zapasowa", lambda e: app.open_subpage("sync"), ft.Icons.BACKUP_OUTLINED),
            ft.TextButton(content="Przejdź na pracę z programem na komputerze…", on_click=lambda e: app.confirm(
                "Praca z komputerem", "Przy pierwszym pobraniu danych z komputera dane telefonu zostaną nimi "
                "ZASTĄPIONE. Żeby przenieść dane z telefonu na komputer: Kopia zapasowa › Zapisz kopię, a na "
                "komputerze Ustawienia › Import danych (.mfx).",
                lambda: (store.use_pc_mode(), app.open_subpage("sync")), yes="Przejdź", danger=False),
                style=ft.ButtonStyle(color=p.muted)),
        ]
    elif store.is_demo:
        mode_controls += [
            txt("Używasz danych przykładowych.", 13, p.warning),
            secondary_button(p, "Zacznij na swoich danych — bez komputera", lambda e: app.confirm(
                "Bez komputera", "Dane przykładowe zostaną usunięte. Zaczniesz od kont Karta i Gotówka oraz "
                "kopert bez budżetu.", lambda: (store.start_solo(fresh=True), app.go_tab(0)), yes="Zacznij",
                danger=False), ft.Icons.PHONE_IPHONE),
        ]
    else:
        mode_controls += [
            ft.Row([ft.Icon(ft.Icons.COMPUTER, color=p.accent), bold("Z programem na komputerze", 15, p.text)]),
            txt("Główna baza jest na komputerze; telefon wysyła zmiany przez OneDrive. Konta, koperty i zlecenia "
                "zakładasz na komputerze.", 12, p.muted),
            ft.TextButton(content="Przejdź na tryb bez komputera…", on_click=lambda e: app.confirm(
                "Bez komputera", "Telefon stanie się główną bazą — obecne dane zostają. Zmiany z telefonu nie będą "
                "już wysyłane na komputer"
                + (f" (niewysłane: {len(store.pending())} — zostaną tylko na telefonie)" if store.pending() else "")
                + ". Dane chroni kopia zapasowa.",
                lambda: (store.start_solo(fresh=False), app.go_tab(0)), yes="Przejdź", danger=False),
                style=ft.ButtonStyle(color=p.muted)),
        ]
    out.append(card(p, ft.Column(mode_controls, spacing=8, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)))

    out.append(section(p, "Dane"))
    data_controls: List[ft.Control] = []
    data_controls.append(secondary_button(p, "Wczytaj dane przykładowe", lambda e: app.confirm(
        "Dane przykładowe", "Zastąpić dane w telefonie przykładowymi? " + (
            "Twoje dane z telefonu zostaną usunięte — zrób najpierw kopię zapasową." if store.is_solo else
            "(Dane na komputerze nie zmienią się.)"),
        lambda: (store.load_demo(), app.go_tab(0)), yes="Wczytaj", danger=False), ft.Icons.SCIENCE_OUTLINED))
    data_controls.append(secondary_button(p, "Usuń wszystkie dane z telefonu", lambda e: app.confirm(
        "Usunąć dane z telefonu?", ("Bez kopii zapasowej danych nie da się odzyskać." if store.is_solo else
                                    "Zmiany, których nie wysłano do OneDrive, zostaną utracone. Dane na komputerze "
                                    "pozostaną bez zmian."),
        lambda: (store.reset_all(), app.open_subpage("welcome")), yes="Usuń"),
        ft.Icons.DELETE_FOREVER_OUTLINED, color=p.negative))
    out.append(card(p, ft.Column(data_controls, spacing=10, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)))

    engine = Path(__file__).resolve().parents[2] / "src" / "ENGINE_VERSION"
    engine_text = engine.read_text(encoding="utf-8").strip() if engine.exists() else "?"
    out.append(section(p, "O aplikacji"))
    out.append(card(p, ft.Column([
        bold(f"Matrix Finance Mobile {MOBILE_VERSION}", 15, p.text),
        txt(f"Silnik budżetu: {engine_text}", 12, p.muted),
        txt("Budżet domowy z oszczędzaniem kopertowym. Dane zostają na telefonie; kopia zapasowa i współpraca z "
            "komputerem — przez zaszyfrowany plik w Twoim OneDrive.", 12, p.muted),
    ], spacing=6)))
    return out
