"""Ustawienia: motyw kolorów, dane przykładowe, usunięcie danych, informacje o wersji."""

from __future__ import annotations

from pathlib import Path
from typing import Any, List

import flet as ft

from mf_mobile import MOBILE_VERSION
from mf_mobile.theme import PALETTES
from mf_mobile.store import month_label
from mf_mobile.ui import bold, card, field, secondary_button, section, txt


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

    out.append(section(p, "Bezpieczeństwo"))
    sec: List[ft.Control] = [ft.Row([ft.Icon(ft.Icons.LOCK_OUTLINE if store.has_pin else ft.Icons.LOCK_OPEN,
                                             color=p.accent if store.has_pin else p.muted),
                                     txt("Blokada PIN-em: włączona" if store.has_pin else "Blokada PIN-em: wyłączona",
                                         14, p.text, expand=True)])]
    sec.append(txt("PIN przy uruchomieniu i po powrocie do aplikacji (po minucie). Zapomniany PIN odblokujesz "
                   "hasłem kopii zapasowej.", 12, p.muted))
    if store.has_pin:
        sec.append(secondary_button(p, "Zmień PIN", lambda e: pin_dialog(app), ft.Icons.PIN_OUTLINED))
        sec.append(ft.TextButton(content="Wyłącz blokadę PIN-em", on_click=lambda e: pin_off_dialog(app),
                                 style=ft.ButtonStyle(color=p.muted)))
    else:
        sec.append(secondary_button(p, "Ustaw PIN", lambda e: pin_dialog(app), ft.Icons.PIN_OUTLINED))
    out.append(card(p, ft.Column(sec, spacing=8, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)))

    out.append(section(p, "Eksport"))
    out.append(card(p, ft.Column([
        txt(f"Transakcje do Excela (CSV) albo raport miesiąca ({month_label(store.ym)}) — do zapisania w Plikach, "
            "wysłania mailem lub wydruku.", 12, p.muted),
        secondary_button(p, "Transakcje miesiąca (CSV)", lambda e: app.page.run_task(export_csv, app, False),
                         ft.Icons.TABLE_VIEW_OUTLINED),
        secondary_button(p, "Wszystkie transakcje (CSV)", lambda e: app.page.run_task(export_csv, app, True),
                         ft.Icons.TABLE_CHART_OUTLINED),
        secondary_button(p, "Raport miesiąca (do druku / PDF)", lambda e: app.page.run_task(export_report, app),
                         ft.Icons.PRINT_OUTLINED),
    ], spacing=10, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)))

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


def pin_dialog(app: Any) -> None:
    """Ustawienie / zmiana PIN-u (4–8 cyfr, dwa razy)."""
    p, store = app.p, app.store
    first = field(p, "Nowy PIN (4–8 cyfr)", password=True, keyboard_type=ft.KeyboardType.NUMBER, autofocus=True,
                  max_length=8)
    second = field(p, "Powtórz PIN", password=True, keyboard_type=ft.KeyboardType.NUMBER, max_length=8)

    def save(e: Any) -> None:
        a, b = first.value or "", second.value or ""
        if not (a.isdigit() and 4 <= len(a) <= 8):
            first.error = "PIN to 4–8 cyfr"
            first.update()
            return
        if a != b:
            second.error = "PIN-y się różnią"
            second.update()
            return
        store.set_pin(a)
        app.close()
        app.render()
        app.toast("PIN ustawiony. Aplikacja zablokuje się po wyjściu na dłużej niż minutę."
                  + ("" if store.password else " Ustaw też hasło kopii — przyda się, gdy zapomnisz PIN."))

    app.show(ft.AlertDialog(
        bgcolor=p.panel, title=bold("PIN do aplikacji", 18),
        content=ft.Column([first, second], tight=True, spacing=10),
        actions=[ft.TextButton(content="Anuluj", on_click=lambda e: app.close()),
                 ft.FilledButton(content="Zapisz", on_click=save,
                                 style=ft.ButtonStyle(bgcolor=p.accent, color=p.on_accent))]))


def pin_off_dialog(app: Any) -> None:
    p, store = app.p, app.store
    current = field(p, "Obecny PIN", password=True, keyboard_type=ft.KeyboardType.NUMBER, autofocus=True,
                    max_length=8)

    def off(e: Any) -> None:
        if not store.check_pin(current.value or ""):
            current.error = "Błędny PIN"
            current.update()
            return
        store.clear_pin()
        app.close()
        app.render()
        app.toast("Blokada PIN-em wyłączona.")

    app.show(ft.AlertDialog(
        bgcolor=p.panel, title=bold("Wyłączyć blokadę?", 18), content=current,
        actions=[ft.TextButton(content="Anuluj", on_click=lambda e: app.close()),
                 ft.FilledButton(content="Wyłącz", on_click=off,
                                 style=ft.ButtonStyle(bgcolor=p.negative, color="#000000"))]))


async def export_csv(app: Any, whole: bool) -> None:
    from mf_mobile.files import deliver

    name, data, count = app.store.csv_bytes(whole)
    if not count:
        app.toast("Brak transakcji do eksportu.")
        return
    if await deliver(app, name, data, "text/csv", "Eksport transakcji (CSV)"):
        app.toast(f"Wyeksportowano {count} transakcji (otworzysz w Excelu / Arkuszach).")


async def export_report(app: Any) -> None:
    from mf_mobile.files import deliver

    name, data = app.store.report_html()
    if await deliver(app, name, data, "text/html", "Raport miesiąca"):
        app.toast("Raport gotowy — otwórz w przeglądarce, aby wydrukować lub zapisać jako PDF.")
