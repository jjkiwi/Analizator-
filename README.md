# Analizator CFD

Analiza rynku i sygnały dla CFD i akcji w XTB: technika, fundamenty, newsy, kalendarz makro.
Nie składa zleceń. Decyzja i transakcja są po stronie użytkownika.

## Stan: v0.3

Testy: 65 w Pythonie, 10 w TypeScripcie. **Żaden element sieciowy nie był uruchomiony na prawdziwych danych**
(środowisko budowania nie miało dostępu do tych serwisów), a panel nie był otwierany w przeglądarce.
Weryfikacja i wdrożenie to zadania w `CLAUDE_CODE/ZADANIA.md`.

## Architektura (bez własnego serwera)

```
                       ┌──────────────── Supabase ────────────────┐
RSS (5 języków) ──────▶│ funkcja news-poll  (co minutę, pg_cron)  │──▶ Telegram
kalendarz makro ──────▶│ funkcja macro-poll (co minutę, pg_cron)  │──▶ Telegram
darmowe modele LLM ◀──▶│                                          │
                       │ Postgres: signals, news, macro_events,   │◀── panel PWA (Vercel)
                       │           fundamental_bias, source_health│
                       └──────────────────▲───────────────────────┘
                                          │ sync (push / pull)
Yahoo / Stooq / Binance ──▶ GitHub Actions: Python co 30 min ──────▶ Telegram
FRED ─────────────────────▶ (świece → wskaźniki → strategie → fuzja → dziennik)
```

- **Tor szybki**: `supabase/functions/` (TypeScript, bez zależności). Reguły są bramką: do modelu trafiają tylko
  newsy z wagą ≥ 2. Łańcuch modeli z `config/llm.yaml`, na końcu zawsze reguły.
- **Tor wolny**: `src/cfd/` (Python). Skan tylko na interwałach, na których właśnie zamknęła się świeca.
- **Cisza nocna** 23–8 czasu polskiego: powiadomienia czekają w tabeli `outbox`, rano jedno podsumowanie.
- **Bezpiecznik**: strategie zapisują sygnały do dziennika (forward test), ale alerty wysyłają tylko te wpisane
  ręcznie do `scan.alert_strategies`. Domyślnie żadna.
- **Konfiguracja**: `config/*.yaml` to jedyne źródło prawdy. `cfd export-config` generuje JSON dla funkcji.

## Zakres

72 instrumenty: 18 indeksów, 16 surowców, 4 metale szlachetne, 3 kryptowaluty, 31 akcji.
Interwały: D1, H4, H1, M30. Strategie: `trend_pullback`, `donchian_breakout`, `mean_reversion`.

## Praca lokalna

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]" && pytest
deno test supabase/tests/
cp .env.example .env
```

```bash
cfd check-sources                 # które mapowania źródeł działają
cfd fetch --interval 1d           # historia do cache
cfd backtest GOLD --strategy donchian_breakout
cfd walkforward US500 --strategy trend_pullback
cfd report --interval 1d          # reports/walidacja_1d.html
cfd scan --interval 4h            # sygnały z ostatniej zamkniętej świecy
cfd regime                        # trend / konsolidacja

cfd news check-feeds | poll | list
cfd macro refresh | upcoming | set-actual --name "cpi" --value 0.4
cfd bias check | update | show

cfd run --once --jobs scan --intervals auto   # to samo, co robi GitHub Actions
cfd run                                       # praca ciągła na własnej maszynie (wszystkie tory w Pythonie)
cfd sync pull | push | both                   # wymiana z Supabase
cfd export-config                             # JSON dla funkcji Supabase
cfd journal | health | dashboard | notify-test
```

## Struktura

```
config/                 instruments, settings, feeds, keywords, macro_rules, fundamentals, llm
src/cfd/                data, features, strategies, backtest, validation, news, macro, fundamentals,
                        fusion, journal, scanner, runner, notify, sync, report, dashboard, db, cli
supabase/migrations/    schemat Postgres z RLS
supabase/functions/     news-poll, macro-poll, _shared (rss, mapper, classify, macro, notify, pipeline, db)
supabase/tests/         testy toru szybkiego (Deno)
supabase/cron.sql.template   harmonogram pg_cron (zawiera sekrety, wykonywany ręcznie)
.github/workflows/      testy, skan (co 30 min), dzienne (bias, raport walidacji)
web/                    panel PWA (tryb demo, dopóki web/config.js jest pusty)
CLAUDE.md, CLAUDE_CODE/ instrukcja i zadania do wykonania na komputerze
DECYZJE.md              decyzje podjęte i otwarte
```

## Znane ograniczenia

- Ceny pochodzą z kontraktów futures, indeksów kasowych i giełd, nie z kwotowań XTB. Poziomy przelicz w xStation.
- Koszty w konfiguracji to założenia, dopóki nie zostaną przepisane ze specyfikacji XTB (zadanie B2).
- M30: ~60 dni darmowej historii, więc brak walidacji; harmonogram GitHuba bywa opóźniony.
- Yahoo podaje kontrakty ciągłe bez korekty rolowania: możliwe sztuczne skoki ceny.
- Darmowe newsy docierają z opóźnieniem od kilkudziesięciu sekund do kilku minut.
- Nazwy modeli i limity w `config/llm.yaml` są niesprawdzone i szybko się dezaktualizują.
- Odczyty makro po publikacji: darmowe źródło jeszcze nieznalezione (zadanie D2).
- Reguły makro i składowe biasu to podręcznikowe heurystyki. Fundamenty spółek jeszcze niezaimplementowane.
- Logika toru szybkiego istnieje w Pythonie i TypeScripcie: zmiany trzeba wprowadzać w obu.
