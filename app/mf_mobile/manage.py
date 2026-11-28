"""
Tryb „Bez komputera”: zakładanie i edycja kont (w tym lokat, kredytów i rat), kopert, celów
oraz stałych płatności — wszystko, co w trybie z komputerem robi się w programie na komputer.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

import flet as ft

from mf_mobile.forms import _error, _sheet
from mf_mobile.store import TYPE_EXPENSE, TYPE_INCOME, money, parse_money, plural, today_iso
from mf_mobile.ui import bold, dropdown, field, primary_button, secondary_button, txt
from src.finance import accounts as acc_api
from src.finance import loans, recurring

EXISTING = "__existing__"  # lokata już założona (bez przelewu)
NONE = "__none__"
RECURRING_LABELS = {TYPE_EXPENSE: "Wydatek (rachunek, subskrypcja)", TYPE_INCOME: "Dochód (pensja)",
                    "Przelew": "Przelew na inne konto", "Na Skarbonkę": "Odkładanie na cel"}


def _num(raw: str) -> Optional[float]:
    return parse_money((raw or "").replace("%", ""))


def _pl(value: float) -> str:
    return f"{value:.2f}".replace(".", ",")


def _iso_pl(iso: Optional[str]) -> str:
    try:
        return datetime.strptime(str(iso)[:10], "%Y-%m-%d").strftime("%d.%m.%Y")
    except (TypeError, ValueError):
        return "—"


def date_row(app: Any, label: str, state: Dict[str, Any], key: str) -> ft.Row:
    """Wiersz „Etykieta: 05.12.2026 [Kalendarz]” zapisujący datę ISO w state[key]."""
    p = app.p
    info = txt(f"{label}: {_iso_pl(state[key])}", 14, p.text, expand=True)

    def pick(e: Any) -> None:
        def changed(ev: Any) -> None:
            value = ev.control.value
            if value:
                state[key] = value.date().isoformat() if isinstance(value, datetime) else str(value)[:10]
                info.value = f"{label}: {_iso_pl(state[key])}"
                info.update()

        start = datetime.strptime(state[key] or today_iso(), "%Y-%m-%d")
        app.show(ft.DatePicker(value=start, first_date=datetime(2000, 1, 1), last_date=datetime(2100, 12, 31),
                               on_change=changed, help_text=label, cancel_text="Anuluj", confirm_text="OK"))

    return ft.Row([info, ft.OutlinedButton(content="Kalendarz", icon=ft.Icons.CALENDAR_MONTH_OUTLINED, on_click=pick,
                                           style=ft.ButtonStyle(color=p.text))],
                  vertical_alignment=ft.CrossAxisAlignment.CENTER)


def toggle(app: Any, label: str, value: bool = False) -> Tuple[ft.Switch, ft.Row]:
    """Przełącznik z opisem, który zawija się na wąskim ekranie. Zwraca (przełącznik, wiersz)."""
    sw = ft.Switch(value=value, active_color=app.p.accent)
    return sw, ft.Row([sw, ft.Container(txt(label, 14, app.p.text), expand=True)],
                      vertical_alignment=ft.CrossAxisAlignment.CENTER)


def _after(app: Any, message: str, booked: int = 0) -> str:
    if booked:
        message += f" Zaksięgowano zaległe płatności: {booked}."
    return message


# =============================================================================
# Konta
# =============================================================================

def account_sheet(app: Any) -> None:
    """Nowe konto: zwykłe, oszczędnościowe, inwestycyjne, lokata/obligacje, kredyt / raty, własny rodzaj."""
    p, store = app.p, app.store
    liquid = store.account_names(liquid_only=True)
    all_names = store.account_names()
    state = {"start": today_iso(), "first_due": date.today().replace(day=min(date.today().day, 28)).isoformat()}

    kind = dropdown(p, "Rodzaj konta", [(f"{k.group} · {k.label}", k.code) for k in acc_api.ACCOUNT_KINDS.values()],
                    "checking")
    name = field(p, "Nazwa (np. mKonto, Revolut, Obligacje EDO)", capitalization=ft.TextCapitalization.SENTENCES)
    institution = field(p, "Bank / instytucja (opcjonalnie)")
    balance = field(p, "Saldo teraz", "0", keyboard_type=ft.KeyboardType.NUMBER, suffix=txt("zł", 16, p.muted))
    rate = field(p, "Oprocentowanie (% w skali roku)", "0", keyboard_type=ft.KeyboardType.NUMBER,
                 suffix=txt("%", 16, p.muted))
    # własny rodzaj
    custom_label = field(p, "Nazwa rodzaju (np. Obligacje skarbowe, Kryptowaluty)")
    custom_group = dropdown(p, "Grupa", [(g, g) for g in acc_api.KIND_GROUPS if g != "Zobowiązania"], "Inwestycje")
    f_liquid, r_liquid = toggle(app, "Środki dostępne na co dzień (płatności)")
    f_rate, r_rate = toggle(app, "Oprocentowanie")
    f_valuation, r_valuation = toggle(app, "Wartość zmienia się (wycena ręczna)")
    # lokata / obligacje
    months = field(p, "Okres (miesiące)", "12", keyboard_type=ft.KeyboardType.NUMBER)
    source = dropdown(p, "Skąd pieniądze", [("Lokata już założona (bez przelewu)", EXISTING)]
                      + [(a, a) for a in liquid], EXISTING)
    return_to = dropdown(p, "Po terminie środki wracają na", [(a, a) for a in liquid], liquid[0] if liquid else None)
    auto_renew, r_renew = toggle(app, "Odnawiaj automatycznie na kolejny okres")
    start_row = date_row(app, "Data założenia", state, "start")
    # kredyt / raty
    count = field(p, "Liczba rat (pozostałych)", "10", keyboard_type=ft.KeyboardType.NUMBER)
    payment = field(p, "Rata miesięczna (puste = wyliczona)", keyboard_type=ft.KeyboardType.NUMBER,
                    suffix=txt("zł", 16, p.muted))
    due_row = date_row(app, "Najbliższa rata", state, "first_due")
    pay_from = dropdown(p, "Raty płacone z konta", [(a, a) for a in liquid], liquid[0] if liquid else None)
    loan_cat = field(p, "Koperta na raty", loans.DEFAULT_CATEGORY)
    disburse = dropdown(p, "Pieniądze z kredytu wpłynęły na", [("Nie — zapisz tylko dług (zakup na raty)", NONE)]
                        + [(a, a) for a in all_names], NONE)
    existing, r_existing = toggle(app, "Spłacam już od dawna — tylko stan, bez historii")
    hint = txt("", 12, p.muted)

    groups = {
        "regular": [institution, balance, rate],
        "custom": [custom_label, custom_group, r_liquid, r_rate, r_valuation, balance],
        "term": [institution, rate, months, start_row, source, return_to, r_renew],
        "loan": [institution, rate, count, payment, due_row, pay_from, loan_cat, r_existing, disburse],
    }
    every = {c for cs in groups.values() for c in cs}

    def mode() -> str:
        info = acc_api.kind_info(kind.value)
        if info.code == "custom":
            return "custom"
        if info.liability:
            return "loan"
        if info.has_term:
            return "term"
        return "regular"

    def refresh(update: bool = True) -> None:
        info = acc_api.kind_info(kind.value)
        m = mode()
        shown = set(groups[m])
        if m == "regular" and not info.has_rate:
            shown.discard(rate)
        if m == "loan" and info.code == "installments":
            shown.discard(disburse)
        for c in every:
            c.visible = c in shown
        balance.label = {"regular": "Wartość teraz" if info.valuation else "Saldo teraz", "custom": "Saldo / wartość teraz"
                         }.get(m, "Saldo teraz")
        amount_label = {"term": "Kwota lokaty / obligacji", "loan": "Ile zostało do spłaty"}.get(m)
        if amount_label:
            balance.visible = True
            balance.label = amount_label
        rate.label = "Oprocentowanie (%; 0 = raty 0%)" if m == "loan" else "Oprocentowanie (% w skali roku)"
        hint.value = {
            "regular": "Saldo początkowe zapisze się bez wpisu w historii (to stan na dziś).",
            "custom": "Własny rodzaj — sam decydujesz, w której grupie jest konto i jak działa.",
            "term": "Odsetki i zwrot po terminie aplikacja rozliczy sama. „Lokata już założona” — bez przelewu.",
            "loan": "Każda rata zaksięguje się sama w dniu płatności: wydatek w kopercie rat + spłata długu.",
        }[m]
        if update:
            sheet.update()

    kind.on_select = lambda e: refresh()

    def save(e: Any) -> None:
        m = mode()
        nm = (name.value or "").strip()
        if not nm:
            return _error(app, name, "Podaj nazwę konta")
        if nm in all_names:
            return _error(app, name, "Konto o tej nazwie już istnieje")
        amount = _num(balance.value or "0")
        if amount is None:
            return _error(app, balance, "Podaj kwotę (np. 1250,00)")
        r = _num(rate.value or "0") or 0.0
        if m == "term":
            n = int(_num(months.value or "") or 0)
            if amount <= 0:
                return _error(app, balance, "Kwota musi być większa od zera")
            if n <= 0:
                return _error(app, months, "Podaj liczbę miesięcy")
            src = None if source.value == EXISTING else source.value
            action: Callable[[], Any] = lambda: store.add_deposit(
                nm, amount, r, n, state["start"], src, institution.value or "", kind.value, bool(auto_renew.value),
                return_to.value)
            msg = f"Założono: {nm} ({money(amount)})."
        elif m == "loan":
            n = int(_num(count.value or "") or 0)
            if amount <= 0:
                return _error(app, balance, "Podaj kwotę do spłaty")
            if n <= 0:
                return _error(app, count, "Podaj liczbę rat")
            if not pay_from.value:
                pay_from.error_text = "Wybierz konto"
                pay_from.update()
                return
            pay = _num(payment.value or "") if (payment.value or "").strip() else None
            to = None if disburse.value in (None, NONE) or existing.value else disburse.value
            action = lambda: store.add_loan(nm, amount, n, state["first_due"], pay_from.value, r, pay, kind.value,
                                            loan_cat.value or "", to, bool(existing.value), institution.value or "")
            msg = f"Dodano: {nm} — rata {money(pay or loans.annuity_payment(amount, r, n))}."
        elif m == "custom":
            flags = ",".join(f for f, sw in (("liquid", f_liquid), ("rate", f_rate), ("valuation", f_valuation))
                             if sw.value)
            if not (custom_label.value or "").strip():
                return _error(app, custom_label, "Nazwij rodzaj konta")
            action = lambda: store.add_account(nm, "custom", amount, "", 0.0, custom_label.value or "",
                                               custom_group.value or "Inwestycje", flags)
            msg = f"Dodano konto {nm}: {money(amount)}."
        else:
            action = lambda: store.add_account(nm, kind.value, amount, institution.value or "", r)
            msg = f"Dodano konto {nm}: {money(amount)}."
        app.close()
        result = {"booked": 0}

        def run() -> None:
            out = action()
            if isinstance(out, int):
                result["booked"] = out

        if app.run_action(run):
            app.toast(_after(app, msg, result["booked"]))

    sheet = _sheet(app, "Nowe konto", [kind, name, custom_label, custom_group, r_liquid, r_rate, r_valuation,
                                       institution, balance, rate, months, start_row, source, return_to, r_renew,
                                       count, payment, due_row, pay_from, loan_cat, r_existing, disburse,
                                       hint, primary_button(p, "Dodaj konto", save, ft.Icons.CHECK)])
    refresh(update=False)
    app.show(sheet)


def account_edit_sheet(app: Any, account: Dict[str, Any]) -> None:
    p, store = app.p, app.store
    info = account.get("kind")
    name = field(p, "Nazwa", account["name"])
    institution = field(p, "Bank / instytucja", account.get("institution") or "")
    has_rate = bool(getattr(info, "has_rate", False))
    rate = field(p, "Oprocentowanie (% w skali roku)", _pl(float(account.get("interest_rate") or 0)),
                 keyboard_type=ft.KeyboardType.NUMBER, suffix=txt("%", 16, p.muted), visible=has_rate)

    def save(e: Any) -> None:
        if not (name.value or "").strip():
            return _error(app, name, "Podaj nazwę")
        r = _num(rate.value or "0") if has_rate else None
        if has_rate and r is None:
            return _error(app, rate, "Podaj oprocentowanie")
        app.close()
        app.run_action(lambda: store.update_account(account["name"], name.value or "", institution.value or "", r),
                       f"Zapisano: {name.value}")

    app.show(_sheet(app, f"Edycja: {account['name']}", [
        name, institution, rate,
        txt("Zmiana nazwy zmienia ją też w historii, celach i zleceniach.", 12, p.muted),
        primary_button(p, "Zapisz", save, ft.Icons.CHECK)]))


def valuation_sheet(app: Any, account: Dict[str, Any]) -> None:
    p, store = app.p, app.store
    current = float(account["balance"])
    value = field(p, "Aktualna wartość", _pl(current), keyboard_type=ft.KeyboardType.NUMBER,
                  suffix=txt("zł", 16, p.muted), text_size=22, autofocus=True)

    def save(e: Any) -> None:
        v = _num(value.value or "")
        if v is None or v < 0:
            return _error(app, value, "Podaj wartość")
        app.close()
        app.run_action(lambda: store.valuation(account["name"], v),
                       f"{account['name']}: wycena {money(v)} ({money(v - current, signed=True)})")

    app.show(_sheet(app, f"Wycena: {account['name']}", [
        txt(f"W aplikacji: {money(current)}", 14, p.muted), value,
        txt("Wpisz wartość z aplikacji maklerskiej / banku. Różnica zapisze się jako zysk lub strata z inwestycji — "
            "nie jest wydatkiem ani dochodem.", 12, p.muted),
        primary_button(p, "Zapisz wycenę", save, ft.Icons.CHECK)]))


def close_account_sheet(app: Any, account: Dict[str, Any]) -> None:
    p, store = app.p, app.store
    bal = float(account["balance"])
    others = [a for a in store.account_names() if a != account["name"]]
    target = dropdown(p, "Pozostałe środki przelej na", [(a, a) for a in others], others[0] if others else None,
                      visible=abs(bal) >= 0.005)

    def do(e: Any) -> None:
        app.close()
        app.run_action(lambda: store.close_account(account["name"], target.value if abs(bal) >= 0.005 else None),
                       f"Zamknięto konto {account['name']}")

    app.show(_sheet(app, f"Zamknąć konto {account['name']}?", [
        txt(f"Saldo: {money(bal)}. Historia wpisów zostaje; konto znika z list.", 13, p.text), target,
        secondary_button(p, "Zamknij konto", do, ft.Icons.ARCHIVE_OUTLINED, color=p.negative)]))


# =============================================================================
# Koperty
# =============================================================================

def envelope_sheet(app: Any, env: Optional[Dict[str, Any]] = None) -> None:
    p, store = app.p, app.store
    editing = env is not None
    name = field(p, "Nazwa koperty", (env or {}).get("name", ""), capitalization=ft.TextCapitalization.SENTENCES,
                 autofocus=not editing)
    budget = field(p, "Budżet miesięczny", _pl(float((env or {}).get("budget") or 0)),
                   keyboard_type=ft.KeyboardType.NUMBER, suffix=txt("zł", 16, p.muted), text_size=20)
    rollover, r_rollover = toggle(app, "Elastyczna — niewydane pieniądze przechodzą na kolejny miesiąc",
                                  bool((env or {}).get("rollover")))

    def save(e: Any) -> None:
        v = _num(budget.value or "0")
        if v is None or v < 0:
            return _error(app, budget, "Podaj kwotę (0 = bez budżetu)")
        if not (name.value or "").strip():
            return _error(app, name, "Podaj nazwę")
        app.close()
        if editing:
            app.run_action(lambda: store.update_envelope(env["id"], name.value or "", v, bool(rollover.value)),
                           f"{name.value}: budżet {money(v)}")
        else:
            app.run_action(lambda: store.add_envelope(name.value or "", v, bool(rollover.value)),
                           f"Nowa koperta {name.value}: {money(v)}")

    def delete(e: Any) -> None:
        app.close()
        app.confirm(f"Usunąć kopertę {env['name']}?", "Wpisy z tą kopertą zostaną w historii; koperta zniknie z "
                    "budżetu, a zlecenia stałe stracą przypisanie.", lambda: store.delete_envelope(env["id"]),
                    yes="Usuń")

    buttons: List[ft.Control] = [primary_button(p, "Zapisz", save, ft.Icons.CHECK)]
    if editing:
        buttons.append(secondary_button(p, "Usuń", delete, ft.Icons.DELETE_OUTLINE, color=p.negative))
    app.show(_sheet(app, "Edycja koperty" if editing else "Nowa koperta", [
        name, budget, r_rollover,
        txt("Budżet to kwota na każdy miesiąc. Jednorazowe zmiany w danym miesiącu: „Dołóż / Odejmij”.", 12,
            p.muted), ft.Row(buttons, spacing=10)]))


# =============================================================================
# Cele
# =============================================================================

def goal_sheet(app: Any, goal: Optional[Dict[str, Any]] = None) -> None:
    p, store = app.p, app.store
    editing = goal is not None
    names = store.account_names()
    deadline = (goal or {}).get("target_date") or ""
    state = {"date": deadline or date(date.today().year + 1, date.today().month, 1).isoformat()}
    name = field(p, "Nazwa celu (np. Wakacje, Poduszka finansowa)", (goal or {}).get("name", ""),
                 capitalization=ft.TextCapitalization.SENTENCES, autofocus=not editing)
    target = field(p, "Kwota docelowa", _pl(float((goal or {}).get("target_amount") or 0)) if editing else "",
                   keyboard_type=ft.KeyboardType.NUMBER, suffix=txt("zł", 16, p.muted), text_size=20)
    default_acc = (goal or {}).get("account_type")
    account = dropdown(p, "Pieniądze trzymasz na koncie", [(a, a) for a in names],
                       default_acc if default_acc in names else (names[0] if names else None))
    has_date, r_has_date = toggle(app, "Termin (aplikacja policzy, ile odkładać miesięcznie)", bool(deadline))
    when = date_row(app, "Do kiedy", state, "date")
    when.visible = bool(deadline)

    def show_date(e: Any) -> None:
        when.visible = bool(has_date.value)
        when.update()

    has_date.on_change = show_date

    def save(e: Any) -> None:
        v = _num(target.value or "")
        if v is None or v <= 0:
            return _error(app, target, "Podaj kwotę docelową")
        if not (name.value or "").strip():
            return _error(app, name, "Podaj nazwę")
        d = state["date"] if has_date.value else None
        app.close()
        if editing:
            app.run_action(lambda: store.update_goal(goal["id"], name.value or "", v, account.value, d),
                           f"Zapisano cel {name.value}")
        else:
            app.run_action(lambda: store.add_goal(name.value or "", v, account.value, d),
                           f"Nowy cel {name.value}: {money(v)}")

    def delete(e: Any) -> None:
        app.close()
        current = float(goal.get("current_amount") or 0)
        app.confirm(f"Usunąć cel {goal['name']}?",
                    f"Odłożone {money(current)} wrócą jako dostępne na koncie {goal.get('account_type')}."
                    if current else "Cel zostanie usunięty.", lambda: store.delete_goal(goal["id"]), yes="Usuń")

    buttons: List[ft.Control] = [primary_button(p, "Zapisz", save, ft.Icons.CHECK)]
    if editing:
        buttons.append(secondary_button(p, "Usuń", delete, ft.Icons.DELETE_OUTLINE, color=p.negative))
    app.show(_sheet(app, "Edycja celu" if editing else "Nowy cel", [
        name, target, account, r_has_date, when, ft.Row(buttons, spacing=10)]))


# =============================================================================
# Stałe płatności (zlecenia)
# =============================================================================

def recurring_sheet(app: Any, item: Optional[Dict[str, Any]] = None) -> None:
    p, store = app.p, app.store
    editing = item is not None
    liquid = store.account_names(liquid_only=True)
    names = store.account_names()
    goals = store.goals()
    state = {"start": (item or {}).get("start_date") or today_iso()}

    r_type = dropdown(p, "Rodzaj", [(label, code) for code, label in RECURRING_LABELS.items()],
                      (item or {}).get("type") or TYPE_EXPENSE)
    name = field(p, "Nazwa (np. Czynsz, Netflix, Pensja)", (item or {}).get("name", ""),
                 capitalization=ft.TextCapitalization.SENTENCES)
    amount = field(p, "Kwota", _pl(float(item["amount"])) if editing else "", keyboard_type=ft.KeyboardType.NUMBER,
                   suffix=txt("zł", 16, p.muted), text_size=20)
    account = dropdown(p, "Konto", [(a, a) for a in names],
                       (item or {}).get("account_type") or (liquid[0] if liquid else None))
    category = dropdown(p, "Koperta", [(c, c) for c in store.category_names()], (item or {}).get("category"),
                        enable_filter=True)
    target = dropdown(p, "Na konto", [(a, a) for a in names], (item or {}).get("target_account"))
    goal = dropdown(p, "Na cel", [(g["name"], str(g["id"])) for g in goals],
                    str(item["piggy_id"]) if editing and item.get("piggy_id") else None)
    cycle = dropdown(p, "Jak często", [(c, c) for c in recurring.RECURRING_CYCLES],
                     (item or {}).get("cycle") or "Miesięcznie")
    start = date_row(app, "Pierwsza płatność", state, "start")

    def refresh(update: bool = True) -> None:
        t = r_type.value
        category.visible = t in (TYPE_EXPENSE, TYPE_INCOME)
        target.visible = t == "Przelew"
        goal.visible = t == "Na Skarbonkę"
        account.label = "Na konto" if t == TYPE_INCOME else "Z konta"
        category.label = "Kategoria dochodu" if t == TYPE_INCOME else "Koperta"
        if update:
            sheet.update()

    r_type.on_select = lambda e: refresh()

    def save(e: Any) -> None:
        v = _num(amount.value or "")
        if v is None or v <= 0:
            return _error(app, amount, "Podaj kwotę")
        if not (name.value or "").strip():
            return _error(app, name, "Podaj nazwę")
        t = r_type.value
        if t == "Przelew" and (not target.value or target.value == account.value):
            target.error_text = "Wybierz inne konto"
            target.update()
            return
        if t == "Na Skarbonkę" and not goal.value:
            goal.error_text = "Wybierz cel"
            goal.update()
            return
        if t == TYPE_EXPENSE and not category.value:
            category.error_text = "Wybierz kopertę"
            category.update()
            return
        app.close()
        result = {"booked": 0}

        def do() -> None:
            result["booked"] = store.save_recurring(
                item["id"] if editing else None, name.value or "", t, v, account.value, cycle.value, state["start"],
                category.value, target.value, int(goal.value) if goal.value else None)

        if app.run_action(do):
            app.toast(_after(app, f"Zapisano: {name.value} {money(v)} ({cycle.value.lower()})", result["booked"]))

    controls: List[ft.Control] = [r_type, name, amount, account, category, target, goal, cycle, start,
                                  txt("Aplikacja zaksięguje płatność sama w dniu terminu (także zaległe — przy "
                                      "uruchomieniu).", 12, p.muted),
                                  primary_button(p, "Zapisz", save, ft.Icons.CHECK)]
    sheet = _sheet(app, "Edycja stałej płatności" if editing else "Nowa stała płatność", controls)
    refresh(update=False)
    app.show(sheet)


def recurring_actions(app: Any, item: Dict[str, Any]) -> None:
    p, store = app.p, app.store

    def go(fn: Callable) -> Callable:
        return lambda e: (app.close(), fn())

    active = item["active"]
    tiles = [
        ft.ListTile(leading=ft.Icon(ft.Icons.EDIT_OUTLINED, color=p.accent), title=txt("Edytuj"),
                    on_click=go(lambda: recurring_sheet(app, item))),
        ft.ListTile(leading=ft.Icon(ft.Icons.PAUSE_CIRCLE_OUTLINE if active else ft.Icons.PLAY_CIRCLE_OUTLINE,
                                    color=p.accent),
                    title=txt("Wstrzymaj" if active else "Wznów"),
                    on_click=go(lambda: app.run_action(lambda: store.toggle_recurring(item["id"]),
                                                       "Wstrzymano" if active else "Wznowiono"))),
        ft.ListTile(leading=ft.Icon(ft.Icons.DELETE_OUTLINE, color=p.negative), title=txt("Usuń"),
                    on_click=go(lambda: app.confirm(f"Usunąć „{item['name']}”?", "Zaksięgowane wpisy zostaną w "
                                                    "historii.", lambda: store.delete_recurring(item["id"]),
                                                    yes="Usuń"))),
    ]
    nd = item.get("next_due")
    app.show(_sheet(app, item["name"], [
        txt(f"{RECURRING_LABELS.get(item['type'], item['type'])} · {item.get('cycle')}", 13, p.muted),
        bold(money(float(item["amount"])), 24, p.text),
        txt(("Następna: " + nd.strftime("%d.%m.%Y")) if nd and active else "Wstrzymana", 13, p.text),
        *tiles]))


def summary_text(items: List[Dict[str, Any]]) -> str:
    active = [i for i in items if i["active"]]
    return f"{plural(len(active), 'aktywna płatność', 'aktywne płatności', 'aktywnych płatności')}"


# =============================================================================
# Automatyczne odkładanie (reguły)
# =============================================================================

AUTOSAVE_MODES = {"income_percent": "Procent każdego wpływu (np. 10% pensji)",
                  "roundup": "Zaokrąglanie wydatków (reszta odkładana)"}


def autosave_sheet(app: Any) -> None:
    p, store = app.p, app.store
    names = store.account_names()
    liquid = store.account_names(liquid_only=True)
    goals = store.goals()
    mode = dropdown(p, "Rodzaj", [(label, code) for code, label in AUTOSAVE_MODES.items()], "income_percent")
    value = field(p, "Ile procent", "10", keyboard_type=ft.KeyboardType.NUMBER, suffix=txt("%", 16, p.muted))
    source = dropdown(p, "Z konta (wpływy / wydatki na tym koncie)", [(a, a) for a in liquid],
                      liquid[0] if liquid else None)
    target_opts = [(f"Cel: {g['name']}", f"goal:{g['id']}") for g in goals] + \
        [(f"Konto: {a}", f"account:{a}") for a in names]
    target = dropdown(p, "Odkładaj na", target_opts, target_opts[0][1] if target_opts else None)
    hint = txt("", 12, p.muted)

    def refresh(update: bool = True) -> None:
        if mode.value == "roundup":
            value.label, value.suffix = "Zaokrąglaj do pełnych", txt("zł", 16, p.muted)
            hint.value = "Np. 10 zł: zakup za 23,40 zł → 6,60 zł trafia na oszczędności."
        else:
            value.label, value.suffix = "Ile procent", txt("%", 16, p.muted)
            hint.value = "Przy każdym dochodzie na tym koncie część od razu trafia na cel lub konto oszczędnościowe."
        if update:
            sheet.update()

    mode.on_select = lambda e: refresh()

    def save(e: Any) -> None:
        v = _num(value.value or "")
        if v is None or v <= 0:
            return _error(app, value, "Podaj wartość większą od zera")
        if not target.value or not source.value:
            target.error_text = "Wybierz, gdzie odkładać"
            target.update()
            return
        kind, tgt = target.value.split(":", 1)
        app.close()
        app.run_action(lambda: store.save_autosave(None, source.value, mode.value, v, kind, tgt),
                       "Dodano regułę odkładania.")

    sheet = _sheet(app, "Automatyczne odkładanie", [mode, value, source, target, hint,
                                                    primary_button(p, "Zapisz regułę", save, ft.Icons.CHECK)])
    refresh(update=False)
    app.show(sheet)


def autosave_actions(app: Any, rule: Dict[str, Any]) -> None:
    p, store = app.p, app.store
    active = bool(rule.get("is_active"))

    def go(fn: Callable) -> Callable:
        return lambda e: (app.close(), fn())

    app.show(_sheet(app, "Reguła odkładania", [
        txt(rule["text"], 14, p.text), txt(f"› {rule['target_label']}", 13, p.muted),
        ft.ListTile(leading=ft.Icon(ft.Icons.PAUSE_CIRCLE_OUTLINE if active else ft.Icons.PLAY_CIRCLE_OUTLINE,
                                    color=p.accent), title=txt("Wstrzymaj" if active else "Wznów"),
                    on_click=go(lambda: app.run_action(lambda: store.toggle_autosave(rule["id"]),
                                                       "Wstrzymano" if active else "Wznowiono"))),
        ft.ListTile(leading=ft.Icon(ft.Icons.DELETE_OUTLINE, color=p.negative), title=txt("Usuń"),
                    on_click=go(lambda: app.confirm("Usunąć regułę?", rule["text"],
                                                    lambda: store.delete_autosave(rule["id"]), yes="Usuń")))]))
