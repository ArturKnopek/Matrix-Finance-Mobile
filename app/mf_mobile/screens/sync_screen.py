"""Synchronizacja z komputerem przez plik w OneDrive (pobierz migawkę / wyślij zmiany)."""

from __future__ import annotations

from typing import Any, List

import flet as ft

from mf_mobile.store import plural
from mf_mobile.ui import banner, bold, card, field, primary_button, secondary_button, section, txt
from src.finance import sync


def build(app: Any) -> List[ft.Control]:
    p, store = app.p, app.store
    pending = store.pending()
    out: List[ft.Control] = []

    status: List[ft.Control] = []
    if store.is_demo:
        status.append(txt("Tryb danych przykładowych — po pobraniu danych z komputera zostaną zastąpione.", 13,
                          p.warning))
    elif store.snapshot_at:
        status.append(ft.Row([ft.Icon(ft.Icons.COMPUTER, color=p.accent, size=20),
                              txt(f"Dane z komputera: {sync.format_stamp(store.snapshot_at)}", 14, p.text)]))
    else:
        status.append(txt("Jeszcze nie pobrano danych z komputera.", 13, p.muted))
    status.append(ft.Row([ft.Icon(ft.Icons.CLOUD_UPLOAD_OUTLINED, color=p.warning if pending else p.muted, size=20),
                          txt(f"Do wysłania: {plural(len(pending), 'zmiana', 'zmiany', 'zmian')}" if pending
                              else "Brak zmian do wysłania", 14,
                              p.text)]))
    sent_at = store.setting("local_ops_sent_at")
    if pending and sent_at:
        status.append(txt(f"Ostatnio zapisano plik zmian: {sync.format_stamp(sent_at)} — zmiany znikną z listy, gdy "
                          "komputer je potwierdzi (po pobraniu nowych danych).", 12, p.muted))
    out.append(card(p, ft.Column(status, spacing=10), highlight=True))

    password = field(p, "Hasło synchronizacji", store.password, password=True, can_reveal_password=True,
                     helper="to samo co na komputerze (Ustawienia › Synchronizacja)")

    def save_password(e: Any = None) -> bool:
        if len(password.value or "") < 6:
            password.error = "Hasło ma co najmniej 6 znaków"
            password.update()
            return False
        store.set_password(password.value)
        return True

    async def download(e: Any) -> None:
        if not save_password():
            return
        files = await app.picker.pick_files(dialog_title="Wybierz MatrixFinance.mfsync (OneDrive › MatrixFinance)",
                                            with_data=True)
        if not files:
            return
        f = files[0]
        if not f.name.endswith(".mfsync"):
            app.toast("To nie jest plik synchronizacji (MatrixFinance.mfsync).", error=True)
            return
        data = f.bytes
        if data is None and f.path:
            with open(f.path, "rb") as fh:
                data = fh.read()
        if not data:
            app.toast("Nie udało się odczytać pliku.", error=True)
            return
        try:
            result = store.import_snapshot(data, password.value)
        except sync.SyncError as err:
            app.toast(str(err), error=True)
            return
        app.subpage = "sync"
        app.render()
        msg = f"Pobrano dane z {sync.format_stamp(result.created_at)}."
        if result.confirmed:
            msg += f" Potwierdzone przez komputer: {result.confirmed}."
        if result.replayed:
            msg += f" Nadal do wysłania: {result.replayed}."
        app.toast(msg)
        if result.rejected or result.failed:
            app.show(ft.AlertDialog(
                title=bold("Część zmian nie została przyjęta", 17),
                content=ft.Column([txt(x, 13, p.text) for x in (result.rejected + result.failed)[:10]], tight=True,
                                  scroll=ft.ScrollMode.AUTO),
                actions=[ft.TextButton(content="OK", on_click=lambda ev: app.close())], bgcolor=p.panel))

    def prepare_upload() -> Any:
        if not store.pending():
            app.toast("Brak zmian do wysłania.")
            return None
        if not save_password():
            return None
        return store.ops_file()

    async def upload(e: Any) -> None:
        """Udostępnij → OneDrive → folder MatrixFinance (zapis bezpośrednio w chmurze, nie w pamięci telefonu)."""
        prepared = prepare_upload()
        if not prepared:
            return
        name, data = prepared
        try:
            result = await app.share.share_files(
                [ft.ShareFile.from_bytes(data, mime_type="application/octet-stream", name=name)],
                title="Wyślij do OneDrive › MatrixFinance", subject=name)
        except Exception as err:
            app.toast(f"Nie udało się otworzyć „Udostępnij”: {err}", error=True)
            return
        status = getattr(getattr(result, "status", None), "value", "unavailable")
        if status == "dismissed":
            app.toast("Anulowano — zmiany czekają dalej.")
            return
        store.mark_sent()
        app.render()
        app.toast("Wysłano. Komputer dopisze zmiany przy najbliższej synchronizacji.")

    async def save_elsewhere(e: Any) -> None:
        """Zapasowo: zapis pliku w wybranym miejscu (np. inna chmura lub menedżer plików)."""
        prepared = prepare_upload()
        if not prepared:
            return
        name, data = prepared
        try:
            path = await app.picker.save_file(dialog_title="Zapisz plik zmian", file_name=name, src_bytes=data)
        except Exception as err:
            app.toast(f"Nie udało się zapisać pliku: {err}", error=True)
            return
        if path is None and not app.page.web:
            return
        store.mark_sent()
        app.render()
        app.toast("Zapisano plik. Pamiętaj, żeby trafił do folderu MatrixFinance w OneDrive.")

    out.append(password)
    out.append(primary_button(p, "Pobierz dane z OneDrive", download, ft.Icons.CLOUD_DOWNLOAD_OUTLINED))
    out.append(secondary_button(p, f"Wyślij zmiany do OneDrive ({len(pending)})", upload,
                                ft.Icons.CLOUD_UPLOAD_OUTLINED))
    out.append(ft.Row([ft.TextButton(content="Zapisz plik zmian w innym miejscu…", on_click=save_elsewhere,
                                     style=ft.ButtonStyle(color=p.muted))], alignment=ft.MainAxisAlignment.END))
    if pending:
        out.append(section(p, "Zmiany czekające na wysłanie"))
        out.append(card(p, ft.Column([txt("• " + sync.describe_op(op), 13, p.text) for op in pending[:30]],
                                     spacing=6)))

    out.append(section(p, "Jak to działa"))
    steps = [
        "Na komputerze: Ustawienia (9) › Synchronizacja z telefonem › ustaw folder w OneDrive i hasło.",
        "Na telefonie zainstaluj aplikację OneDrive i zaloguj się na to samo konto.",
        "„Pobierz dane z OneDrive” › w oknie wyboru plików otwórz menu (trzy kreski) lub „Przeglądaj” › OneDrive › "
        "MatrixFinance › MatrixFinance.mfsync.",
        "Dodawaj wydatki na telefonie. „Wyślij zmiany do OneDrive” › w oknie „Udostępnij” wybierz OneDrive › "
        "folder MatrixFinance › Prześlij.",
        "Komputer dopisze zmiany automatycznie (po zalogowaniu, co 2 minuty, Ctrl+Y). Każda zmiana trafia na "
        "komputer tylko raz — nawet gdy plik wyślesz kilka razy.",
    ]
    out.append(card(p, ft.Column([ft.Row([bold(f"{i}.", 14, p.accent), txt(s, 13, p.text, expand=True)],
                                          vertical_alignment=ft.CrossAxisAlignment.START)
                                  for i, s in enumerate(steps, 1)], spacing=10)))
    out.append(card(p, ft.Column([
        bold("Nie widzisz OneDrive przy pobieraniu?", 13, p.warning),
        txt("Otwórz aplikację OneDrive › MatrixFinance › przy pliku MatrixFinance.mfsync „Więcej” (trzy kropki) › „Pobierz” (zapisze się "
            "w Pobranych), a potem w Matrix Finance wybierz go z folderu Pobrane.", 12, p.text),
    ], spacing=4)))
    out.append(banner(p, ft.Icons.LOCK_OUTLINE, "Pliki są szyfrowane hasłem synchronizacji (AES). Bez hasła nikt "
                      "nie odczyta Twoich danych z OneDrive.", p.accent_dim))
    return out
