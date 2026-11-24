"""Pierwsze uruchomienie: połączenie z komputerem albo dane przykładowe."""

from __future__ import annotations

from typing import Any, List

import flet as ft

from mf_mobile.ui import bold, card, primary_button, secondary_button, txt


def build(app: Any) -> List[ft.Control]:
    p = app.p

    def demo(e: Any) -> None:
        app.store.load_demo()
        app.go_tab(0)

    features = [
        (ft.Icons.MAIL_OUTLINE, "Koperty z przenoszeniem reszty na kolejny miesiąc"),
        (ft.Icons.ADD_CIRCLE_OUTLINE, "Szybkie dodawanie wydatków i dochodów"),
        (ft.Icons.ACCOUNT_BALANCE_WALLET_OUTLINED, "Konta, przelewy, korekty sald, cele"),
        (ft.Icons.SYNC, "Synchronizacja z programem na komputerze przez OneDrive"),
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
        primary_button(p, "Połącz z komputerem (OneDrive)", lambda e: app.open_subpage("sync"), ft.Icons.SYNC),
        secondary_button(p, "Wypróbuj na danych przykładowych", demo, ft.Icons.SCIENCE_OUTLINED),
        txt("Najpierw włącz synchronizację w programie na komputerze: Ustawienia › Synchronizacja z telefonem.", 12,
            p.muted, text_align=ft.TextAlign.CENTER),
    ]
