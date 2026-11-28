"""Transakcje miesiąca: wyszukiwanie, filtr rodzaju, lista dzień po dniu."""

from __future__ import annotations

from datetime import date
from itertools import groupby
from typing import Any, List

import flet as ft

from mf_mobile import forms
from mf_mobile.store import money, plural
from mf_mobile.ui import amount, bold, card, empty, field, txt

DAYS = ["poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota", "niedziela"]
ICONS = {"Wydatek": ft.Icons.SOUTH_EAST, "Dochód": ft.Icons.NORTH_EAST}


def build(app: Any) -> List[ft.Control]:
    p, store = app.p, app.store
    state = app.view_state.setdefault("transactions", {"search": "", "kind": "all", "all": False})
    everywhere = bool(state.get("all")) and bool(state["search"])
    rows = store.transactions(state["search"], state["kind"], limit=300 if everywhere else None,
                              all_months=everywhere)

    search = field(p, "Szukaj (sklep, opis, kwota…)", state["search"], prefix_icon=ft.Icons.SEARCH, dense=True)

    def on_search(e: Any) -> None:
        state["search"] = e.control.value or ""
        app.render()

    search.on_submit = on_search
    search.on_blur = on_search
    kinds = ft.SegmentedButton(
        segments=[ft.Segment(value=v, label=txt(label, 12)) for v, label in
                  (("all", "Wszystkie"), ("expense", "Wydatki"), ("income", "Dochody"), ("transfer", "Inne"))],
        selected=[state["kind"]], show_selected_icon=False,
        on_change=lambda e: (state.update(kind=e.control.selected[0] if e.control.selected else "all"),
                             app.render()))
    out: List[ft.Control] = [search, ft.Row([kinds], scroll=ft.ScrollMode.AUTO)]
    if state["search"]:
        out.append(ft.Row([
            ft.Switch(value=bool(state.get("all")), active_color=p.accent,
                      on_change=lambda e: (state.update(all=bool(e.control.value)), app.render())),
            ft.Container(txt("Szukaj we wszystkich miesiącach", 13, p.text), expand=True)],
            vertical_alignment=ft.CrossAxisAlignment.CENTER))
    spent = sum(-t["signed_amount"] for t in rows if t["type"] == "Wydatek")
    earned = sum(t["signed_amount"] for t in rows if t["type"] == "Dochód")
    out.append(ft.Row([txt(plural(len(rows), "wpis", "wpisy", "wpisów"), 12, p.muted, expand=True),
                       txt(f"wydatki {money(spent)} · dochody {money(earned)}", 12, p.muted)]))
    if not rows:
        out.append(empty(p, "Brak wpisów. Dodaj wydatek przyciskiem +." if not state["search"]
                         else "Nic nie znaleziono.", ft.Icons.RECEIPT_LONG_OUTLINED))
        return out
    for day, items in groupby(rows, key=lambda t: t["date"][:10]):
        items = list(items)
        try:
            d = date.fromisoformat(day)
            header = f"{DAYS[d.weekday()].capitalize()}, {d:%d.%m.%Y}" if everywhere else \
                f"{DAYS[d.weekday()].capitalize()}, {d:%d.%m}"
        except ValueError:
            header = day
        day_total = sum(t["signed_amount"] for t in items if t["type"] in ("Wydatek", "Dochód"))
        tiles: List[ft.Control] = []
        for t in items:
            color = p.negative if t["signed_amount"] < 0 else p.positive
            subtitle = t.get("category") or t["kind_label"]
            subtitle += f" · {t.get('account_type')}"
            if t.get("pending"):
                subtitle += " · ⏳ do wysłania"
            tiles.append(ft.ListTile(
                leading=ft.Icon(ICONS.get(t["type"], ft.Icons.SWAP_HORIZ), color=color),
                title=txt(t.get("shop") or t.get("description") or t["kind_label"], 14, p.text,
                          max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                subtitle=txt(subtitle, 12, p.muted, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                trailing=amount(p, t["signed_amount"], 14, signed=True), dense=True,
                content_padding=ft.Padding.symmetric(horizontal=6),
                on_click=lambda e, tx=t: _open(app, tx)))
        out.append(ft.Row([bold(header, 13, p.muted, expand=True),
                           txt(money(day_total, signed=True) if day_total else "", 12, p.muted)]))
        out.append(card(p, ft.Column(tiles, spacing=0), padding=4))
    return out


def _open(app: Any, tx: dict) -> None:
    if tx["type"] in ("Wydatek", "Dochód"):
        forms.transaction_sheet(app, tx)
    else:
        forms.transaction_details(app, tx)
