"""Analiza: tempo wydatków, trend 6 miesięcy, wydatki wg kopert, sklepy, wskazówki doradcy."""

from __future__ import annotations

from typing import Any, List

import flet as ft

from mf_mobile.store import MONTHS_PL, money, month_label, plural
from mf_mobile.ui import bold, card, section, txt

LEVEL_ICONS = {"alert": (ft.Icons.ERROR_OUTLINE, "negative"), "warn": (ft.Icons.WARNING_AMBER, "warning"),
               "info": (ft.Icons.LIGHTBULB_OUTLINE, "accent"), "ok": (ft.Icons.CHECK_CIRCLE_OUTLINE, "positive")}


def bar(p: Any, value: float, maximum: float, color: str, height: int = 10) -> ft.Row:
    """Pasek poziomy proporcjonalny do wartości (bez bibliotek wykresów — działa też na iPhonie)."""
    share = int(round(1000 * value / maximum)) if maximum > 0 else 0
    share = max(0, min(1000, share))
    cells: List[ft.Control] = []
    if share:
        cells.append(ft.Container(bgcolor=color, height=height, expand=share,
                                  border_radius=ft.BorderRadius.all(height / 2)))
    if share < 1000:
        cells.append(ft.Container(height=height, expand=1000 - share))
    return ft.Row(cells, spacing=0)


def _short(ym: str) -> str:
    y, m = ym.split("-")
    return f"{MONTHS_PL[int(m) - 1][:3]} {y[2:]}"


def build(app: Any) -> List[ft.Control]:
    p, store = app.p, app.store
    out: List[ft.Control] = [ft.Row([
        ft.IconButton(icon=ft.Icons.CHEVRON_LEFT, icon_color=p.accent, on_click=lambda e: app.shift_month(-1)),
        bold(month_label(store.ym), 16, p.text, text_align=ft.TextAlign.CENTER, expand=True),
        ft.IconButton(icon=ft.Icons.CHEVRON_RIGHT, icon_color=p.accent, on_click=lambda e: app.shift_month(1)),
    ])]

    pace = store.month_pace()
    if pace:
        over = pace["available"] > 0 and pace["forecast"] > pace["available"]
        rows: List[ft.Control] = [
            ft.Row([txt("Wydano do dziś", 13, p.muted, expand=True), bold(money(pace["spent"]), 18, p.text)]),
            ft.Row([txt(f"średnio dziennie ({pace['day']} z {pace['days']} dni)", 12, p.muted, expand=True),
                    txt(money(pace["per_day"]), 13, p.text)]),
            ft.Row([txt("prognoza na koniec miesiąca", 12, p.muted, expand=True),
                    bold(money(pace["forecast"]), 14, p.negative if over else p.positive)]),
        ]
        if pace["available"] > 0:
            rows.append(bar(p, pace["spent"], pace["available"], p.negative if over else p.accent))
            rows.append(txt(("Przy tym tempie zabraknie " + money(pace["forecast"] - pace["available"]) +
                             " w kopertach.") if over else
                            f"W kopertach jest {money(pace['available'])} — tempo w normie.", 12,
                            p.warning if over else p.muted))
        out.append(card(p, ft.Column(rows, spacing=8), highlight=True))

    trend = store.trend(6)
    top = max([max(t["income"], t["expense"]) for t in trend] + [0.0])
    out.append(section(p, "Ostatnie 6 miesięcy"))
    if top <= 0:
        out.append(card(p, txt("Brak przychodów i wydatków w tym okresie.", 13, p.muted)))
    else:
        rows = [ft.Row([ft.Container(width=10, height=10, bgcolor=p.positive, border_radius=5),
                        txt("przychody", 12, p.muted),
                        ft.Container(width=10, height=10, bgcolor=p.negative, border_radius=5),
                        txt("wydatki", 12, p.muted)], spacing=6)]
        for t in trend:
            saved = t["income"] - t["expense"]
            empty_month = not t["income"] and not t["expense"]
            rows.append(ft.Column([
                ft.Row([bold(_short(t["ym"]), 13, p.accent if t["ym"] == store.ym else p.text, expand=True),
                        txt("brak wpisów", 12, p.muted) if empty_month else
                        txt(("odłożono " if saved >= 0 else "na minusie ") + money(abs(saved)), 12,
                            p.positive if saved >= 0 else p.negative)]),
                bar(p, t["income"], top, p.positive, 8),
                bar(p, t["expense"], top, p.negative, 8),
            ], spacing=4))
        active = [t for t in trend if t["income"] or t["expense"]]
        avg_exp = sum(t["expense"] for t in active) / max(1, len(active))
        rows.append(txt(f"Średnie wydatki: {money(avg_exp)} / mies.", 12, p.muted))
        out.append(card(p, ft.Column(rows, spacing=12)))

    envs = store.spending_by_envelope()
    out.append(section(p, "Wydatki wg kopert"))
    if not envs:
        out.append(card(p, txt("Brak wydatków w tym miesiącu.", 13, p.muted)))
    else:
        total = sum(e["spent"] for e in envs)
        rows = []
        for e in envs[:10]:
            share = e["spent"] / total * 100 if total else 0
            rows.append(ft.Column([
                ft.Row([txt(e["name"], 14, p.text, expand=True), txt(f"{share:.0f}%", 12, p.muted),
                        bold(money(e["spent"]), 14, p.text)], spacing=8),
                bar(p, e["spent"], envs[0]["spent"], p.negative if e["over"] else p.accent, 8),
            ], spacing=4))
        rows.append(txt(f"Razem: {money(total)}", 12, p.muted))
        out.append(card(p, ft.Column(rows, spacing=10)))

    shops = store.top_shops(5)
    if shops:
        out.append(section(p, "Gdzie wydajesz najwięcej"))
        out.append(card(p, ft.Column([
            ft.Row([txt(s["shop"], 14, p.text, expand=True),
                    txt(plural(s["count"], "raz", "razy", "razy"), 12, p.muted),
                    bold(money(s["total"]), 14, p.text)], spacing=8) for s in shops], spacing=10)))

    tips = store.insights()
    if tips:
        out.append(section(p, "Doradca"))
        rows = []
        for t in tips[:8]:
            icon, color = LEVEL_ICONS.get(t.level, LEVEL_ICONS["info"])
            rows.append(ft.Row([ft.Icon(icon, color=getattr(p, color), size=20),
                                txt(t.text, 13, p.text, expand=True)],
                               vertical_alignment=ft.CrossAxisAlignment.START, spacing=10))
        out.append(card(p, ft.Column(rows, spacing=10)))
    return out
