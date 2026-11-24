"""Konfiguracja ścieżek — MUSI zostać wywołana przed importem silnika (app/src)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]


def configure() -> Path:
    """Katalog danych aplikacji: na telefonie prywatny katalog aplikacji (FLET_APP_STORAGE_DATA)."""
    if str(APP_DIR) not in sys.path:
        sys.path.insert(0, str(APP_DIR))
    if not os.environ.get("MATRIX_FINANCE_HOME"):
        base = os.environ.get("FLET_APP_STORAGE_DATA") or str(Path.home() / ".matrix_finance_mobile")
        os.environ["MATRIX_FINANCE_HOME"] = str(Path(base) / "matrix_finance")
    home = Path(os.environ["MATRIX_FINANCE_HOME"])
    home.mkdir(parents=True, exist_ok=True)
    return home
