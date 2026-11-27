"""
Bezpośrednie połączenie z OneDrive (Microsoft Graph) — bez wybierania plików przy każdej synchronizacji.

* Logowanie raz: „kod urządzenia” (aplikacja pokazuje kod, wpisujesz go na microsoft.com/devicelogin).
  Aplikacja zapamiętuje token odświeżania (w prywatnej bazie aplikacji na telefonie).
* Zapamiętany folder (domyślnie „MatrixFinance” — ten sam, co na komputerze):
    - pobiera  OneDrive/<folder>/MatrixFinance.mfsync   (dane z komputera),
    - zapisuje OneDrive/<folder>/telefon-XXXXXX.mfops   (zawsze ten sam plik — nadpisywany).
* Wymaga identyfikatora aplikacji (Client ID) z rejestracji w Microsoft Entra (instrukcja w README):
  wpisanego w Ustawieniach synchronizacji albo wbudowanego w pliku onedrive_client_id.txt.

Uprawnienia: Files.ReadWrite (pliki w OneDrive), offline_access (odświeżanie logowania), User.Read.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

from src.finance import sync

GRAPH = "https://graph.microsoft.com/v1.0"
LOGIN = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0"
SCOPES = "Files.ReadWrite offline_access User.Read"
DEFAULT_FOLDER = "MatrixFinance"
BUNDLED_CLIENT_ID = Path(__file__).with_name("onedrive_client_id.txt")

SET_CLIENT_ID = "local_od_client_id"
SET_TENANT = "local_od_tenant"
SET_FOLDER = "local_od_folder"
SET_REFRESH = "local_od_refresh"
SET_ACCOUNT = "local_od_account"
SET_LAST = "local_od_last_sync"
SET_AUTO = "local_od_auto"


class OneDriveError(Exception):
    """Błąd połączenia z OneDrive (komunikat dla użytkownika)."""


@dataclass
class DeviceLogin:
    user_code: str
    verification_uri: str
    device_code: str
    interval: int
    expires_at: float
    message: str = ""


@dataclass
class SyncReport:
    uploaded: int = 0
    downloaded: bool = False
    confirmed: int = 0
    rejected: list = None  # type: ignore[assignment]
    snapshot_at: str = ""
    missing_snapshot: bool = False

    def text(self) -> str:
        parts = []
        if self.uploaded:
            parts.append(f"wysłano zmian: {self.uploaded}")
        if self.downloaded:
            parts.append(f"pobrano dane z {sync.format_stamp(self.snapshot_at)}")
            if self.confirmed:
                parts.append(f"potwierdzone przez komputer: {self.confirmed}")
        elif self.missing_snapshot:
            parts.append("brak pliku MatrixFinance.mfsync w folderze — włącz synchronizację na komputerze")
        return "; ".join(parts) or "bez zmian"


def _ssl_context() -> Any:
    import ssl

    try:  # telefon: certyfikaty z pakietu certifi (system Androida nie jest widoczny dla Pythona)
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


class OneDrive:
    def __init__(self, store: Any, http: Optional[Callable[..., Tuple[int, bytes]]] = None) -> None:
        self.store = store
        self._http_impl = http or self._urllib
        self._access: Tuple[str, float] = ("", 0.0)

    # ------------------------------------------------------------------ ustawienia

    @property
    def client_id(self) -> str:
        own = self.store.setting(SET_CLIENT_ID).strip()
        if own:
            return own
        try:
            return BUNDLED_CLIENT_ID.read_text(encoding="utf-8").strip()
        except OSError:
            return ""

    def set_client_id(self, value: str) -> None:
        self.store.set_setting(SET_CLIENT_ID, (value or "").strip())

    @property
    def tenant(self) -> str:
        return self.store.setting(SET_TENANT, "common") or "common"

    @property
    def folder(self) -> str:
        return (self.store.setting(SET_FOLDER) or DEFAULT_FOLDER).strip("/ ") or DEFAULT_FOLDER

    def set_folder(self, value: str) -> None:
        self.store.set_setting(SET_FOLDER, (value or DEFAULT_FOLDER).strip("/ "))

    @property
    def connected(self) -> bool:
        return bool(self.store.setting(SET_REFRESH))

    @property
    def account(self) -> str:
        return self.store.setting(SET_ACCOUNT)

    @property
    def auto(self) -> bool:
        return self.store.setting(SET_AUTO, "1") == "1"

    def set_auto(self, enabled: bool) -> None:
        self.store.set_setting(SET_AUTO, "1" if enabled else "0")

    def location(self) -> str:
        return f"OneDrive › {self.folder.replace('/', ' › ')}"

    def ops_name(self) -> str:
        return sync.ops_file_name()

    def disconnect(self) -> None:
        for key in (SET_REFRESH, SET_ACCOUNT):
            self.store.set_setting(key, "")
        self._access = ("", 0.0)

    # ------------------------------------------------------------------ logowanie (kod urządzenia)

    def start_login(self) -> DeviceLogin:
        if not self.client_id:
            raise OneDriveError("Brak identyfikatora aplikacji (Client ID) — patrz instrukcja poniżej.")
        status, body = self._form(f"{LOGIN.format(tenant=self.tenant)}/devicecode",
                                  {"client_id": self.client_id, "scope": SCOPES})
        data = _json(body)
        if status != 200:
            raise OneDriveError(_auth_error(data, "Nie udało się rozpocząć logowania"))
        return DeviceLogin(data["user_code"], data.get("verification_uri") or "https://microsoft.com/devicelogin",
                           data["device_code"], int(data.get("interval") or 5),
                           time.time() + int(data.get("expires_in") or 900), data.get("message", ""))

    def poll_login(self, login: DeviceLogin) -> bool:
        """True = zalogowano; False = jeszcze czekamy. Błąd (odmowa, wygaśnięcie) — wyjątek."""
        if time.time() > login.expires_at:
            raise OneDriveError("Kod wygasł — zacznij logowanie od nowa.")
        status, body = self._form(f"{LOGIN.format(tenant=self.tenant)}/token", {
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code", "client_id": self.client_id,
            "device_code": login.device_code})
        data = _json(body)
        if status == 200:
            self._save_tokens(data)
            self._load_account()
            return True
        if data.get("error") in ("authorization_pending", "slow_down"):
            return False
        raise OneDriveError(_auth_error(data, "Logowanie nie powiodło się"))

    def _save_tokens(self, data: Dict[str, Any]) -> None:
        self._access = (data["access_token"], time.time() + int(data.get("expires_in") or 3600) - 120)
        if data.get("refresh_token"):
            self.store.set_setting(SET_REFRESH, data["refresh_token"])

    def _token(self) -> str:
        token, valid_until = self._access
        if token and time.time() < valid_until:
            return token
        refresh = self.store.setting(SET_REFRESH)
        if not refresh:
            raise OneDriveError("Nie połączono z OneDrive.")
        status, body = self._form(f"{LOGIN.format(tenant=self.tenant)}/token", {
            "grant_type": "refresh_token", "client_id": self.client_id, "refresh_token": refresh, "scope": SCOPES})
        data = _json(body)
        if status != 200:
            if data.get("error") in ("invalid_grant", "interaction_required"):
                self.disconnect()
                raise OneDriveError("Logowanie do OneDrive wygasło — połącz ponownie.")
            raise OneDriveError(_auth_error(data, "Nie udało się odświeżyć logowania"))
        self._save_tokens(data)
        return self._access[0]

    def _load_account(self) -> None:
        status, body = self._graph("GET", "/me/drive")
        if status == 200:
            owner = (_json(body).get("owner") or {}).get("user") or {}
            self.store.set_setting(SET_ACCOUNT, owner.get("displayName") or owner.get("email") or "konto Microsoft")

    # ------------------------------------------------------------------ pliki

    def _item(self, name: str) -> str:
        path = "/".join(urllib.parse.quote(part) for part in f"{self.folder}/{name}".split("/") if part)
        return f"/me/drive/root:/{path}:"

    def download(self, name: str) -> Optional[bytes]:
        status, body = self._graph("GET", f"{self._item(name)}/content")
        if status == 404:
            return None
        if status != 200:
            raise OneDriveError(f"Nie udało się pobrać {name} (błąd {status}).")
        return body

    def upload(self, name: str, data: bytes) -> None:
        """Zapis do zapamiętanego folderu — zawsze ten sam plik (zastępowany)."""
        status, body = self._graph("PUT", f"{self._item(name)}/content", data,
                                   {"Content-Type": "application/octet-stream"})
        if status == 404 or (status == 409 and b"parent" in body.lower()):
            self._ensure_folder()
            status, body = self._graph("PUT", f"{self._item(name)}/content", data,
                                       {"Content-Type": "application/octet-stream"})
        if status not in (200, 201):
            raise OneDriveError(f"Nie udało się zapisać {name} w OneDrive (błąd {status}).")

    def _ensure_folder(self) -> None:
        parent = "/me/drive/root"
        built = ""
        for part in self.folder.split("/"):
            built = f"{built}/{part}" if built else part
            status, _ = self._graph("GET", f"/me/drive/root:/{urllib.parse.quote(built)}")
            if status == 404:
                payload = json.dumps({"name": part, "folder": {}, "@microsoft.graph.conflictBehavior": "fail"})
                status, _ = self._graph("POST", f"{parent}/children", payload.encode(),
                                        {"Content-Type": "application/json"})
                if status not in (200, 201, 409):
                    raise OneDriveError(f"Nie udało się utworzyć folderu {built} w OneDrive (błąd {status}).")
            parent = f"/me/drive/root:/{urllib.parse.quote(built)}:"

    # ------------------------------------------------------------------ synchronizacja

    def sync_now(self, upload_only: bool = False) -> SyncReport:
        """Wysyła zmiany telefonu (nadpisując jego plik) i pobiera dane z komputera."""
        store = self.store
        report = SyncReport(rejected=[])
        if not store.password:
            raise OneDriveError("Ustaw hasło synchronizacji (to samo co na komputerze).")
        pending = store.pending()
        if pending:
            name, data = store.ops_file()
            self.upload(name, data)
            store.mark_sent()
            report.uploaded = len(pending)
        if not upload_only:
            raw = self.download(sync.SNAPSHOT_FILE)
            if raw is None:
                report.missing_snapshot = True
            else:
                result = store.import_snapshot(raw)
                report.downloaded = True
                report.confirmed = result.confirmed
                report.rejected = result.rejected + result.failed
                report.snapshot_at = result.created_at
        store.set_setting(SET_LAST, sync.now_iso())
        return report

    # ------------------------------------------------------------------ HTTP

    def _graph(self, method: str, path: str, data: Optional[bytes] = None,
               headers: Optional[Dict[str, str]] = None) -> Tuple[int, bytes]:
        hdrs = {"Authorization": f"Bearer {self._token()}", **(headers or {})}
        status, body = self._http_impl(method, GRAPH + path, data, hdrs)
        if status == 401:  # token unieważniony wcześniej niż przewidywano — jedna ponowna próba
            self._access = ("", 0.0)
            hdrs["Authorization"] = f"Bearer {self._token()}"
            status, body = self._http_impl(method, GRAPH + path, data, hdrs)
        return status, body

    def _form(self, url: str, fields: Dict[str, str]) -> Tuple[int, bytes]:
        return self._http_impl("POST", url, urllib.parse.urlencode(fields).encode(),
                               {"Content-Type": "application/x-www-form-urlencoded"})

    @staticmethod
    def _urllib(method: str, url: str, data: Optional[bytes], headers: Dict[str, str]) -> Tuple[int, bytes]:
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=40, context=_ssl_context()) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read() or b""
        except urllib.error.URLError as e:
            raise OneDriveError(f"Brak połączenia z internetem ({e.reason}).")


def _json(body: bytes) -> Dict[str, Any]:
    try:
        return json.loads(body.decode("utf-8") or "{}")
    except (ValueError, UnicodeDecodeError):
        return {}


def _auth_error(data: Dict[str, Any], prefix: str) -> str:
    code = data.get("error", "")
    hints = {
        "invalid_client": "zły identyfikator aplikacji (Client ID) albo w rejestracji nie włączono "
                          "„Zezwalaj na przepływy klientów publicznych”",
        "unauthorized_client": "aplikacja nie dopuszcza tego typu kont — w rejestracji wybierz konta osobiste Microsoft",
        "authorization_declined": "odmówiono dostępu",
        "expired_token": "kod wygasł — zacznij od nowa",
    }
    detail = hints.get(code) or (data.get("error_description") or "").split("\r\n")[0] or code or "nieznany błąd"
    return f"{prefix}: {detail}."
