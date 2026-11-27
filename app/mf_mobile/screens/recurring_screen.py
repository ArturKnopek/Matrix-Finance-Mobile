"""Stałe płatności (zlecenia): rachunki, subskrypcje, pensja, odkładanie — tryb bez komputera."""

from __future__ import annotations

from typing import Any, List

import flet as ft

from mf_mobile import manage
from mf_mobile.store import TYPE_INCOME, money
from mf_mobile.ui import bold, card, empty, primary_button, section, txt

TYPE_ICONS = {"Wydatek": ft.Icons.RECEIPT_LONG_OUTLINED, "Dochód": ft.Icons.PAYMENTS_OUTLINED,
              "Przelew": ft.Icons.SWAP_HORIZ, "Na Skarbonkę": ft.Icons.SAVINGS_OUTLINED}


def build(app: Any) -> List[ft.Control]:
    p, store = app.p, app.store
    items = store.recurring()
    out: List[ft.Control] = []
    from src.finance import recurring

    try:
        cost = recurring.monthly_cost_summary()
    except Exception:
        cost = {"cost": 0.0, "income": 0.0, "saving": 0.0}
    out.append(card(p, ft.Column([
        ft.Row([txt("Stałe koszty miesięcznie", 13, p.muted, expand=True),
                bold(money(cost["cost"]), 18, p.negative if cost["cost"] else p.muted)]),
        ft.Row([txt(f"stałe wpływy {money(cost['income'])}", 12, p.muted, expand=True),
                txt(f"odkładanie {money(cost['saving'])}", 12, p.muted)]),
    ], spacing=6), highlight=True))
    out.append(primary_button(p, "Nowa stała płatność", lambda e: manage.recurring_sheet(app), ft.Icons.ADD))
    if not items:
        out.append(empty(p, "Brak stałych płatności.\nDodaj czynsz, rachunki, subskrypcje albo pensję — aplikacja "
                            "zaksięguje je sama w dniu terminu.", ft.Icons.EVENT_REPEAT))
        return out
    out.append(section(p, manage.summary_text(items)))
    tiles: List[ft.Control] = []
    for r in items:
        nd = r.get("next_due")
        when = (nd.strftime("%d.%m.%Y") if nd else "—") if r["active"] else "wstrzymana"
        detail = [r.get("cycle") or "", when]
        if r.get("category"):
            detail.insert(0, r["category"])
        elif r.get("target_account"):
            detail.insert(0, f"› {r['target_account']}")
        amount = float(r["amount"] or 0)
        tiles.append(ft.ListTile(
            leading=ft.Icon(TYPE_ICONS.get(r["type"], ft.Icons.EVENT_REPEAT),
                            color=p.accent if r["active"] else p.muted),
            title=txt(r["name"], 15, p.text if r["active"] else p.muted),
            subtitle=txt(" · ".join(x for x in detail if x), 12, p.muted, max_lines=1,
                         overflow=ft.TextOverflow.ELLIPSIS),
            trailing=bold(money(amount, signed=True) if r["type"] == TYPE_INCOME else money(amount), 14,
                          p.positive if r["type"] == TYPE_INCOME else p.text),
            dense=True, content_padding=ft.Padding.symmetric(horizontal=6),
            on_click=lambda e, item=r: manage.recurring_actions(app, item)))
    out.append(card(p, ft.Column(tiles, spacing=0), padding=4))
    out.append(txt("Raty kredytów i zakupów na raty dodajesz w Kontach (Nowe konto › Zobowiązania).", 12, p.muted))
    return out
