"""Matrix Finance Mobile — punkt wejścia (Android / iOS / podgląd w przeglądarce)."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mf_mobile import config  # noqa: E402

config.configure()

import flet as ft  # noqa: E402

from mf_mobile.app import main  # noqa: E402

# (bez „if __name__ == '__main__'” — aplikacja zbudowana przez flet build uruchamia ten moduł bezpośrednio)
if os.environ.get("MF_WEB_PREVIEW"):  # podgląd na komputerze: MF_WEB_PREVIEW=8550 python app/main.py
    ft.run(main, view=ft.AppView.WEB_BROWSER, port=int(os.environ["MF_WEB_PREVIEW"]), no_cdn=True)
else:
    ft.run(main)
