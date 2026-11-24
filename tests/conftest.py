"""Testy na izolowanym katalogu danych (nigdy nie dotykają prawdziwych danych)."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

_HOME = tempfile.mkdtemp(prefix="mf_mobile_tests_")
os.environ["HOME"] = _HOME
os.environ["USERPROFILE"] = _HOME
os.environ["MATRIX_FINANCE_HOME"] = str(Path(_HOME) / "dane")

APP = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))
