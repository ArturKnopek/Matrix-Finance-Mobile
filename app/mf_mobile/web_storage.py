"""
Trwałość danych w wersji przeglądarkowej (iPhone: Safari → „Do ekranu początkowego”).

Python działa w przeglądarce (Pyodide) z wirtualnym dyskiem w pamięci — po zamknięciu karty znika.
Dlatego cała baza telefonu (SQLite) jest zapisywana w pamięci przeglądarki (SharedPreferences =
localStorage) po każdej zmianie i odtwarzana przy starcie. Zapis jest kompresowany (zlib, ok. 3× mniej —
localStorage w Safari ma ok. 5 MB; 3000 wpisów ≈ 0,2 MB po kompresji). Starszy zapis (bez kompresji)
wczytuje się bez zmian.
"""

from __future__ import annotations

import base64
import hashlib
import sqlite3
import zlib
from pathlib import Path
from typing import Any, Optional

import flet as ft

KEY = "matrix_finance_db_v1"
ZIP_PREFIX = "z1:"  # zapis skompresowany
_last_digest: Optional[str] = None


def _db_path() -> Path:
    from mf_mobile.store import PHONE_USER
    from src.finance import storage

    return storage.user_db_path(PHONE_USER)


async def restore(prefs: Any) -> bool:
    """Przed utworzeniem Store: odtwarza bazę z pamięci przeglądarki. Zwraca True, gdy były dane."""
    global _last_digest
    try:
        data = await prefs.get(KEY)
    except Exception:
        return False
    if not data:
        return False
    raw = decode(data)
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    _last_digest = hashlib.sha256(raw).hexdigest()
    return True


def snapshot_bytes() -> bytes:
    path = _db_path()
    conn = sqlite3.connect(str(path))
    try:
        return conn.serialize()  # spójny obraz bazy
    except Exception:
        return path.read_bytes()  # tryb dziennika DELETE: plik jest spójny po zatwierdzeniu
    finally:
        conn.close()


async def save(prefs: Any) -> bool:
    """Zapisuje bazę w pamięci przeglądarki (tylko gdy się zmieniła). Zwraca True, gdy zapisano."""
    global _last_digest
    raw = snapshot_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest == _last_digest:
        return False
    await prefs.set(KEY, encode(raw))
    _last_digest = digest
    return True


def encode(raw: bytes) -> str:
    return ZIP_PREFIX + base64.b64encode(zlib.compress(raw, 6)).decode("ascii")


def decode(data: str) -> bytes:
    if data.startswith(ZIP_PREFIX):
        return zlib.decompress(base64.b64decode(data[len(ZIP_PREFIX):]))
    return base64.b64decode(data)  # zapis sprzed wersji 1.4


def new_prefs() -> Any:
    return ft.SharedPreferences()
