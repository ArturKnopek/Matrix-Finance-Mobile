# Matrix Finance Mobile (Android)

Aplikacja na telefon do programu **[Matrix Finance](https://github.com/ArturKnopek/Matrix-Finance-TUI)** — budżet domowy połączony z oszczędzaniem kopertowym. Na telefonie szybko dodajesz wydatki i sprawdzasz koperty, a dane łączą się z programem na komputerze przez **zaszyfrowany plik w Twoim OneDrive** (bez żadnego serwera).

> To osobny projekt. Program na komputer (Linux / Windows z instalatorem) jest w repozytorium **Matrix-Finance-TUI**; oba korzystają z tego samego silnika budżetu (salda, koperty, synchronizacja).

## Instalacja

Pobierz `MatrixFinance-<wersja>.apk` z zakładki **Releases** i otwórz go na telefonie (Android zapyta o zgodę na instalację z tego źródła).

## Co potrafi

| Ekran | Funkcje |
|---|---|
| **Pulpit** | do wydania w kopertach, bilans miesiąca, wydatki, majątek; koperty z paskami (zielony → żółty → czerwony), ostatnie wpisy, nadchodzące płatności, cele |
| **Transakcje** | lista dzień po dniu, wyszukiwanie, filtr (wydatki / dochody / inne), edycja i usuwanie |
| **Koperty** | ile zostało, wykorzystanie, koperty elastyczne (↻), wydatek z koperty, **korekty** („ustaw zostało”, dołóż, odejmij) i **przesuwanie między kopertami** |
| **Konta** | majątek netto, konta wg grup, **przelewy**, **korekta salda** |
| **Cele** | postęp, plan miesięczny, wpłata / wypłata, korekta stanu |
| **+** | nowy wydatek/dochód: kwota, koperta (z informacją ile zostało), konto, sklep, data |

Motywy kolorów jak na komputerze (Matrix, Bursztyn, Cyber, Fiolet, Karmazyn, Mono) i dane przykładowe do wypróbowania.

## Synchronizacja z komputerem przez OneDrive

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
4. Po zmianach na telefonie: *Wyślij zmiany do OneDrive* → zapisz w folderze `MatrixFinance`. Komputer dopisze zmiany automatycznie (po zalogowaniu, co 2 minuty, `Ctrl+Y`) i zapisze nową migawkę.

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
app/mf_mobile/       interfejs: app (nawigacja), store (dane), forms (okna), screens/ (ekrany), theme, ui
app/src/             silnik — KOPIA z Matrix-Finance-TUI (nie edytuj tutaj: tools/update_engine.py)
tests/               testy
tools/               update_engine.py, web_preview.py, make_keystore.sh
```

Licencja MIT.
