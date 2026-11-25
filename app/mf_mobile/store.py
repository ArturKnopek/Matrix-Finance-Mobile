"""
Warstwa danych aplikacji mobilnej — cienka nakładka na wspólny silnik (app/src).

Każda zmiana danych przechodzi przez `sync.record_op`: zostaje od razu zastosowana
na telefonie i odłożona do wysłania na komputer (plik .mfops w OneDrive).
W trybie demonstracyjnym zmiany są tylko lokalne (nic nie trafia do komputera).
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
SET_THEME = "local_theme"
SET_DEMO = "local_demo"
SET_SENT_AT = "local_ops_sent_at"
SET_SENT_COUNT = "local_ops_sent_count"

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


class Store:
    def __init__(self) -> None:
        storage.init_auth_db()
        self.db_path = storage.set_active_user_db(PHONE_USER)
        storage.init_user_db(self.db_path, 0.0, 0.0)
        self.ym = date.today().strftime("%Y-%m")

    # ------------------------------------------------------------------ ustawienia / stan

    def setting(self, key: str, default: str = "") -> str:
        return sync.get_sync_setting(key, default)

    def set_setting(self, key: str, value: Any) -> None:
        sync.set_sync_setting(key, value)

    @property
    def is_demo(self) -> bool:
        return self.setting(SET_DEMO) == "1"

    @property
    def has_data(self) -> bool:
        return self.is_demo or bool(self.setting(sync.SET_SNAPSHOT_AT))

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

    def transactions(self, search: str = "", kind: str = "all", limit: Optional[int] = None) -> List[Dict[str, Any]]:
        type_filter = {"expense": TYPE_EXPENSE, "income": TYPE_INCOME, "transfer": ledger.TRANSFER}.get(kind)
        rows = ledger.fetch_transactions(search_text=search.strip() or None, month_filter=self.ym,
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
        """Zlecenia stałe z komputera (księguje je komputer) — na telefonie tylko podgląd."""
        try:
            return [r for r in recurring.get_upcoming_recurring(10) if r["days"] <= days]
        except Exception:
            return []

    def insights(self) -> List[Any]:
        try:
            return analytics.get_insights(self.ym)
        except Exception:
            return []

    def pending(self) -> List[Dict[str, Any]]:
        return [] if self.is_demo else sync.pending_ops()

    # ------------------------------------------------------------------ zmiany (operacje)

    def _do(self, op: str, data: Dict[str, Any]) -> None:
        if self.is_demo:  # dane przykładowe: tylko lokalnie
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

    # ------------------------------------------------------------------ synchronizacja

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
