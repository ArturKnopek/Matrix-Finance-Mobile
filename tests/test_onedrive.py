"""OneDrive bez wybierania plików — z atrapą serwerów Microsoft (logowanie kodem, Graph, pliki)."""
from __future__ import annotations

import json
import urllib.parse
import uuid

import pytest

from mf_mobile import onedrive
from mf_mobile.store import Store
from src.finance import accounts, storage, sync

PASSWORD = "haslo-sync"


class FakeMicrosoft:
    """Minimalna atrapa: /devicecode, /token, /me/drive, pliki w folderach (PUT/GET), tworzenie folderów."""

    def __init__(self) -> None:
        self.files: dict = {}  # "MatrixFinance/plik" -> bytes
        self.folders = set()
        self.polls = 0
        self.tokens_issued = 0
        self.valid_tokens = set()
        self.requests = []

    def __call__(self, method, url, data, headers):
        self.requests.append((method, url))
        if url.endswith("/devicecode"):
            return 200, json.dumps({"user_code": "ABCD-1234", "device_code": "dev", "interval": 0,
                                    "expires_in": 900, "verification_uri": "https://microsoft.com/devicelogin"}).encode()
        if url.endswith("/token"):
            form = dict(urllib.parse.parse_qsl(data.decode()))
            if form["grant_type"].endswith("device_code"):
                self.polls += 1
                if self.polls < 2:
                    return 400, b'{"error": "authorization_pending"}'
            elif form.get("refresh_token") != "refresh-ok":
                return 400, b'{"error": "invalid_grant"}'
            token = f"t{uuid.uuid4().hex[:6]}"
            self.valid_tokens.add(token)
            return 200, json.dumps({"access_token": token, "refresh_token": "refresh-ok", "expires_in": 3600}).encode()
        if headers["Authorization"].split()[1] not in self.valid_tokens:
            return 401, b'{"error": {"code": "InvalidAuthenticationToken"}}'
        path = urllib.parse.unquote(url.split("/v1.0")[1])
        if path == "/me/drive":
            return 200, b'{"owner": {"user": {"displayName": "Jan Testowy"}}}'
        if path.startswith("/me/drive/root:/") and path.endswith(":/content"):
            key = path[len("/me/drive/root:/"):-len(":/content")]
            folder = key.rsplit("/", 1)[0]
            if method == "GET":
                return (200, self.files[key]) if key in self.files else (404, b"{}")
            if folder not in self.folders:
                return 404, b'{"error": {"code": "itemNotFound"}}'
            self.files[key] = data
            return 201, b"{}"
        if path.startswith("/me/drive/root:/") and method == "GET":
            return (200, b"{}") if path[len("/me/drive/root:/"):] in self.folders else (404, b"{}")
        if path.endswith("/children") and method == "POST":
            self.folders.add(json.loads(data)["name"])
            return 201, b"{}"
        return 400, b"{}"


@pytest.fixture()
def phone():
    s = Store()
    s.reset_all()
    s.set_password(PASSWORD)
    return s


def _connect(store, fake) -> onedrive.OneDrive:
    od = onedrive.OneDrive(store, http=fake)
    od.set_client_id("00000000-test")
    login = od.start_login()
    assert login.user_code == "ABCD-1234"
    assert od.poll_login(login) is False  # czekamy na zalogowanie
    assert od.poll_login(login) is True
    return od


def test_login_remembers_location_and_account(phone):
    fake = FakeMicrosoft()
    od = _connect(phone, fake)
    assert od.connected and od.account == "Jan Testowy"
    assert od.location() == "OneDrive › MatrixFinance"
    od.set_folder("Finanse/Matrix")
    assert od.location() == "OneDrive › Finanse › Matrix"
    od2 = onedrive.OneDrive(phone, http=fake)  # po ponownym uruchomieniu aplikacji
    assert od2.connected and od2.folder == "Finanse/Matrix"
    od2.disconnect()
    assert not od2.connected


def test_missing_client_id_and_expired_login(phone):
    od = onedrive.OneDrive(phone, http=FakeMicrosoft())
    if not od.client_id:
        with pytest.raises(onedrive.OneDriveError):
            od.start_login()
    od.set_client_id("x")
    phone.set_setting(onedrive.SET_REFRESH, "stary-token")
    with pytest.raises(onedrive.OneDriveError, match="wygasło"):
        od.download("cokolwiek")
    assert not od.connected


def test_full_round_trip_through_onedrive(phone, tmp_path):
    fake = FakeMicrosoft()
    # komputer: dane + migawka; OneDrive na komputerze = folder synchronizowany z „chmurą” (atrapą)
    pc = uuid.uuid4().hex
    storage.init_user_db(storage.set_active_user_db(pc), 2000, 100)
    sync.set_sync_setting(sync.SET_PASSWORD, PASSWORD)
    folder = tmp_path / "OneDrive" / "MatrixFinance"
    sync.sync_folder_now(folder)
    fake.folders.add("MatrixFinance")
    fake.files["MatrixFinance/MatrixFinance.mfsync"] = (folder / sync.SNAPSHOT_FILE).read_bytes()

    storage.set_active_user_db("telefon")
    od = _connect(phone, fake)
    report = od.sync_now()
    assert report.downloaded and report.uploaded == 0
    phone.add_transaction("Wydatek", 25, "Jedzenie", "Karta", "Żabka")
    phone.add_transaction("Wydatek", 10, "Jedzenie", "Karta", "Kiosk")
    assert od.sync_now(upload_only=True).uploaded == 2
    phone.add_transaction("Wydatek", 5, "Jedzenie", "Karta", "Bułki")
    od.sync_now(upload_only=True)
    ops_files = [k for k in fake.files if k.endswith(".mfops")]
    assert ops_files == [f"MatrixFinance/{sync.ops_file_name()}"]  # zawsze ten sam plik (nadpisywany)

    # komputer: OneDrive ściąga plik do folderu, program dopisuje zmiany i zapisuje migawkę
    storage.set_active_user_db(pc)
    (folder / sync.ops_file_name()).write_bytes(fake.files[ops_files[0]])
    result = sync.sync_folder_now(folder)
    assert len(result.applied) == 3
    fake.files["MatrixFinance/MatrixFinance.mfsync"] = (folder / sync.SNAPSHOT_FILE).read_bytes()
    pc_balance = accounts.get_account_balance("Karta")

    storage.set_active_user_db("telefon")
    report = od.sync_now()
    assert report.confirmed == 3 and phone.pending() == []
    assert {a["name"]: a["balance"] for a in phone.accounts()}["Karta"] == pytest.approx(pc_balance)


def test_folder_created_when_missing_and_snapshot_absent(phone):
    fake = FakeMicrosoft()
    od = _connect(phone, fake)
    phone.add_transaction("Wydatek", 3, "Jedzenie", "Karta", "x")
    report = od.sync_now()
    assert "MatrixFinance" in fake.folders and report.uploaded == 1
    assert report.missing_snapshot and "włącz synchronizację" in report.text()


def test_expired_access_token_is_refreshed(phone):
    fake = FakeMicrosoft()
    od = _connect(phone, fake)
    fake.valid_tokens.clear()  # serwer unieważnił token
    assert od.download("brak.plik") is None  # 401 -> odświeżenie -> 404
