"""1.4: analiza, podpowiedzi sklepów, eksport, automatyczne odkładanie, PIN, wyszukiwanie we wszystkich miesiącach."""
from __future__ import annotations

from datetime import date, timedelta

import flet as ft
import pytest

from mf_mobile import forms, manage
from mf_mobile.screens import analysis, dashboard, lock, recurring_screen, settings, transactions
from mf_mobile.store import Store
from test_screens import StubApp
from test_solo_screens import _button, _click, _field, _walk


class App(StubApp):
    def __init__(self, store):
        super().__init__(store)
        self.subpage, self.tab, self.locked = None, 0, False

    def unlock(self):
        self.locked = False

    def shift_month(self, delta):
        self.store.shift_month(delta)


@pytest.fixture(autouse=True)
def no_ui_updates(monkeypatch):
    monkeypatch.setattr(ft.BaseControl, "update", lambda self: None)


@pytest.fixture()
def app():
    s = Store()
    s.reset_all()
    s.start_solo(fresh=True)
    s.set_password("haslo-kopii")
    from src.finance import accounts

    accounts.set_account_balance("Karta", 5000, record=False)  # stan początkowy bez wpisu
    return App(s)


def _all(control):
    """Jak _walk, ale także tytuły i podtytuły wierszy list (ListTile)."""
    yield control
    for attr in ("content", "controls", "actions", "title", "subtitle", "leading", "trailing"):
        child = getattr(control, attr, None)
        if isinstance(child, list):
            for c in child:
                yield from _all(c)
        elif isinstance(child, ft.Control):
            yield from _all(child)


def _texts(controls):
    return [str(c.value) for ctl in controls for c in _all(ctl) if isinstance(c, ft.Text) and c.value]


def test_digest_cache_follows_changes(app):
    s = app.store
    s.mark_backup()
    assert not s.backup_needed
    s.add_transaction("Wydatek", 10, "Jedzenie", "Karta", "Żabka")
    assert s.backup_needed  # zmiana przez Store unieważnia zapamiętany skrót
    s.mark_backup()
    assert not s.backup_needed and not s.backup_needed  # drugi raz bez liczenia od nowa


def test_any_month_transactions_and_search(app):
    s = app.store
    last_month = (date.today().replace(day=1) - timedelta(days=3)).isoformat()
    s.add_transaction("Wydatek", 50, "Zakupy", "Karta", "Allegro", day=last_month)
    assert s.transactions() == [] and s.has_transactions()
    assert len(s.transactions("allegro", all_months=True)) == 1
    app.view_state["transactions"] = {"search": "allegro", "kind": "all", "all": True}
    assert any("Allegro" in t for t in _texts(transactions.build(app)))


def test_shop_hints_and_recent_chips(app):
    s = app.store
    for _ in range(3):
        s.add_transaction("Wydatek", 20, "Jedzenie", "Karta", "Biedronka")
    s.add_transaction("Wydatek", 80, "Transport", "Gotówka", "Orlen")
    recent = s.recent_shops()
    assert recent[0]["shop"] == "Biedronka" and recent[0]["count"] == 3
    assert s.shop_hint("orlen") == {"category": "Transport", "account": "Gotówka"}
    assert s.shop_hint("nieznany") is None
    forms.transaction_sheet(app)
    sheet = app.shown[-1]
    chip = next(c for c in _walk(sheet) if isinstance(c, ft.Chip) and c.label.value == "Orlen")
    chip.on_click(None)
    assert _field(sheet, "Sklep").value == "Orlen"
    assert _field(sheet, "Koperta").value == "Transport" and _field(sheet, "Konto").value == "Gotówka"


def test_analysis_numbers_and_screen(app):
    s = app.store
    s.add_transaction("Dochód", 6000, "Wynagrodzenie", "Karta", "Pensja")
    s.add_transaction("Wydatek", 300, "Jedzenie", "Karta", "Lidl")
    s.add_transaction("Wydatek", 120, "Transport", "Karta", "Orlen")
    s.add_transaction("Wydatek", 80, "Jedzenie", "Karta", "Lidl")
    trend = s.trend(6)
    assert len(trend) == 6 and trend[-1]["income"] == 6000 and trend[-1]["expense"] == 500
    by_env = s.spending_by_envelope()
    assert [e["name"] for e in by_env][:2] == ["Jedzenie", "Transport"]
    shops = s.top_shops()
    assert shops[0] == {"shop": "Lidl", "total": 380.0, "count": 2}
    pace = s.month_pace()
    assert pace["spent"] == 500 and pace["forecast"] >= 500
    texts = _texts(analysis.build(app))
    assert "Wydano do dziś" in texts and "Lidl" in texts and any("Stopa oszczędności" in t for t in texts)
    assert any("Analiza i doradca" in t for t in _texts(dashboard.build(app)))
    s.shift_month(-1)
    assert s.month_pace() is None and analysis.build(app)  # poprzedni miesiąc — bez prognozy


def test_export_csv_and_report(app):
    s = app.store
    s.add_transaction("Wydatek", 42.5, "Jedzenie", "Karta", "Piekarnia")
    name, data, count = s.csv_bytes()
    assert name.endswith(f"{s.ym}.csv") and count == 1 and "Piekarnia" in data.decode("utf-8-sig")
    assert s.csv_bytes(whole=True)[0] == "MatrixFinance-transakcje.csv"
    name, html = s.report_html()
    assert name.endswith(".html") and b"<html" in html.lower()


def test_autosave_rules(app):
    s = app.store
    s.add_goal("Poduszka", 10000, "Karta", None)
    goal = s.goals()[0]
    s.save_autosave(None, "Karta", "income_percent", 10, "goal", str(goal["id"]))
    rules = s.autosave_rules()
    assert rules[0]["target_label"] == "Poduszka" and "10% każdego wpływu" in rules[0]["text"]
    s.add_transaction("Dochód", 4000, "Wynagrodzenie", "Karta", "Pensja")
    assert float(s.goals()[0]["current_amount"]) == 400
    assert s.toggle_autosave(rules[0]["id"]) is False
    s.add_transaction("Dochód", 1000, "Wynagrodzenie", "Karta", "Premia")
    assert float(s.goals()[0]["current_amount"]) == 400  # reguła wstrzymana
    s.delete_autosave(rules[0]["id"])
    assert s.autosave_rules() == []
    with pytest.raises(ValueError):
        s.save_autosave(None, "Karta", "income_percent", 150, "goal", str(goal["id"]))
    # formularz
    manage.autosave_sheet(app)
    sheet = app.shown[-1]
    mode = _field(sheet, "Rodzaj")
    mode.value = "roundup"
    mode.on_select(None)
    _field(sheet, "Zaokrąglaj do pełnych").value = "10"
    _click(sheet, "Zapisz regułę")
    assert s.autosave_rules()[0]["mode"] == "roundup"
    assert any("zaokrąglaj" in t.lower() for t in _texts(recurring_screen.build(app)))


def test_pin_lock(app):
    s = app.store
    with pytest.raises(ValueError):
        s.set_pin("12")
    s.set_pin("2468")
    assert s.has_pin and s.pin_length == 4 and s.check_pin("2468") and not s.check_pin("1111")
    app.locked = True
    controls = lock.build(app)
    pin = next(c for ctl in controls for c in _walk(ctl) if isinstance(c, ft.TextField))
    pin.value = "1111"
    pin.on_submit(None)
    assert app.locked and any("Błędny PIN" in t for t in _texts(controls))
    pin.value = "2468"
    pin.on_submit(None)
    assert not app.locked
    # zapomniany PIN: hasło kopii odblokowuje i wyłącza PIN
    app.locked = True
    lock.forgot(app)
    dialog = app.shown[-1]
    _field(dialog, "Hasło kopii").value = "haslo-kopii"
    next(c for c in _walk(dialog) if isinstance(c, ft.FilledButton)).on_click(None)
    assert not app.locked and not s.has_pin
    # ustawienia: ustawienie i wyłączenie PIN-u
    assert any("Blokada PIN-em: wyłączona" in t for t in _texts(settings.build(app)))
    settings.pin_dialog(app)
    dialog = app.shown[-1]
    _field(dialog, "Nowy PIN").value = "13579"
    _field(dialog, "Powtórz PIN").value = "13579"
    next(c for c in _walk(dialog) if isinstance(c, ft.FilledButton)).on_click(None)
    assert s.check_pin("13579") and s.pin_length == 5
    settings.pin_off_dialog(app)
    dialog = app.shown[-1]
    _field(dialog, "Obecny PIN").value = "13579"
    next(c for c in _walk(dialog) if isinstance(c, ft.FilledButton)).on_click(None)
    assert not s.has_pin


def test_pin_not_in_backup(app, tmp_path):
    s = app.store
    s.set_pin("2468")
    raw = s.backup_bytes()
    s.reset_all()
    s.restore_backup(raw, "haslo-kopii")
    assert not s.has_pin  # PIN to ustawienie tego telefonu


def test_first_steps_ignore_new_month(app):
    s = app.store
    env = next(e for e in s.envelopes(only_active=False) if e["name"] == "Jedzenie")
    s.update_envelope(env["id"], "Jedzenie", 900, False)
    last_month = (date.today().replace(day=1) - timedelta(days=3)).isoformat()
    s.add_transaction("Wydatek", 50, "Jedzenie", "Karta", "Lidl", day=last_month)
    assert "Pierwsze kroki" not in _texts(dashboard.build(app))  # nowy miesiąc bez wpisów — bez „pierwszych kroków”


def test_button_helper_exists(app):
    assert _button  # pomocnik z test_solo_screens (import sprawdza zgodność)
