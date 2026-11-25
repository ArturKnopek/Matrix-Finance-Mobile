"""Szkielet aplikacji: nawigacja, pasek górny, przełączanie ekranów, okna i komunikaty."""

from __future__ import annotations

import logging
import traceback
from typing import Any, Callable, List, Optional

import flet as ft

from mf_mobile import MOBILE_VERSION
from mf_mobile.store import Store, month_label
from mf_mobile.theme import Palette, flet_theme, palette
from mf_mobile.ui import bold, txt

log = logging.getLogger(__name__)

TABS = [
    ("Pulpit", ft.Icons.SPACE_DASHBOARD_OUTLINED, ft.Icons.SPACE_DASHBOARD),
    ("Transakcje", ft.Icons.RECEIPT_LONG_OUTLINED, ft.Icons.RECEIPT_LONG),
    ("Koperty", ft.Icons.MAIL_OUTLINE, ft.Icons.MAIL),
    ("Konta", ft.Icons.ACCOUNT_BALANCE_WALLET_OUTLINED, ft.Icons.ACCOUNT_BALANCE_WALLET),
    ("Cele", ft.Icons.SAVINGS_OUTLINED, ft.Icons.SAVINGS),
]
MONTH_TABS = {0, 1, 2}  # ekrany zależne od miesiąca


class MobileApp:
    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.store = Store()
        self.p: Palette = palette(self.store.theme)
        self.tab = 0
        self.subpage: Optional[str] = None  # "sync" | "settings" | "welcome"
        self.view_state: dict = {}  # filtry ekranów (np. wyszukiwanie transakcji)
        self.picker = ft.FilePicker()  # usługa systemowego wyboru plików (OneDrive przez dostawcę dokumentów)
        self.share = ft.Share()  # systemowe „Udostępnij” — wysyłka pliku zmian prosto do aplikacji OneDrive
        self.body = self._new_body()
        self.root = ft.SafeArea(content=self.body, expand=True)
        self._screen_key: Optional[tuple] = None

    @staticmethod
    def _new_body() -> ft.ListView:
        return ft.ListView(expand=True, spacing=12, padding=ft.Padding.only(left=14, right=14, top=6, bottom=96))

    # ================================================================ start / motyw

    def start(self) -> None:
        page = self.page
        page.title = "Matrix Finance"
        page.padding = 0
        page.spacing = 0
        page.theme_mode = ft.ThemeMode.DARK
        self.apply_theme(self.store.theme, render=False)
        page.add(self.root)
        if not self.store.has_data:
            self.subpage = "welcome"
        self.render()

    def apply_theme(self, name: str, render: bool = True) -> None:
        self.store.set_theme(name)
        self.p = palette(name)
        self.page.theme = flet_theme(self.p)
        self.page.dark_theme = flet_theme(self.p)
        self.page.bgcolor = self.p.bg
        if render:
            self.render()

    # ================================================================ rysowanie

    def render(self) -> None:
        self._scroll_top = False
        try:
            self._render()
        except Exception:  # błąd jednego ekranu nie może zamknąć aplikacji
            log.exception("Błąd rysowania ekranu")
            self.body.controls = [txt("Wystąpił błąd ekranu:\n" + traceback.format_exc(limit=3), 12, self.p.negative,
                                      selectable=True)]
        self.page.update()
        if self._scroll_top:
            self.page.run_task(self._scroll_to_top)

    async def _scroll_to_top(self) -> None:
        try:
            await self.body.scroll_to(offset=0, duration=0)
        except Exception:
            pass

    def _render(self) -> None:
        from mf_mobile.screens import accounts, dashboard, envelopes, goals, settings, sync_screen, transactions, welcome

        p = self.p
        key = (self.subpage, self.tab, self.store.ym)
        if key != self._screen_key:  # nowy ekran (albo miesiąc) => lista od góry; po zmianie danych pozycja zostaje
            self._screen_key = key
            self._scroll_top = True
        if self.subpage == "welcome":
            self.page.appbar = None
            self.page.navigation_bar = None
            self.page.floating_action_button = None
            self.body.controls = welcome.build(self)
            return
        if self.subpage in ("sync", "settings"):
            title = "Synchronizacja" if self.subpage == "sync" else "Ustawienia"
            self.page.appbar = self._appbar(title, back=True)
            self.page.navigation_bar = None
            self.page.floating_action_button = None
            builder = sync_screen.build if self.subpage == "sync" else settings.build
            self.body.controls = builder(self)
            return
        self.page.appbar = self._appbar(TABS[self.tab][0])
        self.page.navigation_bar = ft.NavigationBar(
            selected_index=self.tab, bgcolor=p.panel, indicator_color=p.accent_deep, on_change=self._on_tab,
            destinations=[ft.NavigationBarDestination(icon=icon, selected_icon=ft.Icon(sel, color=p.accent),
                                                      label=label) for label, icon, sel in TABS])
        self.page.floating_action_button = self._fab()
        builders = [dashboard.build, transactions.build, envelopes.build, accounts.build, goals.build]
        controls: List[ft.Control] = []
        if self.tab in MONTH_TABS:
            controls.append(self._month_switcher())
        controls += builders[self.tab](self)
        self.body.controls = controls

    def _appbar(self, title: str, back: bool = False) -> ft.AppBar:
        p = self.p
        pending = len(self.store.pending())
        sync_icon = ft.IconButton(
            icon=ft.Icons.SYNC, icon_color=p.warning if pending else p.accent, tooltip="Synchronizacja",
            badge=ft.Badge(label=str(pending), bgcolor=p.warning, text_color=p.on_accent) if pending else None,
            on_click=lambda e: self.open_subpage("sync"))
        actions: List[ft.Control] = []
        if not back:
            actions = [sync_icon, ft.IconButton(icon=ft.Icons.SETTINGS_OUTLINED, icon_color=p.muted,
                                                tooltip="Ustawienia", on_click=lambda e: self.open_subpage("settings"))]
        title_row = ft.Row([bold("MATRIX", 13, p.accent), bold(title, 18, p.text)], spacing=8) if not back \
            else bold(title, 18, p.text)
        return ft.AppBar(title=title_row, bgcolor=p.bg, actions=actions,
                         leading=ft.IconButton(icon=ft.Icons.ARROW_BACK, icon_color=p.text,
                                               on_click=lambda e: self.close_subpage()) if back else None,
                         automatically_imply_leading=False)

    def _month_switcher(self) -> ft.Row:
        p = self.p
        return ft.Row([
            ft.IconButton(icon=ft.Icons.CHEVRON_LEFT, icon_color=p.accent, on_click=lambda e: self.shift_month(-1)),
            bold(month_label(self.store.ym), 16, p.text, text_align=ft.TextAlign.CENTER, expand=True),
            ft.IconButton(icon=ft.Icons.CHEVRON_RIGHT, icon_color=p.accent, on_click=lambda e: self.shift_month(1)),
        ], alignment=ft.MainAxisAlignment.CENTER)

    def _fab(self) -> Optional[ft.FloatingActionButton]:
        from mf_mobile import forms

        p = self.p
        if self.tab == 3:
            return ft.FloatingActionButton(icon=ft.Icons.SWAP_HORIZ, bgcolor=p.accent, foreground_color=p.on_accent,
                                           tooltip="Przelew", on_click=lambda e: forms.transfer_dialog(self))
        if self.tab == 4:
            return None
        return ft.FloatingActionButton(icon=ft.Icons.ADD, bgcolor=p.accent, foreground_color=p.on_accent,
                                       tooltip="Nowy wydatek", on_click=lambda e: forms.transaction_sheet(self))

    # ================================================================ nawigacja

    def _on_tab(self, e: Any) -> None:
        self.tab = int(e.control.selected_index)
        self.render()

    def go_tab(self, index: int) -> None:
        self.subpage = None
        self.tab = index
        self.render()

    def open_subpage(self, name: str) -> None:
        self.subpage = name
        self.render()

    def close_subpage(self) -> None:
        self.subpage = None if self.store.has_data else "welcome"
        self.render()

    def shift_month(self, delta: int) -> None:
        self.store.shift_month(delta)
        self.render()

    # ================================================================ komunikaty / okna

    def toast(self, message: str, error: bool = False) -> None:
        p = self.p
        self.page.show_dialog(ft.SnackBar(content=txt(message, 14, p.on_accent if not error else "#FFFFFF"),
                                          bgcolor=p.accent if not error else p.negative,
                                          behavior=ft.SnackBarBehavior.FLOATING, duration=3500))

    def show(self, dialog: ft.Control) -> None:
        self.page.show_dialog(dialog)

    def close(self) -> None:
        try:
            self.page.pop_dialog()
        except Exception:
            pass

    def confirm(self, title: str, message: str, on_yes: Callable[[], None], yes: str = "Tak",
                danger: bool = True) -> None:
        p = self.p

        def yes_click(e: Any) -> None:
            self.close()
            self.run_action(on_yes)

        self.show(ft.AlertDialog(
            title=bold(title, 18), content=txt(message, 14, p.text), bgcolor=p.panel,
            actions=[ft.TextButton(content="Anuluj", on_click=lambda e: self.close(),
                                   style=ft.ButtonStyle(color=p.muted)),
                     ft.FilledButton(content=yes, on_click=yes_click,
                                     style=ft.ButtonStyle(bgcolor=p.negative if danger else p.accent,
                                                          color="#000000"))]))

    def run_action(self, action: Callable[[], Any], success: Optional[str] = None) -> bool:
        """Wykonuje zmianę danych; błąd silnika (np. brak środków) pokazuje jako komunikat."""
        try:
            action()
        except ValueError as e:
            self.toast(str(e), error=True)
            return False
        except Exception as e:  # pragma: no cover - nieoczekiwany błąd
            log.exception("Błąd operacji")
            self.toast(f"Błąd: {e}", error=True)
            return False
        if success:
            self.toast(success)
        self.render()
        return True


def main(page: ft.Page) -> None:
    logging.basicConfig(level=logging.INFO)
    page.data = MobileApp(page)
    page.data.start()


__all__ = ["MobileApp", "main", "MOBILE_VERSION"]
