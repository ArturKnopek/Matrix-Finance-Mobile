"""
Tryb „Bez komputera”: kopia zapasowa (zaszyfrowany plik .mfx) i przywracanie.

Kopia ma ten sam format co eksport .mfx w programie na komputer, więc:
  * telefon → komputer: program na komputer › Ustawienia › Import danych › plik .mfx,
  * komputer → telefon: program na komputer › Eksport danych (.mfx) › tu „Przywróć z pliku”.
"""

from __future__ import annotations

from typing import Any, List

import flet as ft

from mf_mobile.store import BACKUP_NAME
from mf_mobile.ui import banner, bold, card, field, primary_button, secondary_button, section, txt
from src.finance import sync


def _read_picked(f: Any) -> bytes:
    data = f.bytes
    if data is None and getattr(f, "path", None):
        with open(f.path, "rb") as fh:
            data = fh.read()
    return data or b""


def restore_dialog(app: Any, raw: bytes, source: str) -> None:
    """Pyta o hasło i ZASTĘPUJE dane telefonu danymi z kopii."""
    p, store = app.p, app.store
    password = field(p, "Hasło kopii", store.password, password=True, can_reveal_password=True, autofocus=True)

    def do(e: Any) -> None:
        try:
            counts = store.restore_backup(raw, password.value or "")
        except ValueError as err:
            password.error = str(err)
            password.update()
            return
        app.close()
        app.subpage = None
        app.tab = 0
        due, settled = store.process_due()
        app.render()
        msg = (f"Przywrócono kopię: {counts.get('transactions', 0)} wpisów, {counts.get('accounts', 0)} kont, "
               f"{counts.get('categories', 0)} kopert.")
        if due:
            msg += f" Zaksięgowano zaległe płatności: {due}."
        app.toast(msg)

    app.show(ft.AlertDialog(
        modal=True, bgcolor=p.panel, title=bold("Przywrócić kopię?", 18),
        content=ft.Column([
            txt(f"Źródło: {source}", 13, p.muted),
            txt("Dane w telefonie zostaną ZASTĄPIONE danymi z kopii. Telefon przejdzie w tryb „Bez komputera”.", 13,
                p.text),
            password,
        ], tight=True, spacing=10),
        actions=[ft.TextButton(content="Anuluj", on_click=lambda e: app.close(), style=ft.ButtonStyle(color=p.muted)),
                 ft.FilledButton(content="Przywróć", on_click=do,
                                 style=ft.ButtonStyle(bgcolor=p.negative, color="#000000"))]))


async def pick_and_restore(app: Any) -> None:
    files = await app.picker.pick_files(dialog_title="Wybierz kopię Matrix Finance (.mfx)", with_data=True)
    if not files:
        return
    f = files[0]
    if not (f.name or "").lower().endswith((".mfx", ".json")):
        app.toast("Wybierz plik kopii .mfx (np. MatrixFinance-kopia.mfx).", error=True)
        return
    raw = _read_picked(f)
    if not raw:
        app.toast("Nie udało się odczytać pliku.", error=True)
        return
    restore_dialog(app, raw, f.name)


def build(app: Any) -> List[ft.Control]:
    p, store, od = app.p, app.store, app.onedrive
    out: List[ft.Control] = []

    age = store.backup_age_days()
    needed = store.backup_needed
    status: List[ft.Control] = [
        ft.Row([ft.Icon(ft.Icons.PHONE_IPHONE if app.web else ft.Icons.PHONE_ANDROID, color=p.accent, size=20),
                txt("Tryb „Bez komputera” — telefon jest główną bazą danych.", 14, p.text, expand=True)]),
        ft.Row([ft.Icon(ft.Icons.BACKUP_OUTLINED, color=p.warning if needed else p.positive, size=20),
                txt((f"Ostatnia kopia: {sync.format_stamp(store.backup_at)}" if store.backup_at
                     else "Nie zrobiono jeszcze kopii zapasowej.")
                    + (" · są nowe zmiany" if needed and store.backup_at else ""), 14, p.text, expand=True)]),
    ]
    if needed and (age is None or age >= 7):
        status.append(txt("Zrób kopię — jeśli telefon zginie albo dane przeglądarki zostaną wyczyszczone, kopia jest "
                          "jedynym sposobem odzyskania danych.", 12, p.warning))
    out.append(card(p, ft.Column(status, spacing=10), highlight=True))

    password = field(p, "Hasło kopii zapasowej (min. 6 znaków)", store.password, password=True,
                     can_reveal_password=True, helper="zapamiętaj je — bez hasła kopii nie da się odczytać")

    def password_ok(e: Any = None) -> bool:
        if len(password.value or "") < 6:
            password.error = "Hasło ma co najmniej 6 znaków"
            password.update()
            return False
        store.set_password(password.value)
        return True

    async def share_backup(e: Any) -> None:
        from mf_mobile.files import deliver

        if not password_ok():
            return
        if await deliver(app, BACKUP_NAME, store.backup_bytes(), title="Zapisz kopię Matrix Finance"):
            store.mark_backup()
            app.render()
            app.toast("Kopia gotowa. Trzymaj ją w OneDrive / iCloud (Pliki) lub innym bezpiecznym miejscu.")

    async def save_backup_file(e: Any) -> None:
        if not password_ok():
            return
        data = store.backup_bytes()
        try:
            path = await app.picker.save_file(dialog_title="Zapisz kopię", file_name=BACKUP_NAME, src_bytes=data)
        except Exception as err:
            app.toast(f"Nie udało się zapisać pliku: {err}", error=True)
            return
        if path is None and not app.page.web:
            return
        store.mark_backup()
        app.render()
        app.toast("Zapisano kopię zapasową.")

    async def restore_file(e: Any) -> None:
        await pick_and_restore(app)

    def restore_onedrive(e: Any) -> None:
        def work() -> None:
            try:
                raw = od.download_backup()
            except Exception as err:
                app.toast(str(err), error=True)
                return
            restore_dialog(app, raw, f"{od.location()} › {BACKUP_NAME}")

        app.toast("Pobieram kopię z OneDrive…")
        app.page.run_thread(work)

    out.append(password)
    if not app.web:
        from mf_mobile.screens.sync_screen import onedrive_section

        out += onedrive_section(app, password_ok)
        if od.connected:
            out.append(secondary_button(p, "Przywróć kopię z OneDrive", restore_onedrive,
                                        ft.Icons.CLOUD_DOWNLOAD_OUTLINED))

    out.append(section(p, "Kopia w pliku"))
    out.append(primary_button(p, "Zapisz kopię (Udostępnij › Pliki / OneDrive)", share_backup,
                              ft.Icons.IOS_SHARE if app.web else ft.Icons.SHARE)
               if app.web or not od.connected else
               secondary_button(p, "Zapisz kopię (Udostępnij)", share_backup, ft.Icons.SHARE))
    out.append(ft.Row([ft.TextButton(content="Zapisz kopię w wybranym miejscu…", on_click=save_backup_file,
                                     style=ft.ButtonStyle(color=p.muted))], alignment=ft.MainAxisAlignment.END))
    out.append(secondary_button(p, "Przywróć z pliku (.mfx)", restore_file, ft.Icons.RESTORE))

    out.append(section(p, "Jak to działa"))
    steps = [
        "Wszystko robisz na telefonie: konta, koperty z budżetami, cele, stałe płatności, kredyty i raty. "
        "Zlecenia, raty i lokaty telefon księguje sam (przy uruchomieniu).",
        ("„Zapisz kopię” › Zachowaj w Plikach › OneDrive (albo iCloud). Rób to co jakiś czas — aplikacja przypomni."
         if app.web else
         "Połącz OneDrive — kopia zapisze się sama po każdej zmianie. Bez OneDrive: „Zapisz kopię” › Udostępnij."),
        "Nowy telefon / po wyczyszczeniu danych: „Przywróć z pliku” › wybierz MatrixFinance-kopia.mfx › hasło.",
        "Chcesz kiedyś użyć programu na komputerze? Matrix Finance (PC) › Ustawienia › Import danych › ten plik .mfx "
        "i to samo hasło. W drugą stronę: na komputerze Eksport danych (.mfx), tu „Przywróć z pliku”.",
    ]
    out.append(card(p, ft.Column([ft.Row([bold(f"{i}.", 14, p.accent), txt(s, 13, p.text, expand=True)],
                                          vertical_alignment=ft.CrossAxisAlignment.START)
                                  for i, s in enumerate(steps, 1)], spacing=10)))
    out.append(banner(p, ft.Icons.LOCK_OUTLINE, "Kopia jest szyfrowana Twoim hasłem (AES). Bez hasła nikt jej nie "
                      "odczyta — także z OneDrive.", p.accent_dim))
    return out
