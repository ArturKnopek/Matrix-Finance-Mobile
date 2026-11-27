"""Pierwsze uruchomienie: bez komputera (telefon to główna baza), z komputerem, kopia, dane przykładowe."""

from __future__ import annotations

from typing import Any, List

import flet as ft

from mf_mobile.ui import bold, card, primary_button, secondary_button, txt


def build(app: Any) -> List[ft.Control]:
    p = app.p

    def demo(e: Any) -> None:
        app.store.load_demo()
        app.go_tab(0)

    def solo(e: Any) -> None:
        app.store.start_solo(fresh=True)
        app.go_tab(0)
        app.toast("Tryb bez komputera. Zacznij od sald kont i budżetów kopert.")

    async def restore(e: Any) -> None:
        from mf_mobile.screens.backup_screen import pick_and_restore

        await pick_and_restore(app)

    features = [
        (ft.Icons.MAIL_OUTLINE, "Koperty z przenoszeniem reszty na kolejny miesiąc"),
        (ft.Icons.ADD_CIRCLE_OUTLINE, "Szybkie dodawanie wydatków i dochodów"),
        (ft.Icons.ACCOUNT_BALANCE_WALLET_OUTLINED, "Konta, lokaty, kredyty i raty, cele, stałe płatności"),
        (ft.Icons.PHONE_IPHONE, "Działa samodzielnie na telefonie — kopia zapasowa w OneDrive / Plikach"),
        (ft.Icons.SYNC, "Opcjonalnie: współpraca z programem na komputerze"),
    ]
    return [
        ft.Container(height=30),
        ft.Column([
            ft.Container(content=bold("M", 54, p.on_accent), width=96, height=96, bgcolor=p.accent,
                         border_radius=ft.BorderRadius.all(26), alignment=ft.Alignment.CENTER),
            bold("Matrix Finance", 30, p.accent),
            txt("budżet domowy · oszczędzanie kopertowe", 14, p.muted),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
        ft.Container(height=8),
        card(p, ft.Column([ft.Row([ft.Icon(icon, color=p.accent), txt(t, 14, p.text, expand=True)])
                           for icon, t in features], spacing=12)),
        ft.Container(height=8),
        primary_button(p, "Zacznij — bez komputera", solo, ft.Icons.PHONE_IPHONE),
        txt("Wszystko na telefonie: konta, koperty, cele, stałe płatności. Dane chroni zaszyfrowana kopia.", 12,
            p.muted, text_align=ft.TextAlign.CENTER),
        secondary_button(p, "Przywróć kopię zapasową (.mfx)", restore, ft.Icons.RESTORE),
        secondary_button(p, "Połącz z programem na komputerze", lambda e: app.open_subpage("sync"), ft.Icons.SYNC),
        ft.Row([ft.TextButton(content="Wypróbuj na danych przykładowych", on_click=demo, icon=ft.Icons.SCIENCE_OUTLINED,
                              style=ft.ButtonStyle(color=p.muted))], alignment=ft.MainAxisAlignment.CENTER),
    ]
