"""Warstwa danych telefonu + pełna wymiana z „komputerem” przez plik."""
from __future__ import annotations

import uuid

import pytest

from mf_mobile.store import Store, money, parse_money, plural
from src.finance import accounts, goals, ledger, storage, sync

PASSWORD = "haslo-sync"


@pytest.fixture()
def store():
    s = Store()
    s.reset_all()
    return s


def _pc_snapshot(tmp_path):
    """Tworzy bazę „komputera”, zapisuje migawkę do folderu i wraca do bazy telefonu."""
    pc = uuid.uuid4().hex
    storage.init_user_db(storage.set_active_user_db(pc), 2000, 100)
    with storage.open_user_db(write=True) as conn:
        conn.execute("UPDATE categories SET limit_amount = 600 WHERE name = 'Jedzenie'")
    goals.add_piggy_bank("Rower", 2500, "Karta")
    sync.set_sync_setting(sync.SET_PASSWORD, PASSWORD)
    folder = tmp_path / "OneDrive"
    sync.sync_folder_now(folder)
    return pc, folder


def test_demo_data_and_local_changes(store):
    store.load_demo()
    assert store.is_demo and store.has_data
    s = store.summary()
    assert s["income"] == 8200 and s["expense"] > 0
    env = store.envelopes()
    assert env and all("pct" in e for e in env)
    before = {a["name"]: a["balance"] for a in store.accounts()}["Karta"]
    store.add_transaction("Wydatek", 12.5, "Jedzenie", "Karta", "Żabka")
    after = {a["name"]: a["balance"] for a in store.accounts()}["Karta"]
    assert after == pytest.approx(before - 12.5)
    assert store.pending() == []  # tryb demo: nic nie idzie do komputera


def test_phone_pc_exchange(store, tmp_path):
    pc, folder = _pc_snapshot(tmp_path)
    storage.set_active_user_db("telefon")
    phone = Store()
    imp = phone.import_snapshot((folder / sync.SNAPSHOT_FILE).read_bytes(), PASSWORD)
    assert phone.has_data and imp.confirmed == 0
    assert {a["name"]: a["balance"] for a in phone.accounts()} == {"Karta": 2000.0, "Gotówka": 100.0}
    uid = phone.add_transaction("Wydatek", 40, "Jedzenie", "Karta", "Lidl")
    phone.transfer("Karta", "Gotówka", 100)
    goal = phone.goals()[0]
    phone.goal_move(goal, 300, "Karta")
    phone.set_balance("Gotówka", 150)
    phone.envelope_adjust("Jedzenie", 50)
    assert len(phone.pending()) == 5
    assert any(t["pending"] for t in phone.transactions())
    name, data = phone.ops_file()
    assert name.endswith(".mfops")
    (folder / name).write_bytes(data)
    phone.mark_sent()

    storage.set_active_user_db(pc)  # komputer
    result = sync.sync_folder_now(folder)
    assert len(result.applied) == 5 and not result.rejected
    pc_balances = {a["name"]: round(a["balance"], 2) for a in accounts.get_accounts_overview()}
    assert pc_balances == {"Karta": 1560.0, "Gotówka": 150.0}

    phone = Store()  # telefon wczytuje nową migawkę
    imp = phone.import_snapshot((folder / sync.SNAPSHOT_FILE).read_bytes())
    assert imp.confirmed == 5 and phone.pending() == []
    assert {a["name"]: round(a["balance"], 2) for a in phone.accounts()} == pc_balances
    assert phone.transaction(uid)["shop"] == "Lidl"
    assert next(e for e in phone.envelopes() if e["name"] == "Jedzenie")["adjustment"] == 50


def test_demo_then_real_data_clears_demo(store, tmp_path):
    pc, folder = _pc_snapshot(tmp_path)
    storage.set_active_user_db("telefon")
    phone = Store()
    phone.load_demo()
    phone.add_transaction("Wydatek", 99, "Jedzenie", "Karta", "demo")
    with pytest.raises(sync.SyncError):
        phone.import_snapshot((folder / sync.SNAPSHOT_FILE).read_bytes(), "zle")
    assert phone.is_demo  # złe hasło: dane przykładowe zostają
    phone.import_snapshot((folder / sync.SNAPSHOT_FILE).read_bytes(), PASSWORD)
    assert not phone.is_demo and phone.pending() == []
    assert {a["name"] for a in phone.accounts()} == {"Karta", "Gotówka"}


def test_helpers():
    assert money(1234.5) == "1 234,50 zł"
    assert money(-5, signed=True) == "-5,00 zł"
    assert parse_money("12,50 zł") == 12.5
    assert parse_money("10+5") == 15
    assert parse_money("abc") is None
    assert [plural(n, "wpis", "wpisy", "wpisów") for n in (1, 2, 5, 12, 22, 25)] == \
        ["1 wpis", "2 wpisy", "5 wpisów", "12 wpisów", "22 wpisy", "25 wpisów"]
