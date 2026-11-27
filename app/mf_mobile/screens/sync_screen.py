"""Synchronizacja z komputerem przez plik w OneDrive (pobierz migawkę / wyślij zmiany)."""

from __future__ import annotations

from typing import Any, List

import flet as ft

from mf_mobile.store import BACKUP_NAME, plural
from mf_mobile.ui import banner, bold, card, field, primary_button, secondary_button, section, txt
from src.finance import sync


def onedrive_section(app: Any, password_ok: Any) -> List[ft.Control]:
    """OneDrive bez wybierania plików: logowanie raz, zapamiętany folder, zawsze ten sam plik.

    Z komputerem: pobiera dane komputera i zapisuje plik zmian. Bez komputera: zapisuje kopię zapasową."""
    p, store, od = app.p, app.store, app.onedrive
    solo = store.is_solo
    out: List[ft.Control] = [section(p, "Kopia automatyczna w OneDrive" if solo
                                     else "OneDrive — bez wybierania plików (zalecane)")]
    if app.web and solo:
        out.append(card(p, txt("W wersji przeglądarkowej (iPhone) kopię zapisujesz ręcznie — przyciskiem niżej "
                               "(Udostępnij › Zachowaj w Plikach › OneDrive).", 13, p.text)))
        return out
    if app.web:
        out.append(card(p, txt("W wersji przeglądarkowej (iPhone) synchronizacja działa ręcznie: „Pobierz dane” "
                               "wybiera plik w aplikacji Pliki (OneDrive), a „Wyślij zmiany” — przez Udostępnij.",
                               13, p.text)))
        return out

    if od.connected:
        def sync_click(e: Any) -> None:
            if not password_ok():
                return
            app.toast("Zapisuję kopię w OneDrive…" if solo else "Synchronizuję z OneDrive…")
            app.background_sync(upload_only=False, quiet=False, force=solo)

        folder = field(p, "Folder w OneDrive (zapamiętany)", od.folder, dense=True)

        def change_folder(e: Any) -> None:
            od.set_folder(folder.value or "")
            app.render()
            app.toast(f"Zapamiętano lokalizację: {od.location()}")

        def disconnect(e: Any) -> None:
            app.confirm("Rozłączyć OneDrive?", "Telefon przestanie sam zapisywać i pobierać pliki. Twoje dane zostają.",
                        lambda: od.disconnect(), yes="Rozłącz")

        last = store.setting("local_od_last_sync")
        rows: List[ft.Control] = [
            ft.Row([ft.Icon(ft.Icons.CLOUD_DONE_OUTLINED, color=p.positive), txt(f"Połączono: {od.account}", 14,
                                                                                  p.text, expand=True)]),
            txt("Obecna lokalizacja:", 12, p.muted),
            bold(od.location(), 16, p.accent),
            txt(f"Plik kopii: {BACKUP_NAME} — zawsze ten sam, zastępowany (OneDrive przechowuje też poprzednie "
                "wersje)." if solo else
                f"Plik zmian telefonu: {od.ops_name()} — zawsze ten sam, zastępowany przy wysłaniu. "
                f"Dane z komputera: {sync.SNAPSHOT_FILE}.", 12, p.muted),
            txt((f"Ostatnia kopia: {sync.format_stamp(store.backup_at)}" if store.backup_at else
                 "Jeszcze nie zapisano kopii.") if solo else
                (f"Ostatnia synchronizacja: {sync.format_stamp(last)}" if last else "Jeszcze nie synchronizowano."),
                12, p.muted),
        ]
        if app.sync_status:
            rows.append(txt(app.sync_status, 12, p.warning if "błąd" in app.sync_status.lower() else p.text))
        rows.append(ft.Row([
            ft.Switch(value=od.auto, active_color=p.accent,
                      on_change=lambda e: (od.set_auto(e.control.value), app.render())),
            ft.Container(txt("Automatycznie: po każdej zmianie" if solo else
                             "Automatycznie: przy uruchomieniu i po każdej zmianie", 13, p.text), expand=True)],
            vertical_alignment=ft.CrossAxisAlignment.CENTER))
        out.append(card(p, ft.Column(rows, spacing=6), highlight=True))
        out.append(primary_button(p, "Zapisz kopię teraz" if solo else "Synchronizuj teraz", sync_click,
                                  ft.Icons.BACKUP_OUTLINED if solo else ft.Icons.SYNC))
        out.append(folder)
        out.append(ft.Row([ft.TextButton(content="Zapamiętaj folder", icon=ft.Icons.BOOKMARK_ADDED_OUTLINED,
                                         on_click=change_folder, style=ft.ButtonStyle(color=p.accent)),
                           ft.TextButton(content="Rozłącz OneDrive", on_click=disconnect,
                                         style=ft.ButtonStyle(color=p.muted))],
                          alignment=ft.MainAxisAlignment.SPACE_BETWEEN, wrap=True))
        return out

    client = field(p, "Identyfikator aplikacji (Client ID)", od.client_id, dense=True, expand=True)

    def save_client(e: Any) -> None:
        od.set_client_id(client.value or "")
        app.render()
        app.toast("Zapisano identyfikator aplikacji.")

    def connect(e: Any) -> None:
        if not password_ok():
            return
        try:
            login = od.start_login()
        except Exception as err:
            app.toast(str(err), error=True)
            return
        state = {"cancelled": False}

        async def open_page(ev: Any) -> None:
            try:
                await app.clipboard.set(login.user_code)
            except Exception:
                pass
            await app.urls.launch_url(login.verification_uri)

        def cancel(ev: Any) -> None:
            state["cancelled"] = True
            app.close()

        app.show(ft.AlertDialog(
            modal=True, bgcolor=p.panel, title=bold("Połącz z OneDrive", 18),
            content=ft.Column([
                txt("1. Dotknij „Kopiuj kod i otwórz stronę”.", 13, p.text),
                txt("2. Wklej kod i zaloguj się na konto Microsoft, na którym masz OneDrive.", 13, p.text),
                txt("3. Wróć do aplikacji — połączy się sama.", 13, p.text),
                ft.Container(bold(login.user_code, 30, p.accent, selectable=True), alignment=ft.Alignment.CENTER,
                             padding=ft.Padding.all(10)),
                txt(login.verification_uri, 12, p.muted, selectable=True),
            ], tight=True, spacing=8),
            actions=[ft.TextButton(content="Anuluj", on_click=cancel, style=ft.ButtonStyle(color=p.muted)),
                     ft.FilledButton(content="Kopiuj kod i otwórz stronę", on_click=open_page,
                                     style=ft.ButtonStyle(bgcolor=p.accent, color=p.on_accent))]))

        def wait() -> None:
            import time

            while not state["cancelled"]:
                time.sleep(login.interval)
                try:
                    if od.poll_login(login):
                        app.close()
                        app.render()
                        app.toast(f"Połączono z OneDrive ({od.account}). Lokalizacja: {od.location()}")
                        app.background_sync(upload_only=False, quiet=False, force=solo)
                        return
                except Exception as err:
                    app.close()
                    app.toast(str(err), error=True)
                    return

        app.page.run_thread(wait)

    steps = [
        "Wejdź na portal.azure.com (zaloguj się tym samym kontem Microsoft) › Microsoft Entra ID › "
        "Rejestracje aplikacji › Nowa rejestracja.",
        "Nazwa: Matrix Finance. Typy kont: „Konta w dowolnym katalogu organizacyjnym i osobiste konta Microsoft”. "
        "Zarejestruj.",
        "Uwierzytelnianie › „Zezwalaj na przepływy klientów publicznych”: Tak › Zapisz.",
        "Skopiuj „Identyfikator aplikacji (klienta)” i wklej poniżej (robisz to tylko raz).",
    ]
    out.append(card(p, ft.Column([
        txt(f"Połącz raz z kontem Microsoft — potem telefon sam zapisuje kopię w folderze OneDrive › {od.folder} "
            "po każdej zmianie, bez pytania o lokalizację." if solo else
            "Połącz raz z kontem Microsoft — potem telefon sam zapisuje i pobiera pliki w folderze "
            f"OneDrive › {od.folder}, bez pytania o lokalizację (plik zmian jest zawsze ten sam).", 13, p.text),
        *([] if od.client_id else [
            bold("Najpierw jednorazowo: identyfikator aplikacji", 13, p.warning),
            *[ft.Row([bold(f"{i}.", 12, p.accent), txt(s, 12, p.text, expand=True)],
                     vertical_alignment=ft.CrossAxisAlignment.START) for i, s in enumerate(steps, 1)],
        ]),
    ], spacing=8)))
    if not od.client_id:
        out.append(ft.Row([client, ft.TextButton(content="Zapisz", on_click=save_client,
                                                 style=ft.ButtonStyle(color=p.accent))]))
    out.append(primary_button(p, "Połącz z OneDrive (konto Microsoft)", connect, ft.Icons.CLOUD_OUTLINED)
               if od.client_id else secondary_button(p, "Połącz z OneDrive (najpierw Client ID)", save_client,
                                                     ft.Icons.CLOUD_OUTLINED))
    return out


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
    out += onedrive_section(app, save_password)
    out.append(section(p, "Ręcznie — wybór pliku / Udostępnij"))
    out.append(secondary_button(p, "Pobierz dane z OneDrive (wybierz plik)", download, ft.Icons.CLOUD_DOWNLOAD_OUTLINED))
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
