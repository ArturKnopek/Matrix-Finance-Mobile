"""
Aktualizuje kopię silnika (app/src) z projektu Matrix-Finance-TUI (wersja na komputer).

Silnik budżetu jest wspólny dla komputera i telefonu — dzięki temu obie aplikacje
liczą salda, koperty i synchronizację identycznie. W tym repozytorium NIE edytuj
plików w app/src — zmień je w Matrix-Finance-TUI i uruchom:

    python tools/update_engine.py ../Matrix-Finance-TUI
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "app" / "src"
FILES = [
    "src/__init__.py",
    "src/version.py",
    "src/finance/__init__.py",
    "src/finance/accounts.py",
    "src/finance/analytics.py",
    "src/finance/autosave.py",
    "src/finance/data_io.py",
    "src/finance/envelopes.py",
    "src/finance/goals.py",
    "src/finance/ledger.py",
    "src/finance/loans.py",
    "src/finance/recurring.py",
    "src/finance/storage.py",
    "src/finance/sync.py",
    "src/utils/__init__.py",
    "src/utils/crypto_utils.py",
    "src/utils/fernet_compat.py",
    "src/utils/parsing.py",
    "src/utils/paths.py",
]


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    source = Path(sys.argv[1]).resolve()
    if not (source / "src" / "finance" / "sync.py").exists():
        print(f"To nie jest katalog Matrix-Finance-TUI: {source}")
        return 1
    if TARGET.exists():
        shutil.rmtree(TARGET)
    for rel in FILES:
        dst = TARGET / Path(rel).relative_to("src")
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / rel, dst)
    try:
        commit = subprocess.run(["git", "-C", str(source), "rev-parse", "--short", "HEAD"], capture_output=True,
                                text=True, check=True).stdout.strip()
    except Exception:
        commit = "?"
    version = (source / "src" / "version.py").read_text(encoding="utf-8").split('APP_VERSION = "')[1].split('"')[0]
    (TARGET / "ENGINE_VERSION").write_text(f"Matrix-Finance-TUI {version} ({commit})\n", encoding="utf-8")
    (TARGET / "README.md").write_text(
        "# Silnik Matrix Finance (kopia)\n\n"
        "Kopia silnika z projektu **Matrix-Finance-TUI** (wersja na komputer) — wspólne obliczenia sald, kopert,\n"
        "celów i synchronizacji. **Nie edytuj tych plików tutaj**: zmień je w Matrix-Finance-TUI i uruchom\n"
        "`python tools/update_engine.py ../Matrix-Finance-TUI`.\n\n"
        f"Wersja: Matrix-Finance-TUI {version} ({commit})\n", encoding="utf-8")
    print(f"Skopiowano silnik: Matrix-Finance-TUI {version} ({commit}) -> {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
