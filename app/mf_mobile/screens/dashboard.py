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
        out.append(banner(p, ft.Icons.SCIENCE_OUTLINED, "Dane przykładowe. Swoje dane: Ustawienia › Tryb pracy.",
                          p.warning, "Ustawienia", lambda e: app.open_subpage("settings")))
    if app.backup_reminder():
        age = store.backup_age_days()
        out.append(banner(p, ft.Icons.BACKUP_OUTLINED, "Zrób kopię zapasową danych" + (
            f" — ostatnia {age} dni temu." if age is not None else " — jeszcze żadnej nie ma."), p.warning, "Kopia",
            lambda e: app.open_subpage("sync")))
    if store.is_solo:
        out += _first_steps(app)
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

    out.append(_advisor(app))

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
        out.append(card(p, txt("Brak budżetów w kopertach — ustaw je w zakładce Koperty." if store.can_manage else
                               "Brak budżetów w kopertach — ustawisz je na komputerze.", 13, p.muted)))

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
    if upcoming or store.is_solo:
        out.append(section(p, "Nadchodzące płatności" + ("" if store.is_solo else " (z komputera)"),
                           *(("Zarządzaj", lambda e: app.open_subpage("recurring")) if store.is_solo else ())))
    if not upcoming and store.is_solo:
        out.append(card(p, txt("Brak płatności w najbliższych 14 dniach. Stałe płatności (czynsz, rachunki, pensja) "
                               "dodasz w „Zarządzaj”.", 13, p.muted)))
    if upcoming:
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


def _first_steps(app: Any) -> List[ft.Control]:
    """Bez komputera: pierwsze kroki, dopóki nie ustawiono budżetów i nie ma wpisów."""
    p, store = app.p, app.store
    has_budget = any(e["budget"] > 0 for e in store.envelopes(only_active=False))
    has_tx = store.has_transactions()
    has_balance = any(abs(a["balance"]) > 0 for a in store.accounts())
    if has_budget and has_tx:
        return []
    steps = [
        (has_balance, "Ustaw salda kont (Konta › dotknij konto › Korekta salda) lub dodaj swoje konta.",
         "Konta", lambda e: app.go_tab(3)),
        (has_budget, "Ustaw budżety kopert na miesiąc (Koperty › dotknij kopertę › Edytuj).", "Koperty",
         lambda e: app.go_tab(2)),
        (bool(store.recurring()), "Dodaj stałe płatności: czynsz, rachunki, subskrypcje, pensję.", "Dodaj",
         lambda e: app.open_subpage("recurring")),
        (has_tx, "Zapisuj wydatki przyciskiem +.", None, None),
    ]
    rows: List[ft.Control] = [bold("Pierwsze kroki", 15, p.accent)]
    for done, text, action, handler in steps:
        row: List[ft.Control] = [ft.Icon(ft.Icons.CHECK_CIRCLE if done else ft.Icons.RADIO_BUTTON_UNCHECKED,
                                         color=p.positive if done else p.muted, size=20),
                                 txt(text, 13, p.text if not done else p.muted, expand=True)]
        if action and not done:
            row.append(ft.TextButton(content=action, on_click=handler, style=ft.ButtonStyle(color=p.accent)))
        rows.append(ft.Row(row, spacing=8))
    return [card(p, ft.Column(rows, spacing=8), highlight=True)]


def _advisor(app: Any) -> ft.Control:
    """Najważniejsza wskazówka doradcy + tempo wydatków; dotknięcie otwiera Analizę."""
    p, store = app.p, app.store
    tips = store.insights()
    tip = tips[0] if tips else None
    colors = {"alert": p.negative, "warn": p.warning, "info": p.accent, "ok": p.positive}
    pace = store.month_pace()
    line = ""
    if pace and pace["spent"] > 0:
        line = f"Prognoza wydatków do końca miesiąca: {money(pace['forecast'])}"
    rows: List[ft.Control] = [ft.Row([ft.Icon(ft.Icons.INSIGHTS, color=p.accent, size=20),
                                      bold("Analiza i doradca", 14, p.text, expand=True),
                                      ft.Icon(ft.Icons.CHEVRON_RIGHT, color=p.muted)])]
    if tip:
        rows.append(txt(tip.text, 13, colors.get(tip.level, p.text)))
    if line:
        rows.append(txt(line, 12, p.muted))
    return card(p, ft.Column(rows, spacing=6), on_click=lambda e: app.open_subpage("analysis"))
