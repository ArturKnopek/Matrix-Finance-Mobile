"""Przekazanie pliku użytkownikowi: „Udostępnij” (OneDrive, Pliki, poczta…), a gdy niedostępne — zapis pliku."""

from __future__ import annotations

from typing import Any

import flet as ft


async def deliver(app: Any, name: str, data: bytes, mime: str = "application/octet-stream",
                  title: str = "") -> bool:
    """Zwraca True, gdy plik przekazano (udostępniono albo zapisano); False — anulowano lub błąd."""
    status = "unavailable"
    try:
        result = await app.share.share_files([ft.ShareFile.from_bytes(data, mime_type=mime, name=name)],
                                             title=title or name, subject=name)
        status = getattr(getattr(result, "status", None), "value", "unavailable")
    except Exception:  # np. przeglądarka bez „Udostępnij” dla plików
        status = "unavailable"
    if status == "dismissed":
        app.toast("Anulowano.")
        return False
    if status == "success":
        return True
    try:  # zapasowo: okno zapisu / pobranie pliku (na iPhonie trafia do Pliki › Pobrane)
        path = await app.picker.save_file(dialog_title=title or name, file_name=name, src_bytes=data)
    except Exception as err:
        app.toast(f"Nie udało się zapisać pliku: {err}", error=True)
        return False
    return path is not None or bool(getattr(app.page, "web", False))
