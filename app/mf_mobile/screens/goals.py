"""Cele oszczędnościowe: postęp, plan miesięczny, wpłaty, wypłaty i korekty."""

from __future__ import annotations

from typing import Any, List

import flet as ft

from mf_mobile import forms
from mf_mobile.store import money
from mf_mobile.ui import bold, card, empty, meter, txt


def build(app: Any) -> List[ft.Control]:
    p, store = app.p, app.store
    goals = store.goals()
    if not goals:
        return [empty(p, "Brak celów oszczędnościowych.\n" + (
            "Dodaj pierwszy cel przyciskiem +." if store.can_manage else "Cele dodasz na komputerze."),
            ft.Icons.SAVINGS_OUTLINED)]
    total = sum(float(g["current_amount"] or 0) for g in goals)
    out: List[ft.Control] = [card(p, ft.Row([txt("Odłożone na cele", 13, p.muted, expand=True),
                                            bold(money(total), 20, p.accent)]), highlight=True)]
    for g in goals:
        current, target = float(g["current_amount"] or 0), float(g["target_amount"] or 0)
        plan = []
        if g.get("monthly_needed"):
            plan.append(f"odkładaj {money(g['monthly_needed'])}/mies.")
        if g.get("deadline"):
            plan.append(f"do {g['deadline']:%d.%m.%Y}")
        if g.get("overdue"):
            plan.append("termin minął")
        out.append(card(p, ft.Column([
            ft.Row([bold(g["name"], 15, p.text, expand=True), txt(f"{g['pct']:.0f}%", 14, p.accent)]),
            meter(p, g["pct"], "goal"),
            ft.Row([txt(f"{money(current)} z {money(target)}", 13, p.text, expand=True),
                    txt(f"brakuje {money(g['missing'])}" if g["missing"] > 0 else "osiągnięty ✓", 12, p.muted)]),
            *([txt(" · ".join(plan), 12, p.warning if g.get("overdue") else p.muted)] if plan else []),
        ], spacing=8), on_click=lambda e, goal=g: forms.goal_actions(app, goal)))
    out.append(txt("Dotknij cel: wpłata, wypłata, korekta stanu" + (", edycja, usunięcie." if store.can_manage
                                                                  else "."), 12, p.muted))
    return out
