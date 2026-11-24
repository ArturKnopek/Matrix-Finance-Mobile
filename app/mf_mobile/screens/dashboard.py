"""Pulpit: najważniejsze liczby miesiąca, koperty, ostatnie wpisy, synchronizacja."""

from __future__ import annotations

from typing import Any, List

import flet as ft

from mf_mobile import forms
from mf_mobile.store import money
from mf_mobile.ui import amount, banner, bold, card, envelope_title, kpi, meter, section, txt


def build(app: Any) -> List[ft.Control]:
    p, store = app.p, app.store
    s = store.summary()
    out: List[ft.Control] = []

    if store.is_demo:
        out.append(banner(p, ft.Icons.SCIENCE_OUTLINED, "Dane przykładowe — połącz z komputerem, aby pracować "
                          "na swoich danych.", p.warning, "Połącz", lambda e: app.open_subpage("sync")))
    pending = store.pending()
    if pending:
        out.append(banner(p, ft.Icons.CLOUD_UPLOAD_OUTLINED,
                          f"Zmiany do wysłania na komputer: {len(pending)}", p.warning, "Wyślij",
                          lambda e: app.open_subpage("sync")))

    out.append(ft.Row([kpi(p, "Do wydania", money(s["remaining"]), p.positive if s["remaining"] > 0 else p.muted,
                           f"z {money(s['available'])} w kopertach"),
                       kpi(p, "Bilans miesiąca", money(s["balance"], signed=True),
                           p.positive if s["balance"] >= 0 else p.negative)], spacing=10))
    out.append(ft.Row([kpi(p, "Wydatki", money(s["expense"]), p.negative if s["expense"] else p.muted,
                           f"przychody {money(s['income'])}"),
                       kpi(p, "Majątek", money(s["net_worth"]), p.text, f"dostępne {money(s['liquid'])}")],
                      spacing=10))

    envelopes = [e for e in store.envelopes() if e["available"] > 0 or e["spent"] > 0][:5]
    out.append(section(p, "Koperty", "Wszystkie", lambda e: app.go_tab(2)))
    if envelopes:
        rows: List[ft.Control] = []
        for e in envelopes:
            rows.append(ft.Column([
                ft.Row([envelope_title(p, e["name"], e["rollover"], 14, weight_bold=False),
                        amount(p, e["remaining"], 14)]),
                meter(p, e["pct"]),
            ], spacing=6))
        out.append(card(p, ft.Column(rows, spacing=14)))
    else:
        out.append(card(p, txt("Brak budżetów w kopertach — ustawisz je na komputerze.", 13, p.muted)))

    recent = store.transactions(limit=5)
    out.append(section(p, "Ostatnie wpisy", "Wszystkie", lambda e: app.go_tab(1)))
    if recent:
        tiles = []
        for t in recent:
            tiles.append(ft.ListTile(
                title=txt(t.get("shop") or t.get("category") or t["kind_label"], 14, p.text),
                subtitle=txt(f"{t['date'][8:10]}.{t['date'][5:7]} · {t.get('category') or t['kind_label']}", 12,
                             p.muted),
                trailing=amount(p, t["signed_amount"], 14, signed=True), dense=True,
                content_padding=ft.Padding.symmetric(horizontal=4),
                on_click=lambda e, tx=t: _open(app, tx)))
        out.append(card(p, ft.Column(tiles, spacing=0), padding=6))
    else:
        out.append(card(p, txt("Brak wpisów w tym miesiącu. Dodaj wydatek przyciskiem +.", 13, p.muted)))

    upcoming = store.upcoming()
    if upcoming:
        out.append(section(p, "Nadchodzące płatności (z komputera)"))
        rows = []
        for r in upcoming[:4]:
            when = "dziś" if r["days"] <= 0 else ("jutro" if r["days"] == 1 else f"za {r['days']} dni")
            rows.append(ft.Row([txt(r.get("name") or "", 14, p.text, expand=True), txt(when, 12, p.muted),
                                bold(money(float(r.get("amount") or 0)), 14, p.text)], spacing=10))
        out.append(card(p, ft.Column(rows, spacing=10)))

    goals = store.goals()[:3]
    if goals:
        out.append(section(p, "Cele", "Wszystkie", lambda e: app.go_tab(4)))
        rows = []
        for g in goals:
            rows.append(ft.Column([ft.Row([txt(g["name"], 14, p.text, expand=True),
                                           txt(f"{g['pct']:.0f}%", 13, p.muted)]),
                                   meter(p, g["pct"], "goal")], spacing=6))
        out.append(card(p, ft.Column(rows, spacing=14)))
    return out


def _open(app: Any, tx: dict) -> None:
    if tx["type"] in ("Wydatek", "Dochód"):
        forms.transaction_sheet(app, tx)
    else:
        forms.transaction_details(app, tx)
