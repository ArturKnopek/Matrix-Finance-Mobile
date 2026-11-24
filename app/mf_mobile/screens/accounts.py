"""Konta i majątek: grupy kont, salda, przelewy i korekty sald."""

from __future__ import annotations

from itertools import groupby
from typing import Any, List

import flet as ft

from mf_mobile import forms
from mf_mobile.store import money
from mf_mobile.ui import amount, bold, card, section, txt

GROUP_ICONS = {"Codzienne": ft.Icons.CREDIT_CARD, "Oszczędności": ft.Icons.SAVINGS_OUTLINED,
               "Inwestycje": ft.Icons.SHOW_CHART, "Emerytalne": ft.Icons.ELDERLY}


def build(app: Any) -> List[ft.Control]:
    p, store = app.p, app.store
    s = store.summary()
    out: List[ft.Control] = [card(p, ft.Column([
        txt("Majątek netto", 13, p.muted), bold(money(s["net_worth"]), 28, p.text),
        ft.Row([txt(f"dostępne {money(s['liquid'])}", 12, p.muted, expand=True),
                txt(f"w celach {money(s['goals'])}", 12, p.muted)]),
    ], spacing=4), highlight=True)]
    accounts = store.accounts()
    for group, items in groupby(accounts, key=lambda a: a["group"]):
        items = list(items)
        total = sum(a["balance"] for a in items)
        out.append(section(p, f"{group} · {money(total)}"))
        tiles: List[ft.Control] = []
        for a in items:
            kind = a["kind"]
            sub = kind.label
            if a.get("institution"):
                sub += f" · {a['institution']}"
            if float(a.get("interest_rate") or 0):
                sub += f" · {float(a['interest_rate']):.2f}%"
            tiles.append(ft.ListTile(
                leading=ft.Icon(GROUP_ICONS.get(group, ft.Icons.ACCOUNT_BALANCE), color=p.accent),
                title=txt(a["name"], 15, p.text), subtitle=txt(sub, 12, p.muted, max_lines=1,
                                                               overflow=ft.TextOverflow.ELLIPSIS),
                trailing=amount(p, a["balance"], 15, neutral=a["balance"] >= 0), dense=True,
                content_padding=ft.Padding.symmetric(horizontal=6),
                on_click=lambda e, acc=a: forms.account_actions(app, acc)))
        out.append(card(p, ft.Column(tiles, spacing=0), padding=4))
    out.append(txt("Dotknij konto: przelew lub korekta salda. Nowe konta, lokaty i inwestycje dodasz na komputerze.",
                   12, p.muted))
    return out
