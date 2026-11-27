"""Wersja przeglądarkowa: zapis bazy w pamięci przeglądarki i odtworzenie po ponownym otwarciu."""
from __future__ import annotations

import asyncio

from mf_mobile import web_storage
from mf_mobile.store import Store


class FakePrefs:
    def __init__(self):
        self.data = {}

    async def get(self, key):
        return self.data.get(key)

    async def set(self, key, value):
        self.data[key] = value
        return True


def test_save_and_restore_database():
    prefs = FakePrefs()
    s = Store()
    s.reset_all()
    s.load_demo()
    s.add_transaction("Wydatek", 12.34, "Jedzenie", "Karta", "Piekarnia")
    assert asyncio.run(web_storage.save(prefs)) is True
    assert asyncio.run(web_storage.save(prefs)) is False  # bez zmian — bez zapisu
    before = {a["name"]: a["balance"] for a in s.accounts()}

    s.reset_all()  # „zamknięcie karty”: wirtualny dysk przeglądarki znika
    assert not s.has_data
    assert asyncio.run(web_storage.restore(prefs)) is True
    s2 = Store()
    assert s2.has_data and {a["name"]: a["balance"] for a in s2.accounts()} == before
    assert any(t["shop"] == "Piekarnia" for t in s2.transactions())
