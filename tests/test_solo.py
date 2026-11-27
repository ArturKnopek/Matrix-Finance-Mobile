"""Tryb „Bez komputera”: telefon jako główna baza — zarządzanie, księgowanie, kopia zapasowa."""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from mf_mobile import onedrive
from mf_mobile.store import BACKUP_NAME, Store
from src.finance import accounts, data_io, ledger, storage, sync

PASSWORD = "haslo-kopii"


@pytest.fixture()
def solo():
    s = Store()
    s.reset_all()
    s.start_solo(fresh=True)
    s.set_password(PASSWORD)
    return s


def _balances(store):
    return {a["name"]: round(a["balance"], 2) for a in store.accounts()}


def test_fresh_start_is_local_only(solo):
    assert solo.is_solo and solo.has_data and solo.can_manage and not solo.is_demo
    assert set(_balances(solo)) >= {"Karta", "Gotówka"}
    solo.set_balance("Karta", 3000)
    solo.add_transaction("Wydatek", 45.5, "Jedzenie", "Karta", "Lidl")
    assert _balances(solo)["Karta"] == 2954.5
    assert solo.pending() == [] and sync.pending_ops() == []  # nic nie czeka na komputer


def test_manage_accounts_envelopes_goals(solo):
    solo.add_account("mKonto", "checking", 1500, "mBank")
    solo.add_account("Konto oszcz.", "savings", 8000, "ING", 5.5)
    solo.add_account("ETF", "custom", 2000, custom_label="ETF-y", custom_group="Inwestycje", custom_flags="valuation")
    assert _balances(solo)["mKonto"] == 1500
    assert ledger.fetch_transactions() == []  # saldo początkowe bez historii
    with pytest.raises(ValueError):
        solo.add_account("mKonto", "checking", 1)
    assert solo.valuation("ETF", 2150) == pytest.approx(150)
    solo.update_account("mKonto", "mKonto Plus", "mBank", None)
    assert "mKonto Plus" in solo.account_names()

    solo.add_envelope("Kawa", 120, rollover=True)
    env = {e["name"]: e for e in solo.envelopes(only_active=False)}
    assert env["Kawa"]["budget"] == 120 and env["Kawa"]["rollover"]
    solo.update_envelope(env["Jedzenie"]["id"], "Jedzenie", 1500, False)
    assert {e["name"]: e for e in solo.envelopes()}["Jedzenie"]["budget"] == 1500
    solo.delete_envelope(env["Kawa"]["id"])
    assert "Kawa" not in solo.category_names()

    solo.add_goal("Wakacje", 5000, "Konto oszcz.", "2027-07-01")
    g = solo.goals()[0]
    solo.goal_move(g, 300, "Konto oszcz.")
    solo.update_goal(g["id"], "Wakacje 2027", 6000, "Konto oszcz.", None)
    assert solo.goals()[0]["name"] == "Wakacje 2027"
    assert solo.delete_goal(g["id"]) == 300
    solo.close_account("Konto oszcz.", "mKonto Plus")
    assert "Konto oszcz." not in solo.account_names() and _balances(solo)["mKonto Plus"] == 9500


def test_recurring_and_loans_are_booked_on_phone(solo):
    solo.set_balance("Karta", 5000)
    start = (date.today() - timedelta(days=65)).isoformat()
    booked = solo.save_recurring(None, "Czynsz", "Wydatek", 1200, "Karta", "Miesięcznie", start, category="Rachunki")
    assert booked == 3  # trzy terminy już minęły
    assert _balances(solo)["Karta"] == 5000 - 3 * 1200
    items = solo.recurring()
    assert items[0]["name"] == "Czynsz" and items[0]["active"] and items[0]["next_due"] > date.today()
    assert solo.toggle_recurring(items[0]["id"]) is False  # wstrzymana
    solo.delete_recurring(items[0]["id"])
    assert solo.recurring() == []

    first_due = (date.today() - timedelta(days=31)).isoformat()
    booked = solo.add_loan("Ekspres", 1500, 10, first_due, "Karta", 0.0, kind="installments", category="Raty")
    assert booked == 2
    assert _balances(solo)["Ekspres"] == -1200
    assert solo.process_due() == (0, [])  # nic więcej do zaksięgowania
    # kredyt spłacany od dawna: tylko stan
    solo.add_loan("Hipoteka", 250000, 240, (date.today() + timedelta(days=10)).isoformat(), "Karta", 7.5,
                  kind="loan", existing=True)
    assert _balances(solo)["Hipoteka"] == -250000


def test_existing_deposit_and_matured_settlement(solo):
    start = (date.today() - timedelta(days=200)).isoformat()
    solo.add_deposit("Lokata 6m", 10000, 6.0, 6, start, None, "PKO BP", return_to="Karta")
    assert _balances(solo)["Lokata 6m"] == 10000
    count, settled = solo.process_due()
    assert settled  # lokata po terminie rozliczona (odsetki + zwrot na Kartę)
    assert _balances(solo)["Karta"] > 10000


def test_backup_round_trip_and_pc_compatibility(solo, tmp_path):
    solo.add_account("Revolut", "ewallet", 640)
    solo.add_transaction("Wydatek", 99, "Zakupy", "Karta", "Allegro")
    assert solo.backup_needed
    raw = solo.backup_bytes()
    solo.mark_backup()
    assert not solo.backup_needed and solo.backup_age_days() == 0
    before = _balances(solo)

    # program na komputerze odczyta kopię telefonu (Ustawienia › Import danych, .mfx)
    path = tmp_path / BACKUP_NAME
    path.write_bytes(raw)
    data = data_io.read_export_file(str(path), PASSWORD)
    assert any(r["name"] == "Revolut" for r in data["tables"]["accounts"])

    # nowy telefon: przywrócenie
    solo.reset_all()
    assert "Revolut" not in _balances(solo)
    with pytest.raises(ValueError):
        solo.restore_backup(raw, "zle-haslo")
    counts = solo.restore_backup(raw, PASSWORD)
    assert counts["accounts"] >= 3 and solo.is_solo and _balances(solo) == before
    assert not solo.backup_needed

    # eksport .mfx z komputera wczytuje się na telefonie (komputer → telefon)
    data_io.export_json(str(tmp_path / "pc.mfx"), "haslo-pc")
    solo.reset_all()
    solo.restore_backup((tmp_path / "pc.mfx").read_bytes(), "haslo-pc")
    assert _balances(solo) == before and solo.password == "haslo-pc"


def test_backup_requires_password(solo):
    solo.set_password("")
    with pytest.raises(ValueError):
        solo.backup_bytes()


def test_switching_modes(solo):
    s = solo
    s.add_transaction("Wydatek", 10, "Jedzenie", "Karta", "Żabka")
    s.use_pc_mode()
    assert not s.is_solo and not s.can_manage
    s.add_transaction("Wydatek", 5, "Jedzenie", "Karta", "Żabka")
    assert len(s.pending()) == 1  # z komputerem: zmiana czeka na wysłanie
    s.start_solo(fresh=False)  # dane zostają, skrzynka wyczyszczona
    assert s.is_solo and s.pending() == [] and len(ledger.fetch_transactions()) == 2
    s.load_demo()
    assert s.is_demo and not s.is_solo and s.can_manage


def test_fresh_start_keeps_onedrive_connection(solo):
    solo.set_setting(onedrive.SET_REFRESH, "refresh-ok")
    solo.set_setting(onedrive.SET_ACCOUNT, "Jan")
    solo.start_solo(fresh=True)
    assert solo.setting(onedrive.SET_REFRESH) == "refresh-ok"


def test_onedrive_backup(solo):
    from test_onedrive import FakeMicrosoft, _connect

    fake = FakeMicrosoft()
    od = _connect(solo, fake)
    report = od.sync_now()  # bez komputera: zapis kopii zamiast synchronizacji
    assert report.backup == "saved" and f"MatrixFinance/{BACKUP_NAME}" in fake.files
    assert od.sync_now().backup == "unchanged"  # bez zmian — bez wysyłania
    solo.add_transaction("Wydatek", 12, "Jedzenie", "Karta", "Piekarnia")
    assert od.sync_now().backup == "saved"
    raw = od.download_backup()
    solo.reset_all()
    solo.restore_backup(raw, PASSWORD)
    assert any(t["shop"] == "Piekarnia" for t in ledger.fetch_transactions())
    assert not any(k.endswith(".mfops") for k in fake.files)  # żadnych plików dla komputera
    assert accounts.get_account("Karta") is not None and storage.get_active_user_db()
