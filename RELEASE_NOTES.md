## Matrix Finance Mobile — Android

**Nowe w 1.4:**
* **Analiza i doradca** (Pulpit › „Analiza i doradca”): tempo wydatków i prognoza do końca miesiąca, trend 6 miesięcy
  (przychody / wydatki / ile odłożono), wydatki wg kopert, gdzie wydajesz najwięcej, wskazówki doradcy.
* **Szybsze dodawanie**: podpowiedzi ostatnich sklepów — jedno dotknięcie wpisuje sklep, kopertę i konto; po wpisaniu
  znanego sklepu koperta ustawia się sama.
* **Blokada PIN-em** (Ustawienia › Bezpieczeństwo): przy uruchomieniu i po powrocie do aplikacji; zapomniany PIN —
  odblokowanie hasłem kopii zapasowej.
* **Automatyczne odkładanie** (Stałe płatności): % każdego wpływu albo zaokrąglanie wydatków na cel / konto.
* **Eksport** (Ustawienia › Eksport): transakcje do Excela (CSV) i raport miesiąca do druku / PDF.
* Wyszukiwanie we wszystkich miesiącach (Transakcje › wpisz szukany tekst › przełącznik).
* Niezawodność: dane na iPhonie zapisują się w skompresowanej postaci (≈3× mniej miejsca) z ostrzeżeniem, gdyby zapis
  się nie udał; zaległe płatności księgują się także wtedy, gdy aplikacja jest otwarta przez noc; „Zapisz kopię”
  działa również tam, gdzie „Udostępnij” jest niedostępne; szybsze odświeżanie ekranów.

**Nowe w 1.3:** **działa bez komputera.** Na ekranie powitalnym „Zacznij — bez komputera”: telefon jest główną bazą —
zakładasz konta (także lokaty, obligacje, inwestycje, własne rodzaje), **kredyty i zakupy na raty**, koperty z budżetami,
cele i **stałe płatności** (czynsz, rachunki, pensja, odkładanie); zlecenia, raty i lokaty telefon księguje sam.
Dane chroni **zaszyfrowana kopia zapasowa** `MatrixFinance-kopia.mfx`: na Androidzie z OneDrive zapisuje się sama, na
iPhonie — Udostępnij › Zachowaj w Plikach. Kopię wczytasz na nowym telefonie albo w programie na komputer
(Ustawienia › Import danych). Tryb z komputerem działa jak dotąd (Ustawienia › Tryb pracy).
**iPhone:** ta sama wersja — https://arturknopek.github.io/Matrix-Finance-Mobile/ (Safari › Udostępnij › Do ekranu początkowego).

**Nowe w 1.2.1:** poprawiony układ ekranu Synchronizacja na wąskich telefonach (opis przełącznika
„Automatycznie” i przycisk „Zapamiętaj folder” nie są już ucinane).

**Nowe w 1.2:** OneDrive **bez wybierania plików** — połączenie z kontem Microsoft raz, zapamiętana lokalizacja
(„Obecna lokalizacja: OneDrive › MatrixFinance”), zapis zawsze do tego samego pliku, synchronizacja automatyczna
(przy uruchomieniu i po każdej zmianie) albo przyciskiem. Wymaga jednorazowo identyfikatora aplikacji (Client ID) —
instrukcja w README i w aplikacji. **iPhone:** wersja przeglądarkowa — Safari → https://arturknopek.github.io/Matrix-Finance-Mobile/
→ Udostępnij → „Do ekranu początkowego”.

**Nowe w 1.1:** wysyłanie zmian **prosto do OneDrive** (okno „Udostępnij” → OneDrive → folder MatrixFinance — plik
nie zostaje w pamięci telefonu), kredyty i zakupy na raty w Kontach (rata, postęp, nadpłata), silnik zgodny z
programem na komputer **2.3.0** (zalecana aktualizacja komputera).

Pobierz **`MatrixFinance-<wersja>.apk`** (poniżej, w sekcji *Assets*) na telefon i otwórz plik.
Android zapyta o zgodę na instalację z tego źródła (np. z przeglądarki lub menedżera plików) — zezwól.

**Co potrafi**
* pulpit: do wydania w kopertach, bilans miesiąca, majątek, koperty z paskami, ostatnie wpisy, cele,
* szybkie dodawanie wydatków i dochodów (koperta pokazuje, ile w niej zostało),
* koperty: korekta „zostało”, dołożenie/odjęcie, przesunięcie między kopertami,
* konta: przelewy i korekty sald; cele: wpłaty, wypłaty, korekty,
* motywy kolorów jak w programie na komputerze, dane przykładowe do wypróbowania.

**Synchronizacja z komputerem (OneDrive)**
1. Na komputerze (Matrix Finance 2.3.0): Ustawienia → Synchronizacja z telefonem → folder w OneDrive + hasło.
2. Na telefonie: Synchronizacja → wpisz to samo hasło.
3. **Zalecane — bez wybierania plików:** wklej identyfikator aplikacji (Client ID, instrukcja w aplikacji) →
   „Połącz z OneDrive” → zaloguj się kodem. Od teraz telefon pamięta lokalizację (widać ją jako
   „Obecna lokalizacja: OneDrive › MatrixFinance”), sam pobiera dane z komputera i zapisuje swoje zmiany —
   przy uruchomieniu, po każdej zmianie albo przyciskiem „Synchronizuj teraz”.
4. **Ręcznie (bez Client ID):** „Pobierz dane z OneDrive” → OneDrive → MatrixFinance → `MatrixFinance.mfsync`;
   po zmianach „Wyślij zmiany do OneDrive” → „Udostępnij” → OneDrive → folder MatrixFinance → Prześlij.

Pliki synchronizacji są szyfrowane (AES) hasłem synchronizacji. Zalecany Android 9 lub nowszy.
