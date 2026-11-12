# Wyniki zadań

Jedna sekcja na zadanie z `ZADANIA.md`: co zrobione, co wyszło, co zmienione, co nie działa.
Stan na 2026-11-11. Testy: `pytest` przechodzi w całości.

**Czego nie dało się sprawdzić w tym środowisku** (lista dozwolonych hostów i brak kluczy): Stooq (blokada antybotowa),
Bankier i CNBC (403), polskie feedy i pozostałe banki centralne (hosty niedozwolone), Telegram, klasyfikator LLM na żywo,
API FRED i EIA z kluczem. Szczegóły w sekcjach i w `DECYZJE.md`.

## Scalenie z v0.3 (2026-11-11)

Sekcje A–F poniżej powstały na paczce **v0.2** (41 instrumentów, bez akcji, bez Supabase). Po dostarczeniu paczki v0.3
praca została scalona trójstronnie w gicie (wspólna baza: „v0.2 z czatu”). Stan po scaleniu: `pytest` 149, `deno test` 12.

**Przeniesione do v0.3:** zweryfikowane adaptery świec i `cfd data-quality`, zapasowy host Binance, wykluczenie rolowań,
swapy XTB, odczyty makro `actual`, FRED bez klucza, EIA, COT, poprawki feedów i słów kluczowych, tłumienie powtórek,
`cfd size`, `cfd report --cost-mult`.

**Rozstrzygnięte na rzecz v0.3:**
- Klasyfikator: łańcuch darmowych modeli z `config/llm.yaml`; klasa dla API Anthropic przywrócona do postaci z v0.3
  (moja wersja na SDK i `news/compare.py` usunięte). Poprawki reguł (`RuleClassifier`) zostały.
- ZINC i NICKEL usunięte (decyzja 7). Google News w formacie `locales` (5 języków), z zachowanym `when: "1d"`.
- Interwał 30m dodany do zweryfikowanego adaptera Yahoo (limit 59 dni przyjęty z dokumentacji, niesprawdzony na żywo).

**Dopisane przy scalaniu:**
- Tor szybki w TypeScripcie zgodny z Pythonem: skróty `cs:`, `exclude`, frazy wysokiej wagi tylko w tytule,
  `high_impact_moves`, obniżanie zapowiedzi i pytań do wagi 2, tłumienie powtórek (`news.repeat_cooldown_minutes`).
  Te same przypadki testowe dają identyczny wynik w obu językach. `cfd export-config` eksportuje nowe pola.

**Nieaktualne po scaleniu (zostawione, do decyzji):**
- `deploy/` (systemd, Docker, Windows) i zadanie `dashboard` w `cfd run`: decyzja 2 wybrała chmurę. Przydatne tylko dla G4.
- Sekcje C3 i F3 poniżej opisują stan z v0.2.

**Braki zgodności Python ↔ TypeScript:** odczyty `actual` (D2) działają tylko w Pythonie (`macro/actuals.py`);
`supabase/functions/_shared/macro.ts` ich nie ma. Reguły EIA/COT/FRED dotyczą toru wolnego, więc TS ich nie potrzebuje.

**Akcje (A1 z v0.3):** 30 z 31 mapowań Yahoo działa. `SPL.PL` → `SPL.WA` nie zwraca danych (spółka zmieniła nazwę na
Erste Bank Polska; właściwy ticker do ustalenia). Spółki z UK są w pensach (OXB.L 555, OXIG.L 2628): do porównania ze skalą w XTB.
Wyniki walk-forward dla akcji i dla interwału 1h: sekcja „B1 po scaleniu” na końcu pliku.

## A1. Sprawdzenie mapowań źródeł

Stan na 2026-11-10/11. Pełny wynik: `CLAUDE_CODE/check-sources.txt` (działa 44, nie działa 16).

**Co wyszło**

| Źródło | Wynik |
|---|---|
| Yahoo (yfinance 1.8.0) | wszystkie 41 mapowań działa, żaden ticker nie wymagał poprawki |
| Binance | 3/3 działa, ale tylko przez zapasowy host `data-api.binance.vision` (`api.binance.com` zwraca HTTP 451, patrz A2) |
| Stooq | 0/13: z tego środowiska Stooq zrywa połączenie albo odpowiada 404/stroną weryfikacji przeglądarki (patrz A2). Mapowania Stooq pozostają **niepotwierdzone** |
| ZINC, NICKEL | brak źródła |

- Wszystkie 14 pozycji BŁĄD ze Stooq to blokada serwisu, a nie zły symbol, więc symboli Stooq nie zmieniałem (nie ma jak ich sprawdzić). Pozostałe 2 BŁĄD to ZINC i NICKEL.
- **W20**: dopisane `yahoo: "WIG20.WA"`. Yahoo ma dla tego symbolu tylko świece 1h (do 730 dni wstecz); zapytanie dzienne zwraca błąd (`period=max` niedozwolony) albo samą bieżącą sesję. Adapter składa więc świece dzienne z godzinowych (498 sesji od 2024-11-12). Stooq zostaje pierwszym źródłem W20 dla 1d (pełna historia), Yahoo jest zapasem i jedynym źródłem 4h/1h. To indeks kasowy, a CFD W20 w XTB jest oparty na kontrakcie FW20: poziomy różnią się o bazę.
- **ZINC, NICKEL**: darmowego źródła nie znalazłem. Yahoo nie ma kontraktów LME (`NI=F`, `LZS=F` nie istnieją). `ZNC=F` (cynk CME) istnieje, ale to martwa seria rozliczeniowa: 100% świec z ostatnich 250 ma zerowy zasięg, 95% zamknięć bez zmiany, zero obrotu. Jedyny działający zamiennik to ETC z giełdy w Londynie `ZINC.L` i `NICK.L` (WisdomTree, historia dzienna od 2008, 1h dostępne): oddają kierunek, ale cena to kilkanaście USD za jednostkę, nie USD za tonę, więc poziomów SL/TP nie da się przenieść. Pola `sources` zostają puste, pytanie w `_decyzje_A.md`.
- Hosty spoza listy dozwolonych (np. `stooq.pl`) dają `CONNECT tunnel failed 403`: to blokada środowiska, nie serwisu. Nie obchodziłem.

**Porównanie zamknięć między źródłami** (ostatnie zamknięte świece dzienne, 41 sesji od 2026-10-01)

| Para | Różnica | Wniosek |
|---|---|---|
| BTCUSDT (Binance) vs BTC-USD (Yahoo) | ostatnia +0,10%, maks. 0,36% | ten sam instrument (USDT vs USD, inna godzina odcięcia doby) |
| ETHUSDT vs ETH-USD | ostatnia +0,15%, maks. 0,31% | jw. |
| SOLUSDT vs SOL-USD | ostatnia +0,11%, maks. 0,35% | jw. |
| ES=F vs ^SPX (kontrakt vs indeks kasowy) | średnio +0,54%, ostatnia +0,32% (7574,2 vs 7549,9) | różny instrument bazowy |
| NQ=F vs ^NDX | średnio +0,63%, ostatnia +0,38% | jw. |
| YM=F vs ^DJI | średnio +0,40%, ostatnia +0,21% | jw. |
| RTY=F vs ^RUT | średnio +0,47%, ostatnia +0,28% | jw. |

Żadna para nie przekracza progu 2%. Par Yahoo vs Stooq (np. `ES=F` vs `^spx`) nie dało się porównać bezpośrednio, bo Stooq nie odpowiada; zastąpiłem je porównaniem kontraktu z indeksem kasowym w samym Yahoo. Baza kontrakt-indeks to dziś 0,2-0,6% i rośnie z odległością do wygaśnięcia: poziomy SL/TP liczone na `=F` trzeba przeliczać na kwotowanie XTB. Z tego samego powodu `DataService` nie skleja serii z różnych źródeł (przy zmianie źródła pobiera całość od nowa).

**Zmiany w kodzie**: `config/instruments.yaml` (W20, komentarze), `src/cfd/data/service.py` (priorytet źródeł = kolejność wpisów `sources` instrumentu zamiast stałej globalnej; dla dotychczasowych wpisów kolejność wychodzi ta sama).

**Nie działa / otwarte**: Stooq (całość), ZINC, NICKEL, W20 dzienne dłuższe niż 2 lata.

## A2. Naprawa adapterów

**Yahoo** (`src/cfd/data/yahoo.py`)
- yfinance działa przez proxy środowiska bez zmian (curl_cffi respektuje `HTTPS_PROXY` i CA bundle). Raz pojawiło się `Crumb fetch rate-limited (HTTP 429)` przy seriach co 2-3 s: zapytanie i tak się powiodło. Adapter ma teraz odstęp min. 2 s między zapytaniami.
- **Strefa czasowa**: yfinance zwraca indeks w strefie giełdy (`America/New_York` dla CME/ICE, `Europe/Berlin`, `Asia/Tokyo`, `America/Chicago` dla VIX, UTC dla krypto). Świeca dzienna ma znacznik północy czasu giełdy, co po zamianie na UTC dawało 04:00 albo 05:00 zależnie od czasu letniego. Poprawione: świece 1d mają teraz datę sesji o 00:00 UTC (tak samo jak Stooq i Binance).
- **Limit 1h**: sprawdzony dokładnie. 729 dni działa (CL=F: 11 310 świec), 731 i 750 dni zwraca błąd „The requested range must be within the last 730 days". Stała 729 zostaje.
- **Cichy pusty wynik**: yfinance przy złym symbolu lub zakresie poza limitem tylko wypisuje komunikat i oddaje pustą ramkę. Adapter rzuca teraz `DataSourceError` z opisem.
- **Świece 4h**: stare okna od północy UTC były błędne dla kontraktów. CME handluje 18:00-17:00 czasu NY z godzinną przerwą; okno 20:00-24:00 UTC łączyło końcówkę jednej sesji z początkiem następnej, a granice przesuwały się o godzinę przy zmianie czasu. Teraz okna liczone są od otwarcia sesji w czasie giełdy (otwarcie wykrywane z danych jako najczęstsza godzina pierwszej świecy po przerwie): dla CME 18-22, 22-02, 02-06, 06-10, 10-14, 14-17 NY przez cały rok (ostatnie okno ma 3 godziny), dla DAX/WIG20 od 09:00 czasu lokalnego (09-13, 13-17, 17-17:30), dla kawy od 04:00 NY, krypto od 00:00 UTC. Przy 4h adapter pobiera zawsze min. 60 dni świec 1h, żeby otwarcie sesji wyznaczać stabilnie także przy aktualizacji przyrostowej, i odrzuca pierwszą (potencjalnie niepełną) świecę.
- **Dzienne z godzinowych**: gdy Yahoo nie daje historii 1d (WIG20.WA), dni są składane z 1h (z ostrzeżeniem w logu).

**Stooq** (`src/cfd/data/stooq.py`)
- Pobieranie CSV **nie działa** z tego środowiska. Zaobserwowane odpowiedzi na `https://stooq.com/q/d/l/?s=...&i=d`: (1) HTTP 200 ze stroną HTML „This site requires JavaScript to verify your browser" (zaobserwowane przez koordynatora), (2) zerwanie połączenia w trakcie negocjacji TLS po ok. 10 s (większość prób, także z nagłówkiem przeglądarki i przy odstępach 6-20 s), (3) HTTP 404 dla `^spx`, `^ndx`, `cl.f`. To samo dla `robots.txt` i punktu `/q/l/`. Wygląda to na ochronę antybotową po stronie Stooq (lub na trasie do niego), nie na brak klucza. Limitu dziennego nie dało się zmierzyć, bo nie przeszło ani jedno pobranie.
- Captchy nie obchodzę. Adapter rozpoznaje stronę weryfikacji, inną stronę HTML, komunikat o limicie dziennym i „No data" i w każdym przypadku rzuca `DataSourceError` z jasnym opisem; odstęp między zapytaniami 5 s.
- Trzeba sprawdzić z komputera użytkownika (polski adres IP), czy Stooq oddaje tam CSV. Jeśli nie, źródło jest do usunięcia.

**Binance** (`src/cfd/data/binance.py`)
- `api.binance.com` zwraca HTTP 451 („Service unavailable from a restricted location"). Dodany zapasowy host `data-api.binance.vision` (to samo API, te same dane). Adapter próbuje hosty po kolei, zapamiętuje działający i nie wraca do zablokowanego przy kolejnych stronach. Błąd 400 (zły symbol) nie powoduje przełączania.
- Naprawiony błąd: limit 60 stron × 1000 świec ucinał historię 1h (od 2017 to ok. 81 stron), więc pierwsze pobranie kończyło się w 2023 roku. Limit podniesiony do 200 stron, a jego przekroczenie jest teraz błędem, nie cichym ucięciem.
- Zużycie limitu: pełna historia 1h trzech par to ok. 220 zapytań z odstępem 0,3 s; nagłówek `x-mbx-used-weight-1m` pokazał 88 w trakcie testów (limitu nie zbliżyłem).

**Próbki i testy**: `tests/fixtures/yahoo_CL=F_1h.csv`, `yahoo_CL=F_1d.csv`, `yahoo_WIG20.WA_1h.csv` (surowe ramki yfinance, okres obejmuje zmianę czasu w USA), `binance_klines_BTCUSDT_1d.json`, `binance_451_restricted.json`. Testy w `tests/test_data_adapters.py` (17): indeks 1d, UTC, okna 4h przed i po zmianie czasu, brak zaglądania w przyszłość przy składaniu 4h, dzienne z godzinowych, pusty wynik, limit 730 dni, przełączanie hosta Binance, odpowiedzi Stooq.

**Zastrzeżenie**: prawdziwej strony weryfikacji Stooq nie udało mi się zapisać (połączenie było zrywane, zanim przyszła odpowiedź). Plik `tests/fixtures/stooq_js_challenge_reconstructed.html` to rekonstrukcja z jednym znanym zdaniem, a nie surowa odpowiedź; nazwa pliku i komentarz w teście to zaznaczają. Do podmiany na oryginał, gdy uda się go pobrać.

## A3. Historia i jakość danych

`cfd fetch` dla 1d, 4h i 1h wykonane: 41 z 43 instrumentów w każdym interwale (brak tylko ZINC i NICKEL). Cache: `data/candles/` (32 MB, 123 pliki Parquet). Źródła: Binance dla krypto, Yahoo dla reszty. Aktualizacja przyrostowa sprawdzona (bez duplikatów, okna 4h zgodne z pełnym pobraniem).

Nowe polecenie: `cfd data-quality [--interval 1d|4h|1h] [SYMBOLE] [--markdown] [--details N]` (czyta tylko cache, bez sieci). Moduł `src/cfd/data/quality.py`.

Definicje:
- **luki**: 1d: ponad 2 dni robocze z rzędu bez świecy; 1h/4h: przerwa, której długość nie powtarza się regularnie (nie jest przerwą dobową ani nocną) i która nie jest weekendem ani świętem; krypto: każda brakująca świeca,
- **zero-zasięg**: high = low (cała historia oraz ostatnie 500 świec),
- **skoki**: luka otwarcia lub zmiana zamknięcia wobec poprzedniego zamknięcia większa niż 8 × ATR(14) z poprzednich świec (skok nie zawyża własnego ATR).

### 1d

| symbol | swiec | od | do | luki | najdl. luka | zero-zasieg | w ost. 500 | skoki>8ATR | najwiekszy skok |
|---|---|---|---|---|---|---|---|---|---|
| US500 | 6603 | 2000-09-18 | 2026-11-11 | 1 | 6 dni | 0 | 0 | 0 | - |
| US100 | 6603 | 2000-09-18 | 2026-11-11 | 1 | 6 dni | 1 | 0 | 0 | - |
| US30 | 6194 | 2002-04-05 | 2026-11-11 | 0 | - | 6 | 1 | 0 | - |
| US2000 | 2353 | 2017-07-10 | 2026-11-11 | 0 | - | 0 | 0 | 0 | - |
| DE40 | 9830 | 1987-12-30 | 2026-11-11 | 16 | 6 dni | 1490 | 0 | 2 | -24.6 ATR 1991-08-19 |
| UK100 | 10828 | 1984-01-03 | 2026-11-11 | 0 | - | 5 | 0 | 1 | -13.0 ATR 1987-10-19 |
| FRA40 | 9322 | 1990-03-01 | 2026-11-11 | 1 | 6 dni | 2 | 0 | 1 | -8.9 ATR 1991-08-19 |
| EU50 | 4919 | 2007-03-30 | 2026-11-11 | 15 | 7 dni | 8 | 0 | 0 | - |
| SPA35 | 8449 | 1993-07-12 | 2026-11-11 | 7 | 6 dni | 0 | 0 | 0 | - |
| ITA40 | 7373 | 1997-12-31 | 2026-11-11 | 9 | 6 dni | 1455 | 0 | 0 | - |
| NED25 | 8698 | 1992-10-12 | 2026-11-11 | 0 | - | 2 | 0 | 0 | - |
| SUI20 | 9042 | 1990-11-09 | 2026-11-11 | 25 | 6 dni | 7 | 0 | 1 | -13.0 ATR 1991-08-19 |
| W20 | 498 | 2024-11-12 | 2026-11-10 | 2 | 6 dni | 0 | 0 | 0 | - |
| JP225 | 15204 | 1965-01-05 | 2026-11-11 | 72 | 11 dni | 5734 | 0 | 14 | -21.4 ATR 1987-10-20 |
| AUS200 | 8589 | 1992-11-23 | 2026-11-11 | 2 | 7 dni | 1866 | 1 | 0 | - |
| HK.cash | 9838 | 1986-12-31 | 2026-11-11 | 30 | 7 dni | 573 | 0 | 5 | -16.6 ATR 1987-10-26 |
| VIX | 9286 | 1990-01-02 | 2026-11-11 | 1 | 7 dni | 508 | 0 | 7 | +25.0 ATR 1991-11-15 |
| USDIDX | 14184 | 1971-01-04 | 2026-11-11 | 2 | 7 dni | 3726 | 0 | 13 | -63.9 ATR 1971-08-31 |
| OIL | 4796 | 2007-07-30 | 2026-11-11 | 3 | 17 dni | 93 | 0 | 0 | - |
| OIL.WTI | 6582 | 2000-08-23 | 2026-11-11 | 1 | 4 dni | 0 | 0 | 0 | - |
| NATGAS | 6581 | 2000-08-30 | 2026-11-11 | 1 | 4 dni | 1 | 0 | 1 | +9.5 ATR 2003-02-24 |
| GASOLINE | 6539 | 2000-11-01 | 2026-11-11 | 0 | - | 85 | 0 | 0 | - |
| COCOA | 6737 | 2000-01-03 | 2026-11-11 | 2 | 6 dni | 966 | 126 | 1 | +12.9 ATR 2021-07-12 |
| COFFEE | 6735 | 2000-01-03 | 2026-11-11 | 2 | 7 dni | 565 | 78 | 0 | - |
| SUGAR | 6698 | 2000-03-01 | 2026-11-11 | 2 | 7 dni | 2 | 1 | 0 | - |
| COTTON | 6736 | 2000-01-03 | 2026-11-10 | 1 | 7 dni | 501 | 83 | 1 | -8.4 ATR 2022-06-24 |
| CORN | 6587 | 2000-07-17 | 2026-11-11 | 2 | 14 dni | 192 | 0 | 10 | +14.8 ATR 2003-10-23 |
| WHEAT | 6599 | 2000-07-17 | 2026-11-11 | 1 | 10 dni | 263 | 17 | 4 | +10.5 ATR 2005-02-22 |
| SOYBEAN | 6579 | 2000-09-15 | 2026-11-11 | 0 | - | 152 | 7 | 6 | -10.0 ATR 2005-01-18 |
| SOYOIL | 6628 | 2000-03-15 | 2026-11-11 | 6 | 15 dni | 567 | 29 | 3 | +13.1 ATR 2005-02-22 |
| CATTLE | 6441 | 2001-03-01 | 2026-11-10 | 2 | 33 dni | 900 | 0 | 7 | +58.5 ATR 2004-12-01 |
| LEANHOGS | 6509 | 2000-12-15 | 2026-11-10 | 0 | - | 586 | 0 | 54 | -25.3 ATR 2025-08-15 |
| COPPER | 6580 | 2000-08-30 | 2026-11-11 | 0 | - | 172 | 13 | 1 | +8.1 ATR 2025-07-08 |
| ALUMINIUM | 3113 | 2014-05-06 | 2026-11-11 | 3 | 27 dni | 2635 | 413 | 2 | +112.0 ATR 2018-04-02 |
| ZINC | 0 | - | - | - | - | - | - | - | brak danych w cache |
| NICKEL | 0 | - | - | - | - | - | - | - | brak danych w cache |
| GOLD | 6575 | 2000-08-30 | 2026-11-11 | 1 | 4 dni | 979 | 0 | 6 | +17.0 ATR 2001-09-14 |
| SILVER | 6577 | 2000-08-30 | 2026-11-11 | 0 | - | 1764 | 46 | 1 | -8.1 ATR 2007-08-16 |
| PLATINUM | 6599 | 1997-10-29 | 2026-11-11 | 22 | 78 dni | 3224 | 314 | 11 | -18.5 ATR 2008-09-29 |
| PALLADIUM | 6604 | 1998-09-28 | 2026-11-11 | 24 | 64 dni | 3820 | 374 | 8 | +72.2 ATR 2008-02-28 |
| BITCOIN | 3374 | 2017-08-17 | 2026-11-11 | 0 | - | 0 | 0 | 1 | +9.1 ATR 2019-04-02 |
| ETHEREUM | 3374 | 2017-08-17 | 2026-11-11 | 0 | - | 0 | 0 | 1 | +8.8 ATR 2026-08-19 |
| SOLANA | 2284 | 2020-08-11 | 2026-11-11 | 0 | - | 0 | 0 | 0 | - |

### 4h

| symbol | swiec | od | do | luki | najdl. luka | zero-zasieg | w ost. 500 | skoki>8ATR | najwiekszy skok |
|---|---|---|---|---|---|---|---|---|---|
| US500 | 2998 | 2024-11-12 | 2026-11-11 | 9 | 12 h | 3 | 0 | 1 | -11.1 ATR 2024-12-18 |
| US100 | 2996 | 2024-11-12 | 2026-11-11 | 7 | 12 h | 0 | 0 | 1 | -8.1 ATR 2024-12-18 |
| US30 | 2997 | 2024-11-12 | 2026-11-11 | 8 | 12 h | 2 | 0 | 1 | -9.6 ATR 2024-12-18 |
| US2000 | 3001 | 2024-11-12 | 2026-11-11 | 6 | 12 h | 0 | 0 | 0 | - |
| DE40 | 1509 | 2024-11-12 | 2026-11-11 | 2 | 5 dni | 0 | 0 | 0 | - |
| UK100 | 1503 | 2024-11-12 | 2026-11-11 | 0 | - | 0 | 0 | 0 | - |
| FRA40 | 1519 | 2024-11-12 | 2026-11-11 | 0 | - | 0 | 0 | 0 | - |
| EU50 | 1490 | 2024-11-12 | 2026-11-11 | 4 | 5 dni | 0 | 0 | 0 | - |
| SPA35 | 1501 | 2024-11-12 | 2026-11-11 | 1 | 10 dni | 0 | 0 | 2 | -8.4 ATR 2025-04-04 |
| ITA40 | 1508 | 2024-11-12 | 2026-11-11 | 2 | 5 dni | 0 | 0 | 0 | - |
| NED25 | 1519 | 2024-11-12 | 2026-11-11 | 0 | - | 0 | 0 | 0 | - |
| SUI20 | 1490 | 2024-11-12 | 2026-11-11 | 4 | 5 dni | 0 | 0 | 0 | - |
| W20 | 1492 | 2024-11-12 | 2026-11-10 | 2 | 5 dni | 43 | 28 | 0 | - |
| JP225 | 967 | 2024-11-13 | 2026-11-11 | 4 | 6 dni | 0 | 0 | 0 | - |
| AUS200 | 1005 | 2024-11-13 | 2026-11-11 | 1 | 5 dni | 0 | 0 | 0 | - |
| HK.cash | 974 | 2024-11-13 | 2026-11-11 | 3 | 6 dni | 3 | 3 | 1 | -8.0 ATR 2025-04-07 |
| VIX | 2034 | 2024-11-12 | 2026-11-11 | 0 | - | 0 | 0 | 3 | +17.0 ATR 2025-01-27 |
| USDIDX | 3040 | 2024-11-12 | 2026-11-11 | 3 | 8 h | 23 | 0 | 0 | - |
| OIL | 3000 | 2024-11-12 | 2026-11-11 | 3 | 8 h | 1 | 0 | 1 | +9.2 ATR 2026-03-08 |
| OIL.WTI | 2985 | 2024-11-12 | 2026-11-11 | 4 | 8 h | 1 | 0 | 1 | +8.5 ATR 2026-03-08 |
| NATGAS | 2981 | 2024-11-12 | 2026-11-11 | 4 | 8 h | 0 | 0 | 0 | - |
| GASOLINE | 2978 | 2024-11-12 | 2026-11-11 | 7 | 8 h | 6 | 0 | 2 | +15.8 ATR 2025-03-02 |
| COCOA | 1486 | 2024-11-12 | 2026-11-11 | 0 | - | 3 | 0 | 0 | - |
| COFFEE | 1492 | 2024-11-12 | 2026-11-11 | 0 | - | 1 | 0 | 0 | - |
| SUGAR | 1483 | 2024-11-12 | 2026-11-11 | 0 | - | 1 | 0 | 0 | - |
| COTTON | 1786 | 2024-11-12 | 2026-11-11 | 2 | 10 dni | 222 | 155 | 0 | - |
| CORN | 2453 | 2024-11-12 | 2026-11-11 | 3 | 12 h | 0 | 0 | 1 | -15.7 ATR 2026-01-12 |
| WHEAT | 2453 | 2024-11-12 | 2026-11-11 | 3 | 12 h | 0 | 0 | 0 | - |
| SOYBEAN | 2454 | 2024-11-12 | 2026-11-11 | 3 | 12 h | 0 | 0 | 0 | - |
| SOYOIL | 2452 | 2024-11-12 | 2026-11-11 | 3 | 12 h | 2 | 0 | 0 | - |
| CATTLE | 994 | 2024-11-12 | 2026-11-10 | 0 | - | 0 | 0 | 0 | - |
| LEANHOGS | 994 | 2024-11-12 | 2026-11-10 | 0 | - | 0 | 0 | 5 | -23.4 ATR 2025-07-31 |
| COPPER | 3004 | 2024-11-12 | 2026-11-11 | 3 | 8 h | 0 | 0 | 2 | -13.5 ATR 2025-07-30 |
| ALUMINIUM | 2701 | 2024-11-12 | 2026-11-11 | 8 | 12 h | 146 | 53 | 0 | - |
| ZINC | 0 | - | - | - | - | - | - | - | brak danych w cache |
| NICKEL | 0 | - | - | - | - | - | - | - | brak danych w cache |
| GOLD | 3004 | 2024-11-12 | 2026-11-11 | 3 | 8 h | 0 | 0 | 0 | - |
| SILVER | 3004 | 2024-11-12 | 2026-11-11 | 3 | 8 h | 0 | 0 | 0 | - |
| PLATINUM | 3002 | 2024-11-12 | 2026-11-11 | 3 | 8 h | 0 | 0 | 0 | - |
| PALLADIUM | 3002 | 2024-11-12 | 2026-11-11 | 3 | 8 h | 0 | 0 | 0 | - |
| BITCOIN | 20224 | 2017-08-17 | 2026-11-11 | 8 | 32 h | 1 | 0 | 5 | +16.3 ATR 2019-04-02 |
| ETHEREUM | 20224 | 2017-08-17 | 2026-11-11 | 8 | 32 h | 1 | 0 | 4 | +10.1 ATR 2026-08-19 |
| SOLANA | 13700 | 2020-08-11 | 2026-11-11 | 0 | - | 0 | 0 | 0 | - |

### 1h

| symbol | swiec | od | do | luki | najdl. luka | zero-zasieg | w ost. 500 | skoki>8ATR | najwiekszy skok |
|---|---|---|---|---|---|---|---|---|---|
| US500 | 11409 | 2024-11-12 | 2026-11-11 | 12 | 12 h | 9 | 2 | 7 | +12.0 ATR 2025-01-15 |
| US100 | 11407 | 2024-11-12 | 2026-11-11 | 10 | 12 h | 4 | 2 | 7 | +10.7 ATR 2024-12-22 |
| US30 | 11402 | 2024-11-12 | 2026-11-11 | 11 | 12 h | 5 | 0 | 11 | +15.7 ATR 2024-12-22 |
| US2000 | 11417 | 2024-11-12 | 2026-11-11 | 10 | 12 h | 1 | 0 | 6 | +17.2 ATR 2025-01-15 |
| DE40 | 4527 | 2024-11-12 | 2026-11-11 | 2 | 5 dni | 1 | 0 | 2 | -10.1 ATR 2025-02-03 |
| UK100 | 4512 | 2024-11-12 | 2026-11-11 | 0 | - | 0 | 0 | 0 | - |
| FRA40 | 4551 | 2024-11-12 | 2026-11-11 | 0 | - | 0 | 0 | 3 | -8.7 ATR 2025-10-06 |
| EU50 | 4469 | 2024-11-12 | 2026-11-11 | 4 | 5 dni | 0 | 0 | 3 | +9.8 ATR 2026-01-05 |
| SPA35 | 4502 | 2024-11-12 | 2026-11-11 | 1 | 10 dni | 2 | 0 | 3 | -13.0 ATR 2026-04-30 |
| ITA40 | 4523 | 2024-11-12 | 2026-11-11 | 2 | 5 dni | 0 | 0 | 1 | -8.4 ATR 2025-05-23 |
| NED25 | 4550 | 2024-11-12 | 2026-11-11 | 0 | - | 0 | 0 | 1 | +9.8 ATR 2026-01-02 |
| SUI20 | 4468 | 2024-11-12 | 2026-11-11 | 5 | 5 dni | 0 | 0 | 0 | - |
| W20 | 4472 | 2024-11-12 | 2026-11-10 | 2 | 5 dni | 43 | 26 | 1 | -8.9 ATR 2025-02-03 |
| JP225 | 3379 | 2024-11-13 | 2026-11-11 | 4 | 6 dni | 0 | 0 | 8 | +11.3 ATR 2026-05-07 |
| AUS200 | 3520 | 2024-11-12 | 2026-11-11 | 0 | - | 1 | 0 | 4 | -10.5 ATR 2024-12-18 |
| HK.cash | 3395 | 2024-11-13 | 2026-11-11 | 5 | 5 dni | 3 | 0 | 1 | -13.0 ATR 2025-04-07 |
| VIX | 7092 | 2024-11-12 | 2026-11-11 | 0 | - | 0 | 0 | 6 | +20.2 ATR 2025-01-27 |
| USDIDX | 11893 | 2024-11-12 | 2026-11-11 | 12 | 12 h | 29 | 0 | 6 | +10.0 ATR 2026-10-14 |
| OIL | 11394 | 2024-11-12 | 2026-11-11 | 14 | 12 h | 27 | 0 | 9 | -14.9 ATR 2026-07-22 |
| OIL.WTI | 11306 | 2024-11-12 | 2026-11-11 | 18 | 12 h | 27 | 0 | 2 | +9.1 ATR 2026-03-08 |
| NATGAS | 11306 | 2024-11-12 | 2026-11-11 | 11 | 12 h | 39 | 1 | 7 | +20.4 ATR 2025-09-23 |
| GASOLINE | 11210 | 2024-11-12 | 2026-11-11 | 25 | 12 h | 88 | 0 | 30 | +35.6 ATR 2026-02-11 |
| COCOA | 4834 | 2024-11-12 | 2026-11-11 | 3 | 4 h | 5 | 0 | 0 | - |
| COFFEE | 4858 | 2024-11-12 | 2026-11-11 | 3 | 5 h | 2 | 0 | 0 | - |
| SUGAR | 4865 | 2024-11-12 | 2026-11-11 | 3 | 5 h | 15 | 2 | 2 | -12.2 ATR 2025-02-03 |
| COTTON | 4841 | 2024-11-12 | 2026-11-11 | 73 | 10 dni | 395 | 134 | 2 | +9.3 ATR 2026-11-10 |
| CORN | 9283 | 2024-11-12 | 2026-11-11 | 6 | 10 h | 6 | 0 | 12 | -24.1 ATR 2026-01-12 |
| WHEAT | 9280 | 2024-11-12 | 2026-11-11 | 7 | 10 h | 4 | 0 | 1 | -9.5 ATR 2026-01-12 |
| SOYBEAN | 9285 | 2024-11-12 | 2026-11-11 | 8 | 10 h | 4 | 0 | 9 | +14.3 ATR 2026-02-04 |
| SOYOIL | 9275 | 2024-11-12 | 2026-11-11 | 7 | 10 h | 12 | 0 | 3 | -10.6 ATR 2026-06-17 |
| CATTLE | 2987 | 2024-11-12 | 2026-11-10 | 0 | - | 1 | 0 | 0 | - |
| LEANHOGS | 2986 | 2024-11-12 | 2026-11-10 | 0 | - | 0 | 0 | 11 | -42.0 ATR 2025-07-31 |
| COPPER | 11424 | 2024-11-12 | 2026-11-11 | 10 | 12 h | 2 | 0 | 4 | -28.4 ATR 2025-07-30 |
| ALUMINIUM | 8177 | 2024-11-12 | 2026-11-11 | 37 | 13 h | 1059 | 129 | 7 | +14.1 ATR 2026-03-29 |
| ZINC | 0 | - | - | - | - | - | - | - | brak danych w cache |
| NICKEL | 0 | - | - | - | - | - | - | - | brak danych w cache |
| GOLD | 11435 | 2024-11-12 | 2026-11-11 | 9 | 12 h | 7 | 2 | 1 | +11.5 ATR 2025-07-30 |
| SILVER | 11431 | 2024-11-12 | 2026-11-11 | 10 | 12 h | 6 | 0 | 1 | +8.8 ATR 2025-08-22 |
| PLATINUM | 11422 | 2024-11-12 | 2026-11-11 | 9 | 12 h | 3 | 0 | 1 | +8.4 ATR 2025-09-02 |
| PALLADIUM | 11406 | 2024-11-12 | 2026-11-11 | 11 | 12 h | 26 | 0 | 0 | - |
| BITCOIN | 80832 | 2017-08-17 | 2026-11-11 | 28 | 34 h | 4 | 0 | 29 | +21.6 ATR 2023-08-29 |
| ETHEREUM | 80832 | 2017-08-17 | 2026-11-11 | 28 | 34 h | 8 | 0 | 25 | +15.2 ATR 2023-08-29 |
| SOLANA | 54778 | 2020-08-11 | 2026-11-11 | 10 | 5 h | 2 | 0 | 8 | +11.6 ATR 2023-01-02 |

### Wnioski z tabel

- **Stara historia dzienna jest w wielu seriach bezwartościowa dla strategii opartych na ATR**: Yahoo podaje tam tylko zamknięcie (open = high = low = close). Dotyczy m.in. JP225 (5734 świec), USDIDX (3726), PALLADIUM (3820), PLATINUM (3224), ALUMINIUM (2635 z 3113), SILVER (1764), DE40 (1490), ITA40 (1455), AUS200 (1866). Kolumna „w ost. 500" pokazuje, czy problem jest aktualny. Raport walk-forward na 1d obejmuje te okresy: do rozważenia obcięcie historii do pierwszej daty z prawdziwym zasięgiem (nie zrobiłem, to zmienia wyniki walidacji).
- **ALUMINIUM (`ALI=F`) i COTTON są słabe także teraz**: w ostatnich 500 świecach 1h odpowiednio 129 i 134 o zerowym zasięgu, ALUMINIUM ma 1059 takich świec 1h łącznie, COTTON 73 luki. Niska płynność kontraktu, wyniki strategii na tych seriach będą niewiarygodne.
- **Dziury w historii dziennej**: PLATINUM (22 luki, najdłuższa 78 dni), PALLADIUM (24, 64 dni), CATTLE (33 dni), ALUMINIUM (27 dni), JP225 (72 luki). W ostatnich 2 latach (4h/1h) luki to prawie wyłącznie skrócone sesje świąteczne (24 grudnia, 3 lipca) po 8-12 h.
- **Binance**: 28 luk w 1h (najdłuższa 34 h) to brakujące świece w danych samej giełdy (sprawdzone przykłady: 2019-05-15, 2019-08-15, 2020-02-19), najpewniej przerwy techniczne.
- **W20**: 43 świece 1h o zerowym zasięgu (ostatnia godzina sesji bywa pojedynczym kwotowaniem zamknięcia).
- **Skoki > 8 ATR na 1h** są głównie prawdziwymi ruchami na otwarciu sesji po weekendzie lub po danych, nie błędami. Wyjątki to rolowania (niżej).

### Rolowanie kontraktów: ropa i gaz

Yahoo `=F` to kontrakt najbliższy bez korekty: w pierwszej sesji po wygaśnięciu seria przeskakuje na następny kontrakt. Daty wygaśnięcia policzyłem z reguł giełdy (CL: 3 dni robocze przed 25. dniem miesiąca; NG: 3. dzień roboczy od końca miesiąca) i sprawdziłem na danych: luka otwarcia jest podwyższona dokładnie w pierwszej sesji po tak wyznaczonej dacie i wraca do normy sesję później. Dane dzienne od 2010 r., 202 rolowania na instrument.

| | świece rolowania | pozostałe świece |
|---|---|---|
| **WTI** luka otwarcia, mediana | 0,20 ATR | 0,08 ATR |
| WTI luka otwarcia, 90. percentyl / maks. | 0,60 / 1,6 ATR | 0,24 / 3,9 ATR |
| WTI zmiana zamknięcia, mediana | 1,52% | 1,23% |
| **Gaz** luka otwarcia, mediana | 0,46 ATR | 0,09 ATR |
| Gaz luka otwarcia, 90. percentyl / maks. | 1,55 / 4,6 ATR | 0,31 / 2,3 ATR |
| Gaz zmiana zamknięcia, mediana / 90. percentyl | 3,22% / 11,48% | 1,88% / 5,33% |

- **Ropa WTI**: skok rolowania jest mały (typowo 0,2 ATR, nigdy powyżej 1,6 ATR). Kontrakty sąsiednie różnią się dziś o 1,4% (grudzień 86,04 vs styczeń 84,86). Wpływ na sygnały niewielki.
- **Gaz**: skok jest duży i sezonowy. Średnia zmiana na świecy rolowania wg miesiąca: październik +7,7%, wrzesień +4,2%, kwiecień +4,0%, styczeń −9,2%. Przykłady z ostatniego roku: 2025-09-29 +15,2%, 2025-10-30 +17,2%, 2025-12-30 −15,3%, 2026-01-29 −47,5% (luka −4,6 ATR). Najbliższe rolowanie (ok. 26 listopada): styczeń jest dziś o 10,9% droższy od grudnia (3,655 vs 3,296). Tych ruchów nie ma na CFD: XTB koryguje je przy rolowaniu, więc backtest na `NG=F` widzi zyski i straty, których handlujący by nie miał.
- **Próg 8 ATR nie wykrywa rolowań ropy i gazu**: żaden z 404 skoków rolowania go nie przekracza (największy to 4,6 ATR na gazie; przy progu 4 ATR gaz ma 4 skoki od 2010 r., z czego 2 to rolowania). Próg 8 ATR łapie za to rolowania tam, gdzie kontrakty różnią się bardzo mocno: LEANHOGS (54 skoki na 1d, mediana dnia miesiąca to 15., czyli termin wygaśnięcia; np. 2025-08-15 otwarcie 89,13 po zamknięciu 109,65, czyli −18% z dnia na dzień). Skoki na CORN, SOYBEAN i CATTLE wyglądają podobnie, ale nie sprawdzałem ich dat z kalendarzem wygasania.

**Zaimplementowane minimum**: `cfd.data.quality.roll_flags(df, source_symbol)` zwraca maskę świec pierwszej sesji po wygaśnięciu (działa dla 1d, 4h i 1h), `expiry_dates` liczy kalendarz dla `CL=F` i `NG=F`. Dni wolne brane są z samych danych, więc wynik może odbiegać o 1 sesję od kalendarza giełdy. Maska **nie jest podłączona** do strategii ani backtestu: to zmienia wyniki walidacji, więc zostawiam decyzję (pytanie w `_decyzje_A.md`).

**Proponowane obejście, w kolejności opłacalności**
1. Wykluczyć świece rolowania z sygnałów i liczyć ATR/wskaźniki z pominięciem ich luki (tanie, maska już jest). Do rozszerzenia o kalendarze pozostałych kontraktów; dla LEANHOGS, CATTLE i zbóż wystarczy na początek próg ATR, bo tam skoki są ogromne.
2. Korekta wsteczna (odjęcie luki rolowania od całej wcześniejszej historii) dla NATGAS i LEANHOGS. Lukę można oszacować z samej serii jako open nowego kontraktu minus close starego, ale zawiera też prawdziwy ruch nocny (typowo 0,1 ATR, więc błąd jest mały wobec skoku). Dokładna korekta wymaga cen obu kontraktów w dniu rolowania: Yahoo udostępnia tylko kontrakty jeszcze notowane (`NGZ26.NYM` działa, wygasły `CLX26.NYM` zwraca 404), więc dokładną różnicę da się zbierać tylko na bieżąco, od teraz.
3. Dla ropy nic nie robić poza flagą: skok mieści się w szumie.

**Zmiany w kodzie**: nowy `src/cfd/data/quality.py`, `src/cfd/cli.py` (tylko polecenie `data-quality`), `src/cfd/data/base.py` (`Throttle`), testy `tests/test_data_quality.py` (7).

**Nie działa / do zrobienia**: maska rolowania tylko dla CL i NG i niepodłączona do strategii; brak danych ZINC/NICKEL; historia W20 tylko 2 lata; README nadal opisuje świece jako „tylko na atrapach" (nie mój plik).

## B1. Raport walk-forward

**Co zrobione.** `cfd report --interval 1d` i `--interval 4h` na cache z A3 (41 instrumentów × 3 strategie = 123 kombinacje
na interwał; ZINC i NICKEL nie mają danych). Opcja `cfd report --cost-mult 2` mnoży spread i swapy (test odporności).
Raport liczony dwa razy: najpierw na założonych kosztach, potem (2026-11-11) po dwóch zmianach z decyzji użytkownika:
swapy z tabeli XTB (B2) i wykluczenie świec rolowania. Progi walidacji i siatki parametrów bez zmian.

**Wykluczenie rolowań: co zmienione w kodzie.**
- `data/quality.py: roll_mask` — maska świec rolowania: kalendarz wygaśnięć dla ropy WTI i gazu (wszystkie interwały)
  oraz, dla pozostałych kontraktów `=F` na świecach dziennych, luka otwarcia ponad 8 ATR z poprzednich świec.
  Oflagowane na 1d: OIL.WTI 314, NATGAS 314, LEANHOGS 47, PLATINUM 11, CATTLE 7, PALLADIUM 6, pozostałe 0–3.
- `backtest/engine.py` — otwarta pozycja jest na świecy rolowania przesuwana o lukę (wejście, SL i TP razem),
  więc skok nie daje zysku ani straty. `validation/walkforward.py`, `report.py`, `cli.py` — sygnał ze świecy rolowania
  jest zerowany. `scanner.py` — skaner na żywo nie zgłasza sygnału ze świecy rolowania.
- Uzasadnienie (zasada 6): to usunięcie ruchów, których na CFD nie ma, a nie poluzowanie progów. Zmiana działa w obie
  strony: zabiera sztuczne zyski i sztuczne straty.
- Ograniczenie: mniejsze rolowania Brenta, benzyny, zbóż i metali nie są wykrywane (brak kalendarzy, luka poniżej 8 ATR).

**Co wyszło (aktualne: swapy XTB, rolowania wykluczone, spready założone).**

| Interwał | Koszty | PASS | WEAK | FAIL |
|---|---|---|---|---|
| 1d | swapy XTB, spready założone | 5 | 22 | 96 |
| 1d | ×2 | 2 | 10 | 111 |
| 4h | swapy XTB, spready założone | 1 | 7 | 115 |
| 4h | ×2 | 2 | 1 | 120 |

Lista PASS z kontrolą dodatkową:

| Instrument | Strategia | Int. | Trans. | Skut. | Oczek. R | PF | Suma R | Max DD | Koszty ×2 | Drugi interwał |
|---|---|---|---|---|---|---|---|---|---|---|
| SPA35 | donchian_breakout | 1d | 122 | 45% | +0.28 | 1.45 | +34.4 | -8.9% | WEAK (112 trans., +0.17R, PF 1.24) | FAIL (5 trans., -0.68R, PF 0.44) |
| VIX | mean_reversion | 1d | 103 | 54% | +0.39 | 1.78 | +39.8 | -9.1% | PASS (103 trans., +0.38R, PF 1.76) | FAIL (24 trans., +0.24R, PF 1.48) |
| SOYBEAN | donchian_breakout | 1d | 97 | 42% | +0.21 | 1.32 | +20.3 | -9.4% | WEAK (88 trans., +0.09R, PF 1.13) | FAIL (20 trans., +0.17R, PF 1.28) |
| LEANHOGS | mean_reversion | 1d | 37 | 51% | +0.38 | 1.55 | +14.2 | -10.3% | PASS (37 trans., +0.28R, PF 1.38) | FAIL (0 trans.) |
| PALLADIUM | trend_pullback | 1d | 66 | 52% | +0.19 | 1.34 | +12.6 | -5.9% | WEAK (61 trans., +0.09R, PF 1.16) | FAIL (29 trans., -0.00R, PF 1.00) |
| ALUMINIUM | mean_reversion | 4h | 41 | 54% | +0.35 | 1.71 | +14.4 | -3.2% | PASS (41 trans., +0.26R, PF 1.50) | FAIL (10 trans., -1.19R, PF 0.22) |

**Które PASS przetrwały: żaden.** Koszty ×2 przetrwały trzy (VIX i LEANHOGS na 1d, ALUMINIUM na 4h), ale żadna kombinacja
nie ma PASS na drugim interwale, a każda z tych trzech ma osobne zastrzeżenie:

- **VIX** — `^VIX` to indeks kasowy; CFD w XTB jest na kontrakcie futures z contango. Wynik z indeksu nie przenosi się
  na instrument, którym da się handlować.
- **LEANHOGS** — 37 transakcji, a wynik powstał dopiero po usunięciu 47 świec rolowania (przedtem +0,00R przy 62 transakcjach).
  Tak duża zależność od jednej korekty danych to powód do nieufności, nie do zaufania. Na 4h brak transakcji.
- **ALUMINIUM** — dane 4h dziurawe, dużo świec o zerowym zasięgu (A3), 41 transakcji.

**Co zmieniły swapy XTB i wykluczenie rolowań** (1d): z listy PASS wypadły OIL donchian_breakout (+0,20R → +0,10R),
NATGAS mean_reversion (+0,26R → +0,21R) i SILVER mean_reversion (+0,35R → +0,25R); wszystkie trzy to teraz WEAK.
Doszły SOYBEAN donchian_breakout i LEANHOGS mean_reversion. Podejrzenie z pierwszego raportu, że PASS na gazie to artefakt
rolowania, potwierdziło się tylko częściowo: wynik spadł, ale pozostał dodatni.

**Obraz zbiorczy.** 5 PASS na 123 kombinacje to ok. 4%, czyli tyle, ile daje przypadek. Suma wyników wszystkich
instrumentów jest ujemna dla każdej strategii na obu interwałach:

| Strategia | 1d: transakcje | 1d: suma R | 1d: mediana oczek. R | 4h: transakcje | 4h: suma R | 4h: mediana oczek. R |
|---|---|---|---|---|---|---|
| trend_pullback | 2681 | −139,7 | −0,08 | 958 | −59,1 | −0,01 |
| donchian_breakout | 3566 | −355,9 | −0,09 | 1537 | −46,9 | −0,14 |
| mean_reversion | 1892 | −218,5 | −0,19 | 756 | −101,4 | −0,16 |

**Wniosek: żadna strategia nie przechodzi walidacji.** `alert_strategies` zostaje puste.

**Zastrzeżenia.** Spready to nadal założenia. Historia 4h z Yahoo to ok. 2 lata, więc okien testowych jest mało.
Stara historia bez zasięgu świec (A3) nie jest odfiltrowana. Pełny raport liczy się ok. 4 min (1d) i ok. 2 min (4h).

### Pierwszy przebieg (koszty założone, rolowania nieodfiltrowane) — dla porównania

| Interwał | Koszty | PASS | WEAK | FAIL |
|---|---|---|---|---|
| 1d | z konfiguracji (założenia) | 6 | 28 | 89 |
| 1d | ×2 | 3 | 11 | 109 |
| 4h | z konfiguracji (założenia) | 1 | 7 | 115 |
| 4h | ×2 | 1 | 2 | 120 |

Lista PASS z kontrolą dodatkową:

| Instrument | Strategia | Int. | Trans. | Skut. | Oczek. R | PF | Suma R | Max DD | Koszty ×2 | Drugi interwał |
|---|---|---|---|---|---|---|---|---|---|---|
| SPA35 | donchian_breakout | 1d | 131 | 44% | +0.25 | 1.40 | +33.2 | -11.3% | WEAK (115 trans., +0.19R, PF 1.29) | FAIL (5 trans., -0.67R, PF 0.45) |
| VIX | mean_reversion | 1d | 103 | 54% | +0.39 | 1.78 | +39.8 | -9.1% | PASS (103 trans., +0.38R, PF 1.76) | FAIL (24 trans., +0.24R, PF 1.49) |
| OIL | donchian_breakout | 1d | 74 | 46% | +0.20 | 1.34 | +15.0 | -9.2% | WEAK (74 trans., +0.10R, PF 1.16) | FAIL (33 trans., -0.43R, PF 0.46) |
| NATGAS | mean_reversion | 1d | 45 | 49% | +0.26 | 1.49 | +11.6 | -4.8% | PASS (45 trans., +0.23R, PF 1.42) | FAIL (17 trans., -0.21R, PF 0.69) |
| SILVER | mean_reversion | 1d | 55 | 45% | +0.35 | 1.55 | +19.0 | -5.5% | WEAK (45 trans., +0.30R, PF 1.45) | FAIL (12 trans., -0.63R, PF 0.28) |
| PALLADIUM | trend_pullback | 1d | 69 | 51% | +0.24 | 1.44 | +16.2 | -7.4% | PASS (66 trans., +0.20R, PF 1.36) | FAIL (29 trans., +0.02R, PF 1.03) |
| ALUMINIUM | mean_reversion | 4h | 41 | 54% | +0.35 | 1.69 | +14.2 | -3.2% | PASS (41 trans., +0.25R, PF 1.47) | FAIL (10 trans., -1.22R, PF 0.21) |

**Które PASS przetrwały: żaden.** Koszty ×2 przetrwały cztery (VIX, NATGAS, PALLADIUM na 1d, ALUMINIUM na 4h),
ale żadna kombinacja nie ma PASS na drugim interwale (wszystkie FAIL). Do tego trzy z tych czterech mają osobny problem z danymi:

- **NATGAS** — seria `NG=F` ma sztuczne skoki przy rolowaniu (A3: do −47,5% na jednej świecy), których na CFD nie ma.
  Powrót do średniej „zarabia” właśnie na takich skokach, więc ten wynik jest najpewniej artefaktem.
- **VIX** — `^VIX` to indeks kasowy; CFD w XTB jest na kontrakcie futures z silnym contango, a koszt utrzymania pozycji
  nie przypomina założonego swapu. Wynik z indeksu nie przenosi się na instrument, którym da się handlować.
- **ALUMINIUM** — dane 4h są dziurawe i mają dużo świec o zerowym zasięgu (A3), 41 transakcji.
- **PALLADIUM** — jedyny bez zastrzeżeń do danych bieżących, ale na 4h oczekiwana to +0,02R, a stara historia 1d to same zamknięcia.

**Obraz zbiorczy.** 6 PASS na 123 kombinacje to ok. 5%, czyli tyle, ile daje przypadek. Suma wyników wszystkich instrumentów
jest ujemna dla każdej strategii na obu interwałach:

| Strategia | 1d: transakcje | 1d: suma R | 1d: mediana oczek. R | 4h: transakcje | 4h: suma R | 4h: mediana oczek. R |
|---|---|---|---|---|---|---|
| trend_pullback | 2768 | −86,8 | −0,05 | 973 | −40,8 | +0,01 |
| donchian_breakout | 3813 | −491,7 | −0,09 | 1535 | −25,0 | −0,12 |
| mean_reversion | 2015 | −197,8 | −0,16 | 788 | −100,7 | −0,16 |

## B2. Koszty z XTB

**Co zrobione (częściowo).** Użytkownik dostarczył PDF „Tabela stawek punktów swapowych... obowiązująca od 09.11.2026”.
Stawki kosztów finansowania dla wszystkich 43 instrumentów są wpisane w `config/instruments.yaml` w polu `costs`
(stawka dzienna w % × 365 / 100; wartość dodatnia = koszt) i B1 jest powtórzone.

| Grupa | Long rocznie | Short rocznie | Założenie sprzed zmiany (long / short) |
|---|---|---|---|
| US500, US100, US30, US2000 | 8,0% | 0,08% | 6% / 1% |
| DE40 | 6,5% | 1,6% | 6% / 1% |
| GOLD, COCOA, COFFEE, SUGAR | 12,6% | 4,6% | 6–8% / 1–2% |
| OIL, OIL.WTI, NATGAS, GASOLINE | 15,6% | 7,7% | 8% / 2% |
| SILVER, PLATINUM, PALLADIUM | 14,1% | 6,2% | 6% / 1% |
| pozostałe towary (zboża, miedź, aluminium) | 8,5% | 0,6% | 8% / 2% |
| BITCOIN, ETHEREUM, SOLANA | 35,5% | 10,1% | 25% / 10% |

**Co nie działa.**
- PDF nie zawiera spreadów ani wartości nominalnej lota: spready w `cost_defaults` to nadal założenia, a
  `config/contracts.yaml` jest pusty.
- Strona https://www.xtb.com/pl/specyfikacja-instrumentow (wskazana przez użytkownika) nie ma tabeli w HTML; ładuje ją
  skrypt z adresu, który odpowiedział HTTP 403 (zapora). Zabezpieczenia nie obchodziłem; do programu nie dodałem
  żadnego pobierania z XTB (zasada 2).
- AUS200 ma w XTB symbol `AU200.cash`: stawka wzięta z tego wiersza, nazwa w konfiguracji bez zmian.
- Stawki XTB się zmieniają; po nowej tabeli trzeba je wpisać ponownie (ręcznie).
- Backtest liczy swap jako stały procent ceny wejścia za każdą noc kalendarzową; XTB liczy od bieżącej ceny.

## B3. Kalkulator wielkości pozycji

**Co zrobione.** `cfd size SYMBOL --entry X --sl Y --risk-pct Z --equity E [--account-currency PLN] [--fx-rate K]
[--lot-multiplier M --currency USD]`. Moduł `src/cfd/sizing.py`, 11 testów w `tests/test_sizing.py`.
Wolumen = ryzyko / (|wejście − SL| × mnożnik lota × kurs), zaokrąglony **w dół** do kroku lota, więc strata na SL nigdy
nie przekracza zadanego procentu. Gdy nawet minimalny lot przekracza ryzyko, wynik to 0 z wyjaśnieniem.

**Co nie działa.** `config/contracts.yaml` jest celowo pusty: mnożników lota nie wpisywałem z pamięci, bo błąd oznacza
błędną wielkość pozycji. Do czasu uzupełnienia (B2) trzeba podać `--lot-multiplier` i `--currency` ręcznie; bez nich
polecenie kończy się jasnym błędem. Kurs walutowy podaje użytkownik (`--fx-rate`), program go nie pobiera.
Specyfikacja kontraktów jest w osobnym pliku, a nie w polu `costs` w `instruments.yaml`, bo to inny rodzaj danych niż koszty.
Wynik nie uwzględnia spreadu, swapu ani poślizgu.

## C1. Feedy

**Co zrobione.** `cfd news check-feeds` na żywo (10–11.11.2026, środowisko w chmurze za proxy z listą hostów), ręczne sprawdzenie nagłówków odpowiedzi, poprawki `config/feeds.yaml` i adaptera `src/cfd/news/rss.py`.

**Wynik (stan końcowy: działa 18 z 18 włączonych; 9 wpisów wyłączonych czeka na sprawdzenie u użytkownika).**

| Status | Feedy |
|---|---|
| działa | `fed_press`, `ecb_press`, `eia_today`, `eia_press`, `marketwatch`, `coindesk`, nowy `wsj_markets` (Dow Jones, 61 pozycji), 8 zapytań Google News EN, 2 nowe zapytania Google News PL (`NBP stopy procentowe`, `GPW WIG20`) |
| serwis odrzuca automat | `bankier_news`, `bankier_gielda` (HTTP 403, nagłówek `cf-mitigated: challenge`, czyli wyzwanie Cloudflare; także dla `robots.txt`), `cnbc_top` (HTTP 403 „Access Denied” z Akamai). Sprawdzone z adresu IP centrum danych; z domowego łącza mogą działać. Ustawione `enabled: false`, zabezpieczeń nie obchodzę (zasada 3). |
| serwis zmienił adres | `coindesk`: adres z końcowym `/` odpowiadał 308; poprawiony na `…/outboundfeeds/rss`. |
| niesprawdzalne tutaj (host zablokowany przez proxy środowiska) | nowe wpisy `nbp_news`, `pap_biznes`, `pap_espi`, `boe_news`, `boj_news`, `snb_press`: adresy z pamięci, nigdy niepobrane, `enabled: false`, komentarz „niezweryfikowane (host zablokowany w srodowisku testowym)”. |
| odrzucone | `mw_marketpulse` (Dow Jones) odpowiada 200, ale najnowsza pozycja jest z lipca 2025: martwy feed, nie dodany. |

**Hosty do odblokowania, żeby dokończyć weryfikację:** `nbp.pl`, `biznes.pap.pl`, `www.gpw.pl`, `www.bankofengland.co.uk`, `www.boj.or.jp`, `www.snb.ch`, `search.cnbc.com` (alternatywny adres RSS CNBC). Prościej: uruchomić `cfd news check-feeds` z własnego komputera; polecenie sprawdza teraz także wyłączone wpisy i oznacza je `[wylaczony w feeds.yaml]`.

**Google News.**
- Przekierowanie 302 pojawia się tylko wtedy, gdy w adresie brakuje kompletu `hl`, `gl`, `ceid` (Google dokleja domyślne). Adapter zawsze je wysyła i dostaje 200 od razu; gdyby 302 jednak przyszło, klient `httpx` ma `follow_redirects=True` (test na atrapie transportu).
- Blokada: łącznie ok. 20 przebiegów po 8–10 zapytań, w tym 14 kolejnych co ok. 4 minuty przez 54 minuty (20:42–21:37 UTC): 0 błędów, 0 odpowiedzi 429, 0 przekierowań na stronę `/sorry/`, czas przebiegu stały 10–11 s. Przy odstępie 5 minut Google nie blokuje. Nie testowałem dłużej niż godzinę ani z domowego adresu IP.
- Dodany parametr `when: "1d"`: bez niego wyszukiwarka zwraca też artykuły sprzed tygodni.
- Feed zawiera zastrzeżenie Google: użytek osobisty, niekomercyjny, w czytniku RSS (patrz pytanie w decyzjach).

**Zmienione w kodzie.**
- `rss.py`: pole `enabled` we wpisie feedu; zapytanie Google News jako napis albo słownik `{q, hl, gl, ceid}` (polska edycja); `when`; `fetch_feed` zgłasza `DataSourceError` z przyczyną (HTTP 403 z ochrony przed botami, 429, strona blokady Google, odpowiedź niebędąca XML, feed bez pozycji) zamiast surowego wyjątku albo cichej pustej listy.
- `rss.py`: Google News dokleja do tytułu „ - Wydawca”, a opis to powtórzony tytuł. Wydawca jest teraz odcinany, opis pomijany. W próbce 599 newsów 13 dostało symbol albo wagę wyłącznie przez nazwę wydawcy („Crude Oil Prices Today | OilPrice.com”, „Crypto News”).
- `cli.py` (`news check-feeds`): sprawdza także wyłączone wpisy, krótszy komunikat błędu.
- Fixtures z prawdziwych odpowiedzi: `tests/fixtures/news_gnews_gold_price.xml`, `news_gnews_pl_nbp.xml`, `news_fed_press.xml`.

**Co nie działa.** Polskie źródła bezpośrednie (Bankier, PAP Biznes, ESPI/EBI, NBP) nie są potwierdzone: Bankier odrzuca automat, reszta niesprawdzalna stąd. Do tego czasu Polskę pokrywają tylko dwa zapytania Google News PL (10 i 17 pozycji na dobę).

## C2. Jakość mapowania i klasyfikacji

**Co zrobione.** Trzy serie `cfd news poll` (10.11.2026, dzień publikacji CPI w USA): 2 przebiegi o 07:40 UTC, 4 przebiegi 15:42–15:52 i 14 przebiegów co ok. 4 minuty 20:42–21:37 (ostatnia seria już na nowej konfiguracji i nowym kodzie). W bazie 1067 newsów. Próba bazowa do oceny starych reguł: 599 newsów z dwóch pierwszych serii (408 zmapowanych; wagi: 85 × 3, 212 × 2, 97 × 1, 16 duplikatów).

**Fałszywe trafienia słów kluczowych (próba bazowa, liczone po całych słowach).**

| Słowo | Trafień | Wynik |
|---|---|---|
| `fed` | 53 | 0 fałszywych (wszystkie „Fed”). Zawężone do pisowni `Fed`/`FOMC`, bo „fed up”, „fed cattle” przeszłyby. |
| `gold` | 84 | ok. 30 nie dotyczy XAU/USD: ceny detaliczne w Indiach, Pakistanie, Indonezji, Wietnamie (ok. 15), spółki wydobywcze: Kinross, Barrick, Equinox, „gold miners” (ok. 12), pozostałe. Dodana lista wykluczeń; odcina 24 z 84. |
| `eth`, `ether` | 2 + 1 | 0 fałszywych; zawężone do pisowni `ETH`, `Ether`. |
| `lng` | 2 | 1 fałszywe („LNG Traffic Through Hormuz”: nie Henry Hub). Zastąpione przez `lng exports`, `us lng`. |
| `wall street` | 8 | 5 to „co mówi Wall Street” (analitycy), nie indeks. Przeniesione z US500 wprost do tematu `us_stocks`. |
| `soybean` | 1 | 1 fałszywe („Soybean Oil”); wykluczenie. |
| `inflation` (temat USA) | 88 | łapało inflację spoza USA (Grecja, Indie). Zawężone do `CPI`, `us inflation`, `inflation report/data`, `PCE`. |
| `surge`, `plunge`, `crash`, `record high` | 9 + 5 + 3 + 4 | ok. połowa dotyczy czegoś innego niż instrument (rentowności, auta, emisje CO2, pojedyncze akcje). Liczą się teraz tylko razem z dopasowaniem wprost. |
| `bankruptcy`, `default`, `emergency`, `halts` | 1 | 1 fałszywe („Global Bankruptcy Fears”). Zawężone do fraz („files for bankruptcy”, „debt default”, „emergency meeting”, „trading halted”). |
| `corn`, `sugar`, `boj`, `gpw`, `cotton`, `coffee` | 0 | brak trafień tego dnia, więc brak pomiaru. Zawężone zapobiegawczo do fraz rynkowych („corn futures”, „sugar prices”) i pisowni skrótów (`BoJ`, `GPW`); testy na przykładach („blood sugar”, „corn dogs”, „bój”). |

**Ręczna ocena 50 newsów z wagą 3 (stare reguły, pierwsze 50 w kolejności pobrania).**
- 22 z 50 (44%) opisywały faktyczne, świeże zdarzenie rynkowe (odczyt CPI, Waller o podwyżce o 0,5 pkt, Nagel z EBC, spadek ropy po słowach Trumpa o Iranie, produkcja OPEC).
- Z tych 22 tylko 5 to pierwsza informacja o zdarzeniu; 17 to kolejne redakcje piszące o tym samym. Użyteczny alert: 5 z 50 (10%).
- 22 z 50 (44%) to zapowiedzi, prognozy i komentarze („ahead of CPI”, „Price Forecast”, „What to expect”), podbite do 3 przez samo słowo „CPI”.
- 6 z 50 (12%) to szum (podsumowania wczorajszej sesji, „Global Bankruptcy”).
- Skutek praktyczny: jeden przebieg o 15:42 wysłałby 60 alertów.

**Zmiany w regułach i ich efekt.**
- Frazy wysokiej wagi szukane tylko w tytule; słowa ruchu (`surge`, `plunge`…) tylko przy dopasowaniu wprost.
- Tytuł będący zapowiedzią, prognozą albo pytaniem dostaje najwyżej 2.
- Kolejny news o temacie, który w ostatnich 60 minutach dostał już wagę 3 (te same frazy + ten sam instrument), dostaje 2 (`repeat_cooldown_minutes` w `process_items`).
- Te same 599 newsów przeliczone nowymi regułami: waga 3 dla 16 zamiast 85; z ocenionych 50 zostaje 10. Uwaga: w tym przeliczeniu okno 60 minut objęło całą próbę naraz, więc efekt tłumienia powtórek jest zawyżony.
- Na żywo, nowa konfiguracja: przebieg nadrabiający 5 godzin dał 12 alertów (wcześniej 60 w podobnej sytuacji), potem 13 przebiegów ciągłych przez 54 minuty dało 2 alerty na 106 nowych newsów.
- Reguły nadal nie rozumieją treści: wśród 16 pozostałych „trójek” ok. połowa jest trafna. Resztę ma odsiać LLM (C3).

**Opóźnienie publikacja → pobranie** (newsy, które pojawiły się między kolejnymi przebiegami co ok. 4 minuty; 127 pozycji):

| Źródło | n | mediana | p25 | p90 | do 10 min |
|---|---|---|---|---|---|
| MarketWatch | 6 | 4,5 min | 3,1 | 6,4 | 6 z 6 |
| WSJ Markets | 6 | 4,8 min | 3,3 | 7,7 | 6 z 6 |
| Google News | 115 | 64 min | 11,9 | 368 | 26 z 115 (23%) |

- Feedy bezpośrednie: opóźnienie równe odstępowi odpytywania plus 1–3 minuty; przy `poll_seconds: 120` realnie 2–5 minut.
- Google News: wolny i nierówny. Jedna trzecia pozycji (38 z 115) pojawia się w wynikach ponad 3 godziny po publikacji. Nadaje się na tło i potwierdzenie, nie na szybki alert.
- Fed, EBC, EIA i CoinDesk nie opublikowały nic nowego w oknach pomiaru, więc brak dla nich liczby.

**Co nie działa / ograniczenia.** Jeden dzień danych, zdominowany przez CPI; słowa rolne i polskie praktycznie bez próby. Nagłówki PL trafiają do W20 tylko przez temat `nbp` (waga 1), bo frazy wysokiej wagi po polsku są nieliczne („podwyżka stóp”, „stopy bez zmian”…).

## C3. Klasyfikator LLM

**Część porównawcza na żywo: niewykonana.** W środowisku nie ma `ANTHROPIC_API_KEY`, więc porównania reguły vs LLM na 50 newsach nie było. Przygotowany skrypt robi to jednym poleceniem po wpisaniu klucza: `python -m cfd.news.compare --limit 50 --min-importance 3` (tabela, zgodność wag, tokeny, koszt).

**Model i wywołanie (źródło: skill `claude-api`, stan 2026-11-03).**
- Tani model to Claude Haiku 5.5, identyfikator `claude-haiku-5-5` (bez sufiksu daty). Domyślna wartość w kodzie i `.env.example` była poprawna.
- Cena: 0,10 USD za 1 mln tokenów wejścia, 0,50 USD za 1 mln tokenów wyjścia (prompty do 100 tys. tokenów). Haiku 4.5 kosztuje 1 / 5 USD.
- Błąd w starym wywołaniu: `max_tokens: 300` przy modelu, który domyślnie „myśli”, a myślenie wlicza się do limitu. Odpowiedź mogła urwać się przed JSON-em i każdy news wracałby po cichu do reguł. Odpowiedź może też zaczynać się od bloku `thinking`.
- Poprawione w `src/cfd/news/classify.py`: oficjalne SDK `anthropic` zamiast ręcznego `httpx`; `max_tokens: 1024`; `output_config: {effort: "low", format: {type: "json_schema", …}}` (gwarantowany JSON zgodny ze schematem zamiast wycinania klamer z tekstu); bloki czytane po typie; `stop_reason` `refusal` i `max_tokens` oznaczają powrót do reguł; zliczanie tokenów i kosztu. Bez `temperature` i bez ręcznego budżetu myślenia (na tym modelu dają błąd 400).
- Kierunki w odpowiedzi to teraz lista `{symbol, direction: up|down|none}`; parser przyjmuje też stary format słownikowy.
- Sprawdzone lokalnie: SDK `anthropic` 2.8.0 przyjmuje parametr `output_config`. Prawdziwego wywołania API nie było.

**Testy na atrapie.** `test_llm_classifier_request_shape_and_response_parsing` (kształt żądania: model, `max_tokens`, `output_config`, brak usuniętych parametrów; odpowiedź z blokiem `thinking` przed tekstem; zliczanie tokenów i kosztu) oraz `test_llm_classifier_falls_back_on_refusal_truncation_and_errors`.

**Szacunek kosztu miesięcznego (szacunek, nie pomiar).**
- Wolumen newsów z wagą regułową ≥ 2, czyli trafiających do LLM: 45 w 54 minuty ciągłego odpytywania wieczorem (ok. 50 na godzinę); 164 z jednego przebiegu po 8 godzinach przerwy (ok. 20 na godzinę, zaniżone, bo feed pokazuje tylko 100 najnowszych pozycji). Przyjmuję 20–50 na godzinę w dni robocze, średnio ok. 800 dziennie, w weekendy ok. 250: razem ok. 20 tys. wywołań miesięcznie. To był dzień CPI, więc raczej górna część zakresu.
- Tokeny na wywołanie (z długości promptu: 651 znaków plus schemat 442 znaki): ok. 500 wejścia i ok. 300 wyjścia łącznie z myśleniem przy `effort: low`.
- Koszt jednego wywołania: 500 × 0,10 / 1 mln + 300 × 0,50 / 1 mln ≈ 0,0002 USD.
- **Miesięcznie ok. 4 USD** (20 tys. × 0,0002). Zakres przy skrajnych założeniach (10–36 tys. wywołań, 0,00012–0,00035 USD każde): 1–13 USD. Na Haiku 4.5 byłoby to ok. 10 razy więcej.
- Po pierwszym uruchomieniu z kluczem `compare` wypisze rzeczywiste tokeny na news; wtedy szacunek warto poprawić.

**Co nie działa / do zrobienia.**
- Pakiet `anthropic` nie jest zadeklarowany w `pyproject.toml` (plik poza moim zakresem). Bez niego klasyfikator LLM loguje ostrzeżenie i wraca do reguł. Trzeba dopisać zależność, np. `llm = ["anthropic>=2.8"]` w `[project.optional-dependencies]`.
- Host `api.anthropic.com` trzeba dopuścić tam, gdzie narzędzie będzie działać.

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

## E1. FRED

**Stan: zrobione bez klucza.** `FRED_API_KEY` nie jest ustawiony, więc ścieżka przez `api.stlouisfed.org` pozostaje niesprawdzona na żywo (bez klucza API odpowiada HTTP 400).

Co zrobione:
- `FredClient` dostał ścieżkę zapasową bez klucza: publiczny plik `https://fred.stlouisfed.org/graph/fredgraph.csv?id=SERIA&cosd=2010-01-01` (ten sam, który pobiera przycisk „Download” na stronie serii). Z kluczem nadal używane jest API.
- Pułapka: `fred.stlouisfed.org` zrywa połączenie (HTTP/2 INTERNAL_ERROR albo pusta odpowiedź), gdy User-Agent udaje przeglądarkę (`Mozilla/5.0 (compatible; ...)`). Z uczciwym `cfd-analyzer/0.2 (python-httpx)` odpowiada 200 za każdym razem (ok. 30 pobrań w tej sesji). Adapter wysyła ten nagłówek, odstęp 3 s na host, 2 ponowienia.
- `cfd bias check` (na żywo, 2026-11-10) dla wszystkich identyfikatorów z `config/fundamentals.yaml`:

| Seria | Wynik | Ostatnia obserwacja |
|---|---|---|
| DFII10 | OK | 2026-11-06 = 2,63 |
| DTWEXBGS | OK | 2026-11-06 = 121,88 |
| DGS10 | OK | 2026-11-06 = 4,86 |
| DGS2 | OK | 2026-11-06 = 4,51 |
| NFCI | OK (tygodniowa) | 2026-10-30 = −0,459 |
| BAMLH0A0HYM2 | OK, ale FRED udostępnia tylko ostatnie 3 lata (od 2023-11-10, 784 obs.) | 2026-11-06 = 3,42 |
| WCESTUS1 | **BŁĄD: HTTP 404, tej serii nie ma w FRED** (to identyfikator EIA) | – |

- Poprawka: `WCESTUS1` zastąpione serią z EIA `EIA:PET.WCESTUS1.W` (patrz E2). Pozostałe identyfikatory bez zmian.
- `cfd bias update`: bias policzony dla 30 instrumentów (ok. 80 s; 29 zapytań, z tego 20 do CFTC). `cfd bias show` pokazuje teraz także składowe.

Ocena sensowności (stan na 2026-11-10, okno 63 dni):
- Szeroki indeks dolara 118,07 → 121,88 (+3,2%, przy szczycie rocznego zakresu 117,4–122,0): składowa −1,55 dla złota, srebra, platyny, miedzi, ropy i krypto. Kierunek i skala zgodne z danymi.
- Realna rentowność 10Y 2,43 → 2,63: −0,68 dla złota i srebra.
- Indeksy USA −0,88: spread high yield 2,68 → 3,34 (−1,74), NFCI −0,545 → −0,459 (−0,66), 10Y 4,78 → 4,86 (−0,23). Wszystkie trzy składowe pokazują to samo zacieśnienie, więc wynik jest spójny.
- USDIDX +0,22: 2Y 4,37 → 4,51 (+0,44), pozycjonowanie neutralne.
- Wniosek: liczby są zgodne z ruchem serii, żadna składowa nie wygląda na błąd znaku ani jednostki. Zastrzeżenia: (1) to heurystyki, nie model, bez sprawdzenia skuteczności na historii; (2) dolar wchodzi do sześciu grup instrumentów, więc biasy są mocno skorelowane; (3) dla BAMLH0A0HYM2 odchylenie liczone jest tylko z 3 lat.

Zmienione: `src/cfd/fundamentals/fred.py`, nowy `src/cfd/fundamentals/_http.py`, `config/fundamentals.yaml`, `src/cfd/cli.py` (polecenia `bias`, `_context`: bias nie wymaga już klucza FRED), testy w `tests/test_fundamentals.py`, próbka `tests/fixtures/fred_fredgraph_BAMLH0A0HYM2.csv`.

Nie działa / niesprawdzone: ścieżka FRED z kluczem (parser pokryty testem, ale tylko na odpowiedzi w formacie z dokumentacji, nie na prawdziwej).

## E2. Zapasy (EIA) i pozycjonowanie (COT)

### EIA
- Nowy `src/cfd/fundamentals/eia.py` (`EiaClient`). Identyfikatory jak w API: `PET.WCESTUS1.W` (ropa bez SPR, tys. baryłek), `PET.WGTSTUS1.W` (benzyna ogółem), `NG.NW2_EPG0_SWO_R48_BCF.W` (gaz w magazynach, Lower 48, Bcf).
- Z `EIA_API_KEY`: API v2 `https://api.eia.gov/v2/seriesid/<ID>`. **Niesprawdzone na żywo**: klucza nie ma, API zwraca `API_KEY_MISSING` (HTTP 403). Format danych (`response.data[].period/value`) wpisany z dokumentacji; próbka z prawdziwej odpowiedzi to tylko komunikat błędu.
- Bez klucza albo gdy API zawiedzie: publiczna strona historii na `www.eia.gov/dnav/...` (dla PET `LeafHandler.ashx?n=PET&s=...&f=W`, dla NG `dnav/ng/hist/<seria>w.htm`). `robots.txt` EIA nie blokuje `/dnav/`, dane rządowe USA są w domenie publicznej, jedno zapytanie na serię na przebieg, odstęp 5 s. Sprawdzone na żywo: ropa 2301 obs. do 2026-10-30 = 409 760, benzyna 1922 obs. = 208 958, gaz 879 obs. = 3 801.
- Składowe: zapasy są sezonowe (zwłaszcza gaz i benzyna), więc doszła opcja `transform: yoy`: liczona jest 28-dniowa zmiana nadwyżki wobec tego samego tygodnia rok wcześniej, znak −1. Test pokazuje, że bez tej transformacji sama sezonowość daje fałszywy sygnał.
- Wyniki 2026-11-10: ropa +1,22 (zapasy −14,4 mln b w 4 tygodnie, rok wcześniej +0,9 mln), benzyna −2,00 (+4,2 mln b, rok wcześniej −13,1 mln), gaz −0,19 (+301 Bcf, rok wcześniej +274 Bcf).

### COT
- Nowy `src/cfd/fundamentals/cot.py` (`CotClient`), API Socrata CFTC bez klucza, raporty „futures only”: `legacy` = zbiór `6dca-aqww` (non-commercial), `disaggregated` = `72hh-3qpy` (managed money), `tff` = `gpe5-46if` (leveraged funds). Wszystkie trzy zbiory sprawdzone na żywo, ostatni raport 2026-11-03. Pobierane 5 lat (261 raportów na kontrakt), odstęp 1 s.
- Nowy typ składowej `type: positioning` (`positioning_score` w `bias.py`, korzysta z `positioning_percentile`): percentyl pozycji netto na tle 156 raportów; ≥ 90 daje −1…−2, ≤ 10 daje +1…+2, w środku 0. Progi, okno i znak konfigurowalne per składowa.
- Mapowanie instrument → kod kontraktu w `config/fundamentals.yaml`, sekcja `cot_contracts` (20 instrumentów: metale, energia, rolne, USDIDX). Kody wzięte z raportu z 2026-11-03 i każdy sprawdzony zapytaniem.
- Odczyty 2026-11-10 (percentyl → składowa): LEANHOGS 1 → +1,94; NATGAS 1 → +1,94; COFFEE 2 → +1,81; PALLADIUM 3 → +1,68; SILVER 4 → +1,55; COCOA 9 → +1,10; GASOLINE 92 → −1,23; SUGAR 96 → −1,55; pozostałe 12 w strefie neutralnej (m.in. GOLD 22, COPPER 47, OIL.WTI ok. 10 (tuż nad progiem), OIL 30).

### Bias dla instrumentów z zadania
| Instrument | Bias | Składowe |
|---|---|---|
| OIL | −0,11 | zapasy ropy +1,22; dolar −1,55; COT 0 (percentyl 30) |
| OIL.WTI | −0,11 | zapasy ropy +1,22; dolar −1,55; COT 0 (percentyl 10) |
| GASOLINE | −0,67 | zapasy benzyny −2,00; zapasy ropy +1,22; COT −1,23 (percentyl 92) |
| NATGAS | +0,87 | magazyny gazu −0,19; COT +1,94 (percentyl 1) |

### Inne zmiany
- `SeriesRouter` (`fundamentals/sources.py`): prefiks identyfikatora wybiera źródło (`EIA:`, `CFTC:`, bez prefiksu FRED).
- Kontrola świeżości: składowa jest odrzucana z błędem, gdy ostatnia obserwacja jest starsza niż `max_age_days` (45). Wcześniej wycofana seria dawałaby po cichu wynik 0.
- Testy: `tests/test_fundamentals.py` (21 testów) na próbkach `fred_fredgraph_BAMLH0A0HYM2.csv`, `eia_hist_WCESTUS1.html`, `eia_hist_nw2_epg0_swo_r48_bcfw.html` (obie strony EIA skrócone do lat 2023–2026), `eia_api_key_missing.json`, `cftc_disaggregated_088691.json`, `cftc_error.json`. Całość: `pytest -q` → 117 passed.

### Ograniczenia
- Składowa COT w strefie neutralnej ma wartość 0 i wchodzi do średniej, więc rozcieńcza pozostałe składowe (np. GOLD: −0,68 i −1,55 dają −0,74 zamiast −1,12). To świadomy, ostrożny wybór; alternatywa (pomijanie neutralnej) wymaga decyzji.
- Dla OIL (Brent) użyty jest kontrakt „BRENT LAST DAY” z NYMEX (otwarte pozycje ok. 208 tys.). Główny Brent na ICE Europe nie jest w raportach CFTC.
- Instrumenty rolne, PALLADIUM mają bias wyłącznie z COT: zwykle 0, przy skrajnościach od razu ±1…2.
- Indeksy akcji i krypto nie dostały składowej COT (nie ustalałem, która grupa uczestników ma tam sens kontrariański).
- Skuteczność składowych kontrariańskich nie była testowana na historii cen.
- Poza moimi plikami zostały nieaktualne opisy: `README.md` (wiersz „zapasy EIA i COT: niezaimplementowane”), `.env.example` (brak `EIA_API_KEY`), `dashboard.py` (tekst „Wymaga FRED_API_KEY”).

## E3. Akcje

Pominięte: brak listy spółek (decyzja użytkownika). Nic nie zmieniono.

## F1. Telegram

Nie wykonane: brak `TELEGRAM_BOT_TOKEN` i `TELEGRAM_CHAT_ID` (decyzja 3), a host `api.telegram.org` nie jest dozwolony
w środowisku testowym. `cfd notify-test` bez kluczy używa konsoli; formatowanie wiadomości widać w logu z F2.

## F2. Pierwszy pełny przebieg

**Co zrobione.** `cfd -v run --once`, potem `cfd health`, `cfd journal`, `cfd dashboard`, a następnie `cfd -v run`
przez 61 minut (2026-11-11, 11:59–13:00 UTC) z pomiarem pamięci co minutę. Bez kluczy: powiadomienia szły na konsolę,
newsy klasyfikowały same reguły.

**Co wyszło: przebieg jednorazowy** (4 min 7 s, nic nie padło):

| Zadanie | Wynik |
|---|---|
| fundamentals | bias policzony dla 27 instrumentów |
| macro | 0 nowych alertów (kalendarz i odczyty odświeżone) |
| news | 12 newsów z alertem |
| scan | 11 nowych sygnałów w dzienniku (1d i 4h), wszystkie otwarte |

`cfd health`: wszystkie włączone źródła OK (świece Yahoo i Binance, 18 feedów, makro, fundamenty).
`cfd journal` i `cfd dashboard` działają; rozliczonych sygnałów jeszcze nie ma.

**Co wyszło: godzina pracy ciągłej.** Proces działał do końca (zatrzymany przez limit czasu testu), 0 wyjątków w logu.

- **Pamięć (RSS):** 123 MB na starcie, 279 MB po 5 min (załadowane świece), 340 MB po 30 min, 350 MB po 60 min.
  Po pierwszych 25 minutach przyrost to ok. 10 MB na pół godziny. Godzina to za mało, żeby rozstrzygnąć, czy to wyciek,
  czy dochodzenie do poziomu stałego: do sprawdzenia w teście dobowym. Limit 1 GB w `deploy/` ma zapas.
- **Zapytania HTTP w godzinę** (z logu `httpx`; Yahoo idzie przez `yfinance` i nie jest tu liczone):

  | Serwis | Zapytań | Uwagi |
  |---|---|---|
  | news.google.com | 100 | 10 zapytań co ok. 6 min, wszystkie 200 |
  | feeds.content.dowjones.io | 44 | MarketWatch i WSJ |
  | data-api.binance.vision | 24 | świece krypto |
  | federalreserve.gov, ecb.europa.eu, coindesk.com | po 22 | |
  | publicreporting.cftc.gov | 20 | COT, jednorazowo przy starcie |
  | www.eia.gov | 13 | zapasy, jednorazowo |
  | fred.stlouisfed.org | 7 | jednorazowo |
  | api.bls.gov | 2 | limit dobowy wyczerpany, zapas FRED zadziałał |
  | stooq.com | 2 | oba nieudane (zerwane połączenie, 404) |
  | nfs.faireconomy.media | 1 | kalendarz z cache |
  | api.binance.com | 1 | 451, potem zapasowy host |

  Razem 280 odpowiedzi: 277 × 200, 2 × 404 (Stooq), 1 × 451 (Binance). **Żaden serwis nie zaczął odrzucać połączeń.**
- **Alerty newsowe:** 2 „PILNE” w godzinę (po 12 w przebiegu nadrabiającym).
- **Panel:** `reports/panel.html` odświeżany co 5 minut przez nowe zadanie `dashboard`.

**Co zmienione w kodzie.** Zadanie `dashboard` w `runner.py` (opis w F3). Poza tym w tym zadaniu nic nie wymagało naprawy:
błędy znalezione wcześniej poprawiono w zadaniach A, C, D i E.

**Co nie działa / uwagi.**
- Każdy skan W20 najpierw próbuje Stooq (nieudane), potem Yahoo: działa, ale zostawia ostrzeżenie w logu przy każdym skanie.
- `cfd health` nadal pokazuje jako BŁĄD wyłączone feedy (Bankier, CNBC) z wcześniejszych prób (pytanie w `DECYZJE.md`).
- Reguły nadal przepuszczają jako „PILNE” tytuły spekulacyjne, np. „Bitcoin May Recover Before The First Rate Cut”
  (fraza „rate cut” w tytule). Klasyfikator regułowy ocenia słowa, nie sens: to argument za LLM albo za węższą listą fraz.
- Jeden news mapuje się na 7 instrumentów (BITCOIN, US500, US100, US30, GOLD, SILVER, USDIDX), bo hasło „rate” dotyka
  wszystkich: alerty są przez to mało konkretne.
- Liczba zapytań do Yahoo nie była mierzona (brak logu z `yfinance`); błędów ani odmów z Yahoo nie było.
- Test trwał godzinę, w jednej sesji europejskiej. Zachowanie przez noc, weekend i otwarcie rynków jest niesprawdzone.

## F3. Uruchamianie w tle

**Co zrobione.** Decyzji „gdzie ma działać” jeszcze nie ma, więc przygotowane są wszystkie trzy warianty w `deploy/`
(opis w `deploy/README.md`): usługa systemd, `Dockerfile` z `docker-compose.yml`, skrypt Harmonogramu zadań Windows.
Każdy ma automatyczny restart po awarii i rotację logów. Odświeżanie `reports/panel.html` robi teraz sam `cfd run`
(nowe zadanie `dashboard`, ustawienie `dashboard.refresh_minutes` w `config/settings.yaml`, domyślnie 5 min), więc
żaden wariant nie potrzebuje osobnego harmonogramu.

**Co nie działa.** Żaden z trzech wariantów nie był uruchomiony na docelowym systemie (tu nie ma systemd w roli
menedżera usług, demona Dockera ani Windows). Samo zadanie `dashboard` jest przetestowane i działało w przebiegu z F2.

## G. Później

Nie zaczynane (wymaga decyzji 13–15). Po B1 uwaga do G3: obecne trzy strategie nie mają przewagi, więc nowe strategie
i filtr reżimu mają sens dopiero po decyzjach o danych (rolowanie, stara historia) i po wpisaniu prawdziwych kosztów.

## B1 po scaleniu z v0.3: akcje i interwał 1h (2026-11-11)

Swapy XTB dla CFD, rolowania wykluczone, spready założone (akcje: 0,30%, bez swapu). 30m pominięte: 59 dni historii
to za mało na walk-forward (750 + 250 świec dałoby jedno okno).

| Zakres | Interwał | Kombinacji | PASS | WEAK | FAIL | PASS przy kosztach ×2 |
|---|---|---|---|---|---|---|
| 30 spółek (SPL.PL bez danych) | 1d | 90 | 4 | 13 | 73 | 2 |
| 30 spółek | 4h | 90 | 0 | 0 | 90 | 0 |
| 71 instrumentów | 1h | 213 | 2 | 23 | 188 | nie liczono |

PASS: akcje 1d — TTWO.US mean_reversion (93 trans., +0,18R), OXIG.UK donchian_breakout (205, +0,29R),
AST.PL donchian_breakout (96, +0,25R; ×2: PASS +0,20R), RBW.PL donchian_breakout (88, +0,33R; ×2: PASS +0,29R).
Żadna z nich nie ma PASS na 4h. 1h — EU50 trend_pullback (39 trans., +0,27R), JP225 trend_pullback (36, +0,38R).

Suma na 1h, wszystkie instrumenty:

| Strategia | Transakcje | Suma R | Mediana oczek. R | W tym koszty (R) |
|---|---|---|---|---|
| trend_pullback | 4666 | −730,3 | −0,20 | 590,0 |
| donchian_breakout | 7531 | −1099,6 | −0,17 | 983,2 |
| mean_reversion | 3679 | −578,7 | −0,11 | 550,5 |

Wnioski:
- Na 1h jest 3–5 razy więcej transakcji niż na 1d, ale wynik jest wyraźnie gorszy. Koszty to ok. 0,13R na transakcję:
  odpowiadają za większość straty, a przed kosztami wynik jest w okolicach zera lub ujemny.
- Akcje na 1d: `donchian_breakout` ma dodatnią sumę (+76,5R na 1631 transakcjach) przy kosztach bazowych i ujemną (−42,2R) przy ×2.
  Cała „przewaga” mieści się w niepewności co do spreadu.
- Na 4h dla akcji historia jest za krótka: prawie wszystkie kombinacje padają na liczbie transakcji.
- Nadal żadna strategia nie przechodzi walidacji.

## Test filtra kontekstowego (2026-11-12)

**Pytanie.** Czy sygnały trzech strategii trafiają częściej, gdy zgadza się z nimi kontekst, który program już liczy?

**Co zrobione.** Polecenie `cfd context-test` (`src/cfd/validation/context.py`, testy w `tests/test_context.py`):
- 31 011 transakcji z okien testowych walk-forward (71 instrumentów, 3 strategie, interwały 1d, 4h, 1h), z kosztami i wykluczonymi rolowaniami.
- Każda transakcja ma etykiety kontekstu znane przed wejściem: reżim rynku na interwale sygnału, trend dzienny z poprzedniej sesji
  (cena względem SMA200), zmienność (percentyl ATR), sesja (Azja / Europa / USA), poziom VIX względem rocznej mediany,
  bias fundamentalny liczony tak, jak byłby znany danego dnia (serie FRED, EIA i COT ucięte o 7 dni opóźnienia publikacji).
- Transakcje podzielone w czasie: starsze 60% to próba odkrywcza, nowsze 40% to próba potwierdzająca. Filtr jest kandydatem,
  gdy na próbie odkrywczej ma co najmniej 200 transakcji, dodatni średni wynik i t ≥ 2; potwierdzonym, gdy na próbie
  niewidzianej ma co najmniej 100 transakcji, dodatni wynik i t ≥ 1,65. Filtry liczone łącznie i osobno dla każdej kategorii instrumentów.
- Jest test, że etykiety nie zaglądają w przyszłość (zmiana danych od świecy wejścia nie zmienia etykiety).

**Co wyszło.**

### Punkt odniesienia (wszystkie sygnaly, bez filtra)

| Interwał | Strategia | Odkrywcza: n | Odkrywcza: śr. R | Potwierdzająca: n | Potwierdzająca: śr. R | Granica prób |
|---|---|---|---|---|---|---|
| 1d | donchian_breakout | 3268 | -0.033 | 1929 | -0.088 | 2016-10-09 |
| 1d | mean_reversion | 1402 | -0.109 | 1270 | -0.134 | 2016-10-09 |
| 1d | trend_pullback | 2250 | -0.012 | 1415 | -0.079 | 2016-10-09 |
| 1h | donchian_breakout | 4790 | -0.118 | 2741 | -0.195 | 2025-11-11 |
| 1h | mean_reversion | 2029 | -0.214 | 1650 | -0.088 | 2025-11-11 |
| 1h | trend_pullback | 2706 | -0.174 | 1960 | -0.133 | 2025-11-11 |
| 4h | donchian_breakout | 1111 | +0.003 | 581 | -0.135 | 2026-01-15 |
| 4h | mean_reversion | 425 | -0.197 | 413 | -0.108 | 2026-01-15 |
| 4h | trend_pullback | 624 | +0.009 | 447 | -0.194 | 2026-01-15 |

Filtrów z wystarczającą próbą: 276. Kandydatów na próbie odkrywczej: 3 (z samego przypadku spodziewane ok. 7). Potwierdzonych na próbie niewidzianej: 0 (z samego przypadku spodziewane ok. 0.2).

### Kandydaci i ich wynik na próbie potwierdzającej

| Int. | Strategia | Zakres | Cecha = wartość | Odkr.: n | Odkr.: śr. R | Odkr.: t | Potw.: n | Potw.: śr. R | Potw.: t | Wynik |
|---|---|---|---|---|---|---|---|---|---|---|
| 1d | donchian_breakout | stocks | vol = niska | 277 | +0.326 | 2.5 | 289 | +0.144 | 1.1 | nie utrzymał się |
| 4h | donchian_breakout | crypto | vol = niska | 262 | +0.277 | 2.7 | 24 | -0.613 | -2.2 | za mała próba |
| 4h | trend_pullback | wszystkie | session = usa | 226 | +0.193 | 2.2 | 169 | -0.204 | -2.2 | nie utrzymał się |

**Wniosek: żaden filtr kontekstowy nie daje przewagi.** Na 276 sprawdzonych filtrów kandydatów było 3, czyli mniej, niż dałby
sam przypadek (ok. 7), i żaden nie utrzymał się na danych niewidzianych. Dwa z trzech odwróciły znak. Zgodność z trendem dziennym,
reżim rynku, bias fundamentalny i poziom VIX nie odróżniają sygnałów dobrych od złych w stopniu pokrywającym koszty.

**Czego test nie obejmuje.** Newsów i kalendarza makro (brak darmowego archiwum: da się je ocenić tylko w przód, z dziennika),
kombinacji dwóch cech naraz (celowo, żeby nie mnożyć hipotez), prawdziwych spreadów XTB (nadal założenia) oraz historii
biasu sprzed dostępności serii. Bias istnieje tylko dla 30 instrumentów.

## Ekran „stan na teraz” (2026-11-12)

**Co zrobione.** `cfd now [--intervals 1h 4h 1d] [--offline]` → `reports/teraz.html` i `reports/teraz.json` (`src/cfd/now.py`).
Samodzielny plik HTML na telefon i komputer (jasny i ciemny motyw). Dla każdego sygnału z ostatniej zamkniętej świecy:
kierunek, cena sygnału, SL, TP, stosunek zysku do ryzyka, zmierzona skuteczność z walidacji (liczba transakcji, odsetek
zyskownych, średni wynik po kosztach), etykiety kontekstu oraz ostrzeżenie, gdy cena dotknęła już SL lub TP.
Sygnały są w trzech grupach: z dodatnim wynikiem w walidacji, niepewne, bez przewagi po kosztach. Na dole kalendarz makro i newsy jako tło.
Potwierdzone filtry kontekstowe byłyby wyróżniane automatycznie (czyta `reports/kontekst_transakcje.parquet`); dziś nie ma żadnego.

**Co nie działa / ograniczenia.**
- Ekran nie liczy wielkości pozycji: brak wartości lota z XTB (`config/contracts.yaml` pusty).
- Sygnał na żywo używa domyślnych parametrów strategii, a statystyka pochodzi z walidacji z parametrami dobieranymi okresowo.
- Statystyki czyta z `reports/**/walidacja_*.json`: po zmianie danych lub kosztów trzeba ponownie uruchomić `cfd report`.
- Plik trzeba wygenerować poleceniem; nie jest jeszcze podłączony do panelu PWA ani do GitHub Actions.

## Zbieranie w przód: newsy i makro przy sygnałach (2026-11-12)

**Po co.** Newsów i kalendarza makro nie da się przetestować wstecz (brak darmowego archiwum). Jedyna droga to zapisywać
kontekst przy każdym sygnale i ocenić go po rozliczeniu.

**Co zrobione.**
- `src/cfd/live_context.py`: przy zapisie sygnału do dziennika dochodzi pełny kontekst z tej chwili: liczba i najwyższa waga
  istotnych newsów dla instrumentu z ostatnich 12 godzin, zgodność ich kierunku z sygnałem, odległość do najbliższej i od
  ostatniej publikacji makro najwyższej wagi (próg 6 godzin), a także etykiety techniczne i bias (te same co w teście kontekstowym).
- `cfd journal-context`: skuteczność rozliczonych sygnałów w podziale na kontekst, z liczbą przypadków, średnim R i statystyką t.
  Grupy poniżej 30 sygnałów są oznaczane „za mało danych” i nie są interpretowane.
- GitHub Actions (`.github/workflows/scan.yml`): skan pobiera teraz także kalendarz makro i newsy (`--jobs macro news scan`),
  generuje ekran i zapisuje go razem z bazą jako artefakt `stan-na-teraz` (14 dni). Podsumowanie dziennika trafia do
  podsumowania przebiegu. Statystyki walidacji dla ekranu są w repozytorium w katalogu `walidacja/`.
- `.github/workflows/pages.yml`: opcjonalna publikacja ekranu jako strony GitHub Pages. Domyślnie wyłączona
  (wymaga włączenia Pages i zmiennej `PUBLIKUJ_STRONE=tak`), bo strona byłaby publiczna.

**Co wyszło.** Jeszcze nic do oceny: w dzienniku jest kilkanaście otwartych sygnałów i żadnego rozliczonego z nowym kontekstem.
Pierwsze sensowne liczby pojawią się po kilku tygodniach (interwał 1h), dla newsów raczej po kilku miesiącach.

**Ustalenia o środowisku.**
- Repozytorium jest **publiczne**, a gałąź robocza jest gałęzią domyślną, więc harmonogram `skan` już działa w GitHub Actions
  (bez limitu minut w repozytorium publicznym). Lista spółek z wyciągu jest przez to publicznie widoczna: to decyzja 17, nadal bez odpowiedzi.
- Harmonogram GitHuba jest zawodny: w pierwszych 6 godzinach wykonał się 1 przebieg z 12 zaplanowanych.
- Bez kluczy modeli newsy klasyfikują same reguły; bez Supabase stan żyje w cache Actions i w artefaktach.

**Co nie działa.** Kontekst newsowy opiera się na kierunku z reguł, który jest słaby (reguły rzadko podają kierunek).
Odległość do publikacji makro nie rozróżnia walut.

**Sprawdzenie w Actions.** Ręcznie uruchomiony `skan` z interwałami 1h, 4h i 1d (2026-11-12 07:44 UTC) zakończył się
powodzeniem po ok. 10 minutach: kalendarz, newsy i skan wykonane, artefakt `stan-na-teraz` (ekran i baza) zapisany, cache stanu zapisany.
Limit czasu przebiegu podniesiony z 15 do 25 minut. Publikacja na Pages nie była sprawdzana (jest wyłączona).

## E3. Akcje: fundamenty spółek (2026-11-12)

**Co zrobione.** `src/cfd/fundamentals/stocks.py`, polecenia `cfd stocks update` i `cfd stocks show [--details]`, sekcja
„Twoje spółki” na ekranie `cfd now`, krok w dziennym przebiegu Actions. Dla każdej spółki z Yahoo: wycena, wzrost przychodów
(ostatni kwartał rok do roku, gdy są dane kwartalne), marże, ROE, zadłużenie, konsensus analityków, data najbliższego raportu.
Test na zapisanej próbce prawdziwej odpowiedzi (`tests/fixtures/yahoo_stock_CDR.WA.json`).

Ocena to lista kontrolna sześciu filarów (każdy −1, 0 albo +1) z jawnymi progami:
wzrost przychodów (> 10% / < 0), zyskowność (marża netto > 10% i ROE > 10% / strata), wycena (C/Z < 15 / > 40 lub strata),
zadłużenie (dług do kapitału < 50% / > 150%), konsensus (cena docelowa > +15% / < −5% od kursu, min. 3 analityków),
trend kursu (powyżej / poniżej średniej z 200 sesji). Suma ≥ +3: „trzymać, można rozważyć dokupienie”; ≤ −3: „rozważyć redukcję”;
inaczej „trzymać i obserwować”. Zgodnie z decyzją 19 słaby obraz to ostrzeżenie dla posiadanej spółki, nie zachęta do krótkiej sprzedaży.

**Co wyszło (2026-11-12).** Dane dla 30 z 31 spółek (bez `SPL.PL`: brak symbolu w Yahoo).
Słaby obraz: DAT.PL (przychody −32% r/r, strata, kurs pod średnią) i OXB.UK (strata, dług do kapitału 273%).
Raport kwartalny w ciągu 14 dni jest oznaczany na ekranie i w `cfd stocks show`.

**Co nie działa / zastrzeżenia.**
- **Progi nie były walidowane.** Darmowych historycznych fundamentów nie ma, więc nie da się sprawdzić, czy „mocny obraz” dawał
  lepsze stopy zwrotu. Ocena porządkuje fakty, nie mierzy szansy zysku.
- Dane Yahoo bywają błędne, np. prognozowane C/Z dla DNP.PL wychodzi 2 (najpewniej nieskorygowany zysk na akcję po splicie),
  co zawyża jej ocenę. Takie wartości trzeba weryfikować w raporcie spółki.
- Banki nie mają pola zadłużenia; dla części spółek z GPW brak konsensusu (poniżej 3 analityków).
- Nie zrobione z zadania E3: SEC EDGAR dla spółek z USA, komunikaty ESPI dla GPW (host niedozwolony w środowisku testowym),
  alert przed raportem jako powiadomienie (powiadomienia są wstrzymane decyzją użytkownika; data jest na ekranie).

