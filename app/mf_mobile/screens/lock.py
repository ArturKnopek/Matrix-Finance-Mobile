"""Blokada aplikacji PIN-em: ekran odblokowania (przy starcie i po powrocie do aplikacji)."""

from __future__ import annotations

import time
from typing import Any, List

import flet as ft

from mf_mobile.ui import bold, field, primary_button, txt

MAX_TRIES = 5
WAIT_SECONDS = 30


def build(app: Any) -> List[ft.Control]:
    p, store = app.p, app.store
    state = app.view_state.setdefault("lock", {"tries": 0, "until": 0.0})
    pin = field(p, "PIN", password=True, keyboard_type=ft.KeyboardType.NUMBER, autofocus=True, text_size=26,
                text_align=ft.TextAlign.CENTER, max_length=8)
    info = txt("", 13, p.negative, text_align=ft.TextAlign.CENTER)

    def attempt(value: str) -> None:
        now = time.monotonic()
        if now < state["until"]:
            info.value = f"Za dużo prób — poczekaj {int(state['until'] - now) + 1} s."
            info.update()
            return
        if store.check_pin(value):
            state.update(tries=0, until=0.0)
            app.unlock()
            return
        state["tries"] += 1
        pin.value = ""
        if state["tries"] >= MAX_TRIES:
            state.update(tries=0, until=now + WAIT_SECONDS)
            info.value = f"Błędny PIN. Spróbuj za {WAIT_SECONDS} s."
        else:
            info.value = f"Błędny PIN (próba {state['tries']} z {MAX_TRIES})."
        pin.update()
        info.update()

    def on_change(e: Any) -> None:
        value = e.control.value or ""
        if store.pin_length and len(value) == store.pin_length:
            attempt(value)

    pin.on_change = on_change
    pin.on_submit = lambda e: attempt(pin.value or "")

    return [
        ft.Container(height=60),
        ft.Column([
            ft.Container(content=ft.Icon(ft.Icons.LOCK_OUTLINE, color=p.on_accent, size=44), width=88, height=88,
                         bgcolor=p.accent, border_radius=ft.BorderRadius.all(24), alignment=ft.Alignment.CENTER),
            bold("Matrix Finance", 26, p.accent),
            txt("Wpisz PIN, aby odblokować", 14, p.muted),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
        ft.Container(height=10),
        pin, info,
        primary_button(p, "Odblokuj", lambda e: attempt(pin.value or ""), ft.Icons.LOCK_OPEN),
        ft.Row([ft.TextButton(content="Nie pamiętasz PIN-u?", on_click=lambda e: forgot(app),
                              style=ft.ButtonStyle(color=p.muted))], alignment=ft.MainAxisAlignment.CENTER),
    ]


def forgot(app: Any) -> None:
    """Zapomniany PIN: odblokowanie hasłem kopii / synchronizacji (PIN zostaje wyłączony)."""
    p, store = app.p, app.store
    if not store.password:
        app.show(ft.AlertDialog(
            bgcolor=p.panel, title=bold("Zapomniany PIN", 18),
            content=txt("Nie ustawiono hasła kopii zapasowej, więc PIN-u nie da się obejść. Możesz usunąć dane z "
                        "telefonu i przywrócić je z kopii (.mfx).", 13, p.text),
            actions=[ft.TextButton(content="Anuluj", on_click=lambda e: app.close()),
                     ft.TextButton(content="Usuń dane", style=ft.ButtonStyle(color=p.negative),
                                   on_click=lambda e: (app.close(), app.confirm(
                                       "Usunąć dane z telefonu?", "Bez kopii zapasowej danych nie da się odzyskać.",
                                       lambda: (store.reset_all(), setattr(app, "subpage", "welcome"),
                                                app.unlock()), yes="Usuń")))]))
        return
    password = field(p, "Hasło kopii zapasowej / synchronizacji", password=True, can_reveal_password=True,
                     autofocus=True)

    def ok(e: Any) -> None:
        if (password.value or "") != store.password:
            password.error = "Złe hasło"
            password.update()
            return
        store.clear_pin()
        app.close()
        app.unlock()
        app.toast("Odblokowano. PIN został wyłączony — ustaw nowy w Ustawieniach.")

    app.show(ft.AlertDialog(
        bgcolor=p.panel, title=bold("Zapomniany PIN", 18),
        content=ft.Column([txt("Wpisz hasło kopii zapasowej (w trybie z komputerem — hasło synchronizacji).", 13,
                               p.text), password], tight=True, spacing=10),
        actions=[ft.TextButton(content="Anuluj", on_click=lambda e: app.close()),
                 ft.FilledButton(content="Odblokuj", on_click=ok,
                                 style=ft.ButtonStyle(bgcolor=p.accent, color=p.on_accent))]))
