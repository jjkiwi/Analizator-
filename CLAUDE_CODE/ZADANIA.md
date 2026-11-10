# Zadania dla Claude Code

Kolejność ma znaczenie: późniejsze zadania zależą od wcześniejszych.
Oznaczenia: **[SIEĆ]** wymaga internetu, **[KLUCZ]** wymaga klucza z `.env` (jeśli go nie ma, pomiń i odnotuj),
**[DECYZJA]** wymaga odpowiedzi w `DECYZJE.md`.

## A. Dane rynkowe

### A1. Sprawdzenie mapowań źródeł [SIEĆ]
`cfd check-sources > CLAUDE_CODE/check-sources.txt`
- Popraw w `config/instruments.yaml` każdy symbol oznaczony BLAD (sprawdź właściwy ticker w Yahoo/Stooq).
- Znajdź darmowe źródło dla ZINC, NICKEL i danych intraday dla W20. Jeśli nie istnieje, zostaw puste i odnotuj.
- Porównaj ostatnie ceny zamknięcia między źródłami tego samego instrumentu. Różnica powyżej ~2%
  oznacza inny instrument bazowy (futures vs indeks kasowy): odnotuj, to wpływa na poziomy SL/TP.

### A2. Naprawa adapterów [SIEĆ]
Pliki: `src/cfd/data/yahoo.py`, `stooq.py`, `binance.py`. Sprawdź na żywych danych:
- Yahoo: interwały 1d i 1h, strefa czasowa indeksu, limit ~730 dni dla 1h, resampling do 4h
  (czy granice świec 4h mają sens dla kontraktów futures handlowanych prawie całą dobę).
- Stooq: czy pobieranie CSV działa bez klucza/captcha i jaki jest limit dzienny. Jeśli wymaga klucza lub blokuje, odnotuj.
- Binance: czy `api.binance.com` jest dostępne z tej lokalizacji. Jeśli nie, dodaj zapasowy host publicznych danych.
- Zapisz po jednej surowej odpowiedzi do `tests/fixtures/` i dopisz testy parsowania.

### A3. Historia i jakość danych [SIEĆ]
`cfd fetch --interval 1d`, potem `4h` i `1h`.
Dopisz polecenie `cfd data-quality`, które dla każdego instrumentu raportuje: liczbę świec, zakres dat,
luki dłuższe niż oczekiwane (weekendy i święta pomiń), świece o zerowym zasięgu, skoki ceny powyżej 8 ATR
(kandydaci na rolowanie kontraktu futures). Wynik do `CLAUDE_CODE/WYNIKI.md`.
Ważne: Yahoo zwraca dla `=F` kontrakt ciągły bez korekty rolowania. Sprawdź na ropie i gazie, jak duże
są skoki przy rolowaniu, i zaproponuj obejście (np. korekta wsteczna albo wykluczenie świec rolowania z sygnałów).

## B. Walidacja strategii

### B1. Raport walk-forward
`cfd report --interval 1d` oraz `cfd report --interval 4h` (wynik w `reports/`).
Skopiuj do `WYNIKI.md` tabelę: ile kombinacji PASS / WEAK / FAIL, lista PASS z liczbami.
Przy ~40 instrumentach i 3 strategiach kilka PASS pojawi się przez przypadek. Dla każdego PASS sprawdź
dodatkowo: wynik przy kosztach ×2 i wynik na drugim interwale. Odnotuj, które PASS to przetrwały.

### B2. Koszty z XTB [DECYZJA]
Gdy użytkownik dostarczy specyfikację instrumentów (spread, punkty swapowe, wartość lota), wpisz ją do
`config/instruments.yaml` w polu `costs` per instrument i powtórz B1. Do tego czasu raport liczony jest na założeniach.

### B3. Kalkulator wielkości pozycji [DECYZJA]
Dopisz `cfd size SYMBOL --entry X --sl Y --risk-pct Z --equity E`: wolumen w lotach tak, by strata na SL
wyniosła zadany procent kapitału. Wymaga wartości lota i waluty instrumentu ze specyfikacji XTB (B2).

## C. Newsy

### C1. Feedy [SIEĆ]
`cfd news check-feeds`. Usuń lub popraw niedziałające adresy w `config/feeds.yaml`.
Dodaj polskie źródła (PAP Biznes, komunikaty ESPI/EBI, NBP) i brakujące banki centralne, jeśli mają RSS.
Sprawdź, czy Google News RSS nie blokuje przy odpytywaniu co 5 minut.

### C2. Jakość mapowania i klasyfikacji [SIEĆ]
Uruchom `cfd news poll` kilkanaście razy w odstępach kilku minut, potem `cfd news list --min-importance 1 --limit 200`.
- Policz fałszywe trafienia słów kluczowych (podejrzane: "fed", "eth", "ether", "gold", "corn", "sugar", "boj", "lng", "gpw").
  Popraw `config/keywords.yaml`: usuń lub zawęź wieloznaczne słowa.
- Oceń ręcznie 50 newsów z wagą 3 z klasyfikatora regułowego: ile faktycznie było pilnych. Wynik do `WYNIKI.md`.
- Zmierz opóźnienie: czas publikacji w feedzie vs czas pobrania. To odpowiedź na pytanie, jak szybki jest tor newsowy.

### C3. Klasyfikator LLM [KLUCZ: ANTHROPIC_API_KEY]
Sprawdź w dokumentacji aktualną nazwę taniego modelu i poprawność wywołania w `news/classify.py`.
Porównaj na tych samych 50 newsach reguły vs LLM. Oszacuj koszt miesięczny przy zaobserwowanym wolumenie
(pamiętaj, że do LLM trafiają tylko newsy z wagą regułową ≥ 2).

## D. Kalendarz makro

### D1. Źródło kalendarza [SIEĆ]
`cfd macro refresh`, potem `cfd macro upcoming`. Zweryfikuj adres i format w `macro/sources.py`
(spisane z pamięci), strefę czasową wydarzeń i limit zapytań. Dopisz test na zapisanej próbce.

### D2. Odczyty bieżące ("actual") [SIEĆ]
Obecne źródło najpewniej nie podaje odczytu po publikacji. Znajdź darmowy sposób: publiczne API urzędów
(BLS, BEA, EIA, Eurostat), FRED z opóźnieniem albo publiczna strona, którą wolno scrapować.
Zaimplementuj jako drugi adapter uzupełniający `actual`. Jeśli nic rozsądnego nie istnieje, opisz to
i zostaw `cfd macro set-actual` plus tor newsowy.

## E. Fundamenty

### E1. FRED [KLUCZ: FRED_API_KEY]
`cfd bias check`, popraw błędne identyfikatory serii w `config/fundamentals.yaml` (niepewne: `WCESTUS1`),
potem `cfd bias update` i `cfd bias show`. Oceń, czy wyniki są sensowne na tle ostatnich miesięcy.

### E2. Zapasy i pozycjonowanie [SIEĆ]
- Adapter EIA (zapasy ropy, benzyny, gazu; darmowy klucz) jako składowe biasu dla OIL, OIL.WTI, GASOLINE, NATGAS.
- Adapter raportów COT z CFTC. Funkcja `positioning_percentile` już istnieje w `fundamentals/bias.py`.
  Dodaj typ składowej "percentyl pozycjonowania" (kontrariańsko przy skrajnościach).

### E3. Akcje [DECYZJA: lista spółek]
Po dostarczeniu listy: mapowania w `instruments.yaml`, moduł fundamentów spółek (wycena, dynamika wyników,
daty raportów) z yfinance i SEC EDGAR, alert przed raportem kwartalnym, dla spółek z GPW komunikaty ESPI.

## F. Powiadomienia i praca ciągła

### F1. Telegram [KLUCZ: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID]
`cfd notify-test`. Sprawdź formatowanie wszystkich typów wiadomości (`notify.py`) na telefonie.

### F2. Pierwszy pełny przebieg [SIEĆ]
`cfd -v run --once`, potem `cfd health`, `cfd journal`, `cfd dashboard`. Napraw wszystko, co padnie.
Następnie `cfd run` na co najmniej godzinę: obserwuj zużycie pamięci, liczbę zapytań do każdego serwisu
i czy żaden nie zaczyna odrzucać połączeń.

### F3. Uruchamianie w tle [DECYZJA: gdzie ma działać]
Przygotuj wariant dla wybranego środowiska: usługa systemd, Harmonogram zadań Windows albo Dockerfile
z `docker-compose.yml`. Automatyczny restart po awarii, rotacja logów, odświeżanie `reports/panel.html` co kilka minut.

## G. Później (nie zaczynaj bez decyzji)

- **G1. Ceny na żywo** z API brokera na koncie demo (Capital.com lub IG): `LivePriceAdapter`, a w alercie newsowym
  informacja, o ile rynek ruszył się od publikacji. Wymaga założenia konta przez użytkownika i sprawdzenia regulaminu API.
- **G2. Pełny panel PWA** (FastAPI + React) zamiast statycznego HTML.
- **G3. Nowe strategie i filtr reżimu rynku** (`features.regime` już istnieje) dopiero po wynikach B1.
