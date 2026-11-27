"""Koperty miesiąca: ile zostało, paski wykorzystania, korekty i przesunięcia."""

from __future__ import annotations

from typing import Any, Dict, List

import flet as ft

from mf_mobile import forms
from mf_mobile.store import money
from mf_mobile.ui import amount, bold, card, empty, envelope_title, meter, section, txt


def build(app: Any) -> List[ft.Control]:
    p, store = app.p, app.store
    s = store.summary()
    envs = store.envelopes()
    out: List[ft.Control] = [card(p, ft.Column([
        ft.Row([txt("Do wydania w kopertach", 13, p.muted, expand=True), bold(money(s["remaining"]), 20, p.positive)]),
        ft.Row([txt(f"przychody {money(s['income'])}", 12, p.muted, expand=True),
                txt(f"przydzielono {money(s['budgeted'])}", 12, p.muted)]),
        ft.Row([txt("do rozdysponowania", 12, p.muted, expand=True),
                bold(money(s["unallocated"]), 13, p.positive if s["unallocated"] >= 0 else p.negative)]),
    ], spacing=6), highlight=True)]
    manage_ok = store.can_manage
    if not envs:
        out.append(empty(p, "Brak kopert z budżetem w tym miesiącu.\n" + (
            "Dotknij kopertę niżej i ustaw budżet albo dodaj nową." if manage_ok else
            "Budżety ustawisz na komputerze."), ft.Icons.MAIL_OUTLINE))
        if manage_ok:
            out += _no_budget(app, [])
        return out
    out.append(section(p, "Dotknij kopertę: wydatek, korekta, przesunięcie"))
    for e in envs:
        details = f"budżet {money(e['budget'])}"
        if e["carried"]:
            details += f" + {money(e['carried'])} z poprz."
        if e["adjustment"]:
            details += f" · korekty {money(e['adjustment'], signed=True)}"
        pct = e["pct"]
        out.append(card(p, ft.Column([
            ft.Row([envelope_title(p, e["name"], e["rollover"]), amount(p, e["remaining"], 16)]),
            meter(p, pct),
            ft.Row([txt(details, 12, p.muted, expand=True),
                    txt(f"wydano {money(e['spent'])}" + (f" · {pct:.0f}%" if pct is not None else ""), 12, p.muted)]),
        ], spacing=8), on_click=lambda ev, env=e: forms.envelope_actions(app, env)))
    out.append(ft.Row([ft.Icon(ft.Icons.AUTORENEW, size=14, color=p.accent),
                       txt("koperta elastyczna — niewydane środki przechodzą na kolejny miesiąc.", 12, p.muted,
                           expand=True)], spacing=4))
    if manage_ok:
        out += _no_budget(app, envs)
    return out


def _no_budget(app: Any, shown: List[Dict[str, Any]]) -> List[ft.Control]:
    """Bez komputera: koperty bez budżetu (dotknij, aby ustawić) i przycisk „Nowa koperta”."""
    from mf_mobile import manage
    from mf_mobile.ui import secondary_button

    p, store = app.p, app.store
    names = {e["name"] for e in shown}
    rest = [e for e in store.envelopes(only_active=False) if e["name"] not in names]
    out: List[ft.Control] = []
    if rest:
        out.append(section(p, "Bez budżetu — dotknij, aby ustawić"))
        out.append(card(p, ft.Column([ft.ListTile(
            title=txt(e["name"], 14, p.text), dense=True, content_padding=ft.Padding.symmetric(horizontal=6),
            trailing=ft.Icon(ft.Icons.EDIT_OUTLINED, color=p.muted, size=18),
            on_click=lambda ev, env=e: manage.envelope_sheet(app, env)) for e in rest], spacing=0), padding=4))
    out.append(secondary_button(p, "Nowa koperta", lambda e: manage.envelope_sheet(app), ft.Icons.ADD))
    return out
