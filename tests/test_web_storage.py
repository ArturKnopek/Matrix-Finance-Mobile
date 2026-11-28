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


def test_compressed_and_legacy_formats():
    import base64

    prefs = FakePrefs()
    s = Store()
    s.reset_all()
    s.start_solo(fresh=True)
    s.add_transaction("Wydatek", 9.99, "Jedzenie", "Karta", "Żabka")
    web_storage._last_digest = None
    assert asyncio.run(web_storage.save(prefs))
    stored = prefs.data[web_storage.KEY]
    raw = web_storage.snapshot_bytes()
    assert stored.startswith(web_storage.ZIP_PREFIX) and len(stored) < len(base64.b64encode(raw))
    assert web_storage.decode(stored) == raw
    legacy = base64.b64encode(raw).decode("ascii")  # zapis z wersji 1.3
    assert web_storage.decode(legacy) == raw
    prefs.data[web_storage.KEY] = legacy
    s.reset_all()
    assert asyncio.run(web_storage.restore(prefs))
    assert any(t["shop"] == "Żabka" for t in Store().transactions())
