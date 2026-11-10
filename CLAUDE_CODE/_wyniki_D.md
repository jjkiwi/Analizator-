## D1. Źródło kalendarza (faireconomy) — zweryfikowane na żywo 2026-11-10

**Co zrobione.** `cfd macro refresh` i `cfd macro upcoming` uruchomione na prawdziwym feedzie; adapter poprawiony i obudowany cache; test na zapisanej próbce.

**Co wyszło.**
- Adres `https://nfs.faireconomy.media/ff_calendar_thisweek.json` jest poprawny (HTTP 200, `application/json`, 105 wierszy na bieżący tydzień → 102 wydarzenia po odrzuceniu 3 świąt).
- Format: lista słowników z polami `title, country, date, impact, forecast, previous`. Pola `actual` **nie ma** — sprawdzone także po publikacji (CPI USA z 13:30 UTC, feed pobrany o 15:44 UTC nadal bez odczytu).
- Strefa czasowa: `date` to ISO 8601 z offsetem czasu nowojorskiego (`-05:00` teraz, latem `-04:00`). Kod poprawnie przelicza na UTC (CPI 08:30-05:00 → 13:30 UTC). Test obejmuje też offset letni.
- `impact`: High/Medium/Low/Holiday; `country`: kod waluty albo `All`. Wartości typu `0.3%`, `194K`, `-0.9M`, `2.81T`, `77B`, aukcje `4.11|3.9` (brana pierwsza liczba).
- Limit zapytań (pomiar): 5 zapytań w ok. 2 minuty przeszło, kolejne dostało **HTTP 429** (strona HTML „Rate Limited”, `retry-after: 205`), czyli okno ok. 5 minut. Odpowiedź ma `cache-control: max-age=60`, a plik zmienia się rzadko (`last-modified` sprzed godziny).
- Feed obejmuje tylko bieżący tydzień (od niedzieli); w weekend lista nadchodzących wydarzeń będzie pusta do czasu podmiany pliku.

**Co zmienione w kodzie.**
- `src/cfd/macro/sources.py`: błędy sieci, statusy ≠ 200, nie-JSON i pusta lista → `DataSourceError` (wcześniej surowe wyjątki httpx / cichy pusty wynik). Plik cache `data/cache/macro/ff_calendar_thisweek.json`: w ciągu 10 minut adapter nie pyta serwera ponownie; przy 429/awarii używa kopii nie starszej niż 24 h (z ostrzeżeniem w logu), starszej nie używa. Wspólny `http_text` z odstępem 3 s na host. Pole `unit` = `%` gdy prognoza w procentach.
- `src/cfd/cli.py` (`macro refresh`): czytelny komunikat zamiast tracebacku, informacja „(z cache)”.
- Testy: `tests/test_macro_sources.py` na próbkach `tests/fixtures/macro/ff_calendar_thisweek.json` i `ff_rate_limited.html` (prawdziwa odpowiedź 429).

**Co nie działa / uwagi.**
- Reguła `stopy_ebc` (`match: "ecb"`) łapie też wystąpienia („ECB President Lagarde Speaks”), więc alert „przed publikacją” przypisuje im DE40/EU50/FRA40; analogicznie `fomc` łapie „FOMC Member … Speaks” (te mają zwykle wagę 1–2, alert jest od 3). Nie zmieniałem — to decyzja o treści reguł.
- Źródło nie ma oficjalnego regulaminu API; to publiczny plik eksportu ForexFactory. Przy `refresh_minutes: 60` robimy 24 zapytania na dobę, daleko od limitu.

## D2. Odczyty bieżące („actual”) — drugi adapter, zweryfikowany na żywo

**Co zrobione.** Nowy moduł `src/cfd/macro/actuals.py`: po godzinie publikacji pobiera właściwą serię urzędową i sam liczy odczyt w tej samej postaci, w jakiej kalendarz podaje prognozę. Mapowanie wydarzenie → seria w `config/macro_rules.yaml`, sekcja `actuals` (17 reguł, tylko USA).

Dostawcy serii (wspólny interfejs `series(id) -> pd.Series`, błąd = `DataSourceError`):

| Dostawca | Źródło | Klucz | Stan |
|---|---|---|---|
| `FredCsvSeries` | `fred.stlouisfed.org/graph/fredgraph.csv?id=…` | nie | działa na żywo; wszystkie 15 identyfikatorów z konfiguracji sprawdzone |
| `BlsSeries` | `api.bls.gov/publicAPI/v2/timeseries/data/<ID>` (GET) | opcjonalny `BLS_API_KEY` | działa na żywo, ale limit dzienny na IP (patrz niżej) |
| `EiaDnavSeries` | publiczne strony historii `www.eia.gov/dnav/…` (ropa, gaz) | nie | działa na żywo; robots.txt zezwala na `/dnav/` |

**Co wyszło (na żywo, 2026-11-10).**
- `cfd macro refresh` po publikacji CPI: `CPI m/m` = 0.4 (prognoza 0.3), `Core CPI m/m` = 0.3 (prognoza 0.2); raz z BLS, raz z FRED — oba źródła dały to samo. Kod wyjścia 0 mimo błędu limitu BLS w tym samym przebiegu.
- Kontrola krzyżowa: wartości policzone dla poprzedniego okresu zgadzają się z polem `previous` z kalendarza dla CPI (0.6), Core CPI (0.3), PPI (1.3), Core PPI (0.7), wniosków o zasiłek (189K), zapasów ropy (−0.9M) i gazu (77B). Pozostałe reguły (NFP, bezrobocie, płace, JOLTS, sprzedaż detaliczna, Core PCE, PKB, stopa Fed, CPI r/r) mają sprawdzone istnienie serii, ale nie porównanie z kalendarzem (brak tych wydarzeń w tym tygodniu).
- Opóźnienie FRED: CPI z 13:30 UTC było w pliku CSV z `last-modified` 14:12 UTC, czyli ok. 40 minut (jeden pomiar). BLS podaje dane w minucie publikacji, o ile nie trafi się na limit. Opóźnienia stron EIA nie zmierzyłem (publikacje w środę/czwartek).
- BLS, limity: bez klucza 25 zapytań/dobę **na adres IP** (z kluczem 500). W tym środowisku IP jest współdzielone i przez większość dnia serwer odpowiadał „daily threshold … has been reached” (HTTP 200, status `REQUEST_NOT_PROCESSED`), także dla v1; pojedyncze zapytania przechodziły. Adapter zamienia to na `DataSourceError` i przechodzi do FRED. Własny licznik (plik `data/cache/macro/bls_budget.json`) ogranicza nas do 20 zapytań/dobę bez klucza.
- `api.stlouisfed.org` i `api.eia.gov` wymagają kluczy — nieużywane w tym module. BEA i Eurostat: hosty zablokowane w tym środowisku (`apps.bea.gov`, `ec.europa.eu`) — niesprawdzalne tutaj.

**Zabezpieczenia.**
- Okres odczytu jest wyliczany z daty publikacji (`period` + `lag`); jeśli źródło go jeszcze nie ma, wynik to „czeka na źródło”, a nie wartość z poprzedniego miesiąca/tygodnia. Dziura w serii (np. brak CPI za 10.2025 — prawdziwy przypadek w danych) daje jawny błąd zamiast zmiany liczonej względem innego okresu; skutek: `CPI y/y` za 10.2026 nie zostanie uzupełnione automatycznie.
- Zaokrąglenie jak w kalendarzu (`decimals`), żeby 0.249 nie było „niespodzianką” wobec 0.2.
- `ActualsFiller.fill` nigdy nie rzuca wyjątku: błędy źródeł trafiają do raportu i logu. Awaria samego kalendarza pozostaje `DataSourceError` (runner zapisuje ją w `health`).
- Odczyt już zapisany w bazie (np. ręcznie przez `set-actual`) nie jest nadpisywany przez automat (`upsert_events`: `COALESCE(actual, excluded.actual)`); `cfd macro set-actual` nadal zawsze nadpisuje.

**Co zmienione w kodzie.**
- nowe: `src/cfd/macro/actuals.py`, `tests/test_macro_sources.py` (15 testów), `tests/fixtures/macro/*` (prawdziwe odpowiedzi FRED, BLS — sukces i limit, EIA ropa i gaz skrócone do 2026 r., FRED 404);
- `config/macro_rules.yaml`: sekcja `actuals`; `src/cfd/macro/__init__.py`: eksporty; `src/cfd/macro/calendar.py`: `upsert_events` jak wyżej;
- `src/cfd/cli.py`: `macro refresh` i `_context` używają `default_source()` (kalendarz + odczyty), więc `cfd run` też dostaje odczyty bez zmian w `runner.py`; `refresh` wypisuje uzupełnione odczyty, oczekujące i błędy źródeł.

**Co nie działa / ograniczenia.**
- Tylko USA. Strefa euro, UK, Japonia, Chiny: brak sprawdzonego darmowego źródła w tym środowisku (Eurostat zablokowany) — zostaje `cfd macro set-actual` i tor newsowy.
- Wskaźniki spoza urzędów (ISM, PMI S&P, ADP, ZEW, Ifo, UoM) nie mają darmowego API — jak wyżej.
- `BlsSeries` z kluczem (`BLS_API_KEY`) przetestowany tylko na atrapie — **niezweryfikowany na żywo**. Identyfikatory BLS potwierdzone na żywo: `CUSR0000SA0`, `CUSR0000SA0L1E`, `LNS14000000`; pozostałe (`CUUR0000SA0`, `WPSFD4`, `WPSFD49104`, `CES0000000001`, `CES0500000003`, `JTS000000000000000JOL`) niesprawdzone — przy błędzie działa zapas FRED.
- `runner.job_macro` wysyła alert „po publikacji” tylko dla wydarzeń z ostatnich 6 godzin. Przy FRED (~40 min) to wystarcza; „Federal Funds Rate” (seria dzienna, wartość dopiero następnego dnia) nie zmieści się w oknie — odczyt trafi do bazy, alertu nie będzie. Nie zmieniałem `runner.py`.
- Odczyt liczony z serii bywa o 0.1 inny niż oficjalny komunikat, gdy urząd zaokrągla z danych niezaokrąglonych (dotyczy głównie sprzedaży detalicznej i PCE); dla CPI/PPI zgodność potwierdzona.
- Feed kalendarza obejmuje tylko bieżący tydzień, więc piątkowy odczyt, którego źródło nie zdąży podać do niedzieli, nie zostanie już uzupełniony.
