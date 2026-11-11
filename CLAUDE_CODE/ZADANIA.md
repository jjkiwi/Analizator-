# Zadania dla Claude Code (v0.3)

Kolejność ma znaczenie. Oznaczenia: **[SIEĆ]** wymaga internetu, **[KLUCZ]** wymaga klucza (gdy go nie ma, pomiń
i odnotuj), **[KONTO]** wymaga konta założonego przez użytkownika, **[DECYZJA]** wymaga odpowiedzi w `DECYZJE.md`.

## A. Dane rynkowe

### A1. Mapowania źródeł [SIEĆ]
`cfd check-sources > CLAUDE_CODE/check-sources.txt`
- Popraw w `config/instruments.yaml` każdy symbol z BLAD. Szczególnie niepewne są akcje (31 pozycji dodanych
  mechanicznie: `.PL`→`.WA`, `.UK`→`.L`, `.FR`→`.PA`, `.ES`→`.MC`) oraz `1YD.DE`, `SPL.PL`, `GNS.PL`, `S2B.PL`, `CRQ.PL`.
- Porównaj ostatnie zamknięcia między źródłami tego samego instrumentu. Różnica powyżej ~2% oznacza inny
  instrument bazowy (futures vs indeks kasowy): odnotuj.
- Spółki z UK są notowane w pensach (GBX): sprawdź, czy ceny z Yahoo zgadzają się skalą z tym, co pokazuje XTB.

### A2. Adaptery [SIEĆ]
Pliki `src/cfd/data/{yahoo,stooq,binance}.py`. Sprawdź na żywych danych:
- Yahoo: interwały 1d, 1h, 30m; strefa czasowa; limity historii (1h ~730 dni, 30m ~60 dni); resampling do 4h.
- Stooq: czy CSV działa bez klucza/captcha, jaki jest limit dzienny.
- Binance: czy `api.binance.com` odpowiada z GitHub Actions (adresy USA bywają blokowane). Jeśli nie, dodaj zapasowy host.
- **Uruchom to samo z GitHub Actions** (`workflow_dispatch` w `skan`): Yahoo częściej ogranicza adresy centrów danych.
- Zapisz po jednej surowej odpowiedzi do `tests/fixtures/` i dopisz testy parsowania.

### A3. Historia i jakość [SIEĆ]
`cfd fetch` dla 1d, 4h, 1h, 30m. Dopisz `cfd data-quality`: liczba świec, zakres dat, luki (bez weekendów i świąt),
świece o zerowym zasięgu, skoki powyżej 8 ATR. Yahoo zwraca dla `=F` kontrakt ciągły bez korekty rolowania:
sprawdź skoki na ropie i gazie i zaproponuj obejście.

## B. Walidacja strategii

### B1. Raport walk-forward
`cfd report` dla 1d, 4h i 1h. Dla 30m historii jest za mało: odnotuj to, nie obchodź.
Do `WYNIKI.md`: liczba PASS / WEAK / FAIL i lista PASS. Dla każdego PASS sprawdź wynik przy kosztach ×2
i na sąsiednim interwale. Przy ~70 instrumentach i 3 strategiach kilka PASS pojawi się przez przypadek.

### B2. Koszty z XTB [SIEĆ]
Strona `https://www.xtb.com/pl/specyfikacja-instrumentow` ładuje tabelę JavaScriptem, więc zwykłe pobranie
zwraca pustą stronę. Odczytaj ją **jednorazowo** w przeglądarce (lub z dokumentów PDF podlinkowanych jako
"Sprawdź dokumenty") i wpisz do `config/instruments.yaml` w polu `costs` per instrument: spread, punkty swapowe
long/short przeliczone na procent roczny, a osobno (nowe pola) wartość lota i walutę. Potem powtórz B1.
Zapisz datę odczytu: te wartości się zmieniają.

### B3. Kalkulator pozycji
`cfd size SYMBOL --entry X --sl Y --risk-pct Z --equity E`: wolumen, przy którym strata na SL to zadany procent
kapitału. Rachunek w PLN, więc uwzględnij przewalutowanie. Wymaga danych z B2.

## C. Newsy

### C1. Feedy [SIEĆ]
`cfd news check-feeds`. Popraw lub usuń niedziałające adresy w `config/feeds.yaml`. Dodaj PAP Biznes,
komunikaty ESPI/EBI i NBP, jeśli mają RSS. Sprawdź, czy Google News RSS nie blokuje 30 zapytań co 5 minut
(także z adresów Supabase).

### C2. Jakość mapowania [SIEĆ]
`cfd news poll` kilkanaście razy co kilka minut, potem `cfd news list --min-importance 1 --limit 200`.
- Policz fałszywe trafienia (podejrzane: "fed", "eth", "ether", "gold", "corn", "sugar", "boj", "lng", "ibex",
  "erste group", "marvell", "iberia"). Zawęź `config/keywords.yaml`.
- Oceń ręcznie 50 newsów z wagą 3 i 50 z wagą 2 z reguł. Użytkownik chce alertów od wagi 2: jeśli wychodzi
  więcej niż ~30 alertów dziennie, zaproponuj zaostrzenie reguł, zamiast po cichu zmieniać próg.
- Zmierz opóźnienie: czas publikacji vs czas pobrania, osobno per język.

### C3. Darmowe modele [KLUCZ: dowolny z config/llm.yaml]
Dla każdego dostawcy z kluczem: sprawdź w dokumentacji aktualną nazwę modelu, adres i limity darmowego planu,
popraw `config/llm.yaml`. Porównaj na tych samych 100 newsach (w tym polskich, niemieckich, francuskich,
hiszpańskich): reguły vs każdy model. Miary: zgodność wagi z oceną ręczną, sensowność kierunku, czas odpowiedzi,
odsetek odpowiedzi niebędących poprawnym JSON. Ustaw kolejność łańcucha według wyniku.

## D. Kalendarz makro

### D1. Źródło [SIEĆ]
`cfd macro refresh`, `cfd macro upcoming`. Zweryfikuj adres, format i strefę czasową (parsery w `macro/sources.py`
i `supabase/functions/_shared/macro.ts`). Sprawdź limit zapytań: funkcja odświeża co 60 minut.

### D2. Odczyty bieżące [SIEĆ]
Znajdź darmowe źródło pola `actual` (API urzędów: BLS, BEA, EIA, Eurostat; FRED z opóźnieniem; strona publiczna
dopuszczająca scraping). Zaimplementuj w obu językach albo opisz, dlaczego się nie da.

## E. Fundamenty

### E1. FRED [KLUCZ: FRED_API_KEY]
`cfd bias check`, popraw identyfikatory (niepewny `WCESTUS1`), `cfd bias update`, `cfd bias show`.

### E2. Zapasy i pozycjonowanie [SIEĆ]
Adapter EIA i adapter COT z CFTC jako nowe typy składowych biasu (`positioning_percentile` już istnieje).

### E3. Akcje [SIEĆ]
Moduł fundamentów spółek dla 31 pozycji z `instruments.yaml`: wycena, dynamika wyników, daty raportów
(yfinance, SEC EDGAR dla USA), alert przed raportem kwartalnym, komunikaty ESPI dla spółek z GPW.
Użytkownik te akcje posiada: sygnał SHORT traktuj jako ostrzeżenie, nie zachętę do krótkiej sprzedaży (patrz DECYZJE 19).

## F. Wdrożenie w chmurze

### F1. Supabase [KONTO]
- `supabase link`, `supabase db push` (migracja `0001_init.sql`).
- Sekrety funkcji: `CRON_SECRET` (wygeneruj losowy), `TELEGRAM_*`, klucze modeli.
- `cfd export-config`, potem `supabase functions deploy news-poll macro-poll`.
- Wywołaj każdą funkcję ręcznie z nagłówkiem `x-cron-secret` i sprawdź odpowiedź oraz tabele.
- Dopiero potem harmonogram: `supabase/cron.sql.template` (zweryfikuj składnię `pg_cron`/`pg_net` w dokumentacji).
- Sprawdź limity darmowego planu: liczba wywołań funkcji miesięcznie (2 funkcje × co minutę ≈ 86 tys.),
  czas wykonania, rozmiar bazy, usypianie nieaktywnych projektów. Jeśli limit wywołań jest za niski,
  połącz obie funkcje w jedną albo wydłuż odstęp i odnotuj.
- Auth: wyłącz rejestrację, dodaj użytkownika (e-mail właściciela), ustaw adres przekierowania na domenę panelu.

### F2. GitHub Actions [KONTO] [DECYZJA 17]
Sekrety repozytorium: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `TELEGRAM_*`, `FRED_API_KEY`.
Uruchom `testy`, potem ręcznie `skan` z `intervals: 1d`. Zmierz czas przebiegu i policz miesięczne zużycie minut
dla harmonogramu co 30 minut. Sprawdź, czy cache `data/` wraca między przebiegami i jak duży jest.

### F3. Panel [KONTO]
Wpisz adres projektu i klucz `anon` do `web/config.js`, wdróż na Vercel (`vercel.json` wskazuje katalog `web`).
Panel nie był otwierany w przeglądarce: sprawdź logowanie linkiem, wszystkie pięć widoków na telefonie
(jasny i ciemny motyw), instalację jako PWA. Rozważ dołączenie biblioteki supabase-js lokalnie zamiast z esm.sh.

### F4. Próba generalna
Zostaw całość na dobę. Sprawdź: liczbę alertów, działanie ciszy nocnej (23–8 czasu polskiego) i porannego
podsumowania, brak duplikatów alertów, tabelę `source_health`, logi funkcji.

## G. Później (nie zaczynaj bez decyzji)

- **G1. Ceny na żywo** z API brokera na koncie demo (Capital.com lub IG): konto zakłada użytkownik.
  `LivePriceAdapter`, a w alercie newsowym informacja, o ile rynek ruszył się od publikacji.
- **G2. Rozbudowa panelu**: wykresy, historia sygnału, kalkulator pozycji.
- **G3. Nowe strategie i filtr reżimu rynku** dopiero po wynikach B1.
- **G4. Przeniesienie na własną maszynę**, jeśli całość się sprawdzi (`cfd run` już to obsługuje).
