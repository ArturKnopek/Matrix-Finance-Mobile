"""
Warstwa danych aplikacji mobilnej — cienka nakładka na wspólny silnik (app/src).

Tryby pracy:
  * „Z komputerem” — każda zmiana przechodzi przez `sync.record_op`: zostaje od razu zastosowana
    na telefonie i odłożona do wysłania na komputer (plik .mfops w OneDrive);
  * „Bez komputera” (samodzielny) — telefon jest główną bazą: zmiany są tylko lokalne, telefon sam
    księguje zlecenia stałe, raty i lokaty, a dane chroni zaszyfrowana kopia zapasowa (.mfx — ten sam
    format co eksport w programie na komputer, więc dane można przenieść w obie strony);
  * dane przykładowe — zmiany tylko lokalne.
"""

from __future__ import annotations

import random
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

from mf_mobile import config

config.configure()

from src.finance import accounts as acc_api  # noqa: E402
from src.finance import analytics, envelopes as env_api, goals as goals_api, ledger, recurring, storage, sync  # noqa: E402,F401
from src.utils.parsing import parse_amount  # noqa: E402

PHONE_USER = "telefon"
SET_PIN = "local_pin"  # sól$skrót — blokada aplikacji PIN-em (nie trafia do kopii)
SET_PIN_LEN = "local_pin_len"
SET_THEME = "local_theme"
SET_DEMO = "local_demo"
SET_SENT_AT = "local_ops_sent_at"
SET_SENT_COUNT = "local_ops_sent_count"
SET_MODE = "local_mode"  # "solo" = bez komputera; inaczej — z komputerem
SET_BACKUP_AT = "local_backup_at"
SET_BACKUP_DIGEST = "local_backup_digest"
BACKUP_NAME = "MatrixFinance-kopia.mfx"

TYPE_EXPENSE, TYPE_INCOME = ledger.EXPENSE, ledger.INCOME
MONTHS_PL = ["styczeń", "luty", "marzec", "kwiecień", "maj", "czerwiec", "lipiec", "sierpień", "wrzesień",
             "październik", "listopad", "grudzień"]


def month_label(ym: str) -> str:
    y, m = ym.split("-")
    return f"{MONTHS_PL[int(m) - 1].capitalize()} {y}"


def plural(n: int, one: str, few: str, many: str) -> str:
    """Polska odmiana: 1 wpis, 2 wpisy, 5 wpisów (12–14 i końcówki 0,1,5–9 => „many”)."""
    n = abs(int(n))
    if n == 1:
        return f"{n} {one}"
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return f"{n} {few}"
    return f"{n} {many}"


def money(value: float, signed: bool = False, currency: str = "zł") -> str:
    fmt = f"{value:+,.2f}" if signed else f"{value:,.2f}"
    return f"{fmt.replace(',', ' ').replace('.', ',')} {currency}".strip()


def _changes(method: Any) -> Any:
    """Metoda zmieniająca dane: unieważnia zapamiętany skrót danych (sprawdzanie „czy jest nowa kopia”)."""
    def wrapper(self: "Store", *args: Any, **kwargs: Any) -> Any:
        try:
            return method(self, *args, **kwargs)
        finally:
            self.touch()

    wrapper.__name__ = method.__name__
    wrapper.__doc__ = method.__doc__
    return wrapper


class Store:
    def __init__(self) -> None:
        storage.init_auth_db()
        self.db_path = storage.set_active_user_db(PHONE_USER)
        storage.init_user_db(self.db_path, 0.0, 0.0)
        self.ym = date.today().strftime("%Y-%m")
        self._generation = 0
        self._digest_cache: Tuple[int, str] = (-1, "")

    def touch(self) -> None:
        """Dane się zmieniły (skrót danych policzy się na nowo przy następnym sprawdzeniu)."""
        self._generation += 1

    # ------------------------------------------------------------------ ustawienia / stan

    def setting(self, key: str, default: str = "") -> str:
        return sync.get_sync_setting(key, default)

    def set_setting(self, key: str, value: Any) -> None:
        sync.set_sync_setting(key, value)

    @property
    def is_demo(self) -> bool:
        return self.setting(SET_DEMO) == "1"

    @property
    def is_solo(self) -> bool:
        """Tryb „Bez komputera”: telefon jest główną bazą danych."""
        return self.setting(SET_MODE) == "solo" and not self.is_demo

    @property
    def local_only(self) -> bool:
        return self.is_demo or self.is_solo

    @property
    def can_manage(self) -> bool:
        """Zakładanie i edycja kont, kopert, celów, zleceń — gdy telefon nie zależy od komputera."""
        return self.local_only

    @property
    def has_data(self) -> bool:
        return self.is_demo or self.is_solo or bool(self.setting(sync.SET_SNAPSHOT_AT))

    @property
    def snapshot_at(self) -> str:
        return self.setting(sync.SET_SNAPSHOT_AT)

    @property
    def password(self) -> str:
        return self.setting(sync.SET_PASSWORD)

    def set_password(self, password: str) -> None:
        self.set_setting(sync.SET_PASSWORD, password)

    @property
    def theme(self) -> str:
        return self.setting(SET_THEME, "matrix")

    def set_theme(self, name: str) -> None:
        self.set_setting(SET_THEME, name)

    def shift_month(self, delta: int) -> str:
        self.ym = env_api.month_add(self.ym, delta)
        return self.ym

    # ------------------------------------------------------------------ odczyt

    def summary(self) -> Dict[str, float]:
        s = env_api.get_budget_summary(self.ym)
        nw = acc_api.get_net_worth()
        return {**s, "balance": s["income"] - s["expense"], "net_worth": nw["total"], "liquid": nw["liquid"],
                "goals": nw["goals"], "debt": nw.get("debt", 0.0)}

    def envelopes(self, only_active: bool = True) -> List[Dict[str, Any]]:
        out = []
        for e in env_api.get_envelope_overview(self.ym):
            if e["name"] in (storage.SAVINGS_CATEGORY, storage.INTEREST_CATEGORY):
                continue
            if only_active and not (e["budget"] or e["spent"] or e["carried"] or e["adjustment"]):
                continue
            out.append(e)
        out.sort(key=lambda e: (-(e["pct"] or 0) if e["available"] > 0 else 1, e["name"]))
        return out

    def category_names(self) -> List[str]:
        return [c for c in env_api.get_unique_categories()
                if c not in (storage.SAVINGS_CATEGORY, storage.INTEREST_CATEGORY)]

    def accounts(self) -> List[Dict[str, Any]]:
        rows = acc_api.get_accounts_overview()
        order = {g: i for i, g in enumerate(acc_api.KIND_GROUPS)}
        return sorted(rows, key=lambda a: (order.get(a["group"], 9), a.get("sort_order") or 0, a["name"]))

    def account_names(self, liquid_only: bool = False) -> List[str]:
        return [v for _, v in acc_api.get_account_options(active_only=True, liquid_only=liquid_only)]

    def goals(self) -> List[Dict[str, Any]]:
        return goals_api.goals_overview()

    def transactions(self, search: str = "", kind: str = "all", limit: Optional[int] = None,
                     all_months: bool = False) -> List[Dict[str, Any]]:
        type_filter = {"expense": TYPE_EXPENSE, "income": TYPE_INCOME, "transfer": ledger.TRANSFER}.get(kind)
        rows = ledger.fetch_transactions(search_text=search.strip() or None,
                                         month_filter=None if all_months else self.ym,
                                         type_filter=type_filter, limit=limit)
        pending = {op["data"].get("uid") for op in self.pending()}
        out = []
        for r in rows:
            d = ledger.describe_entry(r)
            d["pending"] = d.get("tx_uid") in pending
            out.append(d)
        return out

    def transaction(self, uid: str) -> Optional[Dict[str, Any]]:
        row = ledger.get_transaction_by_uid(uid)
        return dict(row) if row else None

    def upcoming(self, days: int = 14) -> List[Dict[str, Any]]:
        """Najbliższe zlecenia stałe i raty (z komputerem — podgląd; bez komputera — księguje telefon)."""
        try:
            return [r for r in recurring.get_upcoming_recurring(10) if r["days"] <= days]
        except Exception:
            return []

    def insights(self) -> List[Any]:
        """Wskazówki doradcy (polski zapis liczb, bez skrótów klawiszowych programu na komputer)."""
        import re

        try:
            tips = analytics.get_insights(self.ym)
        except Exception:
            return []
        for t in tips:
            text = re.sub(r"(\d)\.(\d)", r"\1,\2", t.text.replace(" (Ctrl+R)", "").replace("(Ctrl+R)", ""))
            t.text = text.replace("odśwież, aby", "otwórz aplikację ponownie, aby")
        return tips

    def pending(self) -> List[Dict[str, Any]]:
        return [] if self.local_only else sync.pending_ops()

    # ------------------------------------------------------------------ analiza

    def trend(self, months: int = 6) -> List[Dict[str, Any]]:
        return analytics.get_trend(months, self.ym)

    def spending_by_envelope(self) -> List[Dict[str, Any]]:
        rows = [e for e in env_api.get_envelope_overview(self.ym) if e["spent"] > 0]
        rows.sort(key=lambda e: -e["spent"])
        return rows

    def top_shops(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Gdzie wydajesz najwięcej w miesiącu (sklep, suma, liczba wizyt)."""
        totals: Dict[str, Dict[str, Any]] = {}
        for r in ledger.fetch_transactions(month_filter=self.ym, type_filter=TYPE_EXPENSE):
            shop = (r["shop"] or "").strip()
            if not shop:
                continue
            item = totals.setdefault(shop.lower(), {"shop": shop, "total": 0.0, "count": 0})
            item["total"] += float(r["amount"] or 0)
            item["count"] += 1
        return sorted(totals.values(), key=lambda x: -x["total"])[:limit]

    def month_pace(self) -> Optional[Dict[str, float]]:
        """Bieżący miesiąc: wydano do dziś, średnio dziennie i prognoza do końca miesiąca."""
        import calendar

        today = date.today()
        if self.ym != today.strftime("%Y-%m"):
            return None
        days = calendar.monthrange(today.year, today.month)[1]
        s = env_api.get_budget_summary(self.ym)
        spent = float(s["expense"])
        per_day = spent / today.day
        return {"spent": spent, "per_day": per_day, "forecast": per_day * days, "day": today.day, "days": days,
                "available": float(s["available"]), "income": float(s["income"])}

    # ------------------------------------------------------------------ szybkie dodawanie

    def recent_shops(self, limit: int = 8) -> List[Dict[str, Any]]:
        """Najczęstsze ostatnio sklepy z ich ostatnią kopertą i kontem (podpowiedzi przy dodawaniu)."""
        seen: Dict[str, Dict[str, Any]] = {}
        for r in ledger.fetch_transactions(type_filter=TYPE_EXPENSE, limit=400):
            shop = (r["shop"] or "").strip()
            if not shop or (r["linked_group_id"] or "").startswith("loan-") \
                    or (r["description"] or "").startswith("[CYKLICZNE]"):
                continue  # raty i stałe płatności księgują się same — nie podpowiadamy ich
            key = shop.lower()
            if key not in seen:  # pierwszy = najnowszy wpis tego sklepu
                seen[key] = {"shop": shop, "category": r["category"], "account": r["account_type"], "count": 0}
            seen[key]["count"] += 1
        return sorted(seen.values(), key=lambda x: -x["count"])[:limit]

    def shop_hint(self, shop: str) -> Optional[Dict[str, Any]]:
        """Ostatnia koperta i konto użyte dla tego sklepu."""
        key = (shop or "").strip().lower()
        if not key:
            return None
        with storage.open_user_db() as conn:
            row = conn.execute("SELECT category, account_type FROM transactions WHERE type = ? AND "
                               "py_lower(shop) = ? ORDER BY date DESC, id DESC LIMIT 1", (TYPE_EXPENSE, key)).fetchone()
        return {"category": row["category"], "account": row["account_type"]} if row else None

    # ------------------------------------------------------------------ eksport

    def csv_bytes(self, whole: bool = False) -> Tuple[str, bytes, int]:
        """Transakcje w CSV (Excel): miesiąc albo wszystkie. Zwraca (nazwa pliku, dane, liczba wpisów)."""
        import tempfile
        from pathlib import Path

        from src.finance import data_io

        name = "MatrixFinance-transakcje" + ("" if whole else f"-{self.ym}") + ".csv"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / name
            count = data_io.export_transactions_csv(str(path), None if whole else self.ym)
            return name, path.read_bytes(), count

    def report_html(self) -> Tuple[str, bytes]:
        from src.finance import data_io

        return f"MatrixFinance-raport-{self.ym}.html", data_io.build_monthly_report_html(self.ym).encode("utf-8")

    # ------------------------------------------------------------------ automatyczne odkładanie

    def autosave_rules(self) -> List[Dict[str, Any]]:
        from src.finance import autosave

        goals = {str(g["id"]): g["name"] for g in self.goals()}
        out = []
        for row in autosave.get_autosave_rules():
            r = dict(row)
            r["text"] = autosave.describe_rule(row)
            r["target_label"] = goals.get(str(r["target"]), f"cel #{r['target']}") if r["target_kind"] == "goal" \
                else r["target"]
            out.append(r)
        return out

    @_changes
    def save_autosave(self, rule_id: Optional[int], source: str, mode: str, value: float, target_kind: str,
                      target: str, name: str = "") -> None:
        from src.finance import autosave

        self._ok(autosave.save_autosave_rule(source, mode, value, target_kind, target, name, True, rule_id))

    @_changes
    def delete_autosave(self, rule_id: int) -> None:
        from src.finance import autosave

        autosave.delete_autosave_rule(rule_id)

    @_changes
    def toggle_autosave(self, rule_id: int) -> bool:
        from src.finance import autosave

        return autosave.toggle_autosave_rule(rule_id)

    # ------------------------------------------------------------------ blokada PIN-em

    @property
    def has_pin(self) -> bool:
        return bool(self.setting(SET_PIN))

    @property
    def pin_length(self) -> int:
        try:
            return int(self.setting(SET_PIN_LEN) or 0)
        except ValueError:
            return 0

    @staticmethod
    def _pin_hash(pin: str, salt: bytes) -> str:
        import hashlib

        try:
            return hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, 60000).hex()
        except (AttributeError, ValueError):  # przeglądarka bez pbkdf2 — prostsza pętla
            digest = salt + pin.encode()
            for _ in range(20000):
                digest = hashlib.sha256(digest).digest()
            return digest.hex()

    def set_pin(self, pin: str) -> None:
        import os

        if not (pin.isdigit() and 4 <= len(pin) <= 8):
            raise ValueError("PIN to 4–8 cyfr.")
        salt = os.urandom(16)
        self.set_setting(SET_PIN, salt.hex() + "$" + self._pin_hash(pin, salt))
        self.set_setting(SET_PIN_LEN, str(len(pin)))

    def check_pin(self, pin: str) -> bool:
        import hmac

        stored = self.setting(SET_PIN)
        if not stored or "$" not in stored:
            return True
        salt_hex, digest = stored.split("$", 1)
        return hmac.compare_digest(self._pin_hash(pin or "", bytes.fromhex(salt_hex)), digest)

    def clear_pin(self) -> None:
        self.set_setting(SET_PIN, "")
        self.set_setting(SET_PIN_LEN, "")

    # ------------------------------------------------------------------ zmiany (operacje)

    @_changes
    def _do(self, op: str, data: Dict[str, Any]) -> None:
        if self.local_only:  # bez komputera / dane przykładowe: tylko lokalnie
            sync.apply_op(sync.make_op(op, data), strict=True)
        else:
            sync.record_op(op, data)

    def add_transaction(self, t_type: str, amount: float, category: Optional[str], account: str, shop: str = "",
                        desc: str = "", day: Optional[str] = None) -> str:
        uid = sync.new_uid("tx")
        self._do("tx.add", {"uid": uid, "date": day or date.today().isoformat(), "type": t_type,
                            "category": category, "account": account, "shop": shop, "amount": round(amount, 2),
                            "desc": desc})
        return uid

    def update_transaction(self, uid: str, t_type: str, amount: float, category: Optional[str], account: str,
                           shop: str, desc: str, day: str) -> None:
        self._do("tx.update", {"uid": uid, "date": day, "type": t_type, "category": category, "account": account,
                               "shop": shop, "amount": round(amount, 2), "desc": desc})

    def delete_transaction(self, uid: str) -> None:
        self._do("tx.delete", {"uid": uid})

    def transfer(self, source: str, target: str, amount: float, day: Optional[str] = None, note: str = "") -> None:
        self._do("transfer", {"group": sync.new_uid("trf"), "source": source, "target": target,
                              "amount": round(amount, 2), "date": day or date.today().isoformat(), "note": note})

    def goal_move(self, goal: Dict[str, Any], amount: float, account: str) -> None:
        """amount > 0: wpłata na cel, < 0: wypłata z celu."""
        self._do("goal.move", {"uid": sync.new_uid("tx"), "goal_id": goal["id"], "goal_name": goal["name"],
                               "amount": round(amount, 2), "account": account, "date": date.today().isoformat()})

    def goal_set(self, goal: Dict[str, Any], amount: float) -> None:
        self._do("goal.set", {"goal_id": goal["id"], "goal_name": goal["name"], "amount": round(amount, 2)})

    def set_balance(self, account: str, balance: float, note: str = "") -> None:
        self._do("account.set_balance", {"uid": sync.new_uid("tx"), "account": account, "balance": round(balance, 2),
                                         "date": date.today().isoformat(), "note": note or "Korekta salda (telefon)"})

    def envelope_adjust(self, category: str, amount: float, note: str = "") -> None:
        self._do("envelope.adjust", {"category": category, "ym": self.ym, "amount": round(amount, 2), "note": note})

    def envelope_set(self, category: str, remaining: float) -> None:
        self._do("envelope.set_remaining", {"category": category, "ym": self.ym, "remaining": round(remaining, 2),
                                            "note": "Korekta stanu koperty (telefon)"})

    def envelope_move(self, source: str, target: str, amount: float) -> None:
        self._do("envelope.move", {"source": source, "target": target, "ym": self.ym, "amount": round(amount, 2)})

    # ------------------------------------------------------------------ zarządzanie (tryb bez komputera)

    @staticmethod
    def _ok(result: Tuple[bool, str]) -> None:
        ok, msg = result
        if not ok:
            raise ValueError(msg or "Nie udało się zapisać.")

    @_changes
    def add_account(self, name: str, kind: str, balance: float = 0.0, institution: str = "",
                    rate: float = 0.0, custom_label: str = "", custom_group: str = "",
                    custom_flags: str = "") -> None:
        self._ok(acc_api.add_account(name.strip(), round(balance, 2), account_kind=kind, institution=institution,
                                     interest_rate=rate, opened_at=date.today().isoformat(),
                                     custom_label=custom_label or None, custom_group=custom_group or None,
                                     custom_flags=custom_flags or None))

    @_changes
    def add_deposit(self, name: str, amount: float, rate: float, months: int, start: str, source: Optional[str],
                    institution: str = "", kind: str = "deposit", auto_renew: bool = False,
                    return_to: Optional[str] = None) -> None:
        self._ok(acc_api.open_term_deposit(name.strip(), source, round(amount, 2), rate, int(months), start,
                                           institution=institution or None, kind=kind, auto_renew=auto_renew,
                                           return_to=return_to))

    @_changes
    def add_loan(self, name: str, amount: float, installments: int, first_due: str, pay_from: str,
                 rate: float = 0.0, payment: Optional[float] = None, kind: str = "installments",
                 category: str = "", disburse_to: Optional[str] = None, existing: bool = False,
                 institution: str = "") -> int:
        from src.finance import loans

        self._ok(loans.open_loan(name.strip(), amount, installments, first_due, pay_from, rate, payment, kind,
                                 category or None, disburse_to, institution or None, record_history=not existing))
        return self.process_due()[0]

    @_changes
    def update_account(self, name: str, new_name: str, institution: str, rate: Optional[float]) -> None:
        fields: Dict[str, Any] = {"institution": institution.strip() or None}
        if rate is not None:
            fields["interest_rate"] = rate
        self._ok(acc_api.update_account(name, new_name.strip() or name, **fields))

    @_changes
    def close_account(self, name: str, transfer_to: Optional[str]) -> None:
        self._ok(acc_api.close_account(name, transfer_to))

    @_changes
    def valuation(self, name: str, value: float) -> float:
        return acc_api.update_valuation(name, round(value, 2))

    @_changes
    def add_envelope(self, name: str, budget: float, rollover: bool) -> None:
        name = name.strip()
        if not name:
            raise ValueError("Podaj nazwę koperty.")
        self._ok(env_api.add_category(name, round(budget, 2), rollover))

    @_changes
    def update_envelope(self, c_id: int, name: str, budget: float, rollover: bool) -> None:
        name = name.strip()
        if not name:
            raise ValueError("Podaj nazwę koperty.")
        self._ok(env_api.update_category(c_id, name, round(budget, 2), rollover))

    @_changes
    def delete_envelope(self, c_id: int) -> None:
        env_api.delete_category(c_id)

    @_changes
    def add_goal(self, name: str, target: float, account: str, deadline: Optional[str]) -> None:
        if not name.strip():
            raise ValueError("Podaj nazwę celu.")
        self._ok(goals_api.add_piggy_bank(name.strip(), round(target, 2), account, deadline))

    @_changes
    def update_goal(self, goal_id: int, name: str, target: float, account: str, deadline: Optional[str]) -> None:
        if not name.strip():
            raise ValueError("Podaj nazwę celu.")
        self._ok(goals_api.update_piggy_bank(goal_id, name.strip(), round(target, 2), account, deadline))

    @_changes
    def delete_goal(self, goal_id: int) -> float:
        return goals_api.delete_piggy_bank(goal_id, refund=True)

    def recurring(self) -> List[Dict[str, Any]]:
        out = []
        for row in recurring.get_all_recurring():
            r = dict(row)
            r["next_due"] = recurring.get_recurring_next_due(row)
            r["active"] = int(r.get("is_registered") or 0) == 1
            out.append(r)
        out.sort(key=lambda r: (not r["active"], r["next_due"] or date.max, r["name"]))
        return out

    @_changes
    def save_recurring(self, r_id: Optional[int], name: str, r_type: str, amount: float, account: str,
                       cycle: str, start: str, category: Optional[str] = None, target_account: Optional[str] = None,
                       goal_id: Optional[int] = None) -> int:
        """Dodaje / zmienia zlecenie stałe i od razu księguje terminy, które już minęły. Zwraca ich liczbę."""
        if not name.strip():
            raise ValueError("Podaj nazwę płatności.")
        if amount <= 0:
            raise ValueError("Kwota musi być większa od zera.")
        args = (name.strip(), round(amount, 2), r_type, category if r_type in (TYPE_EXPENSE, TYPE_INCOME) else None,
                account, cycle, start, True, goal_id if r_type == "Na Skarbonkę" else None,
                target_account if r_type == "Przelew" else None)
        self._ok(recurring.update_recurring(r_id, *args) if r_id else recurring.add_recurring(*args))
        return self.process_due()[0]

    @_changes
    def delete_recurring(self, r_id: int) -> None:
        self._ok(recurring.delete_recurring(r_id))

    @_changes
    def toggle_recurring(self, r_id: int) -> bool:
        return recurring.toggle_recurring_pause(r_id)

    @_changes
    def process_due(self) -> Tuple[int, List[str]]:
        """Bez komputera: księguje zaległe zlecenia stałe i raty, rozlicza lokaty po terminie."""
        if not self.local_only:
            return 0, []
        settled = acc_api.settle_matured_deposits()
        return recurring.process_due_payments(), settled

    # ------------------------------------------------------------------ tryb pracy

    @_changes
    def start_solo(self, fresh: bool) -> None:
        """Przejście na tryb „Bez komputera”. fresh=True: czysta baza (konta Karta i Gotówka, koperty)."""
        if fresh or self.is_demo:
            with storage.open_user_db() as conn:  # połączenie z OneDrive zostaje
                keep = [tuple(r) for r in conn.execute("SELECT key, value FROM settings WHERE key LIKE 'local_od_%'")]
            self.reset_all()
            for key, value in keep:
                self.set_setting(key, value)
            with storage.open_user_db(write=True) as conn:
                conn.execute("UPDATE accounts SET account_kind = 'cash' WHERE name = 'Gotówka' "
                             "AND COALESCE(account_kind, 'checking') = 'checking'")
        with storage.open_user_db(write=True) as conn:
            conn.execute("DELETE FROM sync_outbox")
        self.set_setting(SET_DEMO, "0")
        self.set_setting(SET_MODE, "solo")

    def use_pc_mode(self) -> None:
        """Powrót do pracy z komputerem: dane telefonu zastąpi najbliższe pobranie z komputera."""
        self.set_setting(SET_MODE, "pc")

    # ------------------------------------------------------------------ kopia zapasowa (.mfx)

    def backup_bytes(self, password: Optional[str] = None) -> bytes:
        """Zaszyfrowana kopia wszystkich danych — ten sam format, co eksport .mfx programu na komputer."""
        import json

        from src.finance import data_io
        from src.utils.crypto_utils import encrypt_bytes

        password = password or self.password
        if len(password or "") < 6:
            raise ValueError("Ustaw hasło kopii zapasowej (co najmniej 6 znaków).")
        payload = json.dumps(data_io.export_data_dict(), ensure_ascii=False).encode("utf-8")
        return encrypt_bytes(payload, password)

    def data_digest(self) -> str:
        gen, digest = self._digest_cache
        if gen != self._generation:  # liczone raz po każdej zmianie, nie przy każdym odświeżeniu ekranu
            digest = sync.data_fingerprint()
            self._digest_cache = (self._generation, digest)
        return digest

    def has_transactions(self) -> bool:
        """Czy jest jakikolwiek wpis (w dowolnym miesiącu)."""
        with storage.open_user_db() as conn:
            return conn.execute("SELECT 1 FROM transactions LIMIT 1").fetchone() is not None

    @property
    def backup_needed(self) -> bool:
        """Dane zmieniły się od ostatniej kopii."""
        return self.setting(SET_BACKUP_DIGEST) != self.data_digest()

    def mark_backup(self) -> None:
        self.set_setting(SET_BACKUP_AT, storage.now_iso())
        self.set_setting(SET_BACKUP_DIGEST, self.data_digest())

    @property
    def backup_at(self) -> str:
        return self.setting(SET_BACKUP_AT)

    def backup_age_days(self) -> Optional[int]:
        stamp = self.backup_at
        if not stamp:
            return None
        try:
            return (date.today() - date.fromisoformat(stamp[:10])).days
        except ValueError:
            return None

    @_changes
    def restore_backup(self, raw: bytes, password: str) -> Dict[str, int]:
        """Wczytuje kopię (.mfx z telefonu albo eksport z komputera) — ZASTĘPUJE dane telefonu."""
        import json

        from src.finance import data_io
        from src.utils.crypto_utils import decrypt_bytes

        data = None
        if raw.lstrip().startswith(b"{"):
            try:
                data = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, ValueError):
                data = None
        if data is None:
            try:
                data = json.loads(decrypt_bytes(raw, password).decode("utf-8"))
            except ValueError as e:
                raise ValueError("Złe hasło albo uszkodzony plik kopii.") from e
        if data.get("format") != data_io.EXPORT_FORMAT or not isinstance(data.get("tables"), dict):
            raise ValueError("To nie jest kopia Matrix Finance (.mfx).")
        counts = data_io.import_data_dict(data)
        with storage.open_user_db(write=True) as conn:
            conn.execute("DELETE FROM sync_outbox")
        self.set_setting(SET_DEMO, "0")
        self.set_setting(SET_MODE, "solo")
        if len(password or "") >= 6:
            self.set_password(password)
        self.mark_backup()  # dane = kopia
        return counts

    # ------------------------------------------------------------------ synchronizacja

    @_changes
    def import_snapshot(self, raw: bytes, password: Optional[str] = None) -> sync.SnapshotImport:
        password = password or self.password
        if self.is_demo:  # pierwsze prawdziwe dane: koniec trybu demonstracyjnego
            sync.import_snapshot_bytes(raw, password)  # sprawdzenie hasła przed wyczyszczeniem
            with storage.open_user_db(write=True) as conn:
                conn.execute("DELETE FROM sync_outbox")
            self.set_setting(SET_DEMO, "0")
        result = sync.import_snapshot_bytes(raw, password)
        if password:
            self.set_password(password)
        return result

    def ops_file(self) -> Tuple[str, bytes]:
        return sync.ops_file_name(), sync.build_ops_file(self.password, "Telefon")

    def mark_sent(self) -> None:
        self.set_setting(SET_SENT_AT, storage.now_iso())
        self.set_setting(SET_SENT_COUNT, str(len(self.pending())))

    # ------------------------------------------------------------------ dane przykładowe / reset

    @_changes
    def load_demo(self) -> None:
        storage.reset_user_db_hard()
        with storage.open_user_db(write=True) as conn:
            conn.execute("DELETE FROM sync_outbox")
            conn.execute("UPDATE accounts SET balance = 4200 WHERE name = 'Karta'")
            conn.execute("UPDATE accounts SET balance = 300 WHERE name = 'Gotówka'")
        self.set_setting(SET_DEMO, "1")
        today = date.today()
        ym = today.strftime("%Y-%m")
        with storage.open_user_db(write=True) as conn:
            for name, limit, roll in [("Jedzenie", 1400, 1), ("Transport", 400, 0), ("Rachunki", 900, 0),
                                      ("Rozrywka", 300, 1), ("Zdrowie", 200, 0), ("Zakupy", 500, 0)]:
                conn.execute("UPDATE categories SET limit_amount=?, rollover=?, rollover_since=? WHERE name=?",
                             (limit, roll, ym, name))
        acc_api.add_account("Revolut", 850, account_kind="ewallet", institution="Revolut", interest_rate=3.0)
        acc_api.add_account("Oszczędnościowe", 8000, account_kind="savings", institution="mBank", interest_rate=5.0)
        acc_api.add_account("IKE ETF", 3240, account_kind="ike", institution="XTB", yearly_limit=26000)
        goals_api.add_piggy_bank("Wakacje 2027", 6000, "Karta", target_date=f"{today.year + 1}-06-01")
        goals_api.add_piggy_bank("Poduszka finansowa", 10000, "Karta")
        ledger.add_transaction(f"{ym}-01", TYPE_INCOME, "Wynagrodzenie", "Karta", "Pensja", 8200, "", True,
                               apply_autosave=False)
        rnd = random.Random(7)
        shops = {"Jedzenie": (["Biedronka", "Lidl", "Żabka", "Piekarnia"], 15, 95, 9),
                 "Transport": (["Orlen", "Jakdojade"], 20, 90, 3), "Rachunki": (["PGE", "Orange"], 60, 180, 2),
                 "Rozrywka": (["Kino", "Spotify"], 20, 55, 3), "Zdrowie": (["Apteka"], 12, 45, 2),
                 "Zakupy": (["Allegro", "IKEA"], 30, 140, 3)}
        for cat, (names, low, high, count) in shops.items():
            for _ in range(count):
                day = min(28, rnd.randint(1, max(1, today.day)))
                ledger.add_transaction(f"{ym}-{day:02d}", TYPE_EXPENSE, cat, rnd.choice(["Karta", "Karta", "Revolut"]),
                                       rnd.choice(names), round(rnd.uniform(low, high), 2), "", True)
        from src.finance import loans

        loans.open_loan("Ekspres na raty", 1500, 10, (today.replace(day=1) - timedelta(days=40)).isoformat(),
                        "Karta", 0.0, category="Raty", day=(today - timedelta(days=45)).isoformat())
        loans.process_due_installments(today)
        goals_api.update_piggy_bank_balance(1, 1800, "Karta", True)
        goals_api.update_piggy_bank_balance(2, 4200, "Karta", True)
        self.ym = ym

    @_changes
    def reset_all(self) -> None:
        keep_theme = self.theme
        storage.reset_user_db_hard()
        with storage.open_user_db(write=True) as conn:
            conn.execute("DELETE FROM sync_outbox")
            conn.execute("DELETE FROM settings WHERE key LIKE 'sync_%' OR key LIKE 'local_%'")
        self.set_theme(keep_theme)


def parse_money(raw: str) -> Optional[float]:
    return parse_amount((raw or "").replace("zł", "").strip())


def today_iso() -> str:
    return date.today().isoformat()


def yesterday_iso() -> str:
    return (date.today() - timedelta(days=1)).isoformat()
