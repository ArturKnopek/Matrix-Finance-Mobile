"""Każdy ekran i formularz da się zbudować (dane puste i przykładowe) — bez przeglądarki i telefonu."""
from __future__ import annotations

import pytest

from mf_mobile import forms
from mf_mobile.screens import accounts, dashboard, envelopes, goals, settings, sync_screen, transactions, welcome
from mf_mobile.store import Store
from mf_mobile.theme import PALETTES, palette

SCREENS = [dashboard, transactions, envelopes, accounts, goals, sync_screen, settings, welcome]


class _Page:
    web = False

    def update(self) -> None:
        pass


class StubApp:
    def __init__(self, store: Store, theme: str = "matrix") -> None:
        self.store, self.p = store, palette(theme)
        self.view_state: dict = {}
        self.page, self.picker = _Page(), None
        self.shown, self.toasts = [], []

    def render(self): pass
    def go_tab(self, index): pass
    def open_subpage(self, name): pass
    def apply_theme(self, name): pass
    def close(self): pass
    def show(self, dialog): self.shown.append(dialog)
    def toast(self, message, error=False): self.toasts.append((message, error))
    def confirm(self, title, message, on_yes, yes="Tak", danger=True): self.shown.append(title)

    def run_action(self, action, success=None):
        action()
        return True


@pytest.fixture()
def empty_app():
    s = Store()
    s.reset_all()
    return StubApp(s)


@pytest.fixture()
def demo_app():
    s = Store()
    s.reset_all()
    s.load_demo()
    return StubApp(s)


@pytest.mark.parametrize("screen", SCREENS, ids=lambda m: m.__name__.split(".")[-1])
def test_screens_build_with_empty_and_demo_data(screen, empty_app, demo_app):
    assert isinstance(screen.build(empty_app), list)
    assert screen.build(demo_app)


@pytest.mark.parametrize("theme", list(PALETTES))
def test_all_themes(theme, demo_app):
    demo_app.p = palette(theme)
    for screen in SCREENS:
        screen.build(demo_app)


def test_all_forms_open(demo_app):
    app, store = demo_app, demo_app.store
    forms.transaction_sheet(app)
    forms.transaction_sheet(app, preset_category="Jedzenie", preset_type="Dochód")
    tx = next(t for t in store.transactions() if t["type"] == "Wydatek")
    forms.transaction_sheet(app, tx)
    other = next(t for t in store.transactions() if t["type"] == "Transfer")
    forms.transaction_details(app, other)
    forms.transfer_dialog(app)
    acc = store.accounts()[0]
    forms.account_actions(app, acc)
    forms.balance_dialog(app, acc)
    env = store.envelopes()[0]
    forms.envelope_actions(app, env)
    for mode in ("set", "add", "sub", "move"):
        forms.envelope_amount(app, env, mode)
    goal = store.goals()[0]
    forms.goal_actions(app, goal)
    for mode in ("in", "out", "set"):
        forms.goal_amount(app, goal, mode)
    assert len(app.shown) == 16  # 3 transakcje + szczegóły + przelew + konto (2) + koperta (5) + cel (4)
    forms.delete_transaction(app, tx)
    assert app.shown[-1] == "Usunąć wpis?"


def test_transaction_list_filters(demo_app):
    store = demo_app.store
    all_rows = store.transactions()
    assert store.transactions(kind="income") and all(t["type"] == "Dochód" for t in store.transactions(kind="income"))
    assert len(store.transactions(search="biedronka")) <= len(all_rows)
    demo_app.view_state["transactions"] = {"search": "zzz-brak", "kind": "all"}
    assert transactions.build(demo_app)  # pusty wynik -> komunikat „Nic nie znaleziono”


def test_loan_account_on_phone(demo_app):
    app, store = demo_app, demo_app.store
    loan = next(a for a in store.accounts() if a["kind"].liability)
    assert loan["balance"] < 0 and loan["loan"]["payment"] == 150
    forms.account_actions(app, loan)
    forms.balance_dialog(app, loan)  # dla kredytu: „ile zostało do spłaty”
    assert len(app.shown) == 2
    assert any(u.get("loan") == loan["name"] for u in store.upcoming(days=40))
    store.set_balance(loan["name"], -900)
    assert next(a for a in store.accounts() if a["name"] == loan["name"])["balance"] == -900
