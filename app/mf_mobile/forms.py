"""Formularze (okna): transakcja, przelew, korekty, operacje na kopertach i celach."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Callable, Dict, List, Optional

import flet as ft

from mf_mobile.store import TYPE_EXPENSE, TYPE_INCOME, money, parse_money, today_iso, yesterday_iso
from mf_mobile.ui import bold, dropdown, field, primary_button, secondary_button, txt


def _sheet(app: Any, title: str, controls: List[ft.Control]) -> ft.BottomSheet:
    p = app.p
    return ft.BottomSheet(
        content=ft.Container(
            content=ft.Column([bold(title, 20, p.text), *controls], spacing=14, tight=True,
                              scroll=ft.ScrollMode.AUTO, horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
            padding=ft.Padding.only(left=18, right=18, top=8, bottom=24)),
        bgcolor=p.panel, show_drag_handle=True, scrollable=True, use_safe_area=True)


def _error(app: Any, control: ft.TextField, message: str) -> None:
    control.error = message
    control.update()


def _date_label(iso: str) -> str:
    if iso == today_iso():
        return "Dziś"
    if iso == yesterday_iso():
        return "Wczoraj"
    try:
        return datetime.strptime(iso, "%Y-%m-%d").strftime("%d.%m.%Y")
    except ValueError:
        return iso


# =============================================================================
# Transakcja (wydatek / dochód)
# =============================================================================

def transaction_sheet(app: Any, tx: Optional[Dict[str, Any]] = None, preset_category: Optional[str] = None,
                      preset_type: str = TYPE_EXPENSE) -> None:
    p, store = app.p, app.store
    editing = tx is not None
    state = {"type": (tx or {}).get("type") or preset_type, "date": (tx or {}).get("date") or today_iso()}

    kind = ft.SegmentedButton(
        segments=[ft.Segment(value=TYPE_EXPENSE, label=txt("Wydatek"), icon=ft.Icon(ft.Icons.REMOVE)),
                  ft.Segment(value=TYPE_INCOME, label=txt("Dochód"), icon=ft.Icon(ft.Icons.ADD))],
        selected=[state["type"]], show_selected_icon=False)
    amount = field(p, "Kwota", f"{float(tx['amount']):.2f}".replace(".", ",") if editing else "",
                   keyboard_type=ft.KeyboardType.NUMBER, suffix=txt("zł", 16, p.muted), text_size=24,
                   autofocus=not editing)

    envelopes = {e["name"]: e for e in store.envelopes(only_active=False)}

    def category_options() -> List[tuple]:
        names = store.category_names()
        current = (tx or {}).get("category")
        if current and current not in names:
            names.append(current)
        out = []
        for n in names:
            e = envelopes.get(n)
            label = f"{n} · zostało {money(e['remaining'])}" if e and e["available"] > 0 else n
            out.append((label, n))
        return out

    category = dropdown(p, "Koperta", category_options(), (tx or {}).get("category") or preset_category,
                        enable_filter=True)
    accounts = store.account_names(liquid_only=True)
    if editing and tx.get("account_type") and tx["account_type"] not in accounts:
        accounts.append(tx["account_type"])
    balances = {a["name"]: a["balance"] for a in store.accounts()}
    account = dropdown(p, "Konto", [(f"{a} · {money(balances.get(a, 0))}", a) for a in accounts],
                       (tx or {}).get("account_type") or (accounts[0] if accounts else None))
    shop = field(p, "Sklep / od kogo", (tx or {}).get("shop") or "", capitalization=ft.TextCapitalization.SENTENCES)
    desc = field(p, "Opis (opcjonalnie)", (tx or {}).get("description") or "")
    account_values = set(accounts)

    def apply_hint(hint: Optional[Dict[str, Any]], force: bool = False) -> None:
        """Koperta i konto jak ostatnio dla tego sklepu (nie nadpisuje wybranej koperty, chyba że force)."""
        if not hint:
            return
        if hint.get("category") and (force or not category.value):
            category.value = hint["category"]
            category.update()
        if hint.get("account") in account_values and (force or not account.value):
            account.value = hint["account"]
            account.update()

    def on_shop_blur(e: Any) -> None:
        if state["type"] == TYPE_EXPENSE and not editing:
            apply_hint(store.shop_hint(shop.value or ""))

    shop.on_blur = on_shop_blur
    recent: List[ft.Control] = []
    if not editing and state["type"] == TYPE_EXPENSE:
        def pick(item: Dict[str, Any]) -> Callable:
            def handler(e: Any) -> None:
                shop.value = item["shop"]
                shop.update()
                apply_hint(item, force=True)
            return handler

        chips = [ft.Chip(label=txt(r["shop"], 13), on_click=pick(r), bgcolor=p.panel_hi)
                 for r in store.recent_shops(8)]
        if chips:
            recent = [ft.Column([txt("Ostatnie — dotknij, aby wpisać sklep i kopertę:", 12, p.muted),
                                 ft.Row(chips, wrap=True, spacing=6, run_spacing=6)], spacing=6)]
    date_info = txt("", 14, p.text)
    date_btn = ft.OutlinedButton(content="Kalendarz", icon=ft.Icons.CALENDAR_MONTH_OUTLINED,
                                 style=ft.ButtonStyle(color=p.text))

    def date_text(iso: str) -> str:
        label = _date_label(iso)
        full = datetime.strptime(iso, "%Y-%m-%d").strftime("%d.%m.%Y")
        return f"Data: {full}" + (f" ({label.lower()})" if label in ("Dziś", "Wczoraj") else "")

    date_info.value = date_text(state["date"])

    def set_date(iso: str) -> None:
        state["date"] = iso
        date_info.value = date_text(iso)
        date_info.update()

    def on_kind(e: Any) -> None:
        state["type"] = e.control.selected[0] if e.control.selected else TYPE_EXPENSE

    kind.on_change = on_kind

    def pick_date(e: Any) -> None:
        def changed(ev: Any) -> None:
            value = ev.control.value
            if value:
                set_date(value.date().isoformat() if isinstance(value, datetime) else str(value)[:10])

        app.show(ft.DatePicker(value=datetime.strptime(state["date"], "%Y-%m-%d"), first_date=datetime(2015, 1, 1),
                               last_date=datetime(2100, 12, 31), on_change=changed, help_text="Data transakcji",
                               cancel_text="Anuluj", confirm_text="OK"))

    date_btn.on_click = pick_date
    quick_dates = ft.Column([date_info, ft.Row([
        ft.TextButton(content="Dziś", on_click=lambda e: set_date(today_iso()), style=ft.ButtonStyle(color=p.accent)),
        ft.TextButton(content="Wczoraj", on_click=lambda e: set_date(yesterday_iso()),
                      style=ft.ButtonStyle(color=p.accent)),
        date_btn], spacing=4, wrap=True)], spacing=2)

    def save(e: Any) -> None:
        value = parse_money(amount.value or "")
        if value is None or value <= 0:
            return _error(app, amount, "Podaj kwotę większą od zera (np. 12,50)")
        if state["type"] == TYPE_EXPENSE and not category.value:
            category.error_text = "Wybierz kopertę"
            category.update()
            return
        if not account.value:
            account.error_text = "Wybierz konto"
            account.update()
            return

        def do() -> None:
            if editing:
                store.update_transaction(tx["tx_uid"], state["type"], value, category.value, account.value,
                                         shop.value or "", desc.value or "", state["date"])
            else:
                store.add_transaction(state["type"], value, category.value, account.value, shop.value or "",
                                      desc.value or "", state["date"])

        app.close()
        verb = "Zapisano zmiany" if editing else ("Dodano wydatek" if state["type"] == TYPE_EXPENSE else "Dodano dochód")
        app.run_action(do, f"{verb}: {money(value)}")

    buttons: List[ft.Control] = [primary_button(p, "Zapisz", save, ft.Icons.CHECK)]
    if editing:
        buttons.append(secondary_button(p, "Usuń", lambda e: delete_transaction(app, tx), ft.Icons.DELETE_OUTLINE,
                                        color=p.negative))
    app.show(_sheet(app, "Edycja transakcji" if editing else "Nowa transakcja",
                    [kind, amount, *recent, category, account, shop, desc, quick_dates,
                     ft.Row(buttons, spacing=10)]))


def delete_transaction(app: Any, tx: Dict[str, Any]) -> None:
    app.close()
    label = tx.get("shop") or tx.get("category") or tx.get("kind_label") or "wpis"
    extra = "\n\nTo przelew — zostaną usunięte obie jego części." if tx.get("linked_group_id") else ""
    app.confirm("Usunąć wpis?", f"{label}: {money(float(tx['amount']))} ({tx['date']}){extra}",
                lambda: app.store.delete_transaction(tx["tx_uid"]), yes="Usuń")


def transaction_details(app: Any, tx: Dict[str, Any]) -> None:
    """Wpisy inne niż wydatek/dochód (przelewy, cele, korekty) — podgląd i usuwanie."""
    p = app.p
    rows = [txt(f"{tx.get('kind_label')} · {tx['date']}", 14, p.muted),
            bold(money(float(tx.get("signed_amount", tx["amount"])), signed=True), 26,
                 p.positive if tx.get("signed_amount", 0) > 0 else p.negative),
            txt(f"Konto: {tx.get('account_type')}", 14, p.text)]
    if tx.get("shop"):
        rows.append(txt(tx["shop"], 14, p.text))
    if tx.get("description"):
        rows.append(txt(tx["description"], 13, p.muted))
    rows.append(txt("Przelewów i operacji na celach nie edytuje się — usuń wpis i dodaj ponownie.", 12, p.muted))
    rows.append(secondary_button(p, "Usuń", lambda e: delete_transaction(app, tx), ft.Icons.DELETE_OUTLINE,
                                 color=p.negative))
    app.show(_sheet(app, "Szczegóły wpisu", rows))


# =============================================================================
# Przelew między kontami
# =============================================================================

def transfer_dialog(app: Any, source: Optional[str] = None, target: Optional[str] = None) -> None:
    p, store = app.p, app.store
    balances = {a["name"]: a["balance"] for a in store.accounts()}
    names = store.account_names()
    options = [(f"{a} · {money(balances.get(a, 0))}", a) for a in names]
    if len(names) < 2:
        app.toast("Potrzebne są co najmniej dwa konta" + (" (Konta › Nowe konto)." if store.can_manage else
                                                          " (dodasz je na komputerze)."), error=True)
        return
    src = dropdown(p, "Z konta", options, source or names[0])
    dst = dropdown(p, "Na konto", options, target or next(n for n in names if n != (source or names[0])))
    amount = field(p, "Kwota", keyboard_type=ft.KeyboardType.NUMBER, suffix=txt("zł", 16, p.muted), text_size=22,
                   autofocus=True)
    note = field(p, "Tytuł (opcjonalnie)")

    def save(e: Any) -> None:
        value = parse_money(amount.value or "")
        if value is None or value <= 0:
            return _error(app, amount, "Podaj kwotę większą od zera")
        if src.value == dst.value:
            dst.error_text = "Wybierz inne konto"
            dst.update()
            return
        app.close()
        app.run_action(lambda: store.transfer(src.value, dst.value, value, note=note.value or ""),
                       f"Przelew {money(value)}: {src.value} › {dst.value}")

    app.show(_sheet(app, "Przelew między kontami", [
        src, dst, amount, note,
        txt("Przelew nie jest wydatkiem ani dochodem — nie zmienia budżetu.", 12, p.muted),
        primary_button(p, "Przelej", save, ft.Icons.SWAP_HORIZ)]))


# =============================================================================
# Korekta salda konta
# =============================================================================

def balance_dialog(app: Any, account: Dict[str, Any]) -> None:
    p, store = app.p, app.store
    if getattr(account.get("kind"), "liability", False):  # kredyt: korekta = ile zostało do spłaty
        return debt_dialog(app, account)
    current = float(account["balance"])
    value = field(p, "Rzeczywiste saldo", f"{current:.2f}".replace(".", ","), keyboard_type=ft.KeyboardType.NUMBER,
                  suffix=txt("zł", 16, p.muted), text_size=22, autofocus=True)
    diff = txt("Różnica: bez zmian", 14, p.muted)

    def changed(e: Any) -> None:
        v = parse_money(value.value or "")
        if v is None:
            diff.value, diff.color = "Niepoprawna kwota", p.negative
        else:
            d = round(v - current, 2)
            diff.value = "Różnica: bez zmian" if not d else f"Różnica: {money(d, signed=True)}"
            diff.color = p.muted if not d else (p.positive if d > 0 else p.negative)
        diff.update()

    value.on_change = changed

    def save(e: Any) -> None:
        v = parse_money(value.value or "")
        if v is None:
            return _error(app, value, "Podaj saldo (może być ujemne, np. -120,50)")
        app.close()
        if round(v - current, 2) == 0:
            app.toast("Saldo bez zmian.")
            return
        app.run_action(lambda: store.set_balance(account["name"], v), f"Korekta salda {account['name']}: {money(v)}")

    app.show(_sheet(app, f"Korekta salda: {account['name']}", [
        txt(f"Saldo w aplikacji: {money(current)}", 14, p.muted), value, diff,
        txt("Wpisz saldo z aplikacji banku. Różnica zapisze się jako „Korekta salda” — nie jest wydatkiem "
            "ani dochodem.", 12, p.muted),
        primary_button(p, "Zapisz saldo", save, ft.Icons.CHECK)]))


def debt_dialog(app: Any, account: Dict[str, Any]) -> None:
    p, store = app.p, app.store
    current = -float(account["balance"])
    value = field(p, "Zostało do spłaty", f"{current:.2f}".replace(".", ","), keyboard_type=ft.KeyboardType.NUMBER,
                  suffix=txt("zł", 16, p.muted), text_size=22, autofocus=True)

    def save(e: Any) -> None:
        v = parse_money(value.value or "")
        if v is None or v < 0:
            return _error(app, value, "Podaj kwotę długu (0 lub więcej)")
        app.close()
        app.run_action(lambda: store.set_balance(account["name"], -v), f"{account['name']}: do spłaty {money(v)}")

    app.show(_sheet(app, f"Ile zostało: {account['name']}", [
        txt(f"W aplikacji: do spłaty {money(current)}", 14, p.muted), value,
        txt("Wpisz kwotę z harmonogramu banku / sklepu. Raty księguje " + (
            "aplikacja" if store.can_manage else "komputer") + " automatycznie.", 12, p.muted),
        primary_button(p, "Zapisz", save, ft.Icons.CHECK)]))


def account_actions(app: Any, account: Dict[str, Any]) -> None:
    p = app.p

    def go(fn: Callable) -> Callable:
        return lambda e: (app.close(), fn())

    kind = account.get("kind")
    if getattr(kind, "liability", False):
        loan = account.get("loan") or {}
        tiles = [
            ft.ListTile(leading=ft.Icon(ft.Icons.SAVINGS_OUTLINED, color=p.accent), title=txt("Nadpłata"),
                        subtitle=txt("przelew na konto kredytu — dług maleje", 12, p.muted),
                        on_click=go(lambda: transfer_dialog(app, target=account["name"]))),
            ft.ListTile(leading=ft.Icon(ft.Icons.TUNE, color=p.accent), title=txt("Ile zostało do spłaty"),
                        on_click=go(lambda: debt_dialog(app, account))),
        ] + _manage_tiles(app, account, go)
        info = []
        if loan.get("next_due"):
            info.append(f"następna rata {loan['next_due']:%d.%m.%Y}: {money(loan['payment'])}")
        if loan.get("installments"):
            info.append(f"zapłacono {loan['paid']} z {loan['installments']} rat")
        app.show(_sheet(app, account["name"], [
            txt(getattr(kind, "label", ""), 13, p.muted),
            bold(f"Do spłaty {money(-float(account['balance']))}", 24, p.negative if account["balance"] < 0
                 else p.positive),
            *([txt(" · ".join(info), 13, p.text)] if info else []), *tiles]))
        return
    tiles = [
        ft.ListTile(leading=ft.Icon(ft.Icons.SWAP_HORIZ, color=p.accent), title=txt("Przelew z tego konta"),
                    on_click=go(lambda: transfer_dialog(app, source=account["name"]))),
        ft.ListTile(leading=ft.Icon(ft.Icons.SAVINGS_OUTLINED, color=p.accent), title=txt("Przelew na to konto"),
                    on_click=go(lambda: transfer_dialog(app, target=account["name"]))),
        ft.ListTile(leading=ft.Icon(ft.Icons.TUNE, color=p.accent), title=txt("Korekta salda"),
                    subtitle=txt("ustaw saldo zgodne z bankiem", 12, p.muted),
                    on_click=go(lambda: balance_dialog(app, account))),
    ] + _manage_tiles(app, account, go)
    app.show(_sheet(app, account["name"], [
        txt(f"{getattr(kind, 'label', '')} · {account.get('institution') or ''}".strip(" ·"), 13, p.muted),
        bold(money(float(account["balance"])), 26, p.text), *tiles]))


def _manage_tiles(app: Any, account: Dict[str, Any], go: Callable) -> List[ft.Control]:
    """Bez komputera: edycja, wycena (inwestycje) i zamknięcie konta."""
    if not app.store.can_manage:
        return []
    from mf_mobile import manage

    p = app.p
    kind = account.get("kind")
    tiles: List[ft.Control] = []
    if getattr(kind, "valuation", False):
        tiles.append(ft.ListTile(leading=ft.Icon(ft.Icons.SHOW_CHART, color=p.accent), title=txt("Wycena"),
                                 subtitle=txt("aktualna wartość inwestycji", 12, p.muted),
                                 on_click=go(lambda: manage.valuation_sheet(app, account))))
    tiles.append(ft.ListTile(leading=ft.Icon(ft.Icons.EDIT_OUTLINED, color=p.accent),
                             title=txt("Edytuj (nazwa, bank, oprocentowanie)"),
                             on_click=go(lambda: manage.account_edit_sheet(app, account))))
    tiles.append(ft.ListTile(leading=ft.Icon(ft.Icons.ARCHIVE_OUTLINED, color=p.negative), title=txt("Zamknij konto"),
                             on_click=go(lambda: manage.close_account_sheet(app, account))))
    return tiles


# =============================================================================
# Koperty
# =============================================================================

def envelope_actions(app: Any, env: Dict[str, Any]) -> None:
    p = app.p

    def go(fn: Callable) -> Callable:
        return lambda e: (app.close(), fn())

    tiles = [
        ft.ListTile(leading=ft.Icon(ft.Icons.REMOVE_CIRCLE_OUTLINE, color=p.accent), title=txt("Wydatek z koperty"),
                    on_click=go(lambda: transaction_sheet(app, preset_category=env["name"]))),
        ft.ListTile(leading=ft.Icon(ft.Icons.TUNE, color=p.accent), title=txt("Ustaw kwotę „zostało”"),
                    on_click=go(lambda: envelope_amount(app, env, "set"))),
        ft.ListTile(leading=ft.Icon(ft.Icons.ADD, color=p.accent), title=txt("Dołóż do koperty"),
                    on_click=go(lambda: envelope_amount(app, env, "add"))),
        ft.ListTile(leading=ft.Icon(ft.Icons.REMOVE, color=p.accent), title=txt("Odejmij z koperty"),
                    on_click=go(lambda: envelope_amount(app, env, "sub"))),
        ft.ListTile(leading=ft.Icon(ft.Icons.MOVE_UP, color=p.accent), title=txt("Przesuń do innej koperty"),
                    on_click=go(lambda: envelope_amount(app, env, "move"))),
    ]
    if app.store.can_manage:
        from mf_mobile import manage

        tiles.append(ft.ListTile(leading=ft.Icon(ft.Icons.EDIT_OUTLINED, color=p.accent),
                                 title=txt("Edytuj kopertę (nazwa, budżet, elastyczna)"),
                                 on_click=go(lambda: manage.envelope_sheet(app, env))))
    info = (f"Budżet {money(env['budget'])}"
            + (f" + z poprz. {money(env['carried'])}" if env["carried"] else "")
            + (f" + korekty {money(env['adjustment'], signed=True)}" if env["adjustment"] else "")
            + f" · wydano {money(env['spent'])}")
    app.show(_sheet(app, env["name"], [txt(info, 13, p.muted),
                                       bold(f"Zostało {money(env['remaining'])}", 22,
                                            p.negative if env["remaining"] < 0 else p.positive), *tiles]))


def envelope_amount(app: Any, env: Dict[str, Any], mode: str) -> None:
    p, store = app.p, app.store
    titles = {"set": "Ustaw kwotę „zostało”", "add": "Dołóż do koperty", "sub": "Odejmij z koperty",
              "move": "Przesuń do innej koperty"}
    value = field(p, "Kwota", f"{env['remaining']:.2f}".replace(".", ",") if mode == "set" else "",
                  keyboard_type=ft.KeyboardType.NUMBER, suffix=txt("zł", 16, p.muted), text_size=22, autofocus=True)
    controls: List[ft.Control] = [txt(f"{env['name']} · zostało {money(env['remaining'])}", 14, p.muted), value]
    target = None
    if mode == "move":
        others = [(f"{e['name']} · zostało {money(e['remaining'])}", e["name"])
                  for e in store.envelopes(only_active=False) if e["name"] != env["name"]]
        target = dropdown(p, "Do koperty", others, others[0][1] if others else None)
        controls.append(target)

    def save(e: Any) -> None:
        v = parse_money(value.value or "")
        if v is None or (mode != "set" and v <= 0):
            return _error(app, value, "Podaj poprawną kwotę")
        app.close()
        if mode == "set":
            app.run_action(lambda: store.envelope_set(env["name"], v), f"{env['name']}: zostało {money(v)}")
        elif mode == "move":
            app.run_action(lambda: store.envelope_move(env["name"], target.value, v),
                           f"Przesunięto {money(v)} › {target.value}")
        else:
            signed = v if mode == "add" else -v
            app.run_action(lambda: store.envelope_adjust(env["name"], signed),
                           f"{env['name']}: {money(signed, signed=True)}")

    controls.append(txt("Korekta dotyczy bieżącego miesiąca; w kopercie elastycznej reszta przechodzi dalej.", 12,
                        p.muted))
    controls.append(primary_button(p, "Zatwierdź", save, ft.Icons.CHECK))
    app.show(_sheet(app, titles[mode], controls))


# =============================================================================
# Cele
# =============================================================================

def goal_actions(app: Any, goal: Dict[str, Any]) -> None:
    p = app.p

    def go(fn: Callable) -> Callable:
        return lambda e: (app.close(), fn())

    tiles = [
        ft.ListTile(leading=ft.Icon(ft.Icons.ADD_CIRCLE_OUTLINE, color=p.accent), title=txt("Wpłać na cel"),
                    on_click=go(lambda: goal_amount(app, goal, "in"))),
        ft.ListTile(leading=ft.Icon(ft.Icons.REMOVE_CIRCLE_OUTLINE, color=p.accent), title=txt("Wypłać z celu"),
                    on_click=go(lambda: goal_amount(app, goal, "out"))),
        ft.ListTile(leading=ft.Icon(ft.Icons.TUNE, color=p.accent), title=txt("Korekta stanu celu"),
                    subtitle=txt("bez ruchu pieniędzy na kontach", 12, p.muted),
                    on_click=go(lambda: goal_amount(app, goal, "set"))),
    ]
    if app.store.can_manage:
        from mf_mobile import manage

        tiles.append(ft.ListTile(leading=ft.Icon(ft.Icons.EDIT_OUTLINED, color=p.accent),
                                 title=txt("Edytuj lub usuń cel"), on_click=go(lambda: manage.goal_sheet(app, goal))))
    app.show(_sheet(app, goal["name"], [
        txt(f"{money(float(goal['current_amount'] or 0))} z {money(float(goal['target_amount'] or 0))}", 16, p.text),
        *tiles]))


def goal_amount(app: Any, goal: Dict[str, Any], mode: str) -> None:
    p, store = app.p, app.store
    current = float(goal["current_amount"] or 0)
    titles = {"in": "Wpłata na cel", "out": "Wypłata z celu", "set": "Korekta stanu celu"}
    value = field(p, "Rzeczywisty stan" if mode == "set" else "Kwota",
                  f"{current:.2f}".replace(".", ",") if mode == "set" else "", keyboard_type=ft.KeyboardType.NUMBER,
                  suffix=txt("zł", 16, p.muted), text_size=22, autofocus=True)
    controls: List[ft.Control] = [txt(f"{goal['name']} · {money(current)}", 14, p.muted), value]
    account = None
    if mode != "set":
        balances = {a["name"]: a["balance"] for a in store.accounts()}
        names = store.account_names()
        default = goal.get("account_type") if goal.get("account_type") in names else (names[0] if names else None)
        account = dropdown(p, "Z konta" if mode == "in" else "Na konto",
                           [(f"{a} · {money(balances.get(a, 0))}", a) for a in names], default)
        controls.append(account)
        controls.append(txt("To przeniesienie pieniędzy — nie wydatek.", 12, p.muted))

    def save(e: Any) -> None:
        v = parse_money(value.value or "")
        if v is None or v < 0 or (mode != "set" and v == 0):
            return _error(app, value, "Podaj poprawną kwotę")
        app.close()
        if mode == "set":
            app.run_action(lambda: store.goal_set(goal, v), f"{goal['name']}: {money(v)}")
        else:
            app.run_action(lambda: store.goal_move(goal, v if mode == "in" else -v, account.value),
                           f"{titles[mode]}: {money(v)}")

    controls.append(primary_button(p, "Zatwierdź", save, ft.Icons.CHECK))
    app.show(_sheet(app, titles[mode], controls))


def iso_to_pl(iso: str) -> str:
    try:
        return date.fromisoformat(iso[:10]).strftime("%d.%m.%Y")
    except ValueError:
        return iso
