"""
Test wersji przeglądarkowej w silniku Safari (WebKit) z profilem iPhone'a — uruchamiany w GitHub Actions.

    python tools/test_web_iphone.py http://localhost:8000/Matrix-Finance-Mobile/ zrzuty/

Sprawdza: start aplikacji (Python w przeglądarce), dane przykładowe, przejście po zakładkach oraz to,
że po ponownym otwarciu strony dane zostają (zapis w pamięci przeglądarki).
Teksty na ekranie odczytuje z drzewa dostępności Fluttera (semantics) i wypisuje do logu.
"""

import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

URL, OUT = sys.argv[1], Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)
errors = []
console = []


def dump_console() -> None:
    print("==== KONSOLA PRZEGLĄDARKI (ostatnie wpisy) ====")
    for line in console[-120:]:
        print(line[:2000])


def texts(page) -> list:
    page.evaluate("""() => { const p = document.querySelector('flt-semantics-placeholder');
                             if (p) p.click(); }""")
    page.wait_for_timeout(800)
    return page.evaluate("""() => Array.from(document.querySelectorAll('flt-semantics, [aria-label]'))
        .map(e => (e.getAttribute('aria-label') || e.innerText || '').trim()).filter(t => t)""")


def wait_for_text(page, needle: str, timeout: float = 150) -> list:
    start = time.time()
    while time.time() - start < timeout:
        found = texts(page)
        if any(needle in t for t in found):
            return found
        page.wait_for_timeout(2000)
    page.screenshot(path=str(OUT / "blad.png"))
    dump_console()
    raise SystemExit(f"Nie pojawił się tekst „{needle}”. Na ekranie: {texts(page)[:30]}")


def tap(page, label: str) -> None:
    loc = page.locator(f"flt-semantics[aria-label*='{label}'], [role=button][aria-label*='{label}']").first
    if loc.count() == 0:
        loc = page.get_by_text(label).first
    loc.click()
    page.wait_for_timeout(2500)


with sync_playwright() as p:
    browser = p.webkit.launch()
    ctx = browser.new_context(**p.devices["iPhone 15"])
    page = ctx.new_page()
    def on_console(m) -> None:
        console.append(f"[{m.type}] {m.text}")
        if m.type == "error":
            errors.append(m.text)

    page.on("console", on_console)
    page.on("pageerror", lambda e: (errors.append(str(e)), console.append(f"[pageerror] {e}")))
    page.on("worker", lambda w: console.append(f"[worker] {w.url}"))
    t0 = time.time()
    page.goto(URL, wait_until="load")
    found = wait_for_text(page, "Wypróbuj na danych przykładowych")
    print(f"START OK po {time.time() - t0:.0f} s. Ekran powitalny: {found[:8]}")
    page.screenshot(path=str(OUT / "1_start.png"))
    tap(page, "Wypróbuj na danych przykładowych")
    found = wait_for_text(page, "Do wydania")
    print("PULPIT OK:", [t for t in found if len(t) < 60][:25])
    page.screenshot(path=str(OUT / "2_pulpit.png"))
    for tab in ("Transakcje", "Koperty", "Konta", "Cele"):
        tap(page, tab)
        page.screenshot(path=str(OUT / f"3_{tab.lower()}.png"))
        print(f"{tab}: {[t for t in texts(page) if len(t) < 60][:12]}")
    tap(page, "Pulpit")
    tap(page, "Analiza i doradca")
    found = wait_for_text(page, "Wydano do dziś")
    print("ANALIZA:", [t for t in found if len(t) < 70][:14])
    page.screenshot(path=str(OUT / "3_analiza.png"))
    # trwałość: ponowne otwarcie strony -> od razu pulpit z danymi (bez ekranu powitalnego)
    page.reload(wait_until="load")
    found = wait_for_text(page, "Do wydania")
    assert not any("Wypróbuj na danych przykładowych" in t for t in found), "dane nie zostały zapamiętane"
    print("PO PONOWNYM OTWARCIU: dane zachowane ✓")
    page.screenshot(path=str(OUT / "4_po_ponownym_otwarciu.png"))

    # tryb „Bez komputera” na czystym iPhonie (nowa pamięć przeglądarki)
    ctx2 = browser.new_context(**p.devices["iPhone 15"])
    page = ctx2.new_page()
    page.on("console", on_console)
    page.on("pageerror", lambda e: (errors.append(str(e)), console.append(f"[pageerror] {e}")))
    page.goto(URL, wait_until="load")
    wait_for_text(page, "Zacznij — bez komputera")
    tap(page, "Zacznij — bez komputera")
    found = wait_for_text(page, "Pierwsze kroki")
    print("BEZ KOMPUTERA — PULPIT:", [t for t in found if len(t) < 70][:12])
    page.screenshot(path=str(OUT / "5_bez_komputera.png"))
    tap(page, "Kopia zapasowa")
    found = wait_for_text(page, "Zapisz kopię")
    print("KOPIA ZAPASOWA:", [t for t in found if len(t) < 70][:12])
    page.screenshot(path=str(OUT / "6_kopia_zapasowa.png"))
    page.reload(wait_until="load")
    found = wait_for_text(page, "Pierwsze kroki")
    assert not any("Zacznij — bez komputera" in t for t in found), "tryb bez komputera nie został zapamiętany"
    print("BEZ KOMPUTERA PO PONOWNYM OTWARCIU: zachowane ✓")
    browser.close()

python_errors = [e for e in errors if "Traceback" in e or "Error" in e and "favicon" not in e]
print("Błędy konsoli:", python_errors[:10] or "brak")
if any("Traceback" in e for e in python_errors):
    raise SystemExit("Błąd Pythona w przeglądarce")
print("TEST WERSJI NA IPHONE: OK")
