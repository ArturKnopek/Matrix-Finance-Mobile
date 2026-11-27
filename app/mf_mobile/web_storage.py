"""
Trwałość danych w wersji przeglądarkowej (iPhone: Safari → „Do ekranu początkowego”).

Python działa w przeglądarce (Pyodide) z wirtualnym dyskiem w pamięci — po zamknięciu karty znika.
Dlatego cała baza telefonu (SQLite) jest zapisywana w pamięci przeglądarki (SharedPreferences =
localStorage) po każdej zmianie i odtwarzana przy starcie. Baza jest mała (zwykle < 1 MB).
"""

from __future__ import annotations

import base64
import hashlib
import sqlite3
from pathlib import Path
from typing import Any, Optional

import flet as ft

KEY = "matrix_finance_db_v1"
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
    raw = base64.b64decode(data)
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
    await prefs.set(KEY, base64.b64encode(raw).decode("ascii"))
    _last_digest = digest
    return True


def new_prefs() -> Any:
    return ft.SharedPreferences()
