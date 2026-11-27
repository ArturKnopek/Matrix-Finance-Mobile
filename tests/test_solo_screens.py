"""Tryb „Bez komputera”: ekrany i formularze zarządzania — wypełnienie i zapis jak na telefonie."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Iterable

import flet as ft
import pytest

from mf_mobile import forms, manage
from mf_mobile.screens import (accounts, backup_screen, dashboard, envelopes, goals, recurring_screen, settings,
                               welcome)
from mf_mobile.store import Store
from test_screens import StubApp

SOLO_SCREENS = [dashboard, envelopes, accounts, goals, settings, welcome, backup_screen, recurring_screen]


class SoloApp(StubApp):
    def __init__(self, store: Store) -> None:
        super().__init__(store)
        self.subpage, self.tab = None, 0


@pytest.fixture(autouse=True)
def no_ui_updates(monkeypatch):
    """Formularze odświeżają się po zmianie pól — tu nie ma prawdziwej strony."""
    monkeypatch.setattr(ft.BaseControl, "update", lambda self: None)


@pytest.fixture()
def app():
    s = Store()
    s.reset_all()
    s.start_solo(fresh=True)
    s.set_password("haslo-kopii")
    return SoloApp(s)


def _walk(control: Any) -> Iterable[Any]:
    yield control
    for attr in ("content", "controls", "actions"):
        child = getattr(control, attr, None)
        if isinstance(child, list):
            for c in child:
                yield from _walk(c)
        elif child is not None and not isinstance(child, (str, int, float)):
            yield from _walk(child)


def _field(sheet: Any, label: str) -> Any:
    for c in _walk(sheet):
        if isinstance(c, (ft.TextField, ft.Dropdown)) and str(c.label or "").startswith(label):
            return c
    raise AssertionError(f"Brak pola: {label}")


def _button(sheet: Any, text: str) -> Any:
    for c in _walk(sheet):
        if isinstance(c, (ft.FilledButton, ft.OutlinedButton, ft.TextButton)) and c.content == text:
            return c
    raise AssertionError(f"Brak przycisku: {text}")


def _click(sheet: Any, text: str) -> None:
    _button(sheet, text).on_click(None)


def _balances(store):
    return {a["name"]: round(a["balance"], 2) for a in store.accounts()}


@pytest.mark.parametrize("screen", SOLO_SCREENS, ids=lambda m: m.__name__.split(".")[-1])
def test_solo_screens_build(screen, app):
    assert screen.build(app)
    app.store.add_transaction("Wydatek", 20, "Jedzenie", "Karta", "Żabka")
    assert screen.build(app)
    app.web = True  # iPhone (przeglądarka)
    assert screen.build(app)


def test_first_steps_and_reminder(app):
    controls = dashboard.build(app)
    texts = [c.value for ctl in controls for c in _walk(ctl) if isinstance(c, ft.Text)]
    assert "Pierwsze kroki" in texts
    app.store.set_balance("Karta", 100)
    assert any("kopię zapasową" in (t or "") for ctl in dashboard.build(app) for t in
               [c.value for c in _walk(ctl) if isinstance(c, ft.Text)])


def test_new_accounts_of_every_kind(app):
    store = app.store
    manage.account_sheet(app)
    sheet = app.shown[-1]
    _field(sheet, "Nazwa (np.").value = "mKonto"
    _field(sheet, "Saldo teraz").value = "1 250,50"
    _click(sheet, "Dodaj konto")
    assert _balances(store)["mKonto"] == 1250.5

    manage.account_sheet(app)
    sheet = app.shown[-1]
    kind = _field(sheet, "Rodzaj konta")
    kind.value = "deposit"
    kind.on_select(None)
    assert _field(sheet, "Kwota lokaty").visible and _field(sheet, "Okres").visible
    _field(sheet, "Nazwa (np.").value = "Lokata 3m"
    _field(sheet, "Kwota lokaty").value = "500"
    _field(sheet, "Oprocentowanie").value = "6,5"
    _field(sheet, "Okres").value = "3"
    _field(sheet, "Skąd pieniądze").value = "mKonto"
    _click(sheet, "Dodaj konto")
    assert _balances(store)["Lokata 3m"] == 500 and _balances(store)["mKonto"] == 750.5

    manage.account_sheet(app)
    sheet = app.shown[-1]
    kind = _field(sheet, "Rodzaj konta")
    kind.value = "installments"
    kind.on_select(None)
    assert not _field(sheet, "Pieniądze z kredytu").visible  # zakup na raty — bez wypłaty
    _field(sheet, "Nazwa (np.").value = "Telewizor"
    _field(sheet, "Ile zostało do spłaty").value = "2400"
    _field(sheet, "Liczba rat").value = "12"
    _click(sheet, "Dodaj konto")
    assert _balances(store)["Telewizor"] <= -2000
    assert any("rata 200,00 zł" in m for m, _ in app.toasts)

    manage.account_sheet(app)
    sheet = app.shown[-1]
    kind = _field(sheet, "Rodzaj konta")
    kind.value = "custom"
    kind.on_select(None)
    _field(sheet, "Nazwa (np.").value = "Krypto"
    _field(sheet, "Nazwa rodzaju").value = "Kryptowaluty"
    _field(sheet, "Saldo / wartość teraz").value = "300"
    _click(sheet, "Dodaj konto")
    acc = next(a for a in store.accounts() if a["name"] == "Krypto")
    assert acc["kind"].label == "Kryptowaluty"

    manage.account_sheet(app)  # błąd: pusta nazwa — formularz zostaje, pole z błędem
    sheet = app.shown[-1]
    _click(sheet, "Dodaj konto")
    assert _field(sheet, "Nazwa (np.").error


def test_account_actions_edit_valuation_close(app):
    store = app.store
    store.add_account("XTB", "investment", 1000)
    acc = next(a for a in store.accounts() if a["name"] == "XTB")
    forms.account_actions(app, acc)
    titles = [c.title.value for c in _walk(app.shown[-1]) if isinstance(c, ft.ListTile)]
    assert {"Wycena", "Edytuj (nazwa, bank, oprocentowanie)", "Zamknij konto"} <= set(titles)
    manage.valuation_sheet(app, acc)
    _field(app.shown[-1], "Aktualna wartość").value = "1100"
    _click(app.shown[-1], "Zapisz wycenę")
    assert _balances(store)["XTB"] == 1100
    manage.account_edit_sheet(app, acc)
    _field(app.shown[-1], "Nazwa").value = "XTB ETF"
    _click(app.shown[-1], "Zapisz")
    acc = next(a for a in store.accounts() if a["name"] == "XTB ETF")
    manage.close_account_sheet(app, acc)
    _field(app.shown[-1], "Pozostałe środki").value = "Karta"
    _click(app.shown[-1], "Zamknij konto")
    assert "XTB ETF" not in _balances(store) and _balances(store)["Karta"] == 1100


def test_envelope_and_goal_forms(app):
    store = app.store
    manage.envelope_sheet(app)
    _field(app.shown[-1], "Nazwa koperty").value = "Kawa"
    _field(app.shown[-1], "Budżet miesięczny").value = "150"
    _click(app.shown[-1], "Zapisz")
    env = next(e for e in store.envelopes() if e["name"] == "Kawa")
    assert env["budget"] == 150
    forms.envelope_actions(app, env)
    manage.envelope_sheet(app, env)
    _field(app.shown[-1], "Budżet miesięczny").value = "200"
    _click(app.shown[-1], "Zapisz")
    assert next(e for e in store.envelopes() if e["name"] == "Kawa")["budget"] == 200
    manage.envelope_sheet(app, env)
    _click(app.shown[-1], "Usuń")
    assert app.shown[-1] == "Usunąć kopertę Kawa?"

    manage.goal_sheet(app)
    _field(app.shown[-1], "Nazwa celu").value = "Rower"
    _field(app.shown[-1], "Kwota docelowa").value = "3000"
    _click(app.shown[-1], "Zapisz")
    goal = store.goals()[0]
    assert goal["name"] == "Rower" and float(goal["target_amount"]) == 3000
    forms.goal_actions(app, goal)
    manage.goal_sheet(app, goal)
    _click(app.shown[-1], "Usuń")
    assert app.shown[-1] == "Usunąć cel Rower?"


def test_recurring_forms(app):
    store = app.store
    store.set_balance("Karta", 4000)
    store.add_goal("Wakacje", 5000, "Karta", None)
    cases = [("Wydatek", "Netflix", "45", {"Koperta": "Rozrywka"}),
             ("Dochód", "Pensja", "6000", {"Kategoria dochodu": "Wynagrodzenie"}),
             ("Przelew", "Na oszczędności", "500", {"Na konto": "Gotówka"}),
             ("Na Skarbonkę", "Odkładanie", "200", {"Na cel": str(store.goals()[0]["id"])})]
    for r_type, name, amount, extra in cases:
        manage.recurring_sheet(app)
        sheet = app.shown[-1]
        kind = _field(sheet, "Rodzaj")
        kind.value = r_type
        kind.on_select(None)
        _field(sheet, "Nazwa").value = name
        _field(sheet, "Kwota").value = amount
        for label, value in extra.items():
            _field(sheet, label).value = value
        _click(sheet, "Zapisz")
    items = store.recurring()
    assert {i["name"] for i in items} == {"Netflix", "Pensja", "Na oszczędności", "Odkładanie"}
    assert _balances(store)["Karta"] == 4000 - 45 + 6000 - 500 - 200  # terminy na dziś zaksięgowane
    assert _balances(store)["Gotówka"] == 500
    manage.recurring_actions(app, items[0])
    manage.recurring_sheet(app, items[0])
    assert recurring_screen.build(app)


def test_backup_screen_and_restore_dialog(app):
    store = app.store
    store.add_transaction("Wydatek", 33, "Jedzenie", "Karta", "Biedronka")
    raw = store.backup_bytes()
    store.reset_all()
    backup_screen.restore_dialog(app, raw, "test.mfx")
    dialog = app.shown[-1]
    _click(dialog, "Przywróć")  # nowy telefon: hasło nie jest zapamiętane
    assert _field(dialog, "Hasło kopii").error and not store.is_solo
    _field(dialog, "Hasło kopii").value = "haslo-kopii"
    _click(dialog, "Przywróć")
    assert store.is_solo and any(t["shop"] == "Biedronka" for t in store.transactions())
    assert any("Przywrócono kopię" in m for m, _ in app.toasts)
    store.set_setting("local_od_refresh", "token")
    store.set_setting("local_od_account", "Jan")
    assert backup_screen.build(app)  # z połączonym OneDrive: kopia automatyczna


def test_welcome_solo_start(app):
    store = app.store
    store.reset_all()
    controls = welcome.build(app)
    btn = next(c for ctl in controls for c in _walk(ctl)
               if isinstance(c, ft.FilledButton) and c.content == "Zacznij — bez komputera")
    btn.on_click(None)
    assert store.is_solo and store.has_data


def test_loan_due_dates_in_past_are_booked_via_form(app):
    store = app.store
    store.set_balance("Karta", 3000)
    manage.account_sheet(app)
    sheet = app.shown[-1]
    kind = _field(sheet, "Rodzaj konta")
    kind.value = "loan"
    kind.on_select(None)
    assert _field(sheet, "Pieniądze z kredytu").visible
    _field(sheet, "Nazwa (np.").value = "Pożyczka"
    _field(sheet, "Ile zostało do spłaty").value = "1000"
    _field(sheet, "Liczba rat").value = "5"
    _field(sheet, "Pieniądze z kredytu").value = "Karta"
    # data pierwszej raty miesiąc temu — przez stan formularza (kalendarz)
    for c in _walk(sheet):
        if isinstance(c, ft.Text) and str(c.value or "").startswith("Najbliższa rata"):
            break
    store_first = (date.today() - timedelta(days=31)).isoformat()
    manage_state = None
    for cell in _button(sheet, "Dodaj konto").on_click.__closure__ or []:
        val = cell.cell_contents
        if isinstance(val, dict) and "first_due" in val:
            manage_state = val
    assert manage_state is not None
    manage_state["first_due"] = store_first
    _click(sheet, "Dodaj konto")
    assert _balances(store)["Karta"] == 3000 + 1000 - 2 * 200
    assert _balances(store)["Pożyczka"] == -600
