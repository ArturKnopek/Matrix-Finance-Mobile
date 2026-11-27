# Matrix Finance Mobile (Android)

Aplikacja na telefon do programu **[Matrix Finance](https://github.com/ArturKnopek/Matrix-Finance-TUI)** — budżet domowy połączony z oszczędzaniem kopertowym. Na telefonie szybko dodajesz wydatki i sprawdzasz koperty, a dane łączą się z programem na komputerze przez **zaszyfrowany plik w Twoim OneDrive** (bez żadnego serwera).

> To osobny projekt. Program na komputer (Linux / Windows z instalatorem) jest w repozytorium **Matrix-Finance-TUI**; oba korzystają z tego samego silnika budżetu (salda, koperty, synchronizacja).

## Instalacja

**Android:** pobierz `MatrixFinance-<wersja>.apk` z zakładki **Releases** i otwórz go na telefonie (Android zapyta o zgodę na instalację z tego źródła).

**iPhone / iPad:** otwórz w **Safari** stronę **https://arturknopek.github.io/Matrix-Finance-Mobile/** → przycisk *Udostępnij* → **„Do ekranu początkowego”**. Na ekranie pojawi się ikona Matrix Finance, a aplikacja uruchamia się jak zwykła (bez paska Safari). Nie trzeba konta deweloperskiego Apple ani komputera. Szczegóły i ograniczenia — niżej.

## Co potrafi

| Ekran | Funkcje |
|---|---|
| **Pulpit** | do wydania w kopertach, bilans miesiąca, wydatki, majątek; koperty z paskami (zielony → żółty → czerwony), ostatnie wpisy, nadchodzące płatności, cele |
| **Transakcje** | lista dzień po dniu, wyszukiwanie, filtr (wydatki / dochody / inne), edycja i usuwanie |
| **Koperty** | ile zostało, wykorzystanie, koperty elastyczne (↻), wydatek z koperty, **korekty** („ustaw zostało”, dołóż, odejmij) i **przesuwanie między kopertami** |
| **Konta** | majątek netto, konta wg grup, **przelewy**, **korekta salda**; **kredyty i raty** (grupa Zobowiązania): rata, postęp spłaty, następna rata, nadpłata, „ile zostało” |
| **Cele** | postęp, plan miesięczny, wpłata / wypłata, korekta stanu |
| **+** | nowy wydatek/dochód: kwota, koperta (z informacją ile zostało), konto, sklep, data |

Motywy kolorów jak na komputerze (Matrix, Bursztyn, Cyber, Fiolet, Karmazyn, Mono) i dane przykładowe do wypróbowania.

## OneDrive bez wybierania plików (Android, zalecane)

Aplikacja łączy się z Twoim OneDrive **raz** i **zapamiętuje lokalizację** — w *Synchronizacji* widać: **„Obecna lokalizacja: OneDrive › MatrixFinance”**. Potem:
* zmiany z telefonu zapisują się **zawsze do tego samego pliku** `telefon-XXXXXX.mfops` (zastępowany, bez kopii),
* dane z komputera pobierają się z `MatrixFinance.mfsync` w tym samym folderze,
* **automatycznie** przy uruchomieniu i po każdej zmianie (można wyłączyć) albo przyciskiem *Synchronizuj teraz*,
* folder można zmienić (*Folder w OneDrive → Zapamiętaj*), np. na `Finanse/Matrix` — ustaw ten sam na komputerze.

**Jednorazowo potrzebny jest „identyfikator aplikacji” (Client ID)** — Microsoft wymaga, by każda aplikacja łącząca się z OneDrive była zarejestrowana:
1. Wejdź na **portal.azure.com** i zaloguj się kontem Microsoft (tym z OneDrive) → **Microsoft Entra ID** → **Rejestracje aplikacji** → **Nowa rejestracja**.
2. Nazwa: `Matrix Finance`. Obsługiwane typy kont: **„Konta w dowolnym katalogu organizacyjnym i osobiste konta Microsoft”**. *Zarejestruj*.
3. **Uwierzytelnianie** → *Zaawansowane ustawienia* → **„Zezwalaj na przepływy klientów publicznych” = Tak** → *Zapisz*.
4. Skopiuj **„Identyfikator aplikacji (klienta)”** i wklej go w aplikacji: *Synchronizacja → Identyfikator aplikacji → Zapisz* (albo dopisz go do pliku `app/mf_mobile/onedrive_client_id.txt` — będzie wbudowany w kolejne wersje APK).
5. *Połącz z OneDrive* → aplikacja pokaże **kod** → *Kopiuj kod i otwórz stronę* → wklej kod na microsoft.com/devicelogin i zaloguj się. Gotowe.

Uprawnienia: dostęp do plików OneDrive (`Files.ReadWrite`) i odświeżanie logowania. Token logowania jest przechowywany tylko w prywatnych danych aplikacji na telefonie; *Rozłącz OneDrive* go usuwa. Pliki w OneDrive są dodatkowo zaszyfrowane hasłem synchronizacji.

## iPhone — wersja przeglądarkowa (bez App Store)

Apple nie pozwala instalować aplikacji spoza App Store bez płatnego konta deweloperskiego, dlatego na iPhone'a jest **ta sama aplikacja w wersji przeglądarkowej** (Python działa w Safari):
* **Instalacja:** Safari → https://arturknopek.github.io/Matrix-Finance-Mobile/ → *Udostępnij* → **Do ekranu początkowego**.
* **Dane** zostają na iPhonie (w pamięci tej aplikacji z ekranu początkowego) i są zapisywane po każdej zmianie.
* **Synchronizacja z komputerem — ręcznie:** *Pobierz dane z OneDrive* otwiera aplikację **Pliki** (wybierz OneDrive → MatrixFinance → MatrixFinance.mfsync), *Wyślij zmiany do OneDrive* otwiera *Udostępnij* → **Zachowaj w Plikach** → OneDrive → MatrixFinance. (Aplikacja OneDrive musi być zainstalowana — wtedy jest widoczna w Plikach.)
* Pierwsze uruchomienie trwa dłużej (pobiera się środowisko Pythona, potem jest w pamięci podręcznej).
* Alternatywa dla zaawansowanych: wersja natywna przez AltStore/SideStore (darmowe Apple ID, odnawianie co 7 dni) — możliwa, ale wymaga komputera; wersja przeglądarkowa jest prostsza.

## Synchronizacja z komputerem przez OneDrive (ręcznie)

```
 KOMPUTER (baza główna)                          TELEFON
 MatrixFinance.mfsync  ──── OneDrive ────▶  „Pobierz dane z OneDrive”
 (zaszyfrowana migawka danych)                  (komplet danych + Twoje niewysłane zmiany)

 dopisuje zmiany (każdą raz) ◀── OneDrive ──  „Wyślij zmiany do OneDrive”
                                              telefon-XXXXXX.mfops (zaszyfrowane operacje)
```

1. **Komputer** (Matrix Finance 2.2.0+): *Ustawienia (9) → Synchronizacja z telefonem → Ustaw synchronizację* — folder w OneDrive (wykrywany automatycznie) i hasło.
2. **Telefon**: zainstaluj aplikację OneDrive i zaloguj się na to samo konto.
3. W aplikacji: *Synchronizacja → Pobierz dane z OneDrive* → OneDrive → `MatrixFinance` → `MatrixFinance.mfsync`, wpisz to samo hasło.
4. Po zmianach na telefonie: *Wyślij zmiany do OneDrive* → w oknie **Udostępnij** wybierz **OneDrive** → folder `MatrixFinance` → *Prześlij*. Plik trafia prosto do chmury (nie do pamięci telefonu). Komputer dopisze zmiany automatycznie (po zalogowaniu, co 2 minuty, `Ctrl+Y`) i zapisze nową migawkę. Gdyby plik trafił do głównego folderu OneDrive, komputer też go znajdzie.

Każda zmiana z telefonu (wydatek, dochód, edycja, usunięcie, przelew, wpłata/wypłata z celu, korekta salda, korekta i przesunięcie w kopertach) ma unikalny identyfikator — komputer stosuje ją **tylko raz**, nawet gdy plik zapiszesz kilka razy. Zmiana, której nie da się wykonać (np. cel usunięty na komputerze), wraca na telefon jako odrzucona z opisem. Dopóki komputer nie potwierdzi zmian, telefon pokazuje je jako „do wysłania” i nie traci ich przy pobieraniu danych.

Pliki są szyfrowane hasłem synchronizacji (AES-128 + HMAC-SHA256, klucz z PBKDF2, 200 000 iteracji).

## Budowanie i rozwój

```bash
pip install "flet[all]==1.1.3" pytest
python -m pytest                 # testy (silnik, synchronizacja z „komputerem”, wszystkie ekrany i formularze)
python tools/web_preview.py      # podgląd w przeglądarce: http://127.0.0.1:8550
flet build apk                   # APK (Flutter, JDK i Android SDK pobierane automatycznie)
```

APK buduje i testuje na emulatorze GitHub Actions (*Actions → Android (APK)*). Wydanie: *Run workflow* z zaznaczonym „wydanie”. Stały klucz podpisu (aktualizacje bez odinstalowania): `tools/make_keystore.sh` + sekrety repozytorium.

## Struktura

```
app/main.py          punkt wejścia (Flet)
app/mf_mobile/       interfejs: app (nawigacja), store (dane), forms (okna), screens/ (ekrany), theme, ui,
                     onedrive (połączenie z OneDrive), web_storage (dane w przeglądarce — iPhone)
app/src/             silnik — KOPIA z Matrix-Finance-TUI (nie edytuj tutaj: tools/update_engine.py)
tests/               testy
tools/               update_engine.py, web_preview.py, make_keystore.sh
```

Licencja MIT.
