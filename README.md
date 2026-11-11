# Analizator CFD

Analiza rynku i sygnały dla CFD w XTB: technika, fundamenty, newsy, kalendarz makro.
Nie składa zleceń. Decyzja i transakcja są po stronie użytkownika.

## Stan: v0.3

Adaptery sieciowe zostały sprawdzone na żywych danych (listopad 2026); wyniki, liczby i lista rzeczy niesprawdzonych
są w `CLAUDE_CODE/WYNIKI.md`, otwarte pytania w `DECYZJE.md`. Testy (`pytest`) nie wymagają sieci: korzystają
z zapisanych próbek prawdziwych odpowiedzi w `tests/fixtures/`.

**Walidacja walk-forward: żadna z trzech strategii nie ma potwierdzonej przewagi**, dlatego `alert_strategies` jest puste.

| Obszar | Co jest | Sprawdzone |
|---|---|---|
| Instrumenty | 45 symboli XTB z mapowaniem na źródła | lista i mapowania do weryfikacji |
| Świece | Yahoo, Stooq, Binance, źródła zapasowe, cache Parquet, `cfd data-quality` | Yahoo i Binance tak; Stooq blokuje automat |
| Wskaźniki | SMA, EMA, RSI, ATR, ADX, Bollinger, Donchian, MACD, reżim rynku | tak |
| Strategie | trend_pullback, donchian_breakout, mean_reversion | logika tak; skuteczność: brak przewagi (B1) |
| Backtest | spread, swap, luki, podział in/out-of-sample | tak |
| Walidacja | walk-forward z doborem parametrów, ocena PASS/WEAK/FAIL, raport HTML, test kosztów ×2 | tak, na danych rynkowych |
| Dziennik | zapis i rozliczanie sygnałów (forward test), SQLite | tak |
| Newsy | RSS/Atom, deduplikacja, mapowanie na instrumenty, klasyfikacja regułowa i LLM | feedy tak (18 działa); LLM tylko na atrapie |
| Makro | kalendarz, reguły reakcji na odczyt vs prognoza, alert przed publikacją | tak; odczyty po publikacji tylko dla USA |
| Fundamenty | bias −2..+2 z serii FRED, zapasów EIA i pozycjonowania COT | tak, bez kluczy; API z kluczem nie |
| Fuzja | technika + bias + newsy = ocena zgodności sygnału | tak |
| Powiadomienia | Telegram albo konsola | formatowanie tak, wysyłka nie |
| Praca ciągła | `cfd run`, kontrola zdrowia źródeł, zbiorcze alerty o awariach, warianty w `deploy/` | przebieg tak; `deploy/` nie |
| Wielkość pozycji | `cfd size`: loty dla zadanego ryzyka | obliczenia tak; mnożniki lota do uzupełnienia |
| Panel | statyczny HTML z bazy (`cfd dashboard`) | tak |

## Start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]" && pytest
cp .env.example .env            # klucze: patrz DECYZJE.md
```

## Polecenia

```bash
cfd check-sources               # które mapowania źródeł działają
cfd data-quality --interval 1d  # luki, świece o zerowym zasięgu, skoki (rolowanie)
cfd size US500 --entry 5000 --sl 4980 --risk-pct 1 --equity 10000 --lot-multiplier 50 --currency USD --fx-rate 4.0
cfd fetch --interval 1d         # pobierz historię do cache
cfd backtest GOLD --strategy donchian_breakout
cfd walkforward US500 --strategy trend_pullback
cfd report --interval 1d        # wszystkie instrumenty x strategie -> reports/walidacja_1d.html
cfd scan                        # sygnały z ostatniej zamkniętej świecy
cfd regime                      # trend / konsolidacja

cfd news check-feeds | poll | list
cfd macro refresh | upcoming | set-actual --name "cpi" --value 0.4
cfd bias check | update | show

cfd run --once                  # jeden pełny przebieg
cfd run                         # praca ciągła
cfd journal                     # skuteczność sygnałów na żywo
cfd health                      # stan źródeł
cfd dashboard                   # reports/panel.html
cfd notify-test
```

## Jak to działa

```
            ┌─ świece (Yahoo/Stooq/Binance) ─ wskaźniki ─ strategie ─┐
tor wolny ──┤                                                        ├─ fuzja ─ dziennik ─ alert
            └─ serie makro (FRED) ─ bias fundamentalny ──────────────┤
                                                                     │
tor szybki ─── RSS ─ deduplikacja ─ mapowanie ─ klasyfikacja ────────┴─ alert newsowy
            └─ kalendarz makro ─ alert przed publikacją / reakcja na odczyt
```

Zasada bezpieczeństwa: każda strategia z `scan.strategies` zapisuje sygnały do dziennika (forward test),
ale powiadomienia wysyłają tylko strategie wpisane ręcznie do `scan.alert_strategies` po przejściu walidacji.
Domyślnie ta lista jest pusta.

## Struktura

```
config/        instruments, settings, feeds, keywords, macro_rules, fundamentals
src/cfd/
  data/        adaptery świec, DataService (źródła zapasowe), CandleStore
  features/    wskaźniki
  strategies/  strategie + siatki parametrów
  backtest/    silnik i metryki
  validation/  walk-forward
  news/        rss, mapper, classify, pipeline
  macro/       kalendarz, reguły, źródło
  fundamentals/ FRED, bias
  fusion.py  journal.py  scanner.py  runner.py  notify.py  report.py  dashboard.py  db.py  cli.py
CLAUDE.md, CLAUDE_CODE/   instrukcja i zadania do wykonania na komputerze
DECYZJE.md                pytania do użytkownika
```

## Znane ograniczenia

- Ceny pochodzą z kontraktów futures lub indeksów kasowych, nie z kwotowań XTB. Poziomy SL/TP trzeba przeliczyć w xStation.
- Koszty w konfiguracji to założenia. Bez danych ze specyfikacji XTB wyniki backtestów są orientacyjne.
- Yahoo podaje kontrakty ciągłe bez korekty rolowania: możliwe sztuczne skoki ceny (zadanie A3).
- Swap modelowany jako stały procent roczny.
- Backtest: jedna pozycja naraz, brak poślizgu poza lukami.
- Darmowe newsy docierają z opóźnieniem od kilkudziesięciu sekund do kilku minut.
- Klasyfikator regułowy dobrze ocenia wagę newsa, słabo kierunek.
- Odczyty makro po publikacji: automatycznie tylko USA (FRED, BLS, EIA), z opóźnieniem do ok. 40 minut; reszta ręcznie (`cfd macro set-actual`).
- Reguły makro i składowe biasu to podręcznikowe heurystyki, nie model.
- Fundamenty spółek: jeszcze niezaimplementowane (czeka na listę spółek).
