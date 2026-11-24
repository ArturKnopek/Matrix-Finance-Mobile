"""
Podgląd aplikacji w przeglądarce na komputerze (bez telefonu):

    pip install "flet[all]==1.1.3"
    python tools/web_preview.py            # http://127.0.0.1:8550

Dane podglądu trafiają do katalogu .preview_data (nie do danych telefonu ani komputera).
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
env = dict(os.environ, MF_WEB_PREVIEW=os.environ.get("MF_WEB_PREVIEW", "8550"),
           MATRIX_FINANCE_HOME=str(ROOT / ".preview_data"))
print(f"Podgląd: http://127.0.0.1:{env['MF_WEB_PREVIEW']}  (Ctrl+C kończy)")
raise SystemExit(subprocess.call([sys.executable, str(ROOT / "app" / "main.py")], env=env))
