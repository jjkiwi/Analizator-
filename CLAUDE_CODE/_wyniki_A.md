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
